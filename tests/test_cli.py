"""Tests for the command-line entry point."""

import subprocess
import sys


def test_usage_names_the_command_when_run_as_a_module() -> None:
    """The container runs `python -m news_collector.cli`; help must still say news-collector."""
    out = subprocess.run(
        [sys.executable, "-m", "news_collector.cli", "--help"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    assert out.startswith("usage: news-collector ")
