#!/usr/bin/env python3
import argparse
import json
import sys
from pathlib import Path

from context_lens.analyzers import (
    analyze_copilot_transcript,
    analyze_terminal,
    analyze_transcript,
)
from context_lens.patterns import get_registry
from context_lens.diagnostics import print_token_diagnostics
from context_lens.report import print_report
from context_lens.scanner import find_all_sessions


def _session_id_short(path: Path) -> str:
    stem = path.stem
    if len(stem) > 8:
        return stem[:8]
    return stem


def _analyze_session(entry: dict, registry) -> dict:
    path: Path = entry["path"]
    session_type = entry["type"]

    if session_type == "transcript":
        if entry.get("tool") == "copilot":
            analysis = analyze_copilot_transcript(path)
        else:
            analysis = analyze_transcript(path)
    else:
        analysis = analyze_terminal(path)

    pattern_results = registry.analyze_session(analysis)
    warnings = [p.message for p in pattern_results]
    pattern_ids = [p.pattern_id for p in pattern_results]

    return {
        **entry,
        "path": str(path),
        "session_id_short": _session_id_short(path),
        "analysis": analysis,
        "warnings": warnings,
        "pattern_ids": pattern_ids,
        "pattern_results": [
            {
                "pattern_id": p.pattern_id,
                "severity": p.severity,
                "message": p.message,
                "metric": p.metric,
            }
            for p in pattern_results
        ],
    }


def _build_summary(tool_results: list[dict], registry) -> dict:
    total_tokens = 0
    transcript_assistant_tokens = 0
    transcript_user_tokens = 0
    terminal_tokens = 0
    agent_tool_tokens = 0
    projects: set[str] = set()
    pattern_counts: dict[str, int] = {}
    waste_tokens = 0

    for pattern in registry.patterns:
        pattern_counts[pattern.name] = 0

    for session in tool_results:
        analysis = session["analysis"]
        session_type = session.get("type", "")
        projects.add(session["project"])

        session_total = analysis.get("total_tokens", 0)
        total_tokens += session_total

        if session_type == "transcript":
            transcript_assistant_tokens += analysis.get("assistant_tokens", 0)
            transcript_user_tokens += analysis.get("user_tokens", 0)
        elif session_type == "terminal":
            terminal_tokens += session_total
        elif session_type == "tools":
            agent_tool_tokens += session_total

        pattern_ids = session.get("pattern_ids", [])
        if "runaway_assistant" in pattern_ids or "file_dump" in pattern_ids:
            waste_tokens += session_total

        for result in session.get("pattern_results", []):
            pattern = registry.pattern_by_id(result["pattern_id"])
            if pattern is not None:
                pattern_counts[pattern.name] = pattern_counts.get(pattern.name, 0) + 1

    ranked = sorted(
        tool_results,
        key=lambda s: s["analysis"].get("total_tokens", 0),
        reverse=True,
    )
    top_sessions = []
    for s in ranked[:5]:
        analysis = s["analysis"]
        warning_str = "; ".join(s["warnings"]) if s["warnings"] else ""
        entry = {
            "project": s["project"],
            "session_id_short": s["session_id_short"],
            "total_tokens": analysis.get("total_tokens", 0),
            "warnings": warning_str,
        }
        if "turns" in analysis:
            entry["turns"] = analysis["turns"]
        top_sessions.append(entry)

    tools_found = sorted({s["tool"] for s in tool_results if s.get("tool")})
    tools_label = ", ".join(tools_found) if tools_found else "none"

    attributed = (
        transcript_assistant_tokens
        + transcript_user_tokens
        + terminal_tokens
        + agent_tool_tokens
    )
    unattributed_tokens = total_tokens - attributed

    return {
        "total_sessions": len(tool_results),
        "num_projects": len(projects),
        "tools_label": tools_label,
        "total_tokens": total_tokens,
        "assistant_tokens": transcript_assistant_tokens,
        "user_tokens": transcript_user_tokens,
        "transcript_assistant_tokens": transcript_assistant_tokens,
        "transcript_user_tokens": transcript_user_tokens,
        "terminal_tokens": terminal_tokens,
        "agent_tool_tokens": agent_tool_tokens,
        "unattributed_tokens": unattributed_tokens,
        "pattern_counts": pattern_counts,
        "top_sessions": top_sessions,
        "waste_tokens": waste_tokens,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Analyze token waste in Cursor, Claude Code, and Copilot Chat sessions"
    )
    parser.add_argument(
        "--detail", action="store_true", help="Show all sessions"
    )
    parser.add_argument(
        "--json", action="store_true", help="Output raw JSON"
    )
    parser.add_argument(
        "--debug-tokens",
        action="store_true",
        help="Print token source breakdown diagnostic and exit",
    )
    args = parser.parse_args()

    if args.debug_tokens:
        print_token_diagnostics()
        return

    try:
        import tiktoken  # noqa: F401
    except ImportError:
        print("tiktoken not installed. Run: pip install tiktoken")
        sys.exit(1)

    registry = get_registry()
    sessions = find_all_sessions()
    tool_results = [_analyze_session(entry, registry) for entry in sessions]
    summary = _build_summary(tool_results, registry)

    results = {
        "tool_results": tool_results,
        "summary": summary,
    }

    if args.json:
        print(json.dumps(results, indent=2))
    else:
        print_report(results, detail=args.detail)


if __name__ == "__main__":
    main()
