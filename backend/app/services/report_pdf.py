"""PDF export of a viva session report (questions, transcripts, scores, advisory authenticity)."""

from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from fpdf import FPDF

from app.core.config import settings
from app.core.logging import logger
from app.models.session import VivaSession
from app.models.turn import Turn

ADVISORY_NOTE = (
    "Authenticity results are ADVISORY ONLY: indicators to prompt a conversation with the student, "
    "not evidence of misconduct. They never change scores automatically."
)

# (regular, bold) Unicode TTF pairs tried in order; core Helvetica is the last resort.
FONT_CANDIDATES: Sequence[Tuple[str, str]] = (
    ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
    ("C:/Windows/Fonts/arial.ttf", "C:/Windows/Fonts/arialbd.ttf"),
    ("/Library/Fonts/Arial Unicode.ttf", "/Library/Fonts/Arial Unicode.ttf"),
)


def _find_font() -> Optional[Tuple[str, str]]:
    if settings.PDF_FONT_PATH:
        regular = Path(settings.PDF_FONT_PATH)
        bold = regular.with_name(regular.stem + "-Bold" + regular.suffix)
        return str(regular), str(bold if bold.exists() else regular)
    for regular_path, bold_path in FONT_CANDIDATES:
        if Path(regular_path).exists():
            return regular_path, bold_path if Path(bold_path).exists() else regular_path
    return None


class _ReportPDF(FPDF):
    def __init__(self) -> None:
        super().__init__(format="A4")
        self.set_margins(18, 18, 18)
        self.set_auto_page_break(auto=True, margin=18)
        font = _find_font()
        if font:
            self.add_font("Body", "", font[0])
            self.add_font("Body", "B", font[1])
            self._body_family = "Body"
            self._body_unicode = True
        else:
            logger.warning(
                "No Unicode TTF font found for PDF export; non-Latin text will be replaced. Set PDF_FONT_PATH."
            )
            self._body_family = "Helvetica"
            self._body_unicode = False

    def clean(self, text: Any) -> str:
        value = "" if text is None else str(text)
        # Core fonts only cover Latin-1; replace what they cannot draw instead of failing.
        return value if self._body_unicode else value.encode("latin-1", "replace").decode("latin-1")

    def use_font(self, size: float, bold: bool = False) -> None:
        self.set_font(self._body_family, "B" if bold else "", size)

    def para(self, text: Any, size: float = 10, bold: bool = False, gap: float = 1.5) -> None:
        self.use_font(size, bold)
        self.multi_cell(0, size * 0.5, self.clean(text), new_x="LMARGIN", new_y="NEXT")
        self.ln(gap)

    def label_value(self, label: str, value: Any) -> None:
        self.use_font(9, bold=True)
        self.cell(42, 5.5, self.clean(label))
        self.use_font(9)
        self.multi_cell(0, 5.5, self.clean(value), new_x="LMARGIN", new_y="NEXT")

    def footer(self) -> None:
        self.set_y(-12)
        self.use_font(7.5)
        self.set_text_color(110, 110, 110)
        self.cell(0, 5, self.clean(f"VivaIQ report. Authenticity is advisory only. Page {self.page_no()}"), align="C")
        self.set_text_color(0, 0, 0)


def _fmt_score(score: Optional[float]) -> str:
    return f"{score:.1f} / 10" if score is not None else "Not graded"


def _fmt_conf(confidence: Optional[float]) -> str:
    return f"{round(confidence * 100)}%" if confidence is not None else "n/a"


def _sources(refs: Optional[List[Dict[str, Any]]]) -> str:
    out = []
    for ref in refs or []:
        name = ref.get("source") or ref.get("filename") or ref.get("document_id") or "source"
        page = ref.get("page")
        out.append(f"{name} (p. {page})" if page else str(name))
    return "; ".join(out)


def build_session_pdf(session: VivaSession, turns: Sequence[Turn]) -> bytes:
    """Render a session report. `session.student` and `session.subject` must be loaded."""
    pdf = _ReportPDF()
    pdf.set_title(f"Viva report {session.id}")
    pdf.set_author("VivaIQ")
    pdf.add_page()

    pdf.para("Viva Voce Examination Report", size=18, bold=True, gap=3)
    pdf.label_value("Student", session.student.full_name if session.student else "Unknown")
    pdf.label_value("Subject", f"{session.subject.code}: {session.subject.name}" if session.subject else "Unknown")
    pdf.label_value("Date", session.created_at.strftime("%d %b %Y, %H:%M") if session.created_at else "")
    pdf.label_value("Status", session.status.value)
    pdf.label_value("Recording consent", "Given" if session.recording_consent else "Not given")
    pdf.label_value("Overall score", _fmt_score(session.total_score))
    pdf.ln(3)

    # Advisory panel: shaded box so it cannot be mistaken for a verdict.
    pdf.set_fill_color(255, 246, 225)
    pdf.use_font(9, bold=True)
    pdf.multi_cell(
        0,
        5,
        pdf.clean(
            f"Advisory authenticity: {session.overall_authenticity_likelihood.value.upper()} "
            f"(confidence {_fmt_conf(session.overall_authenticity_confidence)})"
        ),
        fill=True,
        new_x="LMARGIN",
        new_y="NEXT",
    )
    pdf.use_font(8.5)
    reasons = session.overall_authenticity_reasons or []
    body = "\n".join(f"- {r}" for r in reasons) if reasons else "No reasons recorded."
    pdf.multi_cell(0, 4.5, pdf.clean(f"{body}\n\n{ADVISORY_NOTE}"), fill=True, new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)

    if session.teacher_notes:
        pdf.para("Teacher notes", size=11, bold=True, gap=1)
        pdf.para(session.teacher_notes, size=9.5, gap=4)

    pdf.para(f"Questions ({len(turns)})", size=13, bold=True, gap=2)
    for turn in sorted(turns, key=lambda t: t.turn_number):
        pdf.para(f"Q{turn.turn_number}. {turn.question_text}", size=10.5, bold=True, gap=1)
        pdf.label_value("Type / topic", f"{turn.question_type} / {turn.topic}")
        pdf.label_value(
            "Score", "Warm-up (not scored)" if turn.question_type == "warmup" else _fmt_score(turn.score_0_10)
        )
        rubric = turn.rubric_breakdown or {}
        dims = [f"{k} {rubric[k]}" for k in ("correctness", "completeness", "clarity", "depth") if k in rubric]
        if dims:
            pdf.label_value("Rubric", ", ".join(dims))
        pdf.label_value("Answer", turn.transcript or "Not answered")
        if turn.feedback:
            pdf.label_value("Feedback", turn.feedback)
        missing = rubric.get("missing_points") or []
        if missing:
            pdf.label_value("Missing points", "; ".join(missing))
        pdf.label_value(
            "Authenticity",
            f"{turn.authenticity_likelihood.value} (advisory, confidence {_fmt_conf(turn.authenticity_confidence)})",
        )
        if turn.authenticity_reasons:
            pdf.label_value("Reasons", "; ".join(turn.authenticity_reasons))
        if turn.source_references:
            pdf.label_value("Sources", _sources(turn.source_references))
        pdf.label_value("Prompt version", turn.prompt_version)
        pdf.ln(3)

    return bytes(pdf.output())
