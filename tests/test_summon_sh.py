"""rites/summon.sh finds a real Python 3.10+, cleans up after itself and leaves the framework URL to the dispatcher."""

import os
import shutil
import stat
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SUMMON_SH = REPO_ROOT / "rites" / "summon.sh"
BASH = shutil.which("bash")
SHELL_FILES = (
    REPO_ROOT / "rites" / "summon.sh",
    REPO_ROOT / "bin" / "grimoire",
    REPO_ROOT / "plugins" / "grimoire" / "scripts" / "session_context.sh",
)
VERSION_CHECK = "'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)'"

pytestmark = pytest.mark.skipif(BASH is None, reason="no bash available")

PROBE_DISPATCHER = (
    "import os, sys\n"
    "print('URL=' + os.environ.get('FRAMEWORK_URL', '<unset>'))\n"
    "print('ARGS=' + ' '.join(sys.argv[1:]))\n"
    "sys.exit(int(os.environ.get('PROBE_EXIT', '0')))\n"
)


def _bash_path(path: Path) -> str:
    return path.as_posix()


def _stage_local(tmp_path: Path) -> Path:
    """A copy of summon.sh beside a probe dispatcher, so it runs as a local script."""
    rites = tmp_path / "stage" / "rites"
    rites.mkdir(parents=True)
    shutil.copy(SUMMON_SH, rites / "summon.sh")
    (rites / "summon.py").write_text(PROBE_DISPATCHER, encoding="utf-8")
    return rites


def _executable(path: Path, text: str) -> Path:
    path.write_text(text, encoding="utf-8", newline="\n")
    path.chmod(path.stat().st_mode | stat.S_IEXEC)
    return path


def _run(args: list[str], env: dict, cwd: Path | None = None, stdin: str | None = None) -> subprocess.CompletedProcess:
    return subprocess.run([BASH, *args], capture_output=True, text=True, env=env, cwd=cwd, input=stdin, timeout=120)


def _clean_env(**extra: str) -> dict:
    env = {k: v for k, v in os.environ.items() if not k.startswith(("FRAMEWORK_", "GRIMOIRE_SUMMON_", "PROBE_"))}
    env.update(extra)
    return env


def test_every_shell_bootstrap_uses_the_same_python_search():
    for path in SHELL_FILES:
        text = path.read_text(encoding="utf-8")
        assert "for candidate in python3 python; do" in text, path
        assert VERSION_CHECK in text, path
        assert "py -3 -c " + VERSION_CHECK in text, path
        assert text.index("for candidate in python3 python; do") < text.index("py -3 -c"), path


def test_framework_url_reaches_the_dispatcher_only_when_the_caller_set_it(tmp_path):
    rites = _stage_local(tmp_path)

    unset = _run([_bash_path(rites / "summon.sh"), "--check"], _clean_env())
    assert unset.returncode == 0, unset.stderr
    assert "URL=<unset>" in unset.stdout and "ARGS=--check" in unset.stdout

    given = _run([_bash_path(rites / "summon.sh")], _clean_env(FRAMEWORK_URL="https://example.com/fork.git"))
    assert "URL=https://example.com/fork.git" in given.stdout


def test_the_dispatcher_exit_code_is_the_bootstrap_exit_code(tmp_path):
    rites = _stage_local(tmp_path)
    result = _run([_bash_path(rites / "summon.sh")], _clean_env(PROBE_EXIT="7"))
    assert result.returncode == 7


def test_a_python_that_is_too_old_does_not_end_the_search(tmp_path):
    rites = _stage_local(tmp_path)
    fakes = tmp_path / "fakes"
    fakes.mkdir()
    _executable(fakes / "python3", "#!/bin/sh\necho 'Python 2.7.18'\nexit 1\n")
    env = _clean_env(PATH=_bash_path(fakes) + os.pathsep + os.environ["PATH"])

    result = _run([_bash_path(rites / "summon.sh")], env)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "Python 2.7" not in result.stdout
    assert "ARGS=" in result.stdout


def _fake_curl(directory: Path, source: Path) -> None:
    """A curl that serves `<anything>/<path>` from the local `source` tree, or fails when asked to."""
    directory.mkdir(exist_ok=True)
    _executable(directory / "curl", f"""#!/bin/sh
dest=""
url=""
while [ $# -gt 0 ]; do
    case "$1" in
        -o) dest="$2"; shift 2 ;;
        http*|file*) url="$1"; shift ;;
        *) shift ;;
    esac
done
[ -n "$FAKE_CURL_FAIL" ] && exit 22
rel="${{url#*://*/}}"
rel="${{rel#*/*/*/}}"
cp "{_bash_path(source)}/$rel" "$dest"
""")


def _stdin_run(tmp_path: Path, extra: dict, *, curl: bool = True) -> tuple[subprocess.CompletedProcess, Path]:
    source = tmp_path / "source"
    (source / "rites" / "templates").mkdir(parents=True)
    (source / "rites" / "data").mkdir()
    (source / "rites" / "summon.py").write_text(PROBE_DISPATCHER, encoding="utf-8")
    for name in ("summon_core.py", "agent_targets.py", "data/agent_targets.json", "templates/grimoire_block.md"):
        (source / "rites" / name).write_text("x\n", encoding="utf-8")
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    fakes = tmp_path / "fakes"
    if curl:
        _fake_curl(fakes, source)
    env = _clean_env(
        TMPDIR=_bash_path(scratch),
        GRIMOIRE_SUMMON_DOWNLOAD_ATTEMPTS="1",
        GRIMOIRE_SUMMON_RETRY_DELAY="0",
        FRAMEWORK_RAW_BASE="https://raw.example/owner/repo/main",
        PATH=(_bash_path(fakes) + os.pathsep if curl else "") + os.environ["PATH"],
        **extra,
    )
    work = tmp_path / "cwd"
    work.mkdir()
    result = _run([], env, cwd=work, stdin=SUMMON_SH.read_text(encoding="utf-8"))
    return result, scratch


def test_the_piped_bootstrap_downloads_runs_and_removes_its_temp_directory(tmp_path):
    result, scratch = _stdin_run(tmp_path, {})
    assert result.returncode == 0, result.stdout + result.stderr
    assert "ARGS=" in result.stdout
    assert list(scratch.iterdir()) == []


def test_the_piped_bootstrap_removes_its_temp_directory_when_a_download_fails(tmp_path):
    result, scratch = _stdin_run(tmp_path, {"FAKE_CURL_FAIL": "1", "GRIMOIRE_SUMMON_CONNECT_TIMEOUT": "2"})
    assert result.returncode != 0
    assert list(scratch.iterdir()) == []


def test_downloads_reach_the_python_fallback_when_neither_curl_nor_wget_exists(tmp_path):
    source = tmp_path / "source"
    (source / "rites" / "templates").mkdir(parents=True)
    (source / "rites" / "data").mkdir()
    (source / "rites" / "summon.py").write_text(PROBE_DISPATCHER, encoding="utf-8")
    for name in ("summon_core.py", "agent_targets.py", "data/agent_targets.json", "templates/grimoire_block.md"):
        (source / "rites" / name).write_text("x\n", encoding="utf-8")
    hide = tmp_path / "hide.sh"
    hide.write_text(
        'command() { if [ "$1" = "-v" ] && { [ "$2" = curl ] || [ "$2" = wget ]; }; then return 1; fi; builtin command "$@"; }\n',
        encoding="utf-8", newline="\n",
    )
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    env = _clean_env(
        BASH_ENV=_bash_path(hide),
        TMPDIR=_bash_path(scratch),
        GRIMOIRE_SUMMON_DOWNLOAD_ATTEMPTS="1",
        FRAMEWORK_RAW_BASE=source.as_uri(),
    )
    work = tmp_path / "cwd"
    work.mkdir()

    result = _run([], env, cwd=work, stdin=SUMMON_SH.read_text(encoding="utf-8"))

    assert result.returncode == 0, result.stdout + result.stderr
    assert "Python download fallback" in result.stdout
    assert "ARGS=" in result.stdout
