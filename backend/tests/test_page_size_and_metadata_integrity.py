import os
import shutil
import tempfile
import pytest
from unittest.mock import patch
from concurrent.futures import ThreadPoolExecutor, as_completed
from fastapi.testclient import TestClient
import pypdf

from backend.app.main import app
from backend.app.database import SessionLocal
from backend.app.core.auth import create_access_token
from backend.app.models.candidate import CandidateProfile
from backend.app.models.resume import ResumeDocument
from backend.app.models.resume_version import ResumeVersion
from backend.app.services.latex_compiler import (
    compile_latex,
    compile_pdf_fallback_reportlab,
    compile_and_validate_resume,
    STORAGE_DIR
)
from backend.app.services.pdf_layout_validator import (
    analyze_pdf,
    classify_page_size,
    determine_page_size,
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
    try:
        # Create dedicated test user
        test_user_id = 99201
        db.query(ResumeVersion).filter(ResumeVersion.resume_id.in_(
            db.query(ResumeDocument.id).filter(ResumeDocument.user_id == test_user_id)
        )).delete(synchronize_session=False)
        db.query(ResumeDocument).filter(ResumeDocument.user_id == test_user_id).delete(synchronize_session=False)
        db.query(CandidateProfile).filter(CandidateProfile.user_id == test_user_id).delete(synchronize_session=False)
        db.commit()

        # Insert fresh candidate
        cand = CandidateProfile(
            user_id=test_user_id,
            name="Integrity Candidate",
            email="integrity@example.com",
            phone="+1 555-0188",
            location="Berlin, Germany",
            degree="B.S. Software Engineering",
            college="Technical University",
            graduation_year=2024,
            cgpa=3.9,
            skills=[{"category": "Languages", "skills": ["Python", "C++", "TypeScript"]}],
            experience=[{
                "id": "exp_1",
                "title": "Systems Engineer",
                "company": "Core Cloud Tech",
                "duration": "2023 - Present",
                "location": "Berlin",
                "bullets": [{"id": "b_1", "text": "Architected low-latency distributed storage pipelines."}]
            }],
            projects=[{
                "id": "proj_1",
                "title": "Kernel Cache Daemon",
                "tech_stack": ["C++", "Linux"],
                "bullets": [{"id": "b_2", "text": "Engineered zero-copy memory ring buffer."}]
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


# ---------------------------------------------------------------------------
# Test 1: A4 compilation and classification
# ---------------------------------------------------------------------------
def test_01_a4_compilation_and_classification(clean_db):
    """
    Compiles an A4 resume (via template with page_size='a4') and verifies with pypdf
    that physical page dimensions match A4 (~595.28 x ~841.89 pt within tolerance)
    and that classify_page_size classifies it as 'A4'.
    """
    cand = clean_db["cand"]
    cand_data = {
        "name": cand.name,
        "email": cand.email,
        "phone": cand.phone,
        "location": cand.location,
        "degree": cand.degree,
        "college": cand.college,
        "skills": cand.skills,
        "experience": cand.experience,
        "projects": cand.projects
    }
    latex = build_latex_template(cand_data, template_id="minimal_professional", page_size="a4")
    assert "a4paper" in latex

    ok, pdf_path, compiler = compile_latex(latex, "test_01_a4_output", page_size="a4")
    assert ok, f"A4 compilation failed: {pdf_path}"
    assert os.path.exists(pdf_path)

    reader = pypdf.PdfReader(pdf_path)
    assert len(reader.pages) >= 1
    page = reader.pages[0]
    w = float(page.mediabox.width)
    h = float(page.mediabox.height)

    assert abs(w - A4_WIDTH) <= TOLERANCE_PT, f"A4 width {w} exceeded tolerance from {A4_WIDTH}"
    assert abs(h - A4_HEIGHT) <= TOLERANCE_PT, f"A4 height {h} exceeded tolerance from {A4_HEIGHT}"
    assert classify_page_size(w, h) == "A4"

    analysis = analyze_pdf(pdf_path)
    assert analysis.page_size == "A4"


# ---------------------------------------------------------------------------
# Test 2: Letter compilation and classification
# ---------------------------------------------------------------------------
def test_02_letter_compilation_and_classification(clean_db):
    """
    Compiles a Letter resume (via template with page_size='letter') and verifies with pypdf
    that physical page dimensions match Letter (~612.0 x ~792.0 pt within tolerance)
    and that classify_page_size classifies it as 'Letter'.
    """
    cand = clean_db["cand"]
    cand_data = {
        "name": cand.name,
        "email": cand.email,
        "phone": cand.phone,
        "location": cand.location,
        "degree": cand.degree,
        "college": cand.college,
        "skills": cand.skills,
        "experience": cand.experience,
        "projects": cand.projects
    }
    latex = build_latex_template(cand_data, template_id="minimal_professional", page_size="letter")
    assert "letterpaper" in latex

    ok, pdf_path, compiler = compile_latex(latex, "test_02_letter_output", page_size="letter")
    assert ok, f"Letter compilation failed: {pdf_path}"
    assert os.path.exists(pdf_path)

    reader = pypdf.PdfReader(pdf_path)
    assert len(reader.pages) >= 1
    page = reader.pages[0]
    w = float(page.mediabox.width)
    h = float(page.mediabox.height)

    assert abs(w - LETTER_WIDTH) <= TOLERANCE_PT, f"Letter width {w} exceeded tolerance from {LETTER_WIDTH}"
    assert abs(h - LETTER_HEIGHT) <= TOLERANCE_PT, f"Letter height {h} exceeded tolerance from {LETTER_HEIGHT}"
    assert classify_page_size(w, h) == "Letter"

    analysis = analyze_pdf(pdf_path)
    assert analysis.page_size == "Letter"


# ---------------------------------------------------------------------------
# Test 3: Explicit page-size selection surviving subsequent compilation
# ---------------------------------------------------------------------------
def test_03_explicit_page_size_selection_surviving_subsequent_compilation(clean_db):
    """
    When page_size is explicitly chosen ('a4'), subsequent compilation without query
    parameters and section updates continue compiling to A4 and persist 'a4' in metadata.
    """
    db = clean_db["db"]
    user_id = clean_db["user_id"]
    headers = auth_headers(user_id)

    # Create resume
    res = client.post(
        "/api/resumes/",
        headers=headers,
        json={"title": "Page Size Survival Resume", "template_id": "minimal_professional"}
    )
    assert res.status_code == 200, res.text
    resume_id = res.json()["id"]

    # Explicit compile with page_size=a4
    comp_res = client.post(
        f"/api/resumes/{resume_id}/compile",
        headers=headers,
        json={"page_size": "a4"}
    )
    assert comp_res.status_code == 200, comp_res.text
    analysis = comp_res.json()["page_analysis"]
    assert analysis["page_size"] == "A4"

    # Re-fetch resume to verify metadata
    get_res = client.get(f"/api/resumes/{resume_id}", headers=headers)
    assert get_res.status_code == 200
    sc = get_res.json()["structured_content"]
    assert sc.get("metadata", {}).get("page_size") == "a4"

    # Compile again without explicit page_size argument
    comp_res2 = client.post(f"/api/resumes/{resume_id}/compile", headers=headers)
    assert comp_res2.status_code == 200
    assert comp_res2.json()["page_analysis"]["page_size"] == "A4"

    # Partial section update
    current_ver = get_res.json()["version"]
    sec_res = client.put(
        f"/api/resumes/{resume_id}/sections",
        headers=headers,
        json={
            "expected_version": current_ver,
            "summary": "Updated summary preserving A4 layout."
        }
    )
    assert sec_res.status_code == 200, sec_res.text
    assert sec_res.json()["page_analysis"]["page_size"] == "A4"
    assert sec_res.json()["structured_content"]["metadata"]["page_size"] == "a4"


# ---------------------------------------------------------------------------
# Test 4: Legacy resume page-size defaults
# ---------------------------------------------------------------------------
def test_04_legacy_resume_page_size_defaults(clean_db):
    """
    Tests deterministic page-size resolution hierarchy:
    1. Explicit requested page size
    2. Structured content metadata
    3. LaTeX source inspection (a4paper vs letterpaper)
    4. Location heuristic (USA -> letter)
    5. International default (a4)
    """
    # Explicit override takes top priority
    assert determine_page_size(explicit_page_size="a4", latex_content=r"\documentclass[letterpaper]{article}") == "a4"
    assert determine_page_size(explicit_page_size="letter", latex_content=r"\documentclass[a4paper]{article}") == "letter"

    # Stored metadata takes priority over LaTeX if no explicit argument
    assert determine_page_size(structured_data={"metadata": {"page_size": "a4"}}, latex_content=r"\documentclass[letterpaper]{article}") == "a4"

    # LaTeX inspection takes priority if no metadata
    assert determine_page_size(latex_content=r"\documentclass[10pt,a4paper]{article}") == "a4"
    assert determine_page_size(latex_content=r"\documentclass[10pt,letterpaper]{article}") == "letter"

    # Location heuristic (USA -> letter)
    assert determine_page_size(profile_location="San Francisco, CA, USA") == "letter"
    assert determine_page_size(profile_location="New York, NY") == "letter"

    # International fallback (default -> a4)
    assert determine_page_size(profile_location="Berlin, Germany") == "a4"
    assert determine_page_size(profile_location=None, latex_content=None) == "a4"


# ---------------------------------------------------------------------------
# Test 5: Partial section update preserving compilation metadata
# ---------------------------------------------------------------------------
def test_05_partial_section_update_preserving_compilation_metadata(clean_db):
    """
    Updating a section via PUT /api/resumes/{id}/sections preserves existing compilation
    metadata (target_page_count, page_size, custom keys) and does not overwrite
    candidate-authored sections (experience, projects, education).
    """
    db = clean_db["db"]
    user_id = clean_db["user_id"]
    headers = auth_headers(user_id)

    res = client.post(
        "/api/resumes/",
        headers=headers,
        json={"title": "Metadata Preservation Resume", "template_id": "minimal_professional"}
    )
    assert res.status_code == 200
    resume_id = res.json()["id"]

    # Initial compilation setting metadata
    comp_res = client.post(
        f"/api/resumes/{resume_id}/compile",
        headers=headers,
        json={"target_page_count": 2, "page_size": "letter"}
    )
    assert comp_res.status_code == 200
    init_ver = client.get(f"/api/resumes/{resume_id}", headers=headers).json()["version"]

    # Partial update modifying only the summary
    update_res = client.put(
        f"/api/resumes/{resume_id}/sections",
        headers=headers,
        json={
            "expected_version": init_ver,
            "summary": "Specialized distributed systems architect with extensive high-scale experience."
        }
    )
    assert update_res.status_code == 200, update_res.text
    data = update_res.json()

    # Verify candidate-authored sections remain intact
    sc = data["structured_content"]
    assert sc["summary"] == "Specialized distributed systems architect with extensive high-scale experience."
    assert len(sc["experience"]) >= 1
    assert sc["experience"][0]["title"] == "Systems Engineer"
    assert len(sc["projects"]) >= 1
    assert sc["projects"][0]["title"] == "Kernel Cache Daemon"

    # Verify metadata keys are preserved
    meta = sc.get("metadata", {})
    assert meta.get("target_page_count") == 2
    assert meta.get("page_size") == "letter"
    assert "layout_metadata" in meta
    assert meta["layout_metadata"]["validation_status"] in ("passed", "warning")


# ---------------------------------------------------------------------------
# Test 6: Version snapshot and restore consistency
# ---------------------------------------------------------------------------
def test_06_version_snapshot_and_restore_consistency(clean_db):
    """
    Restoring a prior version snapshot (POST /api/resumes/{id}/versions/{version_id}/restore)
    restores the exact structured content, LaTeX content, template, and provides an
    independent version PDF without corrupting historical snapshots.
    """
    db = clean_db["db"]
    user_id = clean_db["user_id"]
    headers = auth_headers(user_id)

    res = client.post(
        "/api/resumes/",
        headers=headers,
        json={"title": "Snapshot Restore Resume", "template_id": "minimal_professional"}
    )
    assert res.status_code == 200
    resume_id = res.json()["id"]

    # Compile v1
    c1 = client.post(f"/api/resumes/{resume_id}/compile", headers=headers, json={"page_size": "letter"})
    assert c1.status_code == 200
    r_v1 = client.get(f"/api/resumes/{resume_id}", headers=headers).json()
    v1_pdf = r_v1["pdf_path"]
    assert os.path.exists(v1_pdf)

    # Checkpoint v1 as snapshot
    snap_res = client.post(
        f"/api/resumes/{resume_id}/versions",
        headers=headers,
        json={"change_summary": "Original v1 checkpoint"}
    )
    assert snap_res.status_code == 200
    versions = client.get(f"/api/resumes/{resume_id}/versions", headers=headers).json()
    v1_snapshot_id = versions[0]["id"]

    # Make modification to create v2
    update_res = client.put(
        f"/api/resumes/{resume_id}/sections",
        headers=headers,
        json={
            "expected_version": snap_res.json()["version"],
            "summary": "Modified Summary for Version 2",
            "page_size": "a4"
        }
    )
    assert update_res.status_code == 200
    r_v2 = client.get(f"/api/resumes/{resume_id}", headers=headers).json()
    assert r_v2["structured_content"]["summary"] == "Modified Summary for Version 2"
    assert r_v2["structured_content"]["metadata"]["page_size"] == "a4"

    # Restore v1 snapshot
    restore_res = client.post(
        f"/api/resumes/{resume_id}/versions/{v1_snapshot_id}/restore",
        headers=headers
    )
    assert restore_res.status_code == 200, restore_res.text
    restored = restore_res.json()

    # Verify restored document matches v1 state and has its own independent PDF
    assert restored["version"] > r_v2["version"]
    assert restored["structured_content"]["summary"] != "Modified Summary for Version 2"
    assert restored["pdf_path"] != r_v2["pdf_path"]
    assert os.path.exists(restored["pdf_path"])
    # Verify historical snapshot PDF is still intact on disk
    assert os.path.exists(v1_pdf)


# ---------------------------------------------------------------------------
# Test 7: Repeated compilation not creating unnecessary resume versions
# ---------------------------------------------------------------------------
def test_07_repeated_compilation_not_creating_unnecessary_resume_versions(clean_db):
    """
    Calling POST /api/resumes/{id}/compile multiple times updates the compiled PDF and
    metadata on the active resume without incrementing resume.version or creating
    duplicate ResumeVersion rows.
    """
    db = clean_db["db"]
    user_id = clean_db["user_id"]
    headers = auth_headers(user_id)

    res = client.post(
        "/api/resumes/",
        headers=headers,
        json={"title": "Repeated Compile Resume", "template_id": "minimal_professional"}
    )
    assert res.status_code == 200
    resume_id = res.json()["id"]

    # Count initial versions
    init_versions = db.query(ResumeVersion).filter(ResumeVersion.resume_id == resume_id).count()
    init_version_number = client.get(f"/api/resumes/{resume_id}", headers=headers).json()["version"]

    # Call compile 3 times consecutively
    for i in range(3):
        comp = client.post(f"/api/resumes/{resume_id}/compile", headers=headers)
        assert comp.status_code == 200, f"Compilation #{i+1} failed: {comp.text}"

    # Verify version number did not change
    current_resume = client.get(f"/api/resumes/{resume_id}", headers=headers).json()
    assert current_resume["version"] == init_version_number

    # Verify no new ResumeVersion records were created
    current_version_count = db.query(ResumeVersion).filter(ResumeVersion.resume_id == resume_id).count()
    assert current_version_count == init_versions


# ---------------------------------------------------------------------------
# Test 8: Compilation metadata matching the latest PDF
# ---------------------------------------------------------------------------
def test_08_compilation_metadata_matching_latest_pdf(clean_db):
    """
    Verifies that the stored layout_metadata in structured content matches the actual
    page count, page size, and dimensions of the current compiled PDF on disk.
    """
    db = clean_db["db"]
    user_id = clean_db["user_id"]
    headers = auth_headers(user_id)

    res = client.post(
        "/api/resumes/",
        headers=headers,
        json={"title": "Metadata Match Resume", "template_id": "modern_technical"}
    )
    assert res.status_code == 200
    resume_id = res.json()["id"]

    comp = client.post(f"/api/resumes/{resume_id}/compile", headers=headers, json={"page_size": "letter"})
    assert comp.status_code == 200
    comp_data = comp.json()

    r = client.get(f"/api/resumes/{resume_id}", headers=headers).json()
    pdf_path = r["pdf_path"]
    assert os.path.exists(pdf_path)

    # Inspect physical PDF directly via pypdf
    reader = pypdf.PdfReader(pdf_path)
    actual_pages = len(reader.pages)
    first_page = reader.pages[0]
    actual_w = float(first_page.mediabox.width)
    actual_h = float(first_page.mediabox.height)

    # Compare against stored metadata
    meta = r["structured_content"]["metadata"]["layout_metadata"]
    assert meta["page_count"] == actual_pages
    assert meta["page_size"] == classify_page_size(actual_w, actual_h)
    assert len(meta["page_details"]) == actual_pages
    assert abs(meta["page_details"][0]["width"] - actual_w) <= 0.5
    assert abs(meta["page_details"][0]["height"] - actual_h) <= 0.5


# ---------------------------------------------------------------------------
# Test 9: Database commit failure after PDF promotion
# ---------------------------------------------------------------------------
def test_09_database_commit_failure_after_pdf_promotion(clean_db):
    """
    Simulates a database commit failure during POST /api/resumes/{id}/compile.
    Verifies that the endpoint rolls back cleanly, returns HTTP 500, and leaves
    the resume state consistent without unhandled database lock or broken session.
    """
    db = clean_db["db"]
    user_id = clean_db["user_id"]
    headers = auth_headers(user_id)

    res = client.post(
        "/api/resumes/",
        headers=headers,
        json={"title": "Commit Failure Test Resume", "template_id": "minimal_professional"}
    )
    assert res.status_code == 200
    resume_id = res.json()["id"]

    # Mock Session.commit to raise an exception on commit
    with patch("sqlalchemy.orm.Session.commit", side_effect=RuntimeError("Simulated DB commit error")):
        fail_res = client.post(f"/api/resumes/{resume_id}/compile", headers=headers)
        assert fail_res.status_code == 500
        assert "Database commit failed" in fail_res.json()["detail"]

    # Verify subsequent request succeeds and resume is still accessible
    after_res = client.get(f"/api/resumes/{resume_id}", headers=headers)
    assert after_res.status_code == 200
    assert after_res.json()["title"] == "Commit Failure Test Resume"


# ---------------------------------------------------------------------------
# Test 10: Concurrent compilation preserving correct PDF/version association
# ---------------------------------------------------------------------------
def test_10_concurrent_compilation_preserving_correct_pdf_version_association(clean_db):
    """
    Simulates concurrent compilation requests across multiple threads.
    Verifies that row-level locking (with_for_update) and atomic file promotion
    guarantee that PDF files and resume metadata remain completely consistent.
    """
    db = clean_db["db"]
    user_id = clean_db["user_id"]
    headers = auth_headers(user_id)

    res = client.post(
        "/api/resumes/",
        headers=headers,
        json={"title": "Concurrency Association Resume", "template_id": "software_engineering"}
    )
    assert res.status_code == 200
    resume_id = res.json()["id"]

    def perform_compile(page_size_param: str):
        c = TestClient(app)
        return c.post(
            f"/api/resumes/{resume_id}/compile",
            headers=headers,
            json={"page_size": page_size_param}
        )

    # Concurrently issue 4 compilation requests with alternating page sizes
    results = []
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = [
            executor.submit(perform_compile, "a4" if i % 2 == 0 else "letter")
            for i in range(4)
        ]
        for f in as_completed(futures):
            results.append(f.result())

    # All requests must complete successfully with HTTP 200
    for r in results:
        assert r.status_code == 200, f"Concurrent request failed: {r.text}"

    # Final verification on the resume record
    final_res = client.get(f"/api/resumes/{resume_id}", headers=headers)
    assert final_res.status_code == 200
    final_data = final_res.json()
    assert os.path.exists(final_data["pdf_path"])

    # Physical file dimensions must match the classified page size in metadata
    meta = final_data["structured_content"]["metadata"]["layout_metadata"]
    reader = pypdf.PdfReader(final_data["pdf_path"])
    p0 = reader.pages[0]
    expected_size = classify_page_size(float(p0.mediabox.width), float(p0.mediabox.height))
    assert meta["page_size"] == expected_size
