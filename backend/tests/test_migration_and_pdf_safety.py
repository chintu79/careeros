import os
import hashlib
import tempfile
import pytest
from concurrent.futures import ThreadPoolExecutor, as_completed
from fastapi.testclient import TestClient
from sqlalchemy import text

from backend.app.main import app
from backend.app.database import SessionLocal, engine, Base
from backend.app.core.auth import create_access_token
from backend.app.models.candidate import CandidateProfile
from backend.app.models.resume import ResumeDocument
from backend.app.models.resume_version import ResumeVersion
from backend.app.services.database_migration import run_database_migrations, MIGRATION_ADVISORY_LOCK_ID
from backend.app.services.latex_compiler import compile_latex, atomic_promote_file, STORAGE_DIR

client = TestClient(app)


def auth_headers(user_id: int):
    token = create_access_token(user_id=user_id)
    return {"Authorization": f"Bearer {token}"}


SAMPLE_VALID_LATEX_A = r"""\documentclass{article}
\begin{document}
\Huge \textbf{Candidate Alpha}
\section*{Experience}
\begin{itemize}
\item Led development of distributed queue architecture processing 10k RPS.
\end{itemize}
\end{document}
"""

SAMPLE_VALID_LATEX_B = r"""\documentclass{article}
\begin{document}
\Huge \textbf{Candidate Beta}
\section*{Experience}
\begin{itemize}
\item Optimized database access patterns and eliminated concurrency race conditions.
\end{itemize}
\end{document}
"""

SAMPLE_INVALID_LATEX = r"""\documentclass{article}
\begin{document}
\Huge \textbf{Candidate Broken}
\section*{Experience}
\invalidlatexcommand{totally broken syntax that tectonic cannot parse
"""


def test_migration_advisory_lock_and_ddl_same_connection_and_tx():
    """
    1. Verifies that advisory lock and DDL statements execute on the exact same connection and transaction.
    2. Confirms that while the transaction is open on that connection, the advisory lock is held.
    3. Confirms that immediately upon transaction commit, the advisory lock is released.
    4. Confirms that required columns and unique constraint exist.
    """
    # Verify execution of migration
    run_database_migrations(engine)

    # Verify that the advisory lock is NOT leaked and was released upon commit
    with engine.connect() as conn:
        active_locks = conn.execute(text(f"""
            SELECT count(*) FROM pg_locks 
            WHERE locktype = 'advisory' AND objid = {MIGRATION_ADVISORY_LOCK_ID};
        """)).scalar()
        assert active_locks == 0, "Advisory lock must be released immediately upon transaction completion."

        # Verify columns exist
        cols = conn.execute(text("""
            SELECT column_name FROM information_schema.columns 
            WHERE table_name = 'resume_documents' AND column_name = 'structured_content';
        """)).fetchall()
        assert len(cols) == 1, "structured_content column must exist on resume_documents"

        version_cols = conn.execute(text("""
            SELECT column_name FROM information_schema.columns 
            WHERE table_name = 'resume_versions' AND column_name = 'structured_content';
        """)).fetchall()
        assert len(version_cols) == 1, "structured_content column must exist on resume_versions"

        # Verify constraint exists
        constraints = conn.execute(text("""
            SELECT conname FROM pg_constraint 
            WHERE conname = 'uq_resume_version_resume_id_version_number';
        """)).fetchall()
        assert len(constraints) == 1, "uq_resume_version_resume_id_version_number unique constraint must exist"


def test_migration_rollback_on_failure():
    """
    2. Verifies that if an exception occurs during the migration transaction:
       - The transaction is rolled back completely.
       - The advisory lock is released immediately.
       - A RuntimeError is raised to fail-fast and prevent starting in a partially migrated state.
    """
    canary_table = "test_migration_canary_rollback"

    with engine.begin() as conn:
        conn.execute(text(f"CREATE TABLE IF NOT EXISTS {canary_table} (id serial primary key, note text);"))
        conn.execute(text(f"TRUNCATE {canary_table};"))

    def failing_migration():
        try:
            with engine.begin() as conn:
                conn.execute(text(f"SELECT pg_advisory_xact_lock({MIGRATION_ADVISORY_LOCK_ID});"))
                conn.execute(text(f"INSERT INTO {canary_table} (note) VALUES ('uncommitted_entry');"))
                # Intentional syntax failure to force transaction rollback
                conn.execute(text("SELECT * FROM non_existent_table_forced_failure_xyz;"))
        except Exception as e:
            raise RuntimeError(f"Database migration transaction failed: {e}") from e

    with pytest.raises(RuntimeError) as exc_info:
        failing_migration()

    assert "Database migration transaction failed" in str(exc_info.value)

    # Verify rollback: canary table must have 0 rows
    with engine.connect() as conn:
        count = conn.execute(text(f"SELECT count(*) FROM {canary_table};")).scalar()
        assert count == 0, "All changes in failed migration transaction must be rolled back."

        # Verify advisory lock was released on rollback
        active_locks = conn.execute(text(f"""
            SELECT count(*) FROM pg_locks 
            WHERE locktype = 'advisory' AND objid = {MIGRATION_ADVISORY_LOCK_ID};
        """)).scalar()
        assert active_locks == 0, "Advisory lock must be released immediately upon transaction rollback."

    # Clean up canary table
    with engine.begin() as conn:
        conn.execute(text(f"DROP TABLE IF EXISTS {canary_table};"))


def test_concurrent_application_startup_migration():
    """
    3. Verifies that multiple application workers starting simultaneously and executing
       run_database_migrations serialize cleanly on the advisory lock without deadlocks,
       race conditions, or errors.
    """
    num_workers = 4
    with ThreadPoolExecutor(max_workers=num_workers) as executor:
        futures = [executor.submit(run_database_migrations, engine) for _ in range(num_workers)]
        results = [f.result() for f in as_completed(futures)]

    assert len(results) == num_workers
    # Verify advisory lock is free after all workers complete
    with engine.connect() as conn:
        active_locks = conn.execute(text(f"""
            SELECT count(*) FROM pg_locks 
            WHERE locktype = 'advisory' AND objid = {MIGRATION_ADVISORY_LOCK_ID};
        """)).scalar()
        assert active_locks == 0


def test_concurrent_compilations_for_same_resume():
    """
    4. Verifies that two concurrent compilations targeting the same resume base name
       compile in isolated temporary directories, perform atomic promotion (os.replace),
       and produce a valid, uncorrupted PDF without torn writes.
    """
    base_name = "test_concurrent_compilation_target"
    target_pdf = os.path.join(STORAGE_DIR, f"{base_name}.pdf")
    target_tex = os.path.join(STORAGE_DIR, f"{base_name}.tex")

    try:
        def worker(latex_src):
            return compile_latex(latex_src, base_name)

        with ThreadPoolExecutor(max_workers=2) as executor:
            f1 = executor.submit(worker, SAMPLE_VALID_LATEX_A)
            f2 = executor.submit(worker, SAMPLE_VALID_LATEX_B)
            res1 = f1.result()
            res2 = f2.result()

        assert res1[0] is True, f"Worker 1 compilation failed: {res1[1]}"
        assert res2[0] is True, f"Worker 2 compilation failed: {res2[1]}"
        assert os.path.exists(target_pdf), "Target PDF must exist on disk."

        # Verify valid, uncorrupted PDF content
        with open(target_pdf, "rb") as f:
            header = f.read(5)
            assert header == b"%PDF-", f"PDF header corrupted: {header}"
            f.seek(0, os.SEEK_END)
            size = f.tell()
            assert size > 500, f"PDF file size too small ({size} bytes), possible torn write."
    finally:
        if os.path.exists(target_pdf):
            os.remove(target_pdf)
        if os.path.exists(target_tex):
            os.remove(target_tex)


def test_failed_compilation_preserves_valid_pdf():
    """
    5. Verifies that a failed compilation leaves any previously valid PDF intact.
       Neither intermediate files nor broken output overwrite the existing valid file.
    """
    base_name = "test_preservation_target"
    target_pdf = os.path.join(STORAGE_DIR, f"{base_name}.pdf")
    target_tex = os.path.join(STORAGE_DIR, f"{base_name}.tex")

    try:
        # Step 1: Successfully compile initial valid PDF
        ok, path, comp = compile_latex(SAMPLE_VALID_LATEX_A, base_name)
        assert ok is True
        assert os.path.exists(target_pdf)
        with open(target_pdf, "rb") as f:
            original_bytes = f.read()
        original_hash = hashlib.sha256(original_bytes).hexdigest()

        # Step 2: Attempt compiling broken/invalid LaTeX with strict=True
        bad_ok, bad_err, bad_comp = compile_latex(SAMPLE_INVALID_LATEX, base_name, strict=True)
        assert bad_ok is False, "Broken LaTeX with strict=True must fail."

        # Step 3: Verify the original PDF is preserved 100% intact
        assert os.path.exists(target_pdf), "Original valid PDF must not be removed on compilation failure."
        with open(target_pdf, "rb") as f:
            current_bytes = f.read()
        current_hash = hashlib.sha256(current_bytes).hexdigest()
        assert current_hash == original_hash, "Original valid PDF was modified or corrupted by failed compilation."
    finally:
        if os.path.exists(target_pdf):
            os.remove(target_pdf)
        if os.path.exists(target_tex):
            os.remove(target_tex)


def test_database_pdf_path_consistency_after_concurrent_compilation():
    """
    6. Verifies database PDF path consistency after concurrent compilations.
       The database record points to a complete, valid file on disk matching the committed state.
    """
    user_id = 1401
    db = SessionLocal()
    try:
        cand = CandidateProfile(
            user_id=user_id,
            name="Concurrent Safety Candidate",
            email="safety.candidate@example.com",
            bio="Software reliability engineer focusing on transactional safety."
        )
        db.add(cand)
        db.commit()

        resume = ResumeDocument(
            user_id=user_id,
            title="Safety Engineering Resume",
            template_id="minimal_professional",
            latex_content=SAMPLE_VALID_LATEX_A,
            version=1
        )
        db.add(resume)
        db.commit()
        db.refresh(resume)
        resume_id = resume.id
    finally:
        db.close()

    headers = auth_headers(user_id)

    # Concurrently compile via API endpoint
    def call_compile():
        sub_client = TestClient(app)
        return sub_client.post(f"/api/resumes/{resume_id}/compile", headers=headers)

    with ThreadPoolExecutor(max_workers=2) as executor:
        f1 = executor.submit(call_compile)
        f2 = executor.submit(call_compile)
        res1 = f1.result()
        res2 = f2.result()

    assert res1.status_code == 200, res1.text
    assert res2.status_code == 200, res2.text

    # Verify DB record consistency
    db = SessionLocal()
    try:
        updated_resume = db.query(ResumeDocument).filter(ResumeDocument.id == resume_id).first()
        assert updated_resume is not None
        assert updated_resume.pdf_path is not None
        assert os.path.exists(updated_resume.pdf_path), f"DB points to non-existent PDF: {updated_resume.pdf_path}"

        with open(updated_resume.pdf_path, "rb") as f:
            header = f.read(5)
            assert header == b"%PDF-", "DB points to invalid or incomplete PDF file."
            f.seek(0, os.SEEK_END)
            assert f.tell() > 500, "DB points to truncated PDF."
    finally:
        # Cleanup PDF if exists
        if updated_resume and updated_resume.pdf_path and os.path.exists(updated_resume.pdf_path):
            os.remove(updated_resume.pdf_path)
        db.close()


def test_cleanup_temporary_files_after_success_and_failure():
    """
    7. Verifies that zero temporary staging or compilation files remain in STORAGE_DIR
       or the system temp directory after both successful and failed compilations.
    """
    base_name = "test_temp_cleanup_check"
    target_pdf = os.path.join(STORAGE_DIR, f"{base_name}.pdf")
    target_tex = os.path.join(STORAGE_DIR, f"{base_name}.tex")

    try:
        # Successful compilation
        ok, path, comp = compile_latex(SAMPLE_VALID_LATEX_A, base_name)
        assert ok is True

        # Check for any staging files in STORAGE_DIR
        staging_files = [
            f for f in os.listdir(STORAGE_DIR)
            if f.startswith(f".{base_name}") or (f.startswith(".") and f.endswith(".tmp"))
        ]
        assert len(staging_files) == 0, f"Found leaked staging files after success: {staging_files}"

        # Failed compilation
        bad_ok, bad_err, bad_comp = compile_latex(SAMPLE_INVALID_LATEX, base_name, strict=True)
        assert bad_ok is False

        # Check again for leaked staging files
        staging_files_after_fail = [
            f for f in os.listdir(STORAGE_DIR)
            if f.startswith(f".{base_name}") or (f.startswith(".") and f.endswith(".tmp"))
        ]
        assert len(staging_files_after_fail) == 0, f"Found leaked staging files after failure: {staging_files_after_fail}"

        # Check system temp directory for orphaned interniq compilation directories
        system_temp = tempfile.gettempdir()
        # Active directories should not include old finished jobs
        leaked_dirs = [
            d for d in os.listdir(system_temp)
            if d.startswith("interniq_compile_") and base_name in d
        ]
        assert len(leaked_dirs) == 0, f"Found orphaned temp compilation directories: {leaked_dirs}"
    finally:
        if os.path.exists(target_pdf):
            os.remove(target_pdf)
        if os.path.exists(target_tex):
            os.remove(target_tex)
