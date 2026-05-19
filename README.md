# context-lens
Analyze token waste in your Cursor and Claude Code sessions.

## Quick start
```bash
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install tiktoken
python analyze.py
```

Or without activating the venv:

```bash
python3 -m venv .venv
.venv/bin/pip install tiktoken
.venv/bin/python analyze.py
```

## What it detects
- Runaway assistant output (agent running without user direction)
- Probable file dumps (model regurgitating source files into context)
- Context accumulation (long sessions where early turns keep costing tokens)
- Low signal sessions (tiny user inputs driving large agent spend)

## Notes
- All analysis runs locally. Nothing leaves your machine.
- Token counts are estimates using cl100k_base encoding.
- Transcript files are read-only. Nothing is modified.
