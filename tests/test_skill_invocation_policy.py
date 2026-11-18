"""Auto-invocation policy: the evaluation entry points stay model-invocable."""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILLS = REPO_ROOT / "skills"
FLAG = "disable-model-invocation: true"


def test_evaluation_entry_points_are_model_invocable():
    for path in (SKILLS / "dev" / "validate" / "SKILL.md", SKILLS / "grm" / "check" / "SKILL.md"):
        text = path.read_text(encoding="utf-8")
        assert FLAG not in text, f"{path.parent.name} should stay model-invocable"


def test_no_individual_validator_or_audit_skills_exist():
    for family in ("dev", "grm"):
        assert sorted((SKILLS / family).glob("validate-*")) == []
        assert sorted((SKILLS / family).glob("audit-*")) == []
