# context-lens

Analyze token usage and waste patterns in your local AI coding sessions — Cursor, Claude Code, and GitHub Copilot Chat.

Everything runs on your machine. Transcripts are read-only; nothing is uploaded or modified.

## Why use this?

Agent sessions can burn through context quickly: long assistant replies, pasted file dumps, terminal output, and multi-turn chats where early messages keep getting re-sent. **context-lens** scans your local session files, estimates token counts, and flags sessions that look expensive or low-signal so you can see where context is going.

## Supported tools

| Tool | What gets scanned |
|------|-------------------|
| **Cursor** | `~/.cursor/projects/*/agent-transcripts/*.jsonl`, terminal logs, agent tool output |
| **Claude Code** | `~/.claude/projects/*.jsonl` |
| **GitHub Copilot Chat** | VS Code `workspaceStorage` chat sessions (local, Insiders, remote/SSH paths) |

## Install

Requires Python 3.9+.

```bash
cd context-lens

python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e .
```

## Usage

Run from any directory — it discovers sessions automatically:

```bash
context-lens
```

Or invoke the module directly:

```bash
python analyze.py
```

### Options

| Flag | Description |
|------|-------------|
| `--detail` | List every session, not just the top offenders |
| `--json` | Emit full analysis as JSON (for scripting or dashboards) |
| `--debug-tokens` | Print a diagnostic breakdown of token sources and exit |

Examples:

```bash
context-lens --detail
context-lens --json > report.json
context-lens --debug-tokens
```

## What it detects

Heuristic patterns applied per session:

| Pattern | What it means |
|---------|----------------|
| **Runaway assistant output** | Assistant tokens far exceed user input (ratio > 5:1) |
| **Probable file dump** | A single assistant turn exceeds ~3k tokens (often pasted source) |
| **Context accumulation risk** | Long chats (40+ turns) where early context keeps compounding |
| **Low signal user turns** | Very short user messages driving large agent spend |
| **Large terminal output** | Terminal or tool log files with high token counts |
| **Short session high cost** | Few turns but very high total usage |

The report also breaks down total tokens by source: transcript (user vs assistant), terminal output, agent tools, and unattributed remainder.

## How token counts work

- Estimates use OpenAI’s `cl100k_base` encoding via [tiktoken](https://github.com/openai/tiktoken).
- Counts are **approximate** — useful for comparison and spotting outliers, not for billing.
- Only text found in local session files is counted.

## Privacy

- No network calls during analysis.
- No writes to transcript or config files.
- Data never leaves your machine unless you explicitly share output (e.g. `--json`).

## Project layout

```
analyze.py              # CLI entry point
context_lens/
  scanner.py            # Discovers session files on disk
  analyzers.py          # Parses transcripts and estimates tokens
  patterns.py           # Waste-pattern heuristics
  report.py             # Human-readable report
  diagnostics.py        # Token source debugging
```

## License

MIT — see [LICENSE](LICENSE).
