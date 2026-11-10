import os
import re
import time
import subprocess
import logging
import shutil
import tempfile
import uuid
from contextlib import contextmanager
from functools import wraps
from typing import Dict, Any, Tuple, Optional
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from backend.app.services.pdf_layout_validator import (
    analyze_pdf,
    validate_pdf_layout,
    determine_target_page_count,
    determine_page_size
)

from backend.app.observability.metrics import metrics as _resume_metrics

logger = logging.getLogger(__name__)

def _with_resume_metrics(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        started = time.perf_counter()
        try:
            result = func(*args, **kwargs)
        except Exception:
            _resume_metrics.inc("resume_generation_total", {"outcome": "failure"})
            _resume_metrics.observe(
                "resume_generation_duration_seconds",
                time.perf_counter() - started,
                {"outcome": "failure"},
            )
            raise
        ok = bool(result[0]) if result else False
        _resume_metrics.inc("resume_generation_total", {"outcome": "success" if ok else "failure"})
        _resume_metrics.observe(
            "resume_generation_duration_seconds",
            time.perf_counter() - started,
            {"outcome": "success" if ok else "failure"},
        )
        return result
    return wrapper

# Storage root for resume artifacts. Production uses the default; tests set
# CAREEROS_STORAGE_DIR to an isolated tmp dir before import (see tests/conftest.py).
STORAGE_DIR = os.environ.get("CAREEROS_STORAGE_DIR") or os.path.abspath(os.path.join(os.path.dirname(__file__), "../../storage/resumes"))
os.makedirs(STORAGE_DIR, exist_ok=True)

def atomic_promote_file(source_path: str, target_path: str) -> None:
    """
    Atomically promotes source_path to target_path using POSIX atomic rename (os.replace).
    Staging happens within the target directory to guarantee that rename occurs on
    the same filesystem and is executed as an atomic rename(2) syscall.
    
    If promotion fails or is interrupted, the staging temporary file is cleaned up,
    leaving any pre-existing target_path untouched.
    """
    target_dir = os.path.dirname(target_path)
    os.makedirs(target_dir, exist_ok=True)
    base_name = os.path.basename(target_path)
    staging_path = os.path.join(target_dir, f".{base_name}.{uuid.uuid4().hex}.tmp")
    
    try:
        shutil.copyfile(source_path, staging_path)
        os.replace(staging_path, target_path)
    finally:
        if os.path.exists(staging_path):
            try:
                os.remove(staging_path)
            except OSError:
                pass


class PDFPromotionTransaction:
    """
    Manages filesystem promotion with transactional rollback capability.
    Guarantees that if a database transaction aborts or fails after files have been
    promoted to their permanent storage path, the filesystem state is deterministically
    restored to its pre-promotion state.
    
    - If target file previously existed: restores the original file via atomic rename.
    - If target file did not exist (new version): removes the promoted file so no uncommitted
      artifact lingers on disk.
    - Ensures zero orphaned staging (.tmp) or backup (.backup) files upon completion or failure.
    """
    def __init__(self, target_pdf_path: str, target_tex_path: Optional[str] = None):
        self.target_pdf_path = os.path.abspath(target_pdf_path)
        self.target_tex_path = os.path.abspath(target_tex_path) if target_tex_path else None
        self.backup_pdf_path: Optional[str] = None
        self.backup_tex_path: Optional[str] = None
        self.pre_existed_pdf = os.path.exists(self.target_pdf_path)
        self.pre_existed_tex = os.path.exists(self.target_tex_path) if self.target_tex_path else False
        self.promoted = False
        self.committed = False

    def stage_and_promote(self, tmp_pdf_path: str, tmp_tex_path: Optional[str] = None) -> None:
        """
        Takes backups of pre-existing targets if present, then atomically promotes
        tmp_pdf_path (and optionally tmp_tex_path) to target paths.
        """
        target_dir = os.path.dirname(self.target_pdf_path)
        os.makedirs(target_dir, exist_ok=True)
        base_pdf = os.path.basename(self.target_pdf_path)

        # Back up existing PDF if it exists and hasn't been backed up yet
        if self.pre_existed_pdf and not self.backup_pdf_path and os.path.exists(self.target_pdf_path):
            self.backup_pdf_path = os.path.join(target_dir, f".{base_pdf}.backup.{uuid.uuid4().hex}")
            shutil.copyfile(self.target_pdf_path, self.backup_pdf_path)

        # Back up existing TeX if it exists and hasn't been backed up yet
        if self.target_tex_path and self.pre_existed_tex and not self.backup_tex_path and os.path.exists(self.target_tex_path):
            base_tex = os.path.basename(self.target_tex_path)
            self.backup_tex_path = os.path.join(target_dir, f".{base_tex}.backup.{uuid.uuid4().hex}")
            shutil.copyfile(self.target_tex_path, self.backup_tex_path)

        # Atomically promote files
        atomic_promote_file(tmp_pdf_path, self.target_pdf_path)
        if tmp_tex_path and self.target_tex_path:
            atomic_promote_file(tmp_tex_path, self.target_tex_path)

        self.promoted = True

    def commit(self) -> None:
        """Discards backup files upon successful database commit."""
        self.committed = True
        if self.backup_pdf_path and os.path.exists(self.backup_pdf_path):
            try:
                os.remove(self.backup_pdf_path)
            except OSError:
                pass
            self.backup_pdf_path = None

        if self.backup_tex_path and os.path.exists(self.backup_tex_path):
            try:
                os.remove(self.backup_tex_path)
            except OSError:
                pass
            self.backup_tex_path = None

    def rollback(self) -> None:
        """Restores filesystem to its pre-promotion state."""
        if self.committed:
            return

        if self.promoted:
            # Restore PDF
            if self.pre_existed_pdf and self.backup_pdf_path and os.path.exists(self.backup_pdf_path):
                try:
                    os.replace(self.backup_pdf_path, self.target_pdf_path)
                except OSError as e:
                    logger.error(f"Failed to restore backup PDF {self.backup_pdf_path} to {self.target_pdf_path}: {e}")
                self.backup_pdf_path = None
            else:
                if os.path.exists(self.target_pdf_path):
                    try:
                        os.remove(self.target_pdf_path)
                    except OSError as e:
                        logger.error(f"Failed to remove uncommitted PDF {self.target_pdf_path}: {e}")

            # Restore TeX
            if self.target_tex_path:
                if self.pre_existed_tex and self.backup_tex_path and os.path.exists(self.backup_tex_path):
                    try:
                        os.replace(self.backup_tex_path, self.target_tex_path)
                    except OSError as e:
                        logger.error(f"Failed to restore backup TeX {self.backup_tex_path} to {self.target_tex_path}: {e}")
                    self.backup_tex_path = None
                else:
                    if os.path.exists(self.target_tex_path):
                        try:
                            os.remove(self.target_tex_path)
                        except OSError as e:
                            logger.error(f"Failed to remove uncommitted TeX {self.target_tex_path}: {e}")

        # Ensure any leftover backup files are removed
        if self.backup_pdf_path and os.path.exists(self.backup_pdf_path):
            try:
                os.remove(self.backup_pdf_path)
            except OSError:
                pass
            self.backup_pdf_path = None

        if self.backup_tex_path and os.path.exists(self.backup_tex_path):
            try:
                os.remove(self.backup_tex_path)
            except OSError:
                pass
            self.backup_tex_path = None

        self.promoted = False

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if not self.committed:
            self.rollback()

TECTONIC_BIN = "/home/krishna/.local/bin/tectonic"
if not os.path.exists(TECTONIC_BIN):
    import shutil
    TECTONIC_BIN = shutil.which("tectonic") or "tectonic"

def escape_latex(text: Optional[str]) -> str:
    """Escapes special LaTeX characters for secure, error-free compilation."""
    if not text:
        return ""
    text = str(text)
    conv = {
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
        "~": r"\textasciitilde{}",
        "^": r"\textasciicircum{}",
        "\\": r"\textbackslash{}",
        "<": r"\textless{}",
        ">": r"\textgreater{}",
    }
    regex = re.compile("|".join(re.escape(str(key)) for key in sorted(conv.keys(), key=lambda item: -len(item))))
    return regex.sub(lambda match: conv[match.group()], text)

def build_latex_from_profile(profile_data: Dict[str, Any], template_id: str = "ats_modern") -> str:
    """Generates clean ATS-friendly LaTeX document from candidate profile data without invented information."""
    from backend.app.services.latex_templates import build_latex_template
    return build_latex_template(profile_data, template_id)


def compile_pdf_fallback_reportlab(latex_source: str, pdf_path: str, page_size: str = "letter"):
    """Compiles a clean ATS PDF via ReportLab as a deterministic offline fallback."""
    norm_ps = str(page_size).lower().strip()
    ps = A4 if norm_ps in ("a4", "a4paper") or "a4paper" in latex_source else letter
    doc = SimpleDocTemplate(
        pdf_path,
        pagesize=ps,
        rightMargin=40,
        leftMargin=40,
        topMargin=36,
        bottomMargin=36
    )
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Heading1'],
        fontSize=20,
        leading=24,
        textColor=colors.HexColor('#0f172a'),
        alignment=1,
        spaceAfter=4
    )
    
    contact_style = ParagraphStyle(
        'Contact',
        parent=styles['Normal'],
        fontSize=9,
        leading=12,
        textColor=colors.HexColor('#475569'),
        alignment=1,
        spaceAfter=10
    )
    
    sec_style = ParagraphStyle(
        'SectionHeading',
        parent=styles['Heading2'],
        fontSize=11,
        leading=14,
        textColor=colors.HexColor('#0f172a'),
        textTransform='uppercase',
        spaceBefore=8,
        spaceAfter=3
    )
    
    body_style = ParagraphStyle(
        'Body',
        parent=styles['Normal'],
        fontSize=9,
        leading=13,
        textColor=colors.HexColor('#1e293b'),
        spaceAfter=2
    )

    bullet_style = ParagraphStyle(
        'Bullet',
        parent=styles['Normal'],
        fontSize=9,
        leading=13,
        textColor=colors.HexColor('#334155'),
        leftIndent=12,
        spaceAfter=2
    )

    story = []
    
    name_match = re.search(r'\\Huge\s*\\textbf\{([^}]+)\}', latex_source)
    doc_name = name_match.group(1) if name_match else "Resume"
    story.append(Paragraph(doc_name, title_style))
    
    contact_match = re.search(r'\\begin\{center\}(.*?)\\end\{center\}', latex_source, re.DOTALL)
    if contact_match:
        c_lines = contact_match.group(1).replace(r'\\', '\n').split('\n')
        clean_contact = " | ".join([re.sub(r'\\[a-zA-Z]+(\{[^}]*\})?', '', line).strip() for line in c_lines if line.strip() and doc_name not in line])
        clean_contact = re.sub(r'[\$\\cdot\{\}]', '', clean_contact).strip(" |")
        story.append(Paragraph(clean_contact, contact_style))
    
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor('#cbd5e1'), spaceAfter=8))

    sections = re.findall(r'\\section\*\{([^}]+)\}(.*?)(?=\\section\*|\Z)', latex_source, re.DOTALL)
    for sec_title, sec_body in sections:
        story.append(Paragraph(f"<b>{sec_title.upper()}</b>", sec_style))
        story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor('#94a3b8'), spaceAfter=4))
        
        items = re.findall(r'\\item\s*(.*?)(?=\\item|\Z)', sec_body, re.DOTALL)
        if items:
            for it in items:
                clean_it = re.sub(r'\\textbf\{([^}]+)\}', r'<b>\1</b>', it)
                clean_it = re.sub(r'\\textit\{([^}]+)\}', r'<i>\1</i>', clean_it)
                clean_it = re.sub(r'\\href\{[^}]+\}\{([^}]+)\}', r'\1', clean_it)
                clean_it = re.sub(r'\\[a-zA-Z]+', '', clean_it)
                clean_it = clean_it.replace('{', '').replace('}', '').strip()
                if clean_it:
                    story.append(Paragraph(f"• {clean_it}", bullet_style))
        else:
            lines = [l.strip() for l in sec_body.split('\\\\') if l.strip()]
            for l in lines:
                clean_l = re.sub(r'\\textbf\{([^}]+)\}', r'<b>\1</b>', l)
                clean_l = re.sub(r'\\textit\{([^}]+)\}', r'<i>\1</i>', clean_l)
                clean_l = re.sub(r'\\hfill', '  -  ', clean_l)
                clean_l = re.sub(r'\\[a-zA-Z]+', '', clean_l)
                clean_l = clean_l.replace('{', '').replace('}', '').strip()
                if clean_l:
                    story.append(Paragraph(clean_l, body_style))
                    
        story.append(Spacer(1, 4))
        
    doc.build(story)

@contextmanager
def compile_in_temp_env(
    latex_source: str,
    base_name: str,
    strict: bool = False,
    page_size: Optional[str] = None
):
    """
    Compiles LaTeX in an isolated temporary directory and yields:
    (ok: bool, tmp_pdf_path: str, tmp_tex_path: str, compiler_used: str, error_message: Optional[str])
    
    The temporary directory is strictly cleaned up upon context manager exit,
    preventing any leftover files in the system temp directory.
    """
    with tempfile.TemporaryDirectory(prefix="interniq_compile_") as tmp_dir:
        tmp_tex_path = os.path.join(tmp_dir, f"{base_name}.tex")
        tmp_pdf_path = os.path.join(tmp_dir, f"{base_name}.pdf")

        with open(tmp_tex_path, "w", encoding="utf-8") as f:
            f.write(latex_source)

        compiler_used = "tectonic"
        success = False
        err_msg = None

        try:
            res = subprocess.run(
                [TECTONIC_BIN, tmp_tex_path, "-o", tmp_dir],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=15
            )
            if res.returncode == 0 and os.path.exists(tmp_pdf_path):
                analysis = analyze_pdf(tmp_pdf_path)
                if analysis.is_empty_or_malformed or analysis.page_count == 0:
                    err_msg = analysis.error_message or "Tectonic compiled an empty or malformed PDF"
                    logger.error(err_msg)
                    if strict:
                        yield (False, "", tmp_tex_path, "tectonic", err_msg)
                        return
                else:
                    success = True
                    logger.info(f"Tectonic successfully compiled {tmp_pdf_path}")
            else:
                err_msg = res.stderr or f"Tectonic exited with code {res.returncode}"
                logger.warning(f"Tectonic exit code {res.returncode}: {err_msg[:200]}.")
                if strict:
                    yield (False, "", tmp_tex_path, "tectonic", err_msg.strip())
                    return
        except FileNotFoundError:
            logger.warning(f"Tectonic binary not found at {TECTONIC_BIN}. Falling back to reportlab.")
        except Exception as e:
            logger.warning(f"Tectonic compile invocation failed: {e}.")
            if strict:
                yield (False, "", tmp_tex_path, "tectonic", str(e))
                return

        if not success:
            try:
                effective_page_size = page_size or ("a4" if "a4paper" in latex_source else "letter")
                compile_pdf_fallback_reportlab(latex_source, tmp_pdf_path, page_size=effective_page_size)
                analysis = analyze_pdf(tmp_pdf_path)
                if analysis.is_empty_or_malformed or analysis.page_count == 0:
                    err_msg = analysis.error_message or "ReportLab compiled an empty or malformed PDF"
                    logger.error(err_msg)
                    yield (False, "", tmp_tex_path, "reportlab_ats_engine", err_msg)
                    return
                compiler_used = "reportlab_ats_engine"
                success = True
                logger.info(f"ReportLab successfully compiled fallback ATS PDF {tmp_pdf_path}")
            except Exception as e:
                logger.error(f"ReportLab compilation failed: {e}", exc_info=True)
                yield (False, "", tmp_tex_path, "none", str(e))
                return

        yield (True, tmp_pdf_path, tmp_tex_path, compiler_used, None)


def compile_latex(
    latex_source: str,
    base_name: str,
    strict: bool = False,
    page_size: Optional[str] = None,
    output_dir: Optional[str] = None
) -> Tuple[bool, str, str]:
    """
    Compiles LaTeX to PDF in an isolated temporary directory to ensure concurrency safety
    and atomically promotes the artifact to destination directory (defaults to STORAGE_DIR).
    Returns (success: bool, pdf_path_or_err: str, compiler_used: str).
    """
    dest_dir = output_dir or STORAGE_DIR
    target_pdf_path = os.path.join(dest_dir, f"{base_name}.pdf")
    target_tex_path = os.path.join(dest_dir, f"{base_name}.tex")

    with compile_in_temp_env(latex_source, base_name, strict=strict, page_size=page_size) as (ok, tmp_pdf, tmp_tex, compiler, err):
        if not ok:
            return False, err or "Compilation failed", compiler
        atomic_promote_file(tmp_pdf, target_pdf_path)
        atomic_promote_file(tmp_tex, target_tex_path)
        return True, target_pdf_path, compiler


@_with_resume_metrics
def compile_and_validate_resume(
    latex_source: str,
    base_name: str,
    target_page_count: Optional[int] = None,
    structured_data: Optional[Dict[str, Any]] = None,
    template_id: str = "minimal_professional",
    strict: bool = False,
    page_size: Optional[str] = None,
    promotion_tx: Optional[PDFPromotionTransaction] = None
) -> Tuple[bool, str, str, Dict[str, Any]]:
    """
    Compiles LaTeX to PDF with layout validation and atomic promotion.
    Layout validation is strictly performed BEFORE file promotion.
    If promotion_tx is provided, promotion is staged through the transaction so the caller
    can commit or rollback alongside a database transaction.
    Returns:
        (success: bool, pdf_path_or_err: str, compiler_used: str, validation_result: Dict[str, Any])
    """
    resolved_page_size = determine_page_size(
        explicit_page_size=page_size,
        structured_data=structured_data,
        latex_content=latex_source
    )
    resolved_target = determine_target_page_count(
        template_id=template_id,
        structured_data=structured_data or {},
        explicit_target=target_page_count
    )

    with compile_in_temp_env(latex_source, base_name, strict=strict, page_size=resolved_page_size) as (ok, tmp_pdf, tmp_tex, compiler, err):
        if not ok:
            validation_result = {
                "page_count": 0,
                "target_page_count": resolved_target,
                "page_size": "Unknown",
                "target_page_size": resolved_page_size,
                "validation_status": "failed",
                "warnings": [],
                "errors": [f"Compilation failed: {err}"],
                "section_density": {},
                "diagnostics": ["Fix LaTeX syntax errors or invalid formatting to enable compilation."],
                "page_details": []
            }
            return False, err or "Compilation failed", compiler, validation_result

        # Step 2: Validate PDF layout BEFORE promoting
        validation_result = validate_pdf_layout(
            pdf_path=tmp_pdf,
            target_page_count=resolved_target,
            structured_data=structured_data,
            target_page_size=resolved_page_size
        )
        if validation_result.get("validation_status") == "failed":
            err_msg = "; ".join(validation_result.get("errors", [])) if validation_result.get("errors") else "Layout validation failed"
            return False, err_msg, compiler, validation_result

        # Step 3: Promote file only after successful compilation AND layout validation
        target_pdf_path = os.path.join(STORAGE_DIR, f"{base_name}.pdf")
        target_tex_path = os.path.join(STORAGE_DIR, f"{base_name}.tex")
        if promotion_tx:
            promotion_tx.stage_and_promote(tmp_pdf, tmp_tex)
        else:
            atomic_promote_file(tmp_pdf, target_pdf_path)
            atomic_promote_file(tmp_tex, target_tex_path)

        return True, target_pdf_path, compiler, validation_result
