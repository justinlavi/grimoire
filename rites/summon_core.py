#!/usr/bin/env python3
"""Install core of the Grimoire Summoning Rite.

Sister module to `summon.py` (the dispatcher). It holds the constants, the
logger, the git and HTTP helpers, GitHub and GitLab discovery, the install
pipeline, the routing-block classifier and writer, and the interactive terminal
flow. `rites/summon.sh` downloads this module, `summon.py`, `agent_targets.py`,
`data/agent_targets.json` and `templates/grimoire_block.md` into a temporary
folder and runs them before the framework exists on disk, so the module imports
only the standard library and `agent_targets` at load time. A function that
needs another rite imports it inside the function, after
`use_framework_modules()` has put the framework checkout on the import path.

Mutation profile: apply_only. A run writes the framework checkout, the chosen
grimoire clones, `library.json`, the routing block in each agent instruction
file and the skill folders of each agent.

Usage: run through `summon.py`; this module has no command line of its own.
"""

import json
import os
import re
import subprocess
import sys
from pathlib import Path
from urllib.error import URLError
from urllib.parse import quote, urlparse
from urllib.request import Request, urlopen

from agent_targets import (
    installed_instruction_targets,
    installed_skill_targets,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

RITE_DIR = Path(__file__).resolve().parent
REPO_ROOT = RITE_DIR.parent
GRIMOIRES_HOME = Path.home() / "grimoires"
FRAMEWORK_DIR = Path.home() / ".grimoire"
LOCAL_LIBRARY = GRIMOIRES_HOME / "library.json"
DEFAULT_FRAMEWORK_URL = "https://github.com/justinlavi/grimoire.git"

# The comment `sync_skills.py` stamps into every skill it writes
# (`sync_skills.OWNERSHIP_MARKER`); tests/test_summon_core.py keeps the two equal.
SKILL_OWNERSHIP_MARKER = "FRAMEWORK_SKILL_OWNERSHIP"


def _load_grimoire_block():
    """Load the canonical Grimoire routing block from the markdown template."""
    candidates = [
        RITE_DIR / "templates" / "grimoire_block.md",
        FRAMEWORK_DIR / "rites" / "templates" / "grimoire_block.md",
    ]

    for template_path in candidates:
        if template_path.is_file():
            return "\n" + template_path.read_text(encoding="utf-8")

    checked = ", ".join(str(path) for path in candidates)
    raise FileNotFoundError(
        "Could not find canonical Grimoire routing block template. "
        f"Checked: {checked}"
    )


GRIMOIRE_BLOCK = _load_grimoire_block()

# The BEGIN and END markers define the routing block: the framework owns every
# line between them and the user owns every line outside. The session hook of the
# grimoire plugin carries a copy of the two literals;
# tests/test_summon_core.py keeps them equal.
BEGIN_SENTINEL = "<!-- BEGIN GRIMOIRE KNOWLEDGE BASE -->"
END_SENTINEL = "<!-- END GRIMOIRE KNOWLEDGE BASE -->"

# The block's own title line. It signals only that a block is already present, so
# no mechanical pass appends a second block over a malformed or unmarked one. A
# file that carries it without clean markers goes to judgment.
BLOCK_HEADING = "## Grimoire Knowledge Base"

ROUTING_REASONS = {
    "create": "file absent",
    "present": "routing block present and current",
    "refresh": "routing block out of date",
    "insert": "no routing block - safe to add",
    "review": "block-like but not one clean BEGIN..END region",
    "served": "the grimoire plugin's session hook supplies the block",
}


def canonical_routing_block():
    """The canonical BEGIN..END routing block, no surrounding blank lines."""
    return GRIMOIRE_BLOCK.strip()


def classify_routing_block(content):
    """Classify a file's routing-block state from its markers alone.

    The one classifier of the routing block. Returns:
      create  - no file (write a fresh heading + block)
      present - exactly one clean BEGIN..END region, already current (noop)
      refresh - exactly one clean region, but stale (replace it)
      insert  - no block signature at all, safe to add one mechanically
      review  - block-like but not one clean region (duplicate or malformed
                markers, or an unmarked heading-only block) -> judgment, never
                a mechanical write, so a second block is never appended
    """
    if content is None:
        return "create"
    if content.count(BEGIN_SENTINEL) == 1 and content.count(END_SENTINEL) == 1:
        begin = content.find(BEGIN_SENTINEL)
        end = content.find(END_SENTINEL)
        if begin < end:
            region = content[begin:end + len(END_SENTINEL)]
            return "present" if region == canonical_routing_block() else "refresh"
    if BEGIN_SENTINEL not in content and END_SENTINEL not in content and BLOCK_HEADING not in content:
        return "insert"
    return "review"


def write_text(path, text):
    """Write UTF-8 with LF line endings, replacing the file in one step.

    The self-contained counterpart of `_lib.write_utf8`, which the bootstrap
    cannot import.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        with open(temporary, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
        os.replace(temporary, path)
    except BaseException:
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise


def _plan_routing_block(path):
    """Return `(action, reason, content)` for one instruction file; writes nothing."""
    if not path.is_file():
        return "create", ROUTING_REASONS["create"], None
    try:
        content = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return "review", "not UTF-8", None
    except OSError as exc:
        return "review", f"could not be read ({exc})", None
    action = classify_routing_block(content)
    return action, ROUTING_REASONS[action], content


def routing_block_action(path):
    """Return `(action, reason)` for the instruction file at `path`; writes nothing."""
    action, reason, _content = _plan_routing_block(Path(path))
    return action, reason


def apply_routing_block(path, title, *, apply=True, plugin_served=False):
    """The one writer of the routing block: plan, and under `apply` perform, one file.

    Returns `{"path", "action", "reason", "status"}` and logs nothing. `action`
    is the classifier's, or `served` when `plugin_served` is set and the file
    carries no block: the grimoire plugin's session hook prints the block, so
    nothing is written. `status` is `planned` without `apply`; with it, `ok`
    (wrote), `noop`, `review` (a block-like or unreadable file, left untouched)
    or `error` (the write failed). The function never appends over a block-like
    file, so it never makes a second block.
    """
    path = Path(path)
    action, reason, content = _plan_routing_block(path)
    if plugin_served and action in ("create", "insert"):
        action, reason = "served", ROUTING_REASONS["served"]
    result = {
        "path": str(path),
        "action": action,
        "reason": reason,
        "status": "planned" if not apply else "noop",
    }
    if not apply:
        return result

    if action == "create":
        new = f"# {title}\n" + GRIMOIRE_BLOCK
    elif action == "insert":
        if content.startswith(f"# {title}"):
            cut = content.index("\n") + 1 if "\n" in content else len(content)
            new = content[:cut] + GRIMOIRE_BLOCK + content[cut:]
        else:
            new = content + GRIMOIRE_BLOCK
    elif action == "refresh":
        begin = content.find(BEGIN_SENTINEL)
        end = content.find(END_SENTINEL) + len(END_SENTINEL)
        new = content[:begin] + canonical_routing_block() + content[end:]
    else:
        if action == "review":
            result["status"] = "review"
        return result

    try:
        write_text(path, new)
    except OSError as exc:
        result["status"] = "error"
        result["reason"] = f"could not be written ({exc})"
        return result
    result["status"] = "ok"
    return result


def use_framework_modules():
    """Make the other rites importable once the framework checkout is on disk.

    The piped bootstrap runs this module from a temporary folder that holds no
    other rite. The call appends the framework's `rites` folder to the import
    path, after the folders already there, and does nothing when the rites are
    already importable.
    """
    try:
        import _lib  # noqa: F401
        return
    except ImportError:
        pass
    rites = FRAMEWORK_DIR / "rites"
    if rites.is_dir() and str(rites) not in sys.path:
        sys.path.append(str(rites))


def grimoire_command(rite, *args, root=None):
    """The command that runs `rite` through the framework launcher, as printed for a reader."""
    launcher = Path(root or FRAMEWORK_DIR) / "bin" / "grimoire"
    return " ".join([launcher.as_posix(), rite, *args])


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------


class Logger:
    """Terminal logger with prefixed output.

    Exposes info/ok/warn/err for tagged messages, plus `line()` for raw
    subprocess output that should appear in the user-visible log without a tag
    prefix. Any object with the same surface can stand in (tests, orchestrators).
    """
    def info(self, msg):  print(f"  [INFO]  {msg}")
    def ok(self, msg):    print(f"  [OK]    {msg}")
    def warn(self, msg):  print(f"  [WARN]  {msg}")
    def err(self, msg):   print(f"  [ERROR] {msg}")
    def line(self, text): print(text)


# ---------------------------------------------------------------------------
# Git helpers
# ---------------------------------------------------------------------------


GIT_TIMEOUT = 600  # seconds; backstop so a stalled fetch cannot hang the install


def git(*args, cwd=None, log=None):
    """Run a git command. Returns (success: bool, stdout: str).

    Adapter over git_capture(), which holds the environment, timeout and
    fail-fast prompt handling. Logs the captured stderr line by line on failure
    (or a network hint on the 124 timeout sentinel) when a log is given.
    """
    rc, out, err = git_capture(*args, cwd=cwd)
    if rc != 0 and log is not None:
        if rc == 124:
            log.line(
                f"git timed out after {GIT_TIMEOUT}s - check network access "
                "and that authentication is configured"
            )
        else:
            for line in (err or "").splitlines():
                log.line(line)
    return rc == 0, out


def git_capture(*args, cwd=None):
    """Run a git command, returning (returncode, stdout, stderr).

    `git()` collapses the result to (ok, stdout) and discards stderr; the
    branch-aware update path needs the stderr to tell an auth failure (HTTP 403,
    insufficient_scope) from offline (could not resolve host) from a
    non-fast-forward refusal. The environment sets GIT_TERMINAL_PROMPT=0 so git
    fails instead of asking. A timeout returns 124 and a missing git 127, each
    with an explanatory stderr the caller can classify.
    """
    env = dict(os.environ)
    env.setdefault("GIT_TERMINAL_PROMPT", "0")
    try:
        result = subprocess.run(
            ["git"] + list(args),
            cwd=cwd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=env,
            timeout=GIT_TIMEOUT,
        )
        return result.returncode, (result.stdout or "").strip(), (result.stderr or "").strip()
    except subprocess.TimeoutExpired:
        return 124, "", f"git timed out after {GIT_TIMEOUT}s"
    except FileNotFoundError:
        return 127, "", "git executable not found on PATH"


def detect_framework_url():
    """The origin URL of the git checkout this module runs from, or an empty string."""
    if not (REPO_ROOT / ".git").exists():
        return ""
    ok, url = git("-C", str(REPO_ROOT), "remote", "get-url", "origin")
    return url if ok else ""


def resolve_framework_url(args):
    """Resolve the framework URL: `--framework-url`, then `FRAMEWORK_URL`, then the
    origin of the checkout this module runs from, then the public default."""
    return (
        args.framework_url
        or os.environ.get("FRAMEWORK_URL", "")
        or detect_framework_url()
        or DEFAULT_FRAMEWORK_URL
    )


def git_credential_token(host):
    """Query git credential helper for a stored token/password."""
    try:
        result = subprocess.run(
            ["git", "credential", "fill"],
            input=f"protocol=https\nhost={host}\n\n",
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode != 0:
            return ""
        for line in result.stdout.splitlines():
            if line.startswith("password="):
                return line[len("password="):]
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return ""


# ---------------------------------------------------------------------------
# URL parsing
# ---------------------------------------------------------------------------


def parse_scope_url(url):
    """Parse a scope URL into (host, scope)."""
    raw = url.strip()
    ssh_match = re.match(r"^git@([^:]+):(.+)$", raw)
    if ssh_match:
        host = ssh_match.group(1)
        scope = ssh_match.group(2)
    else:
        if not re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", raw):
            raw = f"https://{raw}"
        parsed = urlparse(raw)
        host = parsed.netloc
        scope = parsed.path.lstrip("/")
    scope = re.sub(r"\.git$", "", scope.rstrip("/"))
    return host.lower(), scope


def _scope_parts(scope):
    return [part for part in scope.split("/") if part]


def _library_key_from_repo_path(path):
    parts = _scope_parts(path)
    return parts[-1] if parts else ""


def _is_github_host(host):
    h = host.lower()
    return h == "github.com" or h.endswith(".github.com") or h.split(".")[0] == "github"


def _is_gitlab_host(host):
    h = host.lower()
    return h == "gitlab.com" or h.endswith(".gitlab.com") or h.split(".")[0] == "gitlab"


# ---------------------------------------------------------------------------
# API discovery
# ---------------------------------------------------------------------------


def _api_get(url, token_header=None, token_value=None):
    """GET a JSON API endpoint. Returns (data, error_string)."""
    from urllib.error import HTTPError
    req = Request(url)
    req.add_header("User-Agent", "grimoire-summon/1.0")
    if token_header and token_value:
        req.add_header(token_header, token_value)
    try:
        with urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode()), None
    except HTTPError as e:
        body = ""
        try:
            body = e.read().decode("utf-8", errors="replace")[:200]
        except Exception:
            pass
        detail = ""
        if body:
            try:
                msg = json.loads(body)
                detail = msg.get("message") or msg.get("error") or body
            except (json.JSONDecodeError, AttributeError):
                detail = body
        return None, f"HTTP {e.code}: {detail}" if detail else f"HTTP {e.code}"
    except URLError as e:
        return None, f"Connection failed: {e.reason}"
    except json.JSONDecodeError:
        return None, "Response was not valid JSON"
    except OSError as e:
        return None, str(e)


LIST_PAGE_SIZE = 100
LIST_MAX_PAGES = 10


def _api_get_all(url, token_header=None, token_value=None):
    """GET a listing endpoint that carries `per_page=100`, following its pages.

    Reads page after page until one holds fewer than `LIST_PAGE_SIZE` entries,
    and at most `LIST_MAX_PAGES` pages. A response that is not a list is
    returned as it is. A failure on the first page is the result; a failure on a
    later page keeps the pages already read. Returns (data, error_string).
    """
    data, err = _api_get(url, token_header=token_header, token_value=token_value)
    if err or not isinstance(data, list):
        return data, err
    entries = list(data)
    page = 1
    while len(data) >= LIST_PAGE_SIZE and page < LIST_MAX_PAGES:
        page += 1
        data, err = _api_get(f"{url}&page={page}", token_header=token_header, token_value=token_value)
        if err or not isinstance(data, list):
            break
        entries.extend(data)
    return entries, None


FRAMEWORK_REPO_NAME = "grimoire"


def _metadata_marks_grimoire(name, description="", topics=None):
    topics = topics or []
    normalized = {str(t).lower() for t in topics}
    name_l = (name or "").lower()
    desc_l = (description or "").lower()
    if name_l == FRAMEWORK_REPO_NAME:
        return False  # the framework describes grimoires; it is not one
    return (
        name_l.endswith("-grimoire")
        or "grimoire" in normalized
        or "grimoire" in desc_l
    )


def _github_entry(repo):
    name = repo.get("name") or _library_key_from_repo_path(repo.get("full_name", ""))
    return {
        "name": name,
        "description": repo.get("description") or "Grimoire",
        "online_path": repo.get("clone_url", ""),
    }


def _gitlab_entry(project):
    path = project.get("path") or _library_key_from_repo_path(project.get("path_with_namespace", ""))
    return {
        "name": project.get("name", path),
        "description": project.get("description") or "Grimoire",
        "online_path": project.get("http_url_to_repo", ""),
    }


def _gitlab_filter_grimoires(data, log):
    if not isinstance(data, list):
        log.warn(f"GitLab API returned unexpected response type: {type(data).__name__}")
        return {}
    entries = {}
    for project in data:
        path = project.get("path", "")
        topics = project.get("topics") or project.get("tag_list") or []
        if not _metadata_marks_grimoire(path, project.get("description", ""), topics):
            continue
        entries[path] = _gitlab_entry(project)
    return entries


def _resolve_token(host, env_var, explicit_token, log):
    if explicit_token:
        return explicit_token
    from_env = os.environ.get(env_var, "")
    if from_env:
        log.info(f"Using token from ${env_var}")
        return from_env
    from_git = git_credential_token(host)
    if from_git:
        log.info(f"Using token from git credential store for {host}")
        return from_git
    return ""


def try_gitlab_discovery(host, scope, token, log):
    auth_h = "PRIVATE-TOKEN" if token else None
    auth_v = token or None

    if len(_scope_parts(scope)) >= 2:
        encoded_project = quote(scope, safe="")
        project_url = f"https://{host}/api/v4/projects/{encoded_project}"
        log.info(f"Trying GitLab project API: {project_url}")
        data, err = _api_get(project_url, token_header=auth_h, token_value=auth_v)
        if isinstance(data, dict) and data.get("http_url_to_repo"):
            key = data.get("path") or _library_key_from_repo_path(scope)
            log.ok(f"Using explicit GitLab project: {key}")
            return {key: _gitlab_entry(data)}
        if err and "404" not in err:
            log.warn(f"GitLab project lookup failed: {err}")

    if not scope:
        url = f"https://{host}/api/v4/projects?search=grimoire&per_page=100"
        log.info(f"Trying GitLab API: {url}")
        data, err = _api_get_all(url, token_header=auth_h, token_value=auth_v)
        if err:
            log.warn(f"GitLab API failed: {err}")
            if not token:
                log.warn("No credentials found - set GITLAB_TOKEN or configure git credential helper")
            return {}
        return _gitlab_filter_grimoires(data, log)

    encoded = quote(scope, safe="")
    group_url = f"https://{host}/api/v4/groups/{encoded}/projects?search=grimoire&per_page=100"
    log.info(f"Trying GitLab groups API: {group_url}")
    data, err = _api_get_all(group_url, token_header=auth_h, token_value=auth_v)
    if data is not None:
        return _gitlab_filter_grimoires(data, log)

    if "404" in (err or ""):
        user = scope.split("/")[0]
        user_url = f"https://{host}/api/v4/users?username={user}"
        log.info(f"Group not found, trying as user namespace: {user}")
        user_data, _ = _api_get(user_url, token_header=auth_h, token_value=auth_v)
        if isinstance(user_data, list) and user_data:
            uid = user_data[0].get("id")
            proj_url = f"https://{host}/api/v4/users/{uid}/projects?search=grimoire&per_page=100"
            log.info(f"Trying GitLab user projects API: {proj_url}")
            data, err = _api_get_all(proj_url, token_header=auth_h, token_value=auth_v)
            if data is not None:
                return _gitlab_filter_grimoires(data, log)

    log.warn(f"GitLab API failed: {err}")
    if not token:
        log.warn("No credentials found - set GITLAB_TOKEN or configure git credential helper")
    return {}


def try_github_discovery(host, scope, token, log):
    api_base = "https://api.github.com" if host == "github.com" else f"https://{host}/api/v3"
    parts = _scope_parts(scope)
    auth_h = "Authorization" if token else None
    auth_v = f"Bearer {token}" if token else None

    if len(parts) >= 2:
        owner, repo_name = parts[0], parts[1]
        repo_url = f"{api_base}/repos/{owner}/{repo_name}"
        log.info(f"Trying GitHub repo API: {repo_url}")
        data, err = _api_get(repo_url, token_header=auth_h, token_value=auth_v)
        if isinstance(data, dict) and data.get("clone_url"):
            key = data.get("name") or repo_name
            log.ok(f"Using explicit GitHub repository: {key}")
            return {key: _github_entry(data)}
        log.warn(f"GitHub repo lookup failed: {err}")
        return {}

    if not parts:
        log.warn("GitHub discovery requires an owner/org or owner/repo URL")
        return {}

    owner = parts[0]
    url = f"{api_base}/orgs/{owner}/repos?per_page=100"
    log.info(f"Trying GitHub org repos API: {url}")
    data, err = _api_get_all(url, token_header=auth_h, token_value=auth_v)
    if err:
        user_url = f"{api_base}/users/{owner}/repos?per_page=100"
        log.info(f"Org lookup failed, trying GitHub user repos API: {user_url}")
        data, err = _api_get_all(user_url, token_header=auth_h, token_value=auth_v)
        if err:
            log.warn(f"GitHub API failed: {err}")
            if not token:
                log.warn("No credentials found - set GITHUB_TOKEN or configure git credential helper")
            return {}
    if not isinstance(data, list):
        log.warn(f"GitHub API returned unexpected response type: {type(data).__name__}")
        return {}
    if token:
        data = _with_own_private_repos(api_base, owner, data, auth_h, auth_v, log)

    entries = {}
    for repo in data:
        name = repo.get("name", "")
        if not _metadata_marks_grimoire(
            name, repo.get("description", ""), repo.get("topics") or [],
        ):
            continue
        entries[name] = _github_entry(repo)
    return entries


def _with_own_private_repos(api_base, owner, public_repos, auth_h, auth_v, log):
    """Merge the token holder's private repositories under `owner` into a public listing.

    `/users/{owner}/repos` and `/orgs/{owner}/repos` list what the public sees;
    `/user/repos` lists what the token sees, including private repositories.
    """
    url = f"{api_base}/user/repos?per_page=100&affiliation=owner,organization_member"
    data, err = _api_get_all(url, token_header=auth_h, token_value=auth_v)
    if err or not isinstance(data, list):
        return public_repos
    seen = {repo.get("name", "") for repo in public_repos}
    merged = list(public_repos)
    for repo in data:
        login = str((repo.get("owner") or {}).get("login", "")).lower()
        if login != owner.lower() or repo.get("name", "") in seen:
            continue
        merged.append(repo)
        seen.add(repo.get("name", ""))
    added = len(merged) - len(public_repos)
    if added:
        log.info(f"Added {added} private repositor{'y' if added == 1 else 'ies'} visible to the token")
    return merged


def discover_grimoires(scope_url, log, explicit_token=""):
    """Discover grimoires from a scope URL. Returns dict of library entries."""
    host, scope = parse_scope_url(scope_url)
    if not host:
        log.warn("Could not parse host from URL")
        return {}

    if scope:
        log.info(f"Searching {host}/{scope} for grimoires...")
    else:
        log.info(f"Searching {host} for grimoires...")

    if _is_github_host(host):
        gh_token = _resolve_token(host, "GITHUB_TOKEN", explicit_token, log)
        entries = try_github_discovery(host, scope, gh_token, log)
        if entries:
            log.ok(f"Discovered {len(entries)} grimoire(s) via GitHub API")
            return entries
    elif _is_gitlab_host(host):
        gl_token = _resolve_token(host, "GITLAB_TOKEN", explicit_token, log)
        entries = try_gitlab_discovery(host, scope, gl_token, log)
        if entries:
            log.ok(f"Discovered {len(entries)} grimoire(s) via GitLab API")
            return entries
    else:
        gl_token = _resolve_token(host, "GITLAB_TOKEN", explicit_token, log)
        entries = try_gitlab_discovery(host, scope, gl_token, log)
        if entries:
            log.ok(f"Discovered {len(entries)} grimoire(s) via GitLab API")
            return entries
        gh_token = _resolve_token(host, "GITHUB_TOKEN", explicit_token, log)
        entries = try_github_discovery(host, scope, gh_token, log)
        if entries:
            log.ok(f"Discovered {len(entries)} grimoire(s) via GitHub API")
            return entries

    log.err(f"No grimoires found at {scope_url} - check the URL, network, and auth tokens")
    return {}


# ---------------------------------------------------------------------------
# Core operations
# ---------------------------------------------------------------------------


def check_git(log):
    ok, _ = git("--version")
    if not ok:
        log.err("git is required but not found on PATH")
        return False
    log.ok("git found")
    return True


# Top-level files of a healthy framework working tree. If `.git/` exists but
# none of these are checked out, the working tree is partial - most commonly
# because `git checkout` aborted on a path that's invalid on this OS (Windows
# rejects names containing < > : " | ? *).
WORKING_TREE_SENTINELS = ("README.md", "framework.json", "grimoire.md")


def working_tree_populated(target_dir):
    """True if the framework working tree under target_dir has at least one sentinel file."""
    return any((target_dir / s).exists() for s in WORKING_TREE_SENTINELS)


def grimoire_tree_populated(target_dir, git_fn=git):
    """True if a grimoire checkout holds its files.

    A grimoire needs no particular file, so any entry beside `.git` counts. A
    repository with no commit has no files to check out and counts as populated.
    """
    try:
        if any(entry.name != ".git" for entry in Path(target_dir).iterdir()):
            return True
    except OSError:
        return False
    has_commit, _ = git_fn("-C", str(target_dir), "rev-parse", "--verify", "--quiet", "HEAD")
    return not has_commit


def attempt_working_tree_recovery(target_dir, name, log, git_fn=git, populated=working_tree_populated):
    """Re-run checkout from HEAD to recover a partial working tree.

    Returns True if recovery succeeded (`populated` holds afterward), False otherwise.
    """
    log.warn(f"{name}: .git/ present but working tree is partial - attempting recovery")
    ok, _ = git_fn("-C", str(target_dir), "checkout", "HEAD", "--", ".", log=log)
    if ok and populated(target_dir):
        log.ok(f"{name}: working tree recovered via `git checkout HEAD -- .`")
        return True
    log.err(
        f"{name}: working tree still partial after recovery. The repository "
        f"likely contains a path invalid on this OS (Windows reserves "
        f"< > : \" | ? *). Inspect with `cd {target_dir} && git status`, "
        f"then either fix the upstream repo or remove {target_dir} and re-summon "
        f"once upstream is corrected."
    )
    return False


def install_framework(framework_url, log, git_fn=git):
    """Clone or update the framework."""
    log.info("Installing the framework...")
    if (FRAMEWORK_DIR / ".git").is_dir():
        log.info("Framework already installed - pulling latest...")
        ok, _ = git_fn("-C", str(FRAMEWORK_DIR), "pull", "--ff-only", log=log)
        if ok:
            log.ok(f"Framework updated: {FRAMEWORK_DIR}")
        else:
            log.warn("Framework pull failed (local changes?) - skipping update")
            log.ok(f"Framework exists: {FRAMEWORK_DIR}")
        if not working_tree_populated(FRAMEWORK_DIR):
            if not attempt_working_tree_recovery(FRAMEWORK_DIR, "Framework", log, git_fn):
                return False
    elif framework_url:
        ref = os.environ.get("FRAMEWORK_REF", "").strip()
        log.info(f"Cloning the framework from {framework_url}" + (f" at {ref}" if ref else "") + "...")
        ref_args = ["--branch", ref] if ref else []
        ok, _ = git_fn("clone", *ref_args, framework_url, str(FRAMEWORK_DIR), log=log)
        if not ok:
            log.err("Failed to clone the framework - check network and git credentials")
            if (FRAMEWORK_DIR / ".git").is_dir() and not working_tree_populated(FRAMEWORK_DIR):
                log.err(
                    "A partial clone was left at {0}. After resolving the cause, "
                    "remove that directory and re-run summon.".format(FRAMEWORK_DIR)
                )
            return False
        if not working_tree_populated(FRAMEWORK_DIR):
            if not attempt_working_tree_recovery(FRAMEWORK_DIR, "Framework", log, git_fn):
                return False
        log.ok(f"Framework cloned to {FRAMEWORK_DIR}")
    else:
        if FRAMEWORK_DIR.is_dir():
            log.ok(f"Framework exists: {FRAMEWORK_DIR}")
        else:
            log.err("Cannot detect framework origin URL")
            return False
    return True


# What `install_grimoire` did for one grimoire. A failure returns None.
CLONED = "cloned"
PULLED = "pulled"
KEPT = "kept"  # a checkout was already there and the pull failed; it stays as it was
SKIPPED = "skipped"  # the folder exists and is not a git checkout; nothing was done


def install_grimoire(key, entry, log, git_fn=git, home=None):
    """Clone or update a single grimoire under `home` (default: the grimoire home).

    Returns what happened: `CLONED`, `PULLED`, `KEPT` (the pull failed and the
    checkout stays as it was) or `SKIPPED` (the folder is not a git checkout and
    was left alone). Returns None when the grimoire is not installed.
    """
    name = entry.get("name", key)
    url = entry.get("online_path", "")
    target = Path(home or GRIMOIRES_HOME) / key

    def populated(folder):
        return grimoire_tree_populated(folder, git_fn)

    if (target / ".git").is_dir():
        log.info(f"{name} already installed - pulling latest...")
        ok, _ = git_fn("-C", str(target), "pull", "--ff-only", log=log)
        if ok:
            log.ok(f"{name} updated: {target}")
        else:
            log.warn(f"{name} pull failed (local changes?) - skipping update")
            log.ok(f"{name} exists: {target}")
        if not populated(target):
            if not attempt_working_tree_recovery(target, name, log, git_fn, populated):
                return None
        return PULLED if ok else KEPT
    if target.is_dir():
        log.warn(f"{name} directory exists but is not a git repo - skipping")
        return SKIPPED

    log.info(f"Cloning {name} from {url}...")
    ok, _ = git_fn("clone", url, str(target), log=log)
    if not ok:
        log.err(f"Failed to clone {name} - check VPN and git credentials")
        if (target / ".git").is_dir() and not populated(target):
            log.err(
                f"A partial clone was left at {target}. After resolving "
                f"the cause, remove that directory and re-run summon."
            )
        return None
    if not populated(target):
        if not attempt_working_tree_recovery(target, name, log, git_fn, populated):
            return None
    log.ok(f"Cloned {name} to {target}")
    return CLONED


def update_local_library(installed_keys, library, log, home=None, access="read", replace_access=False):
    """Register the installed grimoires in `<home>/library.json`. Returns True when it is current.

    The write goes through `sync_library.update_library`: compare-and-swap, fields
    of existing entries kept, `local_path` formatted by `_lib.format_local_path`.
    A key with no entry gains `"access": <access>`; an existing entry keeps its
    own `access`, or lack of one, unless `replace_access` is true. A library that
    cannot be read is left as it is and the function returns False.
    """
    log.info("Updating local library...")
    home = Path(home or GRIMOIRES_HOME)
    library_path = home / "library.json"
    use_framework_modules()
    from _lib import format_local_path
    import sync_library

    discovered = library.get("grimoires", {})

    def register(current):
        for key in installed_keys:
            existing = current["grimoires"].get(key)
            entry = dict(existing) if isinstance(existing, dict) else {}
            if replace_access or not isinstance(existing, dict):
                entry["access"] = access
            online_path = (discovered.get(key) or {}).get("online_path", "")
            entry["local_path"] = format_local_path(home / key)
            if online_path or "online_path" not in entry:
                entry["online_path"] = online_path
            current["grimoires"][key] = entry
        current["grimoires"] = dict(sorted(current["grimoires"].items()))
        return current

    try:
        sync_library.update_library(library_path, register)
    except (sync_library.LibraryUnreadable, sync_library.LibraryWriteConflict) as exc:
        log.err(f"Local library not updated: {exc}")
        log.err(f"Fix that file, then run: {grimoire_command('summon', '--reconcile', '--apply')}")
        return False
    log.ok(f"Local library updated: {library_path}")
    return True


def inject_agent_file(log, target_path, title, plugin_served=False):
    """Write the Grimoire routing block into one agent instruction file.

    Calls `apply_routing_block`, so the install only does the unambiguous work and
    never appends a second block. A block-like file that is not one clean
    BEGIN..END region (duplicate or malformed markers, an unmarked heading-only
    block, a file that is not UTF-8) is left untouched for `/grm-update agentfile`.
    """
    log.info(f"Configuring {target_path.name}...")
    result = apply_routing_block(target_path, title, apply=True, plugin_served=plugin_served)
    name = target_path.name
    if result["status"] == "error":
        log.err(f"{name} {result['reason']}")
    elif result["action"] == "create":
        log.ok(f"Grimoire routing block written to new {name}")
    elif result["action"] == "refresh":
        log.ok(f"Grimoire routing block refreshed in {name}")
    elif result["action"] == "insert":
        log.ok(f"Grimoire routing block injected into {name}")
    elif result["action"] == "served":
        log.ok(f"{name} needs no routing block: the grimoire plugin supplies it (skipping)")
    elif result["action"] == "present":
        log.ok(f"Grimoire routing block already current in {name} (skipping)")
    else:
        log.warn(
            f"{name} is left unchanged ({result['reason']}); "
            "run /grm-update agentfile to fix it"
        )


def inject_agent_configs(log):
    """Write the routing block into the instruction file of each installed agent."""
    for target in installed_instruction_targets(REPO_ROOT):
        inject_agent_file(
            log, target["path"], target["title"],
            plugin_served=target.get("plugin_serves_routing", False),
        )


def _registered_skill_count(skills_dir):
    """Count framework-managed installed skill directories under one target."""
    if not skills_dir.is_dir():
        return 0
    count = 0
    for skill_dir in skills_dir.iterdir():
        skill_file = skill_dir / "SKILL.md"
        if not skill_dir.is_dir() or not skill_file.is_file():
            continue
        try:
            content = skill_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if SKILL_OWNERSHIP_MARKER in content:
            count += 1
    return count


SKILL_SYNC_COUNTS = ("registered", "cleaned", "reset", "blocked")


def skill_sync_script():
    """The `sync_skills.py` of the installed framework, else the one beside this module; None when neither exists."""
    for folder in (FRAMEWORK_DIR / "rites", RITE_DIR):
        script = folder / "sync_skills.py"
        if script.is_file():
            return script
    return None


def run_sync_skills(script, *args, timeout=300):
    """Run `sync_skills.py --format json` with `args`. Returns `(returncode, output)`.

    `output` is the JSON report from stdout, or stderr when stdout is empty. A
    script that cannot start or does not finish returns `(1, <reason>)`.
    """
    command = [sys.executable, str(script), "--format", "json", *args]
    try:
        result = subprocess.run(
            command, capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return 1, f"could not run sync_skills: {exc}"
    return result.returncode, result.stdout or result.stderr


def read_skill_sync_report(output):
    """Read the JSON report of `sync_skills.py --format json`.

    Returns `{"counts", "messages", "problems"}`. `counts` holds the
    `registered`, `cleaned`, `reset` and `blocked` totals the report carries,
    `messages` its warnings, errors and notes as `{"severity", "message", "path"}`,
    and `problems` says, in words, what the report lacked: output that is not
    JSON, or a count that is missing. Nothing here raises.
    """
    report = {"counts": {}, "messages": [], "problems": []}
    try:
        data = json.loads(output)
    except (TypeError, ValueError):
        report["problems"].append("sync_skills printed no JSON report")
        return report
    if not isinstance(data, dict):
        report["problems"].append("sync_skills printed a JSON report that is not an object")
        return report
    summary = data.get("summary")
    summary = summary if isinstance(summary, dict) else {}
    for key in SKILL_SYNC_COUNTS:
        value = summary.get(key)
        if isinstance(value, int) and not isinstance(value, bool):
            report["counts"][key] = value
        else:
            report["problems"].append(f"the sync_skills report has no '{key}' count")
    messages = data.get("messages")
    for message in messages if isinstance(messages, list) else []:
        if isinstance(message, dict) and isinstance(message.get("message"), str):
            report["messages"].append({
                "severity": str(message.get("severity") or "info"),
                "message": message["message"],
                "path": message.get("path"),
            })
    return report


def sync_skills(log):
    """Run the skill registration script and report what it did."""
    log.info("Syncing Grimoire skills...")
    register_script = skill_sync_script()
    command = grimoire_command("sync_skills")

    if register_script is None:
        log.err(f"sync_skills.py not found at {FRAMEWORK_DIR / 'rites'} or {RITE_DIR}")
        log.err(f"Skills NOT synced. Re-run after the framework lands: {command}")
        return False

    rc, output = run_sync_skills(register_script, "--agent", "all")
    report = read_skill_sync_report(output)
    for message in report["messages"]:
        {"error": log.err, "warning": log.warn}.get(message["severity"], log.info)(message["message"])

    if rc != 0:
        log.err(f"Skill sync FAILED (exit {rc}).")
        for problem in report["problems"]:
            log.err(problem)
        if report["problems"] and output.strip():
            log.line(output.strip()[-500:])
        log.err(f"Re-run manually with: {command}")
        return False

    counts = report["counts"]
    if counts:
        log.info(
            "sync_skills: " + ", ".join(f"{counts[key]} {key}" for key in SKILL_SYNC_COUNTS if key in counts)
        )
    targets = installed_skill_targets(REPO_ROOT).values()
    per_target = []
    total = 0
    for config in targets:
        count = _registered_skill_count(config["path"])
        per_target.append(f"{count} to {config['path']}")
        total += count
    log.ok(f"Skills registered: {', '.join(per_target)}")
    if total == 0:
        expected = ", ".join(str(config["path"]) for config in installed_skill_targets(REPO_ROOT).values())
        log.warn(
            "No framework-managed skills landed in any registered agent directory - "
            "this usually means no supported local agent is set up on this machine."
        )
        log.warn(f"Expected skill target(s): {expected}")
        log.warn(f"Re-run after installing your agent of choice: {command}")
    return True


# ---------------------------------------------------------------------------
# Shared install pipeline
# ---------------------------------------------------------------------------


def finalize_install(installed_keys, library, log):
    """Run the post-framework install steps: library, agent blocks, skills.

    Returns True when the library update and the skill registration both succeeded.
    """
    library_ok = update_local_library(installed_keys, library, log) if installed_keys else True
    inject_agent_configs(log)
    skills_ok = sync_skills(log)
    return bool(library_ok and skills_ok)


# ---------------------------------------------------------------------------
# CLI mode
# ---------------------------------------------------------------------------


def _prompt_text(prompt, default=""):
    """Read an interactive prompt from stdin or the controlling terminal."""
    try:
        if sys.stdin.isatty():
            return input(prompt)
        try:
            with open("/dev/tty", "r", encoding="utf-8") as tty_in, \
                    open("/dev/tty", "w", encoding="utf-8") as tty_out:
                tty_out.write(prompt)
                tty_out.flush()
                line = tty_in.readline()
                if line == "":
                    raise EOFError
                return line.rstrip("\n")
        except OSError:
            if default is not None:
                return default
            raise EOFError
    except EOFError:
        if default is not None:
            return default
        raise


def _prompt_cli_mode(scope_preselected):
    if scope_preselected:
        return "clone"
    print()
    print("  What would you like to do?")
    print()
    print("    1) Install the framework               (sets up the framework; build grimoires from scratch)")
    print("    2) Install the framework + clone grimoires  (also pulls existing grimoires from a git host)")
    print()
    while True:
        choice = _prompt_text("  Choice [1]: ", default="1").strip() or "1"
        if choice == "1":
            return "framework_only"
        if choice == "2":
            return "clone"
        print(f"  Invalid choice: {choice!r}. Enter 1 or 2.")


def _cli_select_grimoires(library, log):
    print()
    print("  Available Grimoires:")
    print("  --------------------")
    keys = sorted(library["grimoires"].keys())
    for i, key in enumerate(keys, 1):
        entry = library["grimoires"][key]
        name = entry.get("name", key)
        desc = entry.get("description", "")
        print(f"    {i}) {name:<20s} - {desc}")
    print()
    print("    a) Install ALL grimoires")
    print()
    selection = _prompt_text(
        "  Select grimoires to install (e.g. 1 3 or a for all): ",
        default="",
    ).strip()
    if selection.lower() in ("a", "all"):
        return keys
    selected_keys = []
    for part in selection.split():
        try:
            idx = int(part) - 1
            if 0 <= idx < len(keys):
                selected_keys.append(keys[idx])
            else:
                log.warn(f"Invalid selection: {part} (skipping)")
        except ValueError:
            log.warn(f"Invalid selection: {part} (skipping)")
    return selected_keys


def _print_cli_summary(mode, installed_keys, skills_ok):
    print()
    print("============================================")
    if skills_ok:
        print("  Grimoire Summoning Complete")
    else:
        print("  Grimoire Summoning Complete (with warnings)")
    print("============================================")
    print()
    print("  Framework: ~/.grimoire/")
    print()
    if mode == "framework_only":
        print("  Grimoires: none cloned - framework only.")
        print("  To create your first grimoire, open an agent session and run: /grm-create")
    elif installed_keys:
        print("  Installed grimoires:")
        for key in installed_keys:
            print(f"   - ~/grimoires/{key}/")
    else:
        print("  Grimoires: none landed (clone failures - see log above).")
    print()
    print(f"  Local library: {LOCAL_LIBRARY}")
    instruction_targets = installed_instruction_targets(REPO_ROOT)
    print("  Agent instruction files:")
    for target in instruction_targets:
        print(f"   - {target['label']}: {target['path']}")
    print("  Skill directories:")
    for config in installed_skill_targets(REPO_ROOT).values():
        print(f"   - {config['label']}: {config['path']}")
    print()
    if not skills_ok:
        print("  *** The library update or the skill registration failed - see errors above. Re-run: ***")
        print(f"      {grimoire_command('summon', '--reconcile', '--apply')}")
        print()
    print("  Next steps:")
    agent_labels = ", ".join(target["label"] for target in instruction_targets)
    print(f"    1. Open a new {agent_labels} session")
    print("    2. Try: /grm-setup  (joins an existing grimoire, or starts your first one)")
    print()


def _discover_and_select(scope_url, log):
    """Ask for a scope when none was given, discover its grimoires and let the user pick.

    Returns `(library, selected_keys)`; both are empty when nothing was found or chosen.
    """
    print()
    log.info("Discovering grimoires...")

    if not scope_url:
        print()
        print("  Where are your grimoires hosted?")
        print("  Enter the URL of the group or org containing your grimoires.")
        print("  Press Enter to skip grimoire cloning and install the framework only.")
        print()
        print("  Examples:")
        print("    https://github.com/my-org")
        print("    https://gitlab.company.com/my-group")
        print("    https://gitlab.com/company/grimoires")
        print()
        scope_url = _prompt_text("  Grimoire location: ", default="").strip()

    library = {"grimoires": {}}
    if scope_url:
        library["grimoires"].update(discover_grimoires(scope_url, log))
    else:
        log.info("Skipping discovery (no scope URL provided)")

    if not library["grimoires"]:
        log.warn("No grimoires available to clone. Continuing with framework-only install.")
        return library, []
    log.ok(f"Library loaded ({len(library['grimoires'])} grimoire(s) available)")
    selected_keys = _cli_select_grimoires(library, log)
    if not selected_keys:
        log.warn("No grimoires selected. Continuing with framework-only install.")
    return library, selected_keys


def run_cli(args):
    """Terminal-based interactive summoning flow."""
    log = Logger()
    print()
    print("============================================")
    print("  Grimoire Summoning Rite")
    print("============================================")

    if not check_git(log):
        sys.exit(1)

    GRIMOIRES_HOME.mkdir(parents=True, exist_ok=True)
    log.ok(f"Grimoire home: {GRIMOIRES_HOME}")

    scope_url = args.scope or os.environ.get("GRIMOIRE_SCOPE", "")
    mode = _prompt_cli_mode(scope_preselected=bool(scope_url))

    print()
    framework_url = resolve_framework_url(args)
    if not install_framework(framework_url, log):
        sys.exit(1)
    use_framework_modules()

    outcomes = {}
    library = {"grimoires": {}}

    if mode == "clone":
        library, selected_keys = _discover_and_select(scope_url, log)
        if selected_keys:
            print()
            log.ok(f"Selected {len(selected_keys)} grimoire(s)")
            print()
            log.info("Installing grimoires...")
            print()
            for key in selected_keys:
                outcome = install_grimoire(key, library["grimoires"][key], log)
                if outcome:
                    outcomes[key] = outcome
            if not outcomes:
                log.warn("No grimoires were cloned successfully - continuing with framework-only install.")

    installed_keys = list(outcomes)
    print()
    skills_ok = finalize_install(installed_keys, library, log)
    _print_cli_summary(mode, installed_keys, skills_ok)

    try:
        from summon_state import record_install_transcript
        record_install_transcript(
            GRIMOIRES_HOME, FRAMEWORK_DIR, installed_keys, skills_ok,
            actions={key: "clone" if outcome == CLONED else "pull" for key, outcome in outcomes.items()
                     if outcome in (CLONED, PULLED)},
        )
    except Exception as exc:
        log.warn(f"Install transcript not written: {exc}")
