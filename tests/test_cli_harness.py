import subprocess
import pytest
from pathlib import Path

def test_cli_help():
    """Verify that the script provides help information."""
    result = subprocess.run(["python3", "scripts/test_breakpoint_flow.py", "--help"], 
                           capture_output=True, text=True)
    assert result.returncode == 0
    assert "usage:" in result.stdout.lower()
    assert "--until" in result.stdout
    assert "--from" in result.stdout

def test_cli_invalid_bp():
    """Verify that invalid breakpoint IDs are handled."""
    result = subprocess.run(["python3", "scripts/test_breakpoint_flow.py", "--until", "INVALID_BP"], 
                           capture_output=True, text=True)
    assert result.returncode != 0
    assert "invalid choice" in result.stderr.lower()

def test_cli_until_bp3():
    """Verify that the script accepts a valid breakpoint."""
    result = subprocess.run(["python3", "scripts/test_breakpoint_flow.py", "--until", "BP-3"], 
                           capture_output=True, text=True)
    assert result.returncode == 0
    assert "breakpoint set until: bp-3" in result.stdout.lower()
