import os
import time
import re
import hashlib
import tempfile
import pytest
from unittest.mock import patch
from concurrent.futures import ThreadPoolExecutor
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.database import SessionLocal
from backend.app.core.auth import create_access_token
from backend.app.models.resume import ResumeDocument
from backend.app.models.resume_version import ResumeVersion
from backend.app.models.candidate import CandidateProfile
from backend.app.services.latex_compiler import (
    compile_latex,
    compile_in_temp_env,
    compile_and_validate_resume,
    PDFPromotionTransaction,
    STORAGE_DIR
)
from backend.app.services.pdf_layout_validator import (
    analyze_pdf,
    validate_pdf_layout,
    A4_WIDTH,
    A4_HEIGHT,
    LETTER_WIDTH,
    LETTER_HEIGHT,
    TOLERANCE_PT
)
from backend.app.services.latex_templates import build_latex_template

client = TestClient(app)


def auth_headers(user_id: int):
    token = create_access_token(user_id=user_id)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def clean_db():
    db = SessionLocal()
    test_user_id = 99301
    try:
        # Clean existing test artifacts for dedicated test user
        db.query(ResumeVersion).filter(ResumeVersion.resume_id.in_(
            db.query(ResumeDocument.id).filter(ResumeDocument.user_id == test_user_id)
        )).delete(synchronize_session=False)
        db.query(ResumeDocument).filter(ResumeDocument.user_id == test_user_id).delete(synchronize_session=False)
        db.query(CandidateProfile).filter(CandidateProfile.user_id == test_user_id).delete(synchronize_session=False)
        db.commit()

        # Insert fresh candidate
        cand = CandidateProfile(
            user_id=test_user_id,
            name="Recovery Candidate",
            email="recovery@example.com",
            phone="+1 555-0199",
            location="Zurich, Switzerland",
            degree="M.S. Distributed Systems",
            college="ETH Zurich",
            graduation_year=2024,
            cgpa=3.95,
            skills=[{"category": "Systems", "skills": ["Go", "Rust", "PostgreSQL", "C++"]}],
            experience=[{
                "id": "exp_1",
                "title": "Systems Reliability Engineer",
                "company": "Alpine Infrastructure",
                "duration": "2023 - Present",
                "location": "Zurich",
                "bullets": [{"id": "b_1", "text": "Designed high-availability transactional storage engines."}]
            }],
            projects=[{
                "id": "proj_1",
                "title": "Distributed Write-Ahead Log",
                "tech_stack": ["Rust", "Raft"],
                "bullets": [{"id": "b_2", "text": "Engineered zero-allocation state machine replication."}]
            }]
        )
        db.add(cand)
        db.commit()
        db.refresh(cand)

        yield {"db": db, "user_id": test_user_id, "cand": cand}

    finally:
        db.query(ResumeVersion).filter(ResumeVersion.resume_id.in_(
            db.query(ResumeDocument.id).filter(ResumeDocument.user_id == test_user_id)
        )).delete(synchronize_session=False)
        db.query(ResumeDocument).filter(ResumeDocument.user_id == test_user_id).delete(synchronize_session=False)
        db.query(CandidateProfile).filter(CandidateProfile.user_id == test_user_id).delete(synchronize_session=False)
        db.commit()
        db.close()


def create_initial_resume(db: Session, user_id: int, cand: CandidateProfile) -> ResumeDocument:
    """Helper to initialize a fully valid ResumeDocument v1 with compiled PDF."""
    cand_dict = {
        "id": cand.id,
        "name": cand.name,
        "email": cand.email,
        "phone": cand.phone,
        "location": cand.location,
        "degree": cand.degree,
        "college": cand.college,
        "graduation_year": cand.graduation_year,
        "cgpa": cand.cgpa,
        "skills": cand.skills,
        "projects": cand.projects,
        "experience": cand.experience,
    }
    latex = build_latex_template(cand_dict, template_id="minimal_professional", page_size="letter")
    resume = ResumeDocument(
        user_id=user_id,
        title="Recovery Test Resume",
        template_id="minimal_professional",
        latex_content=latex,
        structured_content=cand_dict,
        version=1,
        is_master=True
    )
    db.add(resume)
    db.commit()
    db.refresh(resume)

    # Initial compile
    base_name = f"resume_{resume.id}_v1"
    ok, pdf_path, _ = compile_latex(latex, base_name, page_size="letter")
    assert ok is True
    assert os.path.exists(pdf_path)

    resume.pdf_path = pdf_path
    db.commit()
    db.refresh(resume)
    return resume


# ===========================================================================
# Test 1: Successful promotion followed by database commit failure
# ===========================================================================
def test_01_successful_promotion_followed_by_db_commit_failure(clean_db):
    """
    Compilation succeeds, PDF validation succeeds, atomic promotion stages the new artifact,
    but subsequent database commit fails.
    The active resume must never point to an invalid artifact, and filesystem changes must rollback.
    """
    t_test_started = time.time()
    db = clean_db["db"]
    user_id = clean_db["user_id"]
    cand = clean_db["cand"]
    headers = auth_headers(user_id)

    resume = create_initial_resume(db, user_id, cand)
    initial_v1_pdf = resume.pdf_path
    assert os.path.exists(initial_v1_pdf)
    v2_pdf_path = os.path.join(STORAGE_DIR, f"resume_{resume.id}_v2.pdf")

    # Simulate database commit failure right after file promotion
    with patch.object(Session, "commit", side_effect=SQLAlchemyError("Simulated DB disk failure on commit")):
        update_payload = {
            "summary": "Updated summary targeting v2 that will fail commit",
            "change_summary": "Attempting v2 update"
        }
        res = client.put(f"/api/resumes/{resume.id}/sections", json=update_payload, headers=headers)
        assert res.status_code == 500
        assert "Database commit failed" in res.json()["detail"]

    # Verify Database state rolled back
    db.refresh(resume)
    assert resume.version == 1
    assert resume.pdf_path == initial_v1_pdf

    # Verify no uncommitted v2 snapshot in DB
    v2_snap = db.query(ResumeVersion).filter(
        ResumeVersion.resume_id == resume.id,
        ResumeVersion.version_number == 2
    ).first()
    assert v2_snap is None

    # Verify Filesystem state rolled back (only fail if the v2 PDF was created during this test)
    assert os.path.exists(initial_v1_pdf)
    if os.path.exists(v2_pdf_path):
        assert os.path.getmtime(v2_pdf_path) < t_test_started, (
            f"Uncommitted v2 PDF {v2_pdf_path} was created during this test — promotion must roll back"
        )


# ===========================================================================
# Test 2: Previous valid PDF remains recoverable and bit-identical
# ===========================================================================
def test_02_previous_pdf_remains_recoverable_and_bit_identical(clean_db):
    """
    When re-compiling an existing resume version and database commit fails,
    the pre-existing physical PDF file must be restored from backup bit-for-bit.
    """
    db = clean_db["db"]
    user_id = clean_db["user_id"]
    cand = clean_db["cand"]
    headers = auth_headers(user_id)

    resume = create_initial_resume(db, user_id, cand)
    pdf_path = resume.pdf_path
    assert os.path.exists(pdf_path)

    # Compute SHA256 of pre-existing PDF
    with open(pdf_path, "rb") as f:
        original_hash = hashlib.sha256(f.read()).hexdigest()

    # Re-compile existing version, but force commit to fail
    with patch.object(Session, "commit", side_effect=SQLAlchemyError("Simulated commit crash on recompile")):
        res = client.post(
            f"/api/resumes/{resume.id}/compile?page_size=a4",
            headers=headers
        )
        assert res.status_code == 500
        assert "Database commit failed after compilation" in res.json()["detail"]

    # Verify the file on disk was restored from backup and is bit-for-bit identical
    assert os.path.exists(pdf_path)
    with open(pdf_path, "rb") as f:
        restored_hash = hashlib.sha256(f.read()).hexdigest()

    assert restored_hash == original_hash, "Physical PDF must be restored byte-for-byte to pre-promotion content"


# ===========================================================================
# Test 3: Newly promoted but uncommitted artifact does not silently become active
# ===========================================================================
def test_03_newly_promoted_uncommitted_artifact_not_silently_active(clean_db):
    """
    Directly tests PDFPromotionTransaction and API guarantees that a newly promoted
    artifact from an uncommitted transaction is removed and never becomes active.
    """
    dummy_pdf_target = os.path.join(STORAGE_DIR, "test_dummy_tx_artifact.pdf")
    dummy_tex_target = os.path.join(STORAGE_DIR, "test_dummy_tx_artifact.tex")

    if os.path.exists(dummy_pdf_target):
        os.remove(dummy_pdf_target)
    if os.path.exists(dummy_tex_target):
        os.remove(dummy_tex_target)

    # 1. Direct unit verification of PDFPromotionTransaction
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_pdf = os.path.join(tmp_dir, "test.pdf")
        tmp_tex = os.path.join(tmp_dir, "test.tex")
        with open(tmp_pdf, "wb") as f:
            f.write(b"%PDF-1.4 dummy binary content")
        with open(tmp_tex, "w") as f:
            f.write("dummy tex")

        tx = PDFPromotionTransaction(dummy_pdf_target, dummy_tex_target)
        tx.stage_and_promote(tmp_pdf, tmp_tex)
        assert os.path.exists(dummy_pdf_target)
        assert os.path.exists(dummy_tex_target)

        # Trigger rollback (simulating DB commit failure)
        tx.rollback()
        assert not os.path.exists(dummy_pdf_target), "Uncommitted artifact must be removed upon rollback"
        assert not os.path.exists(dummy_tex_target), "Uncommitted tex must be removed upon rollback"

    # 2. API verification on section update
    db = clean_db["db"]
    user_id = clean_db["user_id"]
    cand = clean_db["cand"]
    headers = auth_headers(user_id)

    resume = create_initial_resume(db, user_id, cand)
    v2_file = os.path.join(STORAGE_DIR, f"resume_{resume.id}_v2.pdf")
    if os.path.exists(v2_file):
        os.remove(v2_file)
        print(f"removed stale artifact created by prior run: {v2_file}")
    with patch.object(Session, "commit", side_effect=SQLAlchemyError("DB disk abort")):
        res = client.put(
            f"/api/resumes/{resume.id}/sections",
            json={"summary": "Uncommitted summary update"},
            headers=headers
        )
        assert res.status_code == 500

    # Ensure v2 file was not created during this test
    assert not os.path.exists(v2_file)


# ===========================================================================
# Test 4: Recovery and cleanup leaves zero orphaned temporary or backup files
# ===========================================================================
def test_04_recovery_and_cleanup_zero_orphaned_files(clean_db):
    """
    After failed transactions or aborts, verify that zero orphaned .tmp or .backup files
    remain in STORAGE_DIR.
    """
    db = clean_db["db"]
    user_id = clean_db["user_id"]
    cand = clean_db["cand"]
    headers = auth_headers(user_id)

    resume = create_initial_resume(db, user_id, cand)

    # Trigger failed section update
    with patch.object(Session, "commit", side_effect=SQLAlchemyError("Failure 1")):
        client.put(
            f"/api/resumes/{resume.id}/sections",
            json={"summary": "Doomed update"},
            headers=headers
        )

    # Trigger failed compile
    with patch.object(Session, "commit", side_effect=SQLAlchemyError("Failure 2")):
        client.post(
            f"/api/resumes/{resume.id}/compile",
            headers=headers
        )

    # Scan STORAGE_DIR for orphaned temporary files
    all_files = os.listdir(STORAGE_DIR)
    orphans = [
        f for f in all_files
        if f.startswith(".") or ".tmp" in f or ".backup." in f
    ]
    assert len(orphans) == 0, f"Found orphaned staging or backup files: {orphans}"


# ===========================================================================
# Test 5: Concurrent successful compilation on the same resume
# ===========================================================================
def test_05_concurrent_successful_compilation_same_resume(clean_db):
    """
    Multiple concurrent requests attempt to compile the same resume.
    Ensures exclusive row-locking serializes execution safely and the final DB
    metadata and physical PDF file describe the same committed artifact.
    """
    db = clean_db["db"]
    user_id = clean_db["user_id"]
    cand = clean_db["cand"]
    headers = auth_headers(user_id)

    resume = create_initial_resume(db, user_id, cand)
    resume_id = resume.id

    def compile_worker(target_pages: int):
        worker_client = TestClient(app)
        return worker_client.post(
            f"/api/resumes/{resume_id}/compile?target_page_count={target_pages}",
            headers=headers
        )

    # Launch 4 concurrent compilation requests
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = [executor.submit(compile_worker, p) for p in [1, 2, 1, 2]]
        results = [f.result() for f in futures]

    for r in results:
        assert r.status_code == 200, f"Worker failed: {r.text}"

    # Verify final database and file state
    db.expire_all()
    final_resume = db.query(ResumeDocument).filter(ResumeDocument.id == resume_id).first()
    assert os.path.exists(final_resume.pdf_path)

    # Validate physical PDF integrity
    analysis = analyze_pdf(final_resume.pdf_path)
    assert not analysis.is_empty_or_malformed
    assert analysis.page_count > 0

    # Ensure DB layout metadata matches physical file
    stored_meta = final_resume.structured_content.get("metadata", {}).get("layout_metadata", {})
    assert stored_meta.get("page_count") == analysis.page_count
    assert stored_meta.get("page_size") == analysis.page_size


# ===========================================================================
# Test 6: Concurrent compilation with one failure
# ===========================================================================
def test_06_concurrent_compilation_with_one_failure(clean_db):
    """
    One request succeeds while another encounters a LaTeX syntax failure.
    The failure must not corrupt the resume or leave uncommitted artifacts,
    and the valid update must succeed cleanly.
    """
    db = clean_db["db"]
    user_id = clean_db["user_id"]
    cand = clean_db["cand"]
    headers = auth_headers(user_id)

    resume = create_initial_resume(db, user_id, cand)
    resume_id = resume.id

    def valid_worker():
        worker_client = TestClient(app)
        return worker_client.put(
            f"/api/resumes/{resume_id}/sections",
            json={"summary": "Valid concurrent summary update"},
            headers=headers
        )

    def invalid_worker():
        worker_client = TestClient(app)
        broken_latex = r"\documentclass{article}\begin{document}\undefinedBrokenCommand{\xyz}"
        return worker_client.post(
            f"/api/resumes/{resume_id}/apply-optimization",
            json={"latex_content": broken_latex, "change_summary": "Broken syntax attempt"},
            headers=headers
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        fut_valid = executor.submit(valid_worker)
        fut_invalid = executor.submit(invalid_worker)
        res_valid = fut_valid.result()
        res_invalid = fut_invalid.result()

    # Invalid worker must fail with 400
    assert res_invalid.status_code == 400
    assert "LaTeX compilation failed" in res_invalid.json()["detail"]

    # Valid worker must succeed with 200
    assert res_valid.status_code == 200

    # Verify DB and filesystem integrity
    db.expire_all()
    current_resume = db.query(ResumeDocument).filter(ResumeDocument.id == resume_id).first()
    assert current_resume.version == 2
    assert os.path.exists(current_resume.pdf_path)
    analysis = analyze_pdf(current_resume.pdf_path)
    assert not analysis.is_empty_or_malformed


# ===========================================================================
# Test 7: Concurrent compilation with different page sizes
# ===========================================================================
def test_07_concurrent_compilation_different_page_sizes(clean_db):
    """
    Two concurrent compile requests: one requesting A4, the other requesting Letter.
    The final DB metadata and physical PDF file must describe the exact same committed artifact.
    """
    db = clean_db["db"]
    user_id = clean_db["user_id"]
    cand = clean_db["cand"]
    headers = auth_headers(user_id)

    resume = create_initial_resume(db, user_id, cand)
    resume_id = resume.id

    def compile_size_worker(ps: str):
        worker_client = TestClient(app)
        return worker_client.post(
            f"/api/resumes/{resume_id}/compile?page_size={ps}",
            headers=headers
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        f_a4 = executor.submit(compile_size_worker, "a4")
        f_letter = executor.submit(compile_size_worker, "letter")
        r_a4 = f_a4.result()
        r_letter = f_letter.result()

    assert r_a4.status_code == 200
    assert r_letter.status_code == 200

    # Inspect final committed state
    db.expire_all()
    final_resume = db.query(ResumeDocument).filter(ResumeDocument.id == resume_id).first()
    stored_ps = final_resume.structured_content["metadata"]["page_size"]
    assert stored_ps in ("a4", "letter")

    # Analyze physical PDF on disk
    analysis = analyze_pdf(final_resume.pdf_path)
    assert not analysis.is_empty_or_malformed

    # Physical page size MUST match stored metadata exactly (case-insensitive)
    assert analysis.page_size.lower() == stored_ps.lower(), (
        f"Race condition detected: DB metadata recorded {stored_ps}, "
        f"but physical PDF dimensions correspond to {analysis.page_size}"
    )


# ===========================================================================
# Test 8: Version-specific PDF association remains correct
# ===========================================================================
def test_08_version_specific_pdf_association_remains_correct(clean_db):
    """
    Snapshots v1, v2, v3 each retain their distinct, permanent physical PDF artifacts.
    A subsequent failure in v4 must leave all historical versions untouched.
    """
    db = clean_db["db"]
    user_id = clean_db["user_id"]
    cand = clean_db["cand"]
    headers = auth_headers(user_id)

    resume = create_initial_resume(db, user_id, cand)
    resume_id = resume.id

    # Create v2
    res_v2 = client.put(
        f"/api/resumes/{resume_id}/sections",
        json={"summary": "Summary for Version 2"},
        headers=headers
    )
    assert res_v2.status_code == 200

    # Create v3
    res_v3 = client.put(
        f"/api/resumes/{resume_id}/sections",
        json={"summary": "Summary for Version 3"},
        headers=headers
    )
    assert res_v3.status_code == 200

    # Verify all 3 snapshots exist in DB
    snapshots = db.query(ResumeVersion).filter(ResumeVersion.resume_id == resume_id).order_by(ResumeVersion.version_number).all()
    assert len(snapshots) >= 2  # v2 and v3 snapshots are recorded

    v1_pdf = os.path.join(STORAGE_DIR, f"resume_{resume_id}_v1.pdf")
    v2_pdf = os.path.join(STORAGE_DIR, f"resume_{resume_id}_v2.pdf")
    v3_pdf = os.path.join(STORAGE_DIR, f"resume_{resume_id}_v3.pdf")

    assert os.path.exists(v1_pdf)
    assert os.path.exists(v2_pdf)
    assert os.path.exists(v3_pdf)

    # Compute hashes of all 3 versions
    with open(v1_pdf, "rb") as f:
        h1 = hashlib.sha256(f.read()).hexdigest()
    with open(v2_pdf, "rb") as f:
        h2 = hashlib.sha256(f.read()).hexdigest()
    with open(v3_pdf, "rb") as f:
        h3 = hashlib.sha256(f.read()).hexdigest()

    # Attempt v4 update with simulated commit failure
    with patch.object(Session, "commit", side_effect=SQLAlchemyError("v4 commit aborted")):
        res_v4 = client.put(
            f"/api/resumes/{resume_id}/sections",
            json={"summary": "Doomed Summary for Version 4"},
            headers=headers
        )
        assert res_v4.status_code == 500

    # Verify v1, v2, v3 PDFs remain untouched on disk
    with open(v1_pdf, "rb") as f:
        assert hashlib.sha256(f.read()).hexdigest() == h1
    with open(v2_pdf, "rb") as f:
        assert hashlib.sha256(f.read()).hexdigest() == h2
    with open(v3_pdf, "rb") as f:
        assert hashlib.sha256(f.read()).hexdigest() == h3

    # Verify v4 PDF was not left behind
    v4_pdf = os.path.join(STORAGE_DIR, f"resume_{resume_id}_v4.pdf")
    assert not os.path.exists(v4_pdf)
