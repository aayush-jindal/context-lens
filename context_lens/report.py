def print_report(results: dict, detail: bool = False) -> None:
    """Print a formatted token waste report."""
    tool_results = results.get("tool_results", [])
    summary = results.get("summary", {})

    n_sessions = summary.get("total_sessions", len(tool_results))
    n_projects = summary.get("num_projects", 0)
    tools_label = summary.get("tools_label", "cursor")

    total = summary.get("total_tokens", 0)
    assistant = summary.get(
        "transcript_assistant_tokens", summary.get("assistant_tokens", 0)
    )
    user = summary.get("transcript_user_tokens", summary.get("user_tokens", 0))
    terminal = summary.get("terminal_tokens", 0)
    agent_tools = summary.get("agent_tool_tokens", 0)
    unattributed = summary.get("unattributed_tokens", 0)

    def pct(n: int) -> str:
        p = (n / total * 100) if total else 0.0
        return f"({p:4.1f}%)"

    pattern_counts: dict[str, int] = summary.get("pattern_counts", {})

    print("=== CONTEXT LENS REPORT ===")
    print(f"Scanned: {n_sessions} sessions across {n_projects} projects ({tools_label})")
    print()
    print("TOTAL TOKEN USAGE")
    print(f"  Total tokens:              {total:>10,}  (100%)")
    print(f"  ├─ Transcript (assistant): {assistant:>10,}  {pct(assistant)}")
    print(f"  ├─ Transcript (user):      {user:>10,}  {pct(user)}")
    print(f"  ├─ Terminal output:        {terminal:>10,}  {pct(terminal)}")
    print(f"  ├─ Agent tool output:      {agent_tools:>10,}  {pct(agent_tools)}")
    print(f"  └─ Unattributed:           {unattributed:>10,}  {pct(unattributed)}")

    assert abs((assistant + user + terminal + agent_tools) - total) < 10, (
        f"Bucketing error: parts sum to {assistant + user + terminal + agent_tools}, "
        f"total is {total}"
    )
    print()
    print("WASTE PATTERNS DETECTED")

    any_patterns = False
    for pattern_name, count in sorted(pattern_counts.items()):
        if count > 0:
            any_patterns = True
            print(f"  {pattern_name}: {count} sessions")

    if not any_patterns:
        print("  (none detected)")

    print()
    print("TOP 5 MOST EXPENSIVE SESSIONS")
    top_sessions = summary.get("top_sessions", [])
    for rank, session in enumerate(top_sessions[:5], start=1):
        project = session.get("project", "unknown")
        session_id = session.get("session_id_short", "?")
        tokens = session.get("total_tokens", 0)
        turns = session.get("turns", "-")
        warnings = session.get("warnings", "")
        if turns == "-":
            print(
                f"  {rank}. {project} / {session_id}   {tokens:,} tokens   {warnings}"
            )
        else:
            print(
                f"  {rank}. {project} / {session_id}   {tokens:,} tokens   "
                f"{turns} turns   {warnings}"
            )

    waste_tokens = summary.get("waste_tokens", 0)
    n = n_sessions or 1
    session_totals = [
        s.get("analysis", {}).get("total_tokens", 0) for s in tool_results
    ]
    avg_tokens = total / n if n else 0
    worst_tokens = max(session_totals) if session_totals else 0
    worst_multiple = round(worst_tokens / avg_tokens, 1) if avg_tokens else 0.0
    multi_warn = sum(1 for s in tool_results if len(s.get("warnings", [])) >= 2)
    multi_warn_pct = multi_warn / n * 100 if n else 0.0

    def _cost(tokens: int, rate_per_million: float) -> float:
        return tokens * rate_per_million / 1_000_000

    models = [
        ("Claude Sonnet", 3.00),
        ("Claude Opus / GPT-4", 15.00),
        ("GPT-4o", 5.00),
    ]
    team_size = 10

    print()
    print("─" * 66)
    print(
        f"Avg tokens/session: {avg_tokens:,.0f}  |  "
        f"Worst session: {worst_tokens:,} ({worst_multiple}x avg)"
    )
    print(
        f"Sessions with 2+ warnings: {multi_warn} "
        f"({multi_warn_pct:.1f}% of sessions)"
    )
    print()
    print("ESTIMATED COST IMPACT (this machine)")
    print(
        f"  {'Model':<22} {'$/1M tokens':>14}  "
        f"{'Total cost':>12}  {'High-waste cost':>16}"
    )
    print("  " + "─" * 68)
    for name, rate in models:
        total_cost = _cost(total, rate)
        waste_cost = _cost(waste_tokens, rate)
        print(
            f"  {name:<22} ${rate:>6.2f}        "
            f"${total_cost:>6.2f}         ${waste_cost:>6.2f}"
        )
    print()
    print(
        f"  Extrapolated to a {team_size}-engineer team "
        f"(assuming similar usage):"
    )
    for name, rate in models:
        team_cost = _cost(total, rate) * team_size
        print(f"  {name:<22} ${team_cost:>6.2f}/month")
    print()
    print(
        '  "High-waste" = sessions flagged Runaway Assistant '
        "or Probable File Dump"
    )

    if detail:
        print()
        print("=== PER-SESSION DETAIL ===")
        for session in sorted(
            tool_results,
            key=lambda s: s.get("analysis", {}).get("total_tokens", 0),
            reverse=True,
        ):
            project = session.get("project", "unknown")
            session_id = session.get("session_id_short", "?")
            stype = session.get("type", "")
            tool = session.get("tool", "")
            analysis = session.get("analysis", {})
            tokens = analysis.get("total_tokens", 0)
            turns = analysis.get("turns")
            warnings = "; ".join(session.get("warnings", [])) or "(none)"
            path = session.get("path", "")
            if turns is not None:
                print(
                    f"  [{tool}/{stype}] {project} / {session_id}: "
                    f"{tokens:,} tokens, {turns} turns — {warnings}"
                )
            else:
                print(
                    f"  [{tool}/{stype}] {project} / {session_id}: "
                    f"{tokens:,} tokens — {warnings}"
                )
            print(f"    {path}")
