"""Adapter coverage test: every role returned by `pp roles` must have a
corresponding <plugins/claude/agents/{name}.md> file in the bundle.

This catches the case where core adds a new role without the Claude
adapter shipping an agent file for it.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.parent
PLUGIN_AGENTS = REPO_ROOT / "plugins" / "claude" / "agents"
WRAPPER = REPO_ROOT / "plugins" / "claude" / "scripts" / "pp"


def test_every_role_has_agent_file(tmp_path: Path) -> None:
    workspace = tmp_path / "principia"
    workspace.mkdir()
    env = {**os.environ, "PRINCIPIA_ROOT": str(workspace)}

    result = subprocess.run(
        [str(WRAPPER), "roles", "--json"],
        env=env,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr

    payload = json.loads(result.stdout)
    roles = payload["data"]
    role_names = {r["name"] for r in roles}

    agent_files = {p.stem for p in PLUGIN_AGENTS.glob("*.md")}

    missing = role_names - agent_files
    assert not missing, (
        f"core declares roles with no Claude agent file: {missing}. "
        f"Add plugins/claude/agents/<name>.md for each missing role."
    )
