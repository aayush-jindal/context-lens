"""Token source diagnostics for debugging bucketing mismatches."""

from collections import defaultdict
from pathlib import Path

from context_lens.analyzers import (
    analyze_copilot_transcript,
    analyze_terminal,
    analyze_transcript,
)
from context_lens.scanner import find_all_sessions, get_copilot_candidate_paths


def _analyze_with_errors(path: Path, session_type: str, tool: str) -> tuple[dict | None, str | None]:
    try:
        if session_type == "transcript":
            if tool == "copilot":
                return analyze_copilot_transcript(path), None
            return analyze_transcript(path), None
        return analyze_terminal(path), None
    except Exception as exc:
        return None, str(exc)


def run_token_diagnostics() -> dict:
    """Scan all sessions and return a per-source token breakdown."""
    sessions = find_all_sessions()
    copilot_paths_checked = len(get_copilot_candidate_paths())

    stats = {
        "cursor_transcript": {"files": 0, "user": 0, "assistant": 0, "total": 0, "skipped": 0},
        "claude_transcript": {"files": 0, "user": 0, "assistant": 0, "total": 0, "skipped": 0},
        "copilot_transcript": {
            "files": 0,
            "user": 0,
            "assistant": 0,
            "total": 0,
            "skipped": 0,
            "projects": set(),
        },
        "copilot_by_source": defaultdict(int),
        "terminal": {"files": 0, "tokens": 0, "skipped": 0},
        "agent_tools": {"files": 0, "tokens": 0, "skipped": 0},
        "parse_failures": [],
        "copilot_paths_checked": copilot_paths_checked,
    }

    for entry in sessions:
        path: Path = entry["path"]
        session_type = entry["type"]
        tool = entry["tool"]

        analysis, error = _analyze_with_errors(path, session_type, tool)
        if error is not None:
            stats["parse_failures"].append({"path": str(path), "error": error})
            continue

        if analysis is None:
            continue

        if session_type == "transcript":
            if tool == "cursor":
                key = "cursor_transcript"
            elif tool == "copilot":
                key = "copilot_transcript"
            else:
                key = "claude_transcript"
            bucket = stats[key]
            bucket["files"] += 1
            bucket["user"] += analysis.get("user_tokens", 0)
            bucket["assistant"] += analysis.get("assistant_tokens", 0)
            bucket["total"] += analysis.get("total_tokens", 0)
            if tool == "copilot":
                bucket["projects"].add(entry.get("project", "unknown"))
                source = entry.get("source_base", "unknown")
                stats["copilot_by_source"][source] += 1
        elif session_type == "terminal":
            bucket = stats["terminal"]
            bucket["files"] += 1
            bucket["tokens"] += analysis.get("total_tokens", 0)
        elif session_type == "tools":
            bucket = stats["agent_tools"]
            bucket["files"] += 1
            bucket["tokens"] += analysis.get("total_tokens", 0)

    cursor = stats["cursor_transcript"]
    claude = stats["claude_transcript"]
    copilot = stats["copilot_transcript"]
    terminal = stats["terminal"]
    tools = stats["agent_tools"]

    transcript_user = cursor["user"] + claude["user"] + copilot["user"]
    transcript_assistant = cursor["assistant"] + claude["assistant"] + copilot["assistant"]
    transcript_total = cursor["total"] + claude["total"] + copilot["total"]
    transcript_files = cursor["files"] + claude["files"] + copilot["files"]

    sum_of_sources = (
        transcript_total + terminal["tokens"] + tools["tokens"]
    )
    reported_total = sum_of_sources

    # user+assistant may be less than transcript_total (unknown roles)
    transcript_unattributed = transcript_total - transcript_user - transcript_assistant

    copilot_projects = len(copilot["projects"])

    return {
        **stats,
        "transcript_user": transcript_user,
        "transcript_assistant": transcript_assistant,
        "transcript_total": transcript_total,
        "transcript_files": transcript_files,
        "terminal_tokens": terminal["tokens"],
        "terminal_files": terminal["files"],
        "agent_tool_tokens": tools["tokens"],
        "agent_tool_files": tools["files"],
        "cursor_transcript_files": cursor["files"],
        "claude_transcript_files": claude["files"],
        "claude_transcript_tokens": claude["total"],
        "copilot_transcript_tokens": copilot["total"],
        "copilot_transcript_files": copilot["files"],
        "copilot_transcript_projects": copilot_projects,
        "sum_of_sources": sum_of_sources,
        "reported_total": reported_total,
        "difference": 0,
        "transcript_unattributed_roles": transcript_unattributed,
        "total_sessions_found": len(sessions),
    }


def print_token_diagnostics() -> dict:
    """Print and return the token source breakdown report."""
    d = run_token_diagnostics()
    copilot = d["copilot_transcript"]

    print("TOKEN SOURCE BREAKDOWN")
    print("----------------------")
    print(f"  Transcript user tokens:        {d['transcript_user']:>12,}")
    print(f"  Transcript assistant tokens:   {d['transcript_assistant']:>12,}")
    print(f"  Transcript total:              {d['transcript_total']:>12,}")
    if d["transcript_unattributed_roles"]:
        print(
            f"    (unknown roles in transcripts: {d['transcript_unattributed_roles']:>10,})"
        )
    print()
    print(
        f"  Terminal file tokens:          {d['terminal_tokens']:>12,}  "
        f"({d['terminal_files']} files)"
    )
    print(
        f"  Agent-tool file tokens:        {d['agent_tool_tokens']:>12,}  "
        f"({d['agent_tool_files']} files)"
    )
    print(
        f"  Claude Code transcript tokens: {d['claude_transcript_tokens']:>12,}  "
        f"({d['claude_transcript_files']} files, included in transcript totals above)"
    )
    print(
        f"  Copilot Chat transcripts:      {d['copilot_transcript_tokens']:>12,}  "
        f"({d['copilot_transcript_files']} files, "
        f"{d['copilot_transcript_projects']} projects)"
    )
    for source in sorted(d["copilot_by_source"]):
        print(f"    Source: {source:<22} {d['copilot_by_source'][source]} files")
    print()
    print(f"  Sum of all sources:            {d['sum_of_sources']:>12,}")
    print(f"  Reported total:                {d['reported_total']:>12,}")
    print(f"  Difference:                    {d['difference']:>12,}")
    print()
    print("FILE COUNTS")
    print(f"  Transcript files scanned:      {d['transcript_files']}")
    print(f"    Cursor transcripts:            {d['cursor_transcript_files']}")
    print(f"    Claude Code transcripts:       {d['claude_transcript_files']}")
    print(f"    Copilot Chat transcripts:      {d['copilot_transcript_files']}")
    print(f"  Terminal files scanned:        {d['terminal_files']}")
    print(f"  Agent-tool files scanned:      {d['agent_tool_files']}")
    print(f"  Total sessions found:          {d['total_sessions_found']}")
    print()

    if d["copilot_transcript_files"] > 0:
        print(
            f"Copilot: found {d['copilot_transcript_files']} sessions across "
            f"{d['copilot_transcript_projects']} projects"
        )
    else:
        print(
            f"Copilot: no sessions found (checked {d['copilot_paths_checked']} paths)"
        )
    print()

    missing_user_asst = (
        d["sum_of_sources"] - d["transcript_user"] - d["transcript_assistant"]
    )
    print("BUCKETING DIAGNOSIS")
    print(
        f"  Transcript user + assistant:     "
        f"{d['transcript_user'] + d['transcript_assistant']:>12,}"
    )
    print(
        f"  Gap if only user+asst counted:   {missing_user_asst:>12,}  "
        f"({missing_user_asst / d['sum_of_sources'] * 100:.1f}% of total)"
        if d["sum_of_sources"]
        else ""
    )
    print(f"  Terminal tokens:                 {d['terminal_tokens']:>12,}")
    print(f"  Agent-tool tokens:               {d['agent_tool_tokens']:>12,}")
    print()

    if d["parse_failures"]:
        print("PARSE FAILURES")
        for fail in d["parse_failures"]:
            print(f"  {fail['path']}")
            print(f"    {fail['error']}")
        print()
    else:
        print("PARSE FAILURES: (none)")
        print()

    # Identify root cause
    terminal_plus_tools = d["terminal_tokens"] + d["agent_tool_tokens"]
    causes = []
    if terminal_plus_tools > 0 and missing_user_asst >= terminal_plus_tools:
        causes.append(
            f"(A) Terminal + agent-tool ({terminal_plus_tools:,} tokens) in total "
            "but not broken out as user/assistant"
        )
    transcript_gap = d["transcript_unattributed_roles"]
    if transcript_gap > 100:
        causes.append(
            f"(C) Claude Code / Copilot / unknown transcript roles ({transcript_gap:,} tokens) "
            "— schema may use type= not role= at top level"
        )
    if d["difference"] != 0:
        causes.append("(D) Total computed differently from sum of parts")

    if causes:
        print("ROOT CAUSE:")
        for cause in causes:
            print(f"  {cause}")
    else:
        print("ROOT CAUSE: Bucketing is consistent (no gap detected).")

    return d
