"""
Backend test helpers for environment-dependent tests.

Tests that require external tools (Tectonic, Ollama) are selected only when those
tools are available — never bypassed, never weakened. Run the same suite locally
where the tools exist; on runners without them they are reported as skipped,
not hidden.
"""
from __future__ import annotations

import shutil
import socket

import pytest


def _tectonic_available() -> bool:
    return shutil.which("tectonic") is not None


def _ollama_available() -> bool:
    try:
        with socket.create_connection(("localhost", 11434), timeout=0.5):
            return True
    except OSError:
        return False


requires_tectonic = pytest.mark.skipif(
    not _tectonic_available(), reason="system Tectonic binary not available"
)

requires_ollama = pytest.mark.skipif(
    not _ollama_available(), reason="local Ollama not reachable on localhost:11434"
)
