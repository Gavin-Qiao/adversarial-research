from __future__ import annotations

from pathlib import Path

import yaml


def test_pre_commit_covers_ci_python_quality_gates() -> None:
    workflow = yaml.safe_load(Path(".github/workflows/ci.yml").read_text(encoding="utf-8"))
    ci_steps = workflow["jobs"]["test"]["steps"]
    ci_commands = {step["run"] for step in ci_steps if "run" in step}

    config = yaml.safe_load(Path(".pre-commit-config.yaml").read_text(encoding="utf-8"))
    assert config["default_install_hook_types"] == ["pre-commit", "pre-push"]

    local_hooks = {hook["entry"]: hook for repo in config["repos"] if repo["repo"] == "local" for hook in repo["hooks"]}

    expected_hooks = {
        "uv run ruff check scripts/ tests/": "pre-commit",
        "uv run ruff format --check scripts/ tests/": "pre-commit",
        "uv run python -m pytest tests/ -q": "pre-push",
        "uv run python -m mypy scripts/": "pre-push",
    }

    for command, stage in expected_hooks.items():
        assert command in ci_commands
        assert command in local_hooks
        assert local_hooks[command]["stages"] == [stage]
        assert local_hooks[command]["pass_filenames"] is False
