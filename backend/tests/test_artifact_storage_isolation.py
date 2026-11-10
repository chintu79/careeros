"""
Resume artifact storage isolation contract (Phase 3.0.8).

Every pytest session runs with CAREEROS_STORAGE_DIR pointed at a unique tmp
directory (see tests/conftest.py). These tests prove the isolation:
- nothing writes to the live default storage directory;
- two concurrent "sessions" never share an artifact root;
- failed compilation and failed promotion leave zero stray files;
- artifacts land where the metadata says they do.

The live directory is only ever *listed* to prove it is untouched.
"""
import os
import subprocess
import sys
import glob

import pytest

from backend.tests.helpers_env import requires_tectonic
from backend.app.services import latex_compiler
from backend.app.services.latex_compiler import (
    compile_and_validate_resume,
    atomic_promote_file,
    PDFPromotionTransaction,
)

DEFAULT_STORAGE_DIR = os.path.abspath(
    os.path.join(os.path.dirname(latex_compiler.__file__), "../../storage/resumes")
)
STORAGE_DIR = latex_compiler.STORAGE_DIR

VALID_LATEX = (
    "\\documentclass{article}\n"
    "\\begin{document}\n"
    "Hello artifact isolation.\n"
    "\\end{document}\n"
)

BROKEN_LATEX = "\\documentclass{article}\\begin{document}\\badcommand{broken"


def test_storage_dir_is_isolated_for_this_session():
    """The compiler must not be bound to the live default directory."""
    assert STORAGE_DIR != DEFAULT_STORAGE_DIR
    assert os.path.isdir(STORAGE_DIR)


def test_default_storage_directory_is_not_written_to():
    """A real compile+promote cycle must leave the live directory untouched. A fresh
    clone may not have a default storage dir at all — that is trivially safe."""
    before = set(os.listdir(DEFAULT_STORAGE_DIR)) if os.path.isdir(DEFAULT_STORAGE_DIR) else None
    ok, pdf_path, compiler_used, validation = compile_and_validate_resume(
        latex_source=VALID_LATEX,
        base_name="test_artifact_isolation_probe",
        strict=True,
    )
    if before is not None:
        after = set(os.listdir(DEFAULT_STORAGE_DIR))
        assert before == after, "live default storage directory was modified"
    if ok:
        assert os.path.dirname(pdf_path) == STORAGE_DIR
        assert os.path.isfile(pdf_path)


def test_two_concurrent_sessions_get_distinct_artifact_roots(tmp_path):
    """Two independent sessions (env boundary) never share an artifact dir."""
    dirs = [str(tmp_path / f"session-{n}") for n in ("a", "b")]
    children = []
    for d in dirs:
        env = dict(os.environ, CAREEROS_STORAGE_DIR=d)
        children.append(
            subprocess.Popen(
                [
                    sys.executable,
                    "-c",
                    "import os\nfrom backend.app.services import latex_compiler as lc\nwith open(os.path.join(lc.STORAGE_DIR, 'marker.txt'), 'w') as fh:\n    fh.write(os.path.basename(lc.STORAGE_DIR))",
                ],
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
        )
    for child in children:
        out, err = child.communicate(timeout=120)
        assert child.returncode == 0, err.decode(errors="replace")
    assert os.path.isfile(os.path.join(dirs[0], "marker.txt"))
    assert os.path.isfile(os.path.join(dirs[1], "marker.txt"))
    assert dirs[0] != dirs[1]


@requires_tectonic
def test_failed_compilation_leaves_no_artifacts():
    ok, err, compiler_used, validation = compile_and_validate_resume(
        latex_source=BROKEN_LATEX,
        base_name="test_artifact_isolation_broken",
        strict=True,
    )
    assert ok is False
    leftovers = [
        f
        for f in os.listdir(STORAGE_DIR)
        if f.startswith("test_artifact_isolation_broken")
    ]
    assert leftovers == [], f"failed compilation leaked artifacts: {leftovers}"


def test_failed_promotion_restores_pre_existing_artifact():
    """Rollback after promotion must restore the original bytes and clean staging files."""
    target = os.path.join(STORAGE_DIR, "test_artifact_isolation_restore.pdf")
    source_ok = os.path.join(STORAGE_DIR, "test_artifact_isolation_restore_original.pdf")
    with open(target, "wb") as fh:
        fh.write(b"original-bytes")
    with open(source_ok, "wb") as fh:
        fh.write(b"promoted-bytes")

    tx = PDFPromotionTransaction(target_pdf_path=target)
    tx.stage_and_promote(source_ok)
    assert os.path.isfile(target)
    with open(target, "rb") as fh:
        assert fh.read() == b"promoted-bytes"

    tx.rollback()
    with open(target, "rb") as fh:
        assert fh.read() == b"original-bytes"
    leftovers = [
        f
        for f in os.listdir(STORAGE_DIR)
        if "test_artifact_isolation_restore" in f and f.split(".")[-1] in ("tmp", "backup")
    ]
    assert leftovers == [], f"rollback left staging files: {leftovers}"


def test_failed_promotion_removes_new_artifact_entirely():
    """Rollback of a brand-new promotion must remove the promoted file — never ship uncommitted artifacts."""
    target = os.path.join(STORAGE_DIR, "test_artifact_isolation_new.pdf")
    source_ok = os.path.join(STORAGE_DIR, "test_artifact_isolation_new_source.pdf")
    assert not os.path.exists(target)
    with open(source_ok, "wb") as fh:
        fh.write(b"new-artifact-bytes")

    tx = PDFPromotionTransaction(target_pdf_path=target)
    tx.stage_and_promote(source_ok)
    assert os.path.isfile(target)

    tx.rollback()
    assert not os.path.exists(target), "uncommitted artifact survived rollback"
    leftovers = [f for f in os.listdir(STORAGE_DIR) if f.startswith(".test_artifact_isolation_new.pdf.")]
    assert leftovers == [], f"rollback left staging files: {leftovers}"


def test_atomic_promote_renames_into_storage_dir(tmp_path):
    """Metadata contract: the artifact path recorded for a resume must live in STORAGE_DIR."""
    source = tmp_path / "promote-src.pdf"
    source.write_bytes(b"promoted")
    target = os.path.join(STORAGE_DIR, "test_artifact_isolation_atomic.pdf")
    atomic_promote_file(str(source), target)
    assert os.path.isfile(target)
    assert os.path.dirname(target) == STORAGE_DIR
    with open(target, "rb") as fh:
        assert fh.read() == b"promoted"
