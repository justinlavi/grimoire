"""Tests for the shared mutating-rite outcome envelope."""

import json

from diagnostics import ResultReporter


def test_status_defaults_from_content():
    assert ResultReporter("x").status() == "noop"
    assert ResultReporter("x").exit_code() == 0

    wrote = ResultReporter("x")
    wrote.mutation("write", path="a")
    assert wrote.status() == "ok"
    assert wrote.exit_code() == 0

    failed = ResultReporter("x")
    failed.message("error", "boom")
    assert failed.status() == "error"
    assert failed.exit_code() == 1


def test_explicit_status_overrides():
    blocked = ResultReporter("x")
    blocked.set_status("blocked")
    assert blocked.status() == "blocked"
    assert blocked.exit_code() == 1


def test_json_envelope_shape(capsys):
    reporter = ResultReporter("sample_rite", mode="apply")
    reporter.mutation("write", path="chapters/page.md", detail="1 page")
    reporter.emit("json", summary={"pages": 1})

    out = json.loads(capsys.readouterr().out)
    assert out["rite"] == "sample_rite"
    assert out["mode"] == "apply"
    assert out["status"] == "ok"
    assert out["summary"] == {"pages": 1}
    assert out["mutations"][0] == {"action": "write", "path": "chapters/page.md", "detail": "1 page"}


def test_jsonl_emits_one_object_per_line_plus_summary(capsys):
    reporter = ResultReporter("sample_rite", mode="apply")
    reporter.mutation("remove", path="chapters/old_page.md")
    reporter.emit("jsonl", summary={"removed": 3})

    lines = [json.loads(line) for line in capsys.readouterr().out.splitlines() if line.strip()]
    assert lines[0]["type"] == "mutation"
    assert lines[-1] == {"type": "summary", "rite": "sample_rite", "status": "ok", "mode": "apply", "removed": 3}


def test_unknown_format_raises(capsys):
    reporter = ResultReporter("x")
    try:
        reporter.emit("human")
    except ValueError:
        return
    raise AssertionError("expected ValueError for human format")
