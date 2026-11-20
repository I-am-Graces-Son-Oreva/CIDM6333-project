import json
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
EXPECTED_GATE_PERMISSIONS = {
    "*": "deny",
    "git status *": "allow",
    "git diff *": "allow",
    "pwd": "allow",
    "uv sync": "allow",
    "uv lock": "allow",
    "uv run fifth-pick health": "allow",
    "uv run ruff check": "allow",
    "uv run ruff format --check": "allow",
    "uv run ty check": "allow",
    "uv run python -m unittest discover -s tests": "allow",
}


def read_frontmatter_permissions(relative_path: str) -> dict[str, str]:
    text = (REPO_ROOT / relative_path).read_text(encoding="utf-8")
    parts = text.split("---", 2)

    if len(parts) < 3:
        raise AssertionError(f"{relative_path} has no frontmatter")

    permissions: dict[str, str] = {}
    in_permissions = False

    for line in parts[1].splitlines():
        stripped = line.strip()

        if stripped == "permission:":
            in_permissions = True
            continue

        if not in_permissions:
            continue

        if line.startswith("  ") and ":" in stripped:
            key, value = stripped.split(":", 1)
            permissions[key.strip()] = value.strip()
            continue

        if line and not line[0].isspace():
            break

    return permissions


class ControlPlaneTests(unittest.TestCase):
    def test_control_plane_roles_exist(self) -> None:
        for role in ("planner", "builder", "reviewer"):
            self.assertTrue(
                (REPO_ROOT / f".opencode/agents/fifth-pick-{role}.md").is_file(),
                role,
            )

    def test_reviewer_role_denies_edit_write_bash_and_task(self) -> None:
        permissions = read_frontmatter_permissions(".opencode/agents/fifth-pick-reviewer.md")

        self.assertEqual(permissions.get("edit"), "deny")
        self.assertEqual(permissions.get("bash"), "deny")
        self.assertEqual(permissions.get("task"), "deny")
        self.assertEqual(permissions.get("grad-triage-e4_write_triage_note"), "deny")

    def test_planner_role_is_read_only(self) -> None:
        permissions = read_frontmatter_permissions(".opencode/agents/fifth-pick-planner.md")

        self.assertEqual(permissions.get("edit"), "deny")
        self.assertEqual(permissions.get("bash"), "deny")
        self.assertEqual(permissions.get("task"), "deny")
        self.assertEqual(permissions.get("grad-triage-e4_write_triage_note"), "deny")

    def test_builder_denies_mcp_write(self) -> None:
        permissions = read_frontmatter_permissions(".opencode/agents/fifth-pick-builder.md")

        self.assertEqual(permissions.get("grad-triage-e4_write_triage_note"), "deny")

    def test_reviewer_role_declares_pass_fail_concerns(self) -> None:
        text = (REPO_ROOT / ".opencode/agents/fifth-pick-reviewer.md").read_text(encoding="utf-8")

        for verdict in ("PASS", "FAIL", "CONCERNS"):
            self.assertIn(verdict, text)

        self.assertIn("CONCERNS never defaults to PASS", text)

    def test_gate_permission_scope_is_narrow(self) -> None:
        config = json.loads((REPO_ROOT / "opencode.json").read_text(encoding="utf-8"))

        self.assertEqual(config["permission"]["bash"], EXPECTED_GATE_PERMISSIONS)

    def test_gate_and_permission_docs_exist(self) -> None:
        self.assertTrue((REPO_ROOT / "final-project/docs/fifth-pick/gates.md").is_file())
        self.assertTrue((REPO_ROOT / "final-project/docs/fifth-pick/harness.md").is_file())

    def test_var_fifth_pick_is_gitignored(self) -> None:
        ignored = (REPO_ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()

        self.assertIn("var/fifth-pick/", ignored)
