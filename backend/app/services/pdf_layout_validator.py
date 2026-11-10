import os
import re
import math
import logging
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, asdict
import pypdf

logger = logging.getLogger(__name__)

# Tolerance in points for paper size classification
TOLERANCE_PT = 15.0

# Standard dimensions in points (72 points = 1 inch)
# Letter: 8.5 x 11 inches -> 612 x 792 pt
# A4: 210 x 297 mm -> 595.28 x 841.89 pt
LETTER_WIDTH, LETTER_HEIGHT = 612.0, 792.0
A4_WIDTH, A4_HEIGHT = 595.28, 841.89


@dataclass
class PDFPageInfo:
    page_number: int
    width: float
    height: float
    page_size: str
    char_count: int
    word_count: int
    has_text: bool


@dataclass
class PDFAnalysisResult:
    page_count: int
    page_dimensions: List[Dict[str, Any]]
    page_size: str
    is_empty_or_malformed: bool
    pages: List[PDFPageInfo]
    total_char_count: int
    total_word_count: int
    has_inconsistent_dimensions: bool
    trailing_page_empty: bool
    trailing_page_sparse: bool
    error_message: Optional[str] = None


def classify_page_size(width: float, height: float) -> str:
    """Classifies page dimensions into standard formats (Letter, A4, or Custom)."""
    # Check portrait
    if abs(width - LETTER_WIDTH) <= TOLERANCE_PT and abs(height - LETTER_HEIGHT) <= TOLERANCE_PT:
        return "Letter"
    if abs(width - A4_WIDTH) <= TOLERANCE_PT and abs(height - A4_HEIGHT) <= TOLERANCE_PT:
        return "A4"
    # Check landscape
    if abs(width - LETTER_HEIGHT) <= TOLERANCE_PT and abs(height - LETTER_WIDTH) <= TOLERANCE_PT:
        return "Letter (Landscape)"
    if abs(width - A4_HEIGHT) <= TOLERANCE_PT and abs(height - A4_WIDTH) <= TOLERANCE_PT:
        return "A4 (Landscape)"
    return "Custom"


def analyze_pdf(pdf_path: str) -> PDFAnalysisResult:
    """
    Extracts physical dimensions, page count, and text volume from a compiled PDF.
    Deterministic inspection using pypdf.
    """
    if not pdf_path or not os.path.exists(pdf_path):
        return PDFAnalysisResult(
            page_count=0,
            page_dimensions=[],
            page_size="Unknown",
            is_empty_or_malformed=True,
            pages=[],
            total_char_count=0,
            total_word_count=0,
            has_inconsistent_dimensions=False,
            trailing_page_empty=False,
            trailing_page_sparse=False,
            error_message="PDF file does not exist on disk"
        )

    if os.path.getsize(pdf_path) == 0:
        return PDFAnalysisResult(
            page_count=0,
            page_dimensions=[],
            page_size="Unknown",
            is_empty_or_malformed=True,
            pages=[],
            total_char_count=0,
            total_word_count=0,
            has_inconsistent_dimensions=False,
            trailing_page_empty=False,
            trailing_page_sparse=False,
            error_message="PDF file is 0 bytes"
        )

    try:
        reader = pypdf.PdfReader(pdf_path)
        num_pages = len(reader.pages)
        if num_pages == 0:
            return PDFAnalysisResult(
                page_count=0,
                page_dimensions=[],
                page_size="Unknown",
                is_empty_or_malformed=True,
                pages=[],
                total_char_count=0,
                total_word_count=0,
                has_inconsistent_dimensions=False,
                trailing_page_empty=False,
                trailing_page_sparse=False,
                error_message="PDF contains 0 pages"
            )

        pages_info: List[PDFPageInfo] = []
        dimensions_list: List[Dict[str, Any]] = []

        total_chars = 0
        total_words = 0

        for idx, page in enumerate(reader.pages):
            page_num = idx + 1
            w = float(page.mediabox.width)
            h = float(page.mediabox.height)
            size_name = classify_page_size(w, h)

            try:
                raw_text = page.extract_text() or ""
            except Exception:
                raw_text = ""

            cleaned_text = raw_text.strip()
            char_count = len(cleaned_text)
            words = [w for w in cleaned_text.split() if w]
            word_count = len(words)

            total_chars += char_count
            total_words += word_count

            page_info = PDFPageInfo(
                page_number=page_num,
                width=round(w, 2),
                height=round(h, 2),
                page_size=size_name,
                char_count=char_count,
                word_count=word_count,
                has_text=char_count > 0
            )
            pages_info.append(page_info)
            dimensions_list.append({
                "page": page_num,
                "width": page_info.width,
                "height": page_info.height,
                "page_size": size_name
            })

        # Dimension consistency check
        distinct_dimensions = {(p.width, p.height) for p in pages_info}
        has_inconsistent_dims = len(distinct_dimensions) > 1

        # Global page size classification
        if has_inconsistent_dims:
            doc_page_size = "Inconsistent"
        else:
            doc_page_size = pages_info[0].page_size

        # Trailing page checks (only relevant if multiple pages)
        trailing_empty = False
        trailing_sparse = False
        if num_pages > 1:
            last_page = pages_info[-1]
            if last_page.char_count == 0:
                trailing_empty = True
            elif last_page.char_count < 120 and last_page.word_count < 20 and pages_info[0].char_count > 200:
                trailing_sparse = True

        return PDFAnalysisResult(
            page_count=num_pages,
            page_dimensions=dimensions_list,
            page_size=doc_page_size,
            is_empty_or_malformed=False,
            pages=pages_info,
            total_char_count=total_chars,
            total_word_count=total_words,
            has_inconsistent_dimensions=has_inconsistent_dims,
            trailing_page_empty=trailing_empty,
            trailing_page_sparse=trailing_sparse
        )

    except Exception as e:
        logger.warning(f"Failed to parse PDF {pdf_path}: {e}")
        return PDFAnalysisResult(
            page_count=0,
            page_dimensions=[],
            page_size="Unknown",
            is_empty_or_malformed=True,
            pages=[],
            total_char_count=0,
            total_word_count=0,
            has_inconsistent_dimensions=False,
            trailing_page_empty=False,
            trailing_page_sparse=False,
            error_message=f"Malformed PDF: {str(e)}"
        )


def estimate_content_density(structured_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Deterministic pre-compilation content density estimator.
    Calculates section counts and estimated line usage based on standard 10pt ATS styling.
    """
    if not structured_data:
        return {
            "section_counts": {},
            "estimated_lines": 0,
            "estimated_pages": 1,
            "overflow_risk_sections": []
        }

    # Extract sections
    summary = structured_data.get("summary") or ""
    edu_list = structured_data.get("education") or structured_data.get("education_entries") or []
    skills_list = structured_data.get("skills") or []
    exp_list = structured_data.get("experience") or structured_data.get("experiences") or []
    proj_list = structured_data.get("projects") or []
    cert_list = structured_data.get("certifications") or []
    ach_list = structured_data.get("achievements") or []
    pub_list = structured_data.get("publications") or []

    # Count bullet items
    exp_bullets = 0
    for exp in exp_list:
        if isinstance(exp, dict):
            bullets = exp.get("bullets", [])
            exp_bullets += len(bullets) if bullets else (1 if exp.get("description") else 0)

    proj_bullets = 0
    for proj in proj_list:
        if isinstance(proj, dict):
            bullets = proj.get("bullets", [])
            proj_bullets += len(bullets) if bullets else (1 if proj.get("description") else 0)

    summary_words = len(summary.split()) if summary else 0

    section_counts = {
        "summary_words": summary_words,
        "education_entries": len(edu_list),
        "skill_categories": len(skills_list),
        "experience_entries": len(exp_list),
        "experience_bullets": exp_bullets,
        "project_entries": len(proj_list),
        "project_bullets": proj_bullets,
        "certifications": len(cert_list),
        "achievements": len(ach_list),
        "publications": len(pub_list)
    }

    # Estimate line footprint (approximate lines of output in 10pt with 0.6in margins)
    # Header: Name, Contact lines -> ~4 lines
    lines = 4.0

    # Summary: Section title (1.5) + text lines (~16 words/line)
    if summary_words > 0:
        lines += 1.5 + max(1.0, summary_words / 16.0)

    # Education: Section title (1.5) + ~2 lines per institution
    if edu_list:
        lines += 1.5 + len(edu_list) * 2.0

    # Skills: Section title (1.5) + ~1.5 lines per category
    if skills_list:
        lines += 1.5 + max(1.0, len(skills_list) * 1.5)

    # Experience: Section title (1.5) + entry header (2.0 per role) + bullets (1.5 per bullet)
    if exp_list:
        lines += 1.5 + (len(exp_list) * 2.0) + (exp_bullets * 1.5)

    # Projects: Section title (1.5) + project header (2.0 per project) + bullets (1.5 per bullet)
    if proj_list:
        lines += 1.5 + (len(proj_list) * 2.0) + (proj_bullets * 1.5)

    # Certifications: Section title (1.5) + 1 line per cert
    if cert_list:
        lines += 1.5 + len(cert_list) * 1.0

    # Achievements: Section title (1.5) + 1 line per achievement
    if ach_list:
        lines += 1.5 + len(ach_list) * 1.0

    # Publications: Section title (1.5) + 1.2 lines per publication
    if pub_list:
        lines += 1.5 + len(pub_list) * 1.2

    # Standard Letter page accommodates roughly 48-52 lines
    lines_per_page = 50.0
    estimated_pages = max(1, math.ceil(lines / lines_per_page))

    # Identify sections contributing heavily to overflow
    overflow_risks = []
    if exp_bullets >= 6 or len(exp_list) >= 3:
        overflow_risks.append(f"Experience ({len(exp_list)} roles, {exp_bullets} bullets)")
    if proj_bullets >= 6 or len(proj_list) >= 3:
        overflow_risks.append(f"Projects ({len(proj_list)} projects, {proj_bullets} bullets)")
    if summary_words > 80:
        overflow_risks.append(f"Summary ({summary_words} words)")
    if len(cert_list) + len(ach_list) >= 6:
        overflow_risks.append(f"Certifications & Honors ({len(cert_list) + len(ach_list)} items)")

    return {
        "section_counts": section_counts,
        "estimated_lines": round(lines, 1),
        "estimated_pages": estimated_pages,
        "overflow_risk_sections": overflow_risks
    }


def determine_target_page_count(
    template_id: str,
    structured_data: Dict[str, Any],
    explicit_target: Optional[int] = None
) -> int:
    """
    Determines the target page count deterministically:
    1. Explicit override (from request parameter or structured metadata).
    2. Template specific rule (fresher_student -> 1, experience_focused -> 2).
    3. Candidate experience count (>= 2 roles -> 2 pages, otherwise 1 page).
    """
    if explicit_target is not None and explicit_target > 0:
        return explicit_target

    # Check for metadata override in structured content
    meta = structured_data.get("metadata") or {}
    if isinstance(meta, dict) and meta.get("target_page_count"):
        try:
            return int(meta["target_page_count"])
        except (ValueError, TypeError):
            pass

    # Template-based defaults
    if template_id == "fresher_student":
        return 1
    if template_id == "experience_focused":
        return 2

    # Experience heuristic: experienced candidates default to 2 pages, new grads default to 1
    exps = structured_data.get("experience") or structured_data.get("experiences") or []
    if len(exps) >= 2:
        return 2

    return 1


def determine_page_size(
    explicit_page_size: Optional[str] = None,
    structured_data: Optional[Dict[str, Any]] = None,
    latex_content: Optional[str] = None,
    profile_location: Optional[str] = None
) -> str:
    """
    Deterministically resolves page size ("letter" or "a4") following this priority hierarchy:
    1. Explicitly requested page size (from query parameter or request body).
    2. Structured content metadata ("metadata.page_size" or top-level "page_size").
    3. Inspection of existing raw LaTeX content (presence of "a4paper" -> "a4", "letterpaper" -> "letter").
    4. Location heuristic: candidate location containing US/Canada -> "letter".
    5. Default: International standard "a4".
    """
    # 1. Explicit request
    if explicit_page_size and str(explicit_page_size).strip():
        norm = str(explicit_page_size).lower().strip()
        if norm in ("a4", "a4paper"):
            return "a4"
        if norm in ("letter", "letterpaper"):
            return "letter"

    # 2. Structured data metadata
    if structured_data and isinstance(structured_data, dict):
        meta = structured_data.get("metadata")
        if isinstance(meta, dict) and meta.get("page_size"):
            norm = str(meta["page_size"]).lower().strip()
            if norm in ("a4", "a4paper"):
                return "a4"
            if norm in ("letter", "letterpaper"):
                return "letter"
        top_ps = structured_data.get("page_size")
        if top_ps:
            norm = str(top_ps).lower().strip()
            if norm in ("a4", "a4paper"):
                return "a4"
            if norm in ("letter", "letterpaper"):
                return "letter"

    # 3. Existing LaTeX source inspection
    if latex_content and isinstance(latex_content, str):
        if "a4paper" in latex_content:
            return "a4"
        if "letterpaper" in latex_content:
            return "letter"

    # 4. Location heuristic
    loc_to_check = profile_location
    if not loc_to_check and structured_data and isinstance(structured_data, dict):
        pi = structured_data.get("personal_info")
        if isinstance(pi, dict):
            loc_to_check = pi.get("location")
        elif not loc_to_check:
            loc_to_check = structured_data.get("location")

    if loc_to_check and isinstance(loc_to_check, str):
        loc_lower = loc_to_check.lower()
        us_indicators = ["united states", "usa", "canada", ", us", "u.s.", "u.s.a."]
        if any(ind in loc_lower for ind in us_indicators):
            return "letter"
        # State abbreviations check with word boundaries
        if re.search(r'\b(US|USA|CA|NY|TX|WA|IL|MA|FL|GA|NC|VA|NJ|PA|OH|MI|CO|AZ)\b', loc_to_check):
            return "letter"

    # 5. International standard default
    return "a4"


def validate_pdf_layout(
    pdf_path: str,
    target_page_count: int,
    structured_data: Optional[Dict[str, Any]] = None,
    target_page_size: Optional[str] = None
) -> Dict[str, Any]:
    """
    Validates PDF layout and page budgeting against the target page count.
    Distinguishes hard errors (corrupt/empty PDF) from actionable warnings (page overflow, sparse trailing page).
    """
    analysis = analyze_pdf(pdf_path)
    data = structured_data or {}
    density = estimate_content_density(data)

    errors: List[str] = []
    warnings: List[str] = []
    diagnostics: List[str] = []

    # 1. Hard Failures
    if analysis.is_empty_or_malformed:
        errors.append(analysis.error_message or "Compiled PDF is empty or malformed.")
    elif analysis.page_count == 0:
        errors.append("Compiled PDF contains 0 pages.")
    elif analysis.total_char_count == 0:
        errors.append("Compiled PDF contains no readable text content.")

    # Dimension Consistency check (checked for any multi-page document)
    if analysis.has_inconsistent_dimensions:
        warnings.append(
            "Document contains pages with inconsistent physical dimensions or mixed orientations."
        )

    # 2. Page Count Budgeting
    if not errors:
        if analysis.page_count > target_page_count:
            diff = analysis.page_count - target_page_count
            warnings.append(
                f"Resume exceeds target budget of {target_page_count} page(s) (actual: {analysis.page_count} page(s))."
            )
            if density.get("overflow_risk_sections"):
                top_sections = ", ".join(density["overflow_risk_sections"])
                diagnostics.append(
                    f"Sections contributing most to overflow: {top_sections}. Consider shortening bullets or pruning older entries."
                )

        # 3. Trailing Page Quality
        if analysis.trailing_page_empty:
            warnings.append(
                f"Page {analysis.page_count} is an empty trailing page. Trailing whitespace or spacing forced a blank page."
            )
            diagnostics.append(
                "Remove excessive trailing vspace or trailing items to eliminate the empty final page."
            )
        elif analysis.trailing_page_sparse:
            last_page = analysis.pages[-1]
            warnings.append(
                f"Page {analysis.page_count} is suspiciously sparse ({last_page.char_count} characters, {last_page.word_count} words)."
            )
            diagnostics.append(
                f"Content barely spilled onto Page {analysis.page_count}. Condensing 1–2 bullets will fit the resume cleanly on {analysis.page_count - 1} page(s)."
            )

        # 4. Target Page Size Verification
        if target_page_size:
            norm_expected = "a4" if "a4" in str(target_page_size).lower() else "letter"
            norm_detected = "a4" if "a4" in str(analysis.page_size).lower() else ("letter" if "letter" in str(analysis.page_size).lower() else "other")
            if norm_detected != norm_expected:
                warnings.append(
                    f"Compiled PDF page size ({analysis.page_size}) does not match configured target page size ({target_page_size.upper()})."
                )

        # 5. Missing Expected Sections Check
        if data:
            # Read text via reader
            try:
                reader = pypdf.PdfReader(pdf_path)
                all_text = " ".join([page.extract_text() or "" for page in reader.pages]).lower()
            except Exception:
                all_text = ""

            exps = data.get("experience") or data.get("experiences") or []
            if exps and ("experience" not in all_text and "employment" not in all_text and "work" not in all_text):
                warnings.append("Expected 'Experience' section appears to be missing or unrendered in the output.")

            projs = data.get("projects") or []
            if projs and ("project" not in all_text and "systems" not in all_text):
                warnings.append("Expected 'Projects' section appears to be missing or unrendered in the output.")

            edus = data.get("education") or data.get("education_entries") or []
            if edus and ("education" not in all_text and "academic" not in all_text):
                warnings.append("Expected 'Education' section appears to be missing or unrendered in the output.")

    # Determine overall status
    if errors:
        status = "failed"
    elif warnings:
        status = "warning"
    else:
        status = "passed"

    return {
        "page_count": analysis.page_count,
        "target_page_count": target_page_count,
        "page_size": analysis.page_size,
        "target_page_size": target_page_size,
        "validation_status": status,
        "warnings": warnings,
        "errors": errors,
        "section_density": density,
        "diagnostics": diagnostics,
        "page_details": [asdict(p) for p in analysis.pages]
    }
