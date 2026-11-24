"""install_grimoire.py with a link that carries a credential: git keeps it, nothing else records or prints it."""

import base64
import functools
import json
import os
import shutil
import subprocess
import sys
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

import _lib
import install_grimoire
import summon_core
import sync_library
import update_grimoires
from diagnostics import ResultReporter

REPO_ROOT = Path(__file__).resolve().parent.parent
RITE = REPO_ROOT / "rites" / "install_grimoire.py"
GOOD = Path(__file__).parent / "fixtures" / "good_grimoire"
READ = "reader:READTOKEN111"
EDIT = "editor:EDITTOKEN222"
STALE = "editor:STALETOKEN333"
TOKENS = ("READTOKEN111", "EDITTOKEN222", "STALETOKEN333")


class _Handler(SimpleHTTPRequestHandler):
    """Serve a folder of bare repositories to requests that carry an accepted credential."""

    accepted: frozenset = frozenset()

    def do_GET(self):  # noqa: N802 - the base class names the method
        sent = self.headers.get("Authorization", "")
        if sent not in self.accepted:
            self.send_response(401)
            self.send_header("WWW-Authenticate", 'Basic realm="test"')
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        super().do_GET()

    def log_message(self, *args):
        pass


def _git(root: Path, *args: str, env: dict | None = None) -> str:
    result = subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True, text=True, env=env)
    return result.stdout.strip()


@pytest.fixture
def host(tmp_path):
    """A git host on this machine that accepts the read and the edit credential.

    Yields an object with `link(credential, path)`, `publish(name)` and `env`,
    the environment in which git asks nobody for a credential.
    """
    www = tmp_path / "www"
    work = tmp_path / "work"
    shutil.copytree(GOOD, work)
    config = tmp_path / "gitconfig"
    config.write_text("[user]\n\tname = Tester\n\temail = t@example.com\n", encoding="utf-8")
    env = {
        **os.environ, "GIT_CONFIG_GLOBAL": str(config), "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_TERMINAL_PROMPT": "0", "GCM_INTERACTIVE": "never", "GIT_ASKPASS": "",
    }
    _git(work, "init", "-q", "-b", "main", env=env)
    _git(work, "add", "-A", env=env)
    _git(work, "commit", "-q", "-m", "scaffold", env=env)
    for folder in ("team", "mirror"):
        bare = www / folder / "recipes-grimoire.git"
        bare.parent.mkdir(parents=True)
        subprocess.run(["git", "clone", "-q", "--bare", str(work), str(bare)], check=True, capture_output=True, env=env)
        _git(bare, "update-server-info", env=env)
    accepted = frozenset("Basic " + base64.b64encode(c.encode()).decode() for c in (READ, EDIT))
    handler = functools.partial(type("Handler", (_Handler,), {"accepted": accepted}), directory=str(www))
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    port = server.server_address[1]

    class Host:
        pass

    made = Host()
    made.env = env
    made.address = f"http://127.0.0.1:{port}/team/recipes-grimoire.git"
    made.link = lambda credential, folder="team": f"http://{credential}@127.0.0.1:{port}/{folder}/recipes-grimoire.git"

    def publish(name: str) -> None:
        (work / name).write_text(f"{name}\n", encoding="utf-8")
        _git(work, "add", "-A", env=env)
        _git(work, "commit", "-q", "-m", f"add {name}", env=env)
        bare = www / "team" / "recipes-grimoire.git"
        _git(work, "push", "-q", str(bare), "main", env=env)
        _git(bare, "update-server-info", env=env)

    made.publish = publish
    try:
        yield made
    finally:
        server.shutdown()
        server.server_close()


def _run(host, url: str, home: Path, *extra: str) -> dict:
    result = subprocess.run(
        [sys.executable, str(RITE), url, "--home", str(home), "--no-skills", "--format", "json", *extra],
        capture_output=True, text=True, timeout=180, env=host.env,
    )
    return {"returncode": result.returncode, "report": json.loads(result.stdout), "raw": result.stdout + result.stderr}


def _origin(host, home: Path) -> str:
    return _git(home / "recipes-grimoire", "remote", "get-url", "origin", env=host.env)


def _entry(home: Path) -> dict:
    return json.loads((home / "library.json").read_text(encoding="utf-8"))["grimoires"]["recipes-grimoire"]


def _no_token(text: str) -> bool:
    return not any(token in text for token in TOKENS)


def test_a_link_with_a_credential_clones_and_the_credential_stays_with_git(host, tmp_path):
    home = tmp_path / "home"

    out = _run(host, host.link(READ), home)

    assert out["returncode"] == 0, out["raw"]
    assert _origin(host, home) == host.link(READ)
    assert _entry(home) == {
        "access": "read", "local_path": _lib.format_local_path(home / "recipes-grimoire"), "online_path": host.address,
    }
    assert out["report"]["summary"]["url"] == host.address
    assert _no_token(out["raw"])
    assert _no_token((home / "library.json").read_text(encoding="utf-8"))


def test_a_new_credential_for_the_same_address_is_given_to_the_copy_without_a_question(host, tmp_path):
    home = tmp_path / "home"
    _run(host, host.link(READ), home)
    host.publish("later.md")

    out = _run(host, host.link(EDIT), home)

    assert out["returncode"] == 0, out["raw"]
    assert out["report"]["summary"]["credential"] == "refreshed"
    assert out["report"]["summary"]["access"] == "read"
    assert "origin" not in out["report"]["summary"]
    assert [m["action"] for m in out["report"]["mutations"]] == ["remote", "pull", "register"]
    assert _origin(host, home) == host.link(EDIT)
    assert (home / "recipes-grimoire" / "later.md").is_file()
    assert _entry(home)["online_path"] == host.address
    assert _no_token(out["raw"])


def test_access_and_switch_url_bring_a_read_copy_to_edit_with_the_new_credential(host, tmp_path):
    home = tmp_path / "home"
    assert _run(host, host.link(READ), home, "--access", "read", "--switch-url")["report"]["summary"]["access"] == "read"

    out = _run(host, host.link(EDIT), home, "--access", "edit", "--switch-url")

    assert out["returncode"] == 0, out["raw"]
    assert out["report"]["summary"]["access"] == "edit"
    assert out["report"]["summary"]["credential"] == "refreshed"
    assert _origin(host, home) == host.link(EDIT)
    assert _entry(home)["access"] == "edit"
    assert _no_token(out["raw"])

    again = _run(host, host.link(EDIT), home, "--access", "edit", "--switch-url")

    assert again["returncode"] == 0
    assert "credential" not in again["report"]["summary"]
    assert [m["action"] for m in again["report"]["mutations"]] == ["pull", "register"]


def test_a_link_without_a_credential_leaves_the_copys_credential_alone(host, tmp_path):
    home = tmp_path / "home"
    _run(host, host.link(READ), home)

    out = _run(host, host.address, home)

    assert out["returncode"] == 0, out["raw"]
    assert "credential" not in out["report"]["summary"]
    assert _origin(host, home) == host.link(READ)


def test_a_credential_that_cannot_fetch_changes_nothing(host, tmp_path):
    home = tmp_path / "home"
    _run(host, host.link(READ), home)
    library_before = (home / "library.json").read_text(encoding="utf-8")

    out = _run(host, host.link(STALE), home, "--access", "edit", "--switch-url")

    assert out["returncode"] == 1
    assert out["report"]["status"] == "error"
    assert out["report"]["mutations"] == []
    assert any("with the credential in the link" in m["message"] for m in out["report"]["messages"])
    assert _origin(host, home) == host.link(READ)
    assert (home / "library.json").read_text(encoding="utf-8") == library_before
    assert _no_token(out["raw"])


def test_a_first_clone_with_a_refused_credential_prints_no_credential(host, tmp_path):
    home = tmp_path / "home"

    out = _run(host, host.link(STALE), home)

    assert out["returncode"] == 1
    assert any("the credential in the link may be out of date" in m["message"] for m in out["report"]["messages"])
    assert not (home / "library.json").exists()
    assert _no_token(out["raw"])


def test_another_address_still_stops_and_names_both_addresses_without_credentials(host, tmp_path):
    home = tmp_path / "home"
    _run(host, host.link(READ), home)

    out = _run(host, host.link(EDIT, "mirror"), home, "--access", "edit")

    assert out["returncode"] == 1
    assert out["report"]["status"] == "blocked"
    assert out["report"]["summary"]["origin"] == host.address
    assert any("--switch-url" in m["message"] for m in out["report"]["messages"])
    assert _origin(host, home) == host.link(READ)
    assert _entry(home)["access"] == "read"
    assert _no_token(out["raw"])

    switched = _run(host, host.link(EDIT, "mirror"), home, "--access", "edit", "--switch-url")

    assert switched["returncode"] == 0, switched["raw"]
    assert _origin(host, home) == host.link(EDIT, "mirror")
    assert _entry(home)["online_path"] == host.address.replace("/team/", "/mirror/")
    assert _no_token(switched["raw"])


def test_the_human_output_prints_no_credential(host, tmp_path):
    home = tmp_path / "home"

    result = subprocess.run(
        [sys.executable, str(RITE), host.link(READ), "--home", str(home), "--no-skills"],
        capture_output=True, text=True, timeout=180, env=host.env,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert host.address in result.stdout
    assert _no_token(result.stdout + result.stderr)


@pytest.mark.parametrize("url, stripped, credential", [
    ("https://token@git.example.com/you/notes.git", "https://git.example.com/you/notes.git", "token"),
    ("https://user:secret@git.example.com:8443/you/notes", "https://git.example.com:8443/you/notes", "user:secret"),
    ("https://user:p@ss@git.example.com/notes", "https://git.example.com/notes", "user:p@ss"),
    ("https://user:p#s?s@git.example.com/notes", "https://git.example.com/notes", "user:p#s?s"),
    ("https://git.example.com/notes?ref=a@b", "https://git.example.com/notes?ref=a@b", ""),
    ("https://git.example.com/you@work/notes", "https://git.example.com/you@work/notes", ""),
    ("ssh://git@git.example.com/you/notes.git", "ssh://git@git.example.com/you/notes.git", ""),
    ("ssh://git:secret@git.example.com/you/notes.git", "ssh://git@git.example.com/you/notes.git", "secret"),
    ("git@git.example.com:you/notes.git", "git@git.example.com:you/notes.git", ""),
    ("C:/repos/notes.git", "C:/repos/notes.git", ""),
    ("  https://token@git.example.com/notes  ", "https://git.example.com/notes", "token"),
])
def test_strip_credentials_and_address_credentials(url, stripped, credential):
    assert _lib.strip_credentials(url) == stripped
    assert _lib.address_credentials(url) == credential


def test_scrub_credentials_cleans_every_address_in_a_text():
    text = (
        "fatal: unable to access 'https://user:TOKEN@git.example.com/x.git/': 403; "
        "moved from https://TOKEN@git.example.com/y to ssh://git:SECRET@git.example.com/z; "
        "git@git.example.com:you/notes stays, and so does you@example.com"
    )

    cleaned = _lib.scrub_credentials(text)

    assert "TOKEN" not in cleaned and "SECRET" not in cleaned
    assert _lib.scrub_credentials("see https://user:TO#KEN?x@git.example.com/x.git now") == "see https://git.example.com/x.git now"
    assert "https://git.example.com/x.git/" in cleaned and "ssh://git@git.example.com/z" in cleaned
    assert "git@git.example.com:you/notes" in cleaned and "you@example.com" in cleaned


def test_two_links_that_differ_only_by_credential_are_one_address():
    assert install_grimoire.same_address("https://READ@git.example.com/you/notes.git", "https://EDIT@git.example.com/You/Notes/")
    assert not install_grimoire.same_address("https://READ@git.example.com/you/notes", "https://READ@read.example.com/you/notes")


def test_an_envelope_never_carries_a_credential(tmp_path, capsys):
    reporter = ResultReporter("sample", root=tmp_path, mode="apply")
    reporter.message("error", "could not fetch https://user:TOKEN@git.example.com/x.git")
    reporter.mutation("remote", path=tmp_path, detail="https://TOKEN@git.example.com/a -> https://TOKEN@git.example.com/b")

    reporter.emit("json", summary={"url": "https://TOKEN@git.example.com/x", "nested": {"list": ["https://u:TOKEN@h/x"]}})

    printed = capsys.readouterr().out
    assert "TOKEN" not in printed
    assert json.loads(printed)["summary"] == {"url": "https://git.example.com/x", "nested": {"list": ["https://h/x"]}}


def test_the_library_sync_records_an_address_without_its_credential(tmp_path):
    home = tmp_path / "home"
    checkout = home / "notes"
    shutil.copytree(GOOD, checkout)
    (checkout / "grimoire.json").write_text(json.dumps({"name": "notes", "skill_prefix": "nt", "description": "notes"}), encoding="utf-8")
    _git(checkout, "init", "-q", "-b", "main")
    _git(checkout, "remote", "add", "origin", "https://TOKEN@git.example.com/you/notes.git")

    scan = sync_library.scan_grimoire_home(home)
    fresh = sync_library.build_synced_library(scan, {"grimoires": {}}, home)
    held = sync_library.build_synced_library(
        scan, {"grimoires": {"notes": {"local_path": "x", "online_path": "https://OLD:TOKEN@git.example.com/you/notes.git"}}}, home,
    )

    assert fresh["grimoires"]["notes"]["online_path"] == "https://git.example.com/you/notes.git"
    assert held["grimoires"]["notes"]["online_path"] == "https://git.example.com/you/notes.git"


def test_the_update_report_shows_an_address_without_a_credential_the_library_still_holds(tmp_path):
    entry = {"local_path": str(tmp_path / "gone"), "online_path": "https://OLD:TOKEN@git.example.com/you/notes.git"}

    record = update_grimoires.process_grimoire("notes", entry, REPO_ROOT, apply=False, fetch=False)

    assert record["online_path"] == "https://git.example.com/you/notes.git"
    assert record["host"] == "git.example.com"


def test_the_installer_log_prints_no_credential(capsys):
    log = summon_core.Logger()

    log.info("Cloning notes from https://user:TOKEN@git.example.com/you/notes.git...")
    log.line("fatal: unable to access 'https://TOKEN@git.example.com/you/notes.git/'")

    printed = capsys.readouterr().out
    assert "TOKEN" not in printed
    assert "https://git.example.com/you/notes.git" in printed


def _local_remote(tmp_path: Path) -> Path:
    work = tmp_path / "local-work"
    shutil.copytree(GOOD, work)
    _git(work, "init", "-q", "-b", "main")
    _git(work, "-c", "user.name=Tester", "-c", "user.email=t@example.com", "add", "-A")
    _git(work, "-c", "user.name=Tester", "-c", "user.email=t@example.com", "commit", "-q", "-m", "scaffold")
    bare = tmp_path / "recipes-grimoire.git"
    subprocess.run(["git", "clone", "-q", "--bare", str(work), str(bare)], check=True, capture_output=True)
    return bare


def _join(url: str, home: Path, *extra: str) -> dict:
    result = subprocess.run(
        [sys.executable, str(RITE), url, "--home", str(home), "--no-skills", "--format", "json", *extra],
        capture_output=True, text=True, timeout=180,
    )
    return json.loads(result.stdout)


def test_a_copy_set_to_reading_while_it_holds_unshared_work_gets_a_warning_with_counts(tmp_path):
    remote = _local_remote(tmp_path)
    home = tmp_path / "home"
    fresh = _join(str(remote), home, "--access", "edit")
    assert "unshared" not in fresh["summary"]
    copy = home / "recipes-grimoire"
    (copy / "mine.md").write_text("mine\n", encoding="utf-8")
    _git(copy, "add", "-A")
    _git(copy, "-c", "user.name=Tester", "-c", "user.email=t@example.com", "commit", "-q", "-m", "mine")
    (copy / "draft.md").write_text("draft\n", encoding="utf-8")

    out = _join(str(remote), home, "--access", "read")

    assert out["status"] == "ok"
    assert out["summary"]["access"] == "read"
    assert out["summary"]["unshared"] == {"changes": 1, "commits": 1}
    warnings = [m["message"] for m in out["messages"] if m["severity"] == "warning"]
    assert any("1 unsaved change(s), 1 commit(s)" in text for text in warnings)
    assert (copy / "mine.md").is_file() and (copy / "draft.md").is_file()


def test_a_clean_copy_set_to_reading_gets_no_warning(tmp_path):
    remote = _local_remote(tmp_path)
    home = tmp_path / "home"
    _join(str(remote), home, "--access", "edit")

    out = _join(str(remote), home, "--access", "read")

    assert out["summary"]["access"] == "read"
    assert "unshared" not in out["summary"]
    assert not [m for m in out["messages"] if m["severity"] == "warning"]


SETUP_PLAYBOOK = REPO_ROOT / "invocations" / "grm" / "setup.md"
SETUP_SKILL = REPO_ROOT / "skills" / "grm" / "setup" / "SKILL.md"


def test_the_setup_command_takes_the_whole_text_so_an_access_word_and_a_spaced_folder_both_arrive():
    skill = SETUP_SKILL.read_text(encoding="utf-8")
    rendered = (REPO_ROOT / "plugins" / "grimoire" / "skills" / "setup" / "SKILL.md").read_text(encoding="utf-8")

    assert 'argument-hint: "[git url | folder] [read | edit]"' in skill
    assert "\narguments:" not in skill
    assert "$ARGUMENTS" in skill and "$ARGUMENTS" in rendered


def test_the_setup_playbook_runs_the_join_with_the_access_the_user_named():
    playbook = SETUP_PLAYBOOK.read_text(encoding="utf-8")

    assert 'install_grimoire "<url>" --access <read|edit> --switch-url --format json' in playbook
    assert 'install_grimoire "<url>" --format json' in playbook
    assert "Never conclude from step 1 that a link needs no install." in playbook
    assert "Never write out the credential part of a link" in playbook


def test_a_link_with_only_a_user_name_keeps_that_name_in_the_copy_and_out_of_the_library(tmp_path, monkeypatch):
    """Some hosts put an account name in every clone link; git keeps the link whole and asks its helper for the rest."""
    link = "https://team@git.example.com/team/notes/_git/notes"
    home = tmp_path / "home"
    checkout = home / "notes"
    shutil.copytree(GOOD, checkout)
    _git(checkout, "init", "-q", "-b", "main")
    _git(checkout, "remote", "add", "origin", link)

    assert install_grimoire.same_address(link, "https://git.example.com/team/notes/_git/notes")
    assert _lib.strip_credentials(link) == "https://git.example.com/team/notes/_git/notes"
    assert sync_library.detect_origin_url(checkout) == link


def test_the_setup_playbook_says_what_an_access_word_after_a_folder_means():
    playbook = SETUP_PLAYBOOK.read_text(encoding="utf-8")

    assert "Pass `$access` to a rite in lower case." in playbook
    assert "a folder the user adopts is theirs to edit" in playbook


def test_an_argument_error_prints_no_credential(tmp_path):
    result = subprocess.run(
        [sys.executable, str(RITE), "https://TOKEN@git.example.com/a.git", "https://user:TOKEN@git.example.com/b.git",
         "--home", str(tmp_path / "home")],
        capture_output=True, text=True, timeout=60,
    )

    assert result.returncode == 2
    assert "TOKEN" not in result.stdout + result.stderr
    assert "https://git.example.com/b.git" in result.stderr


def test_a_join_drops_a_credential_that_another_library_entry_still_holds(tmp_path):
    remote = _local_remote(tmp_path)
    home = tmp_path / "home"
    home.mkdir()
    (home / "library.json").write_text(json.dumps({"grimoires": {
        "other": {"local_path": "$HOME/grimoires/other", "online_path": "https://OLD:TOKEN@git.example.com/you/other.git", "access": "read"},
    }}), encoding="utf-8")

    _join(str(remote), home)

    library = json.loads((home / "library.json").read_text(encoding="utf-8"))["grimoires"]
    assert library["other"] == {
        "local_path": "$HOME/grimoires/other", "online_path": "https://git.example.com/you/other.git", "access": "read",
    }
    assert "recipes-grimoire" in library

