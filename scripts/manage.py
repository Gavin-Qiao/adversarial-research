#!/usr/bin/env python3
"""
Principia — design management system for algorithm design from first principles.

User-facing commands:
    scaffold <level> <name> Create claim structure (legacy: cycle/unit/sub-unit)
    status                  Auto-generate PROGRESS.md
    validate                Check referential integrity
    query <sql>             Query the evidence database
    list [--type] [--status] Browse claims and evidence
    results                 Generate RESULTS.md summary
    cascade <id>            Preview impact of disproving a claim
    settle <id>             Mark a claim as proven
    falsify <id> [--by id]  Mark a claim as disproven and cascade

Internal commands (used by skills and agents):
    build, new, next, context, prompt, waves, investigate-next,
    parse-framework, register, artifacts, codebook, post-verdict,
    log-dispatch, dispatch-log, assumptions
"""

from __future__ import annotations

import argparse
import textwrap
from pathlib import Path

from commands import (
    cmd_artifacts,
    cmd_autonomy_config,
    cmd_build,
    cmd_cascade,
    cmd_context,
    cmd_dashboard,
    cmd_dispatch_log,
    cmd_extend_debate,
    cmd_falsify,
    cmd_investigate_next,
    cmd_list,
    cmd_log_dispatch,
    cmd_new,
    cmd_next,
    cmd_parse_framework,
    cmd_post_verdict,
    cmd_prompt,
    cmd_query,
    cmd_register,
    cmd_reopen,
    cmd_replace_verdict,
    cmd_scaffold,
    cmd_settle,
    cmd_waves,
)
from frontmatter import (
    _FM_RE as _FM_RE,
)
from frontmatter import (
    _parse_yaml_value as _parse_yaml_value,
)
from frontmatter import (
    _yaml_val as _yaml_val,
)
from frontmatter import (
    extract_title as extract_title,
)
from reports import cmd_assumptions, cmd_codebook, cmd_results, cmd_status
from validation import cmd_validate, cmd_validate_paste

import config as _cfg
from config import init_paths

# Re-export path globals from config so tests can do `from manage import DB_PATH` etc.
# These are live aliases: callers that import them by name get the current config value.
_PATH_GLOBALS = frozenset({"RESEARCH_DIR", "DB_PATH", "CONTEXT_DIR", "PROGRESS_PATH", "FOUNDATIONS_PATH"})


def __getattr__(name: str) -> object:
    if name in _PATH_GLOBALS:
        return getattr(_cfg, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Principia design management system",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""\
            Examples:
              python manage.py --root design scaffold claim enrichment
              python manage.py --root design validate
              python manage.py --root design status
              python manage.py --root design results
              python manage.py --root design query "SELECT id, status FROM nodes WHERE type='claim'"
        """),
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path("design"),
        help="Path to design root directory (default: design/)",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # new
    p_new = sub.add_parser("new", help="Create a new markdown file with auto-generated frontmatter")
    p_new.add_argument("path", help="Relative path from research root (e.g. cycles/cycle-1/...)")
    p_new.set_defaults(func=cmd_new)

    # build
    p_build = sub.add_parser("build", help="Rebuild SQLite DB from all markdown files")
    p_build.set_defaults(func=cmd_build)

    # validate
    p_val = sub.add_parser("validate", help="Check referential integrity and required fields")
    p_val.add_argument("--json", action="store_true", help="Output as JSON")
    p_val.set_defaults(func=cmd_validate)

    # falsify
    p_fals = sub.add_parser("falsify", help="Mark a node as falsified and cascade")
    p_fals.add_argument("id", help="Node ID to falsify")
    p_fals.add_argument("--by", help="Evidence ID that falsified it", default=None)
    p_fals.add_argument("--dry-run", action="store_true", help="Preview without making changes")
    p_fals.add_argument("--force", action="store_true", help="Skip confirmation prompt")
    p_fals.set_defaults(func=cmd_falsify)

    # settle
    p_settle = sub.add_parser("settle", help="Mark a node as settled")
    p_settle.add_argument("id", help="Node ID to settle")
    p_settle.set_defaults(func=cmd_settle)

    # reopen
    p_reopen = sub.add_parser("reopen", help="Delete verdict and reset claim to active for re-evaluation")
    p_reopen.add_argument("id", help="Node ID to reopen")
    p_reopen.set_defaults(func=cmd_reopen)

    # replace-verdict
    p_rv = sub.add_parser("replace-verdict", help="Delete verdict and reset claim to pre-verdict state")
    p_rv.add_argument("path", help="Claim path")
    p_rv.set_defaults(func=cmd_replace_verdict)

    # status
    p_stat = sub.add_parser("status", help="Auto-generate PROGRESS.md from the DB")
    p_stat.set_defaults(func=cmd_status)

    # dashboard
    p_dash = sub.add_parser("dashboard", help="Control panel: phase, claims, verdicts, blockers")
    p_dash.set_defaults(func=cmd_dashboard)

    # assumptions
    p_assu = sub.add_parser("assumptions", help="Auto-generate FOUNDATIONS.md")
    p_assu.set_defaults(func=cmd_assumptions)

    # query
    p_query = sub.add_parser("query", help="Run arbitrary SQL against the DB")
    p_query.add_argument("sql", help="SQL query to execute")
    p_query.add_argument("--json", action="store_true", help="Output as JSON")
    p_query.set_defaults(func=cmd_query)

    # list
    p_list = sub.add_parser("list", help="List nodes with optional filters")
    p_list.add_argument("--type", default=None, help="Filter by node type (claim, assumption, evidence, ...)")
    p_list.add_argument("--status", default=None, help="Filter by status (pending, active, settled, falsified, ...)")
    p_list.add_argument("--json", action="store_true", help="Output as JSON")
    p_list.set_defaults(func=cmd_list)

    # impact (was cascade)
    p_casc = sub.add_parser("cascade", help="Preview: what breaks if this claim is disproven?")
    p_casc.add_argument("id", help="Node ID to analyze")
    p_casc.set_defaults(func=cmd_cascade)

    # scaffold
    p_scaffold = sub.add_parser("scaffold", help="Create directory structure")
    p_scaffold.add_argument("level", choices=["claim"], help="What to scaffold")
    p_scaffold.add_argument("name", help="Slug name (e.g., enrichment, bottleneck)")
    p_scaffold.add_argument("--falsification", default=None, help="Pre-registered falsification criterion")
    p_scaffold.add_argument(
        "--maturity",
        default=None,
        choices=["theorem-backed", "supported", "conjecture", "experiment"],
    )
    p_scaffold.add_argument("--confidence", default=None, choices=["high", "moderate", "low"])
    p_scaffold.add_argument("--statement", default=None, help="Claim statement text")
    p_scaffold.set_defaults(func=cmd_scaffold)

    # results — generate RESULTS.md
    p_results = sub.add_parser("results", help="Generate RESULTS.md summary document")
    p_results.set_defaults(func=cmd_results)

    # --- Internal commands (hidden from --help, used by skills/agents) ---

    p_reg = sub.add_parser("register")  # register experimenter artifact
    p_reg.add_argument("--id", required=True)
    p_reg.add_argument("--name", required=True)
    p_reg.add_argument("--type", required=True, choices=["function", "class", "script", "dataset"])
    p_reg.add_argument("--path", required=True)
    p_reg.add_argument("--description", default=None)
    p_reg.add_argument("--deps", default=None)
    p_reg.add_argument("--cycle", default=None)
    p_reg.set_defaults(func=cmd_register)

    p_art = sub.add_parser("artifacts")  # list registered artifacts
    p_art.set_defaults(func=cmd_artifacts)

    p_cb = sub.add_parser("codebook")  # generate TOOLKIT.md
    p_cb.set_defaults(func=cmd_codebook)

    p_next = sub.add_parser("next")  # determine next action for a sub-unit
    p_next.add_argument("path", nargs="?", default="auto")
    p_next.set_defaults(func=cmd_next)

    p_ctx = sub.add_parser("context")  # assemble context document
    p_ctx.add_argument("path")
    p_ctx.set_defaults(func=cmd_context)

    p_prompt = sub.add_parser("prompt")  # generate external agent prompt
    p_prompt.add_argument("path")
    p_prompt.set_defaults(func=cmd_prompt)

    p_waves = sub.add_parser("waves")  # show execution waves
    p_waves.add_argument("--json", action="store_true")
    p_waves.set_defaults(func=cmd_waves)

    p_logd = sub.add_parser("log-dispatch")  # log a dispatch event
    p_logd.add_argument("--cycle", required=True)
    p_logd.add_argument("--agent", required=True)
    p_logd.add_argument("--action", required=True, choices=["dispatch", "side_dispatch", "override"])
    p_logd.add_argument("--round", type=int, default=None)
    p_logd.add_argument("--details", default=None)
    p_logd.set_defaults(func=cmd_log_dispatch)

    p_dlog = sub.add_parser("dispatch-log")  # show dispatch audit trail
    p_dlog.add_argument("--cycle", default=None)
    p_dlog.add_argument("--json", action="store_true")
    p_dlog.set_defaults(func=cmd_dispatch_log)

    p_inv = sub.add_parser("investigate-next")  # investigation state machine
    p_inv.add_argument("--quick", action="store_true")
    p_inv.set_defaults(func=cmd_investigate_next)

    p_pf = sub.add_parser("parse-framework")  # parse claim registry from blueprint
    p_pf.set_defaults(func=cmd_parse_framework)

    p_pv = sub.add_parser("post-verdict")  # automated post-verdict bookkeeping
    p_pv.add_argument("path")
    p_pv.set_defaults(func=cmd_post_verdict)

    p_vp = sub.add_parser("validate-paste")  # validate pasted agent result
    p_vp.add_argument(
        "--agent",
        required=True,
        choices=["architect", "adversary", "experimenter", "arbiter", "scout", "synthesizer", "deep-thinker"],
    )
    p_vp.add_argument("--file", required=True, help="Path to file containing pasted result")
    p_vp.set_defaults(func=cmd_validate_paste)

    p_ac = sub.add_parser("autonomy-config")  # output autonomy settings as JSON
    p_ac.set_defaults(func=cmd_autonomy_config)

    p_ed = sub.add_parser("extend-debate")  # conductor extends debate rounds for a claim
    p_ed.add_argument("path", help="Claim path")
    p_ed.add_argument("--to", type=int, required=True, help="New max rounds")
    p_ed.set_defaults(func=cmd_extend_debate)

    args = parser.parse_args()
    init_paths(args.root)
    args.func(args)


if __name__ == "__main__":
    main()
