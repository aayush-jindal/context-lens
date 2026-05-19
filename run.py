#!/usr/bin/env python3
"""Bootstrap context-lens: ensure a local venv with deps, then run analysis."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VENV_DIR = ROOT / ".venv"
MIN_PYTHON = (3, 9)


def _venv_python() -> Path:
    if sys.platform == "win32":
        return VENV_DIR / "Scripts" / "python.exe"
    return VENV_DIR / "bin" / "python"


def _check_python_version() -> None:
    if sys.version_info < MIN_PYTHON:
        major, minor = MIN_PYTHON
        print(
            f"Python {major}.{minor}+ is required (found {sys.version_info.major}.{sys.version_info.minor}).",
            file=sys.stderr,
        )
        sys.exit(1)


def _venv_is_ready() -> bool:
    py = _venv_python()
    if not py.is_file():
        return False
    probe = subprocess.run(
        [str(py), "-c", "import tiktoken; import context_lens"],
        cwd=ROOT,
        capture_output=True,
    )
    return probe.returncode == 0


def _ensure_venv() -> Path:
    py = _venv_python()
    if py.is_file():
        return py
    print("Creating virtual environment in .venv …")
    subprocess.check_call([sys.executable, "-m", "venv", str(VENV_DIR)])
    return _venv_python()


def _install_deps(py: Path) -> None:
    print("Installing dependencies (one-time setup) …")
    subprocess.check_call(
        [
            str(py),
            "-m",
            "pip",
            "install",
            "--disable-pip-version-check",
            "-q",
            "-e",
            str(ROOT),
        ],
        cwd=ROOT,
    )


def _run_analysis(py: Path, args: list[str]) -> int:
    return subprocess.call([str(py), str(ROOT / "analyze.py"), *args], cwd=ROOT)


def main() -> None:
    _check_python_version()
    args = sys.argv[1:]

    if _venv_is_ready():
        py = _venv_python()
    else:
        py = _ensure_venv()
        _install_deps(py)

    sys.exit(_run_analysis(py, args))


if __name__ == "__main__":
    main()
