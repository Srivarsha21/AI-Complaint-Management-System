"""Complaint report as a landscape A4 PDF (ReportLab).

Layout: title, generation time (IST), scope and applied filters, summary
counts, then the complaint table. The table header repeats on every page and
each page carries a "Page X of Y" footer.

Limitation: the built-in Helvetica font covers Latin text only; subjects
written in other scripts (e.g. Telugu) are not rendered correctly.
"""

from io import BytesIO
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.lib.utils import simpleSplit
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.reports.common import PRIORITY_LABELS, STATUS_LABELS, ReportData, format_ist

PAGE_SIZE = landscape(A4)
MARGIN = 12 * mm
HEADER_BG = colors.HexColor("#312e81")
STRIPE_BG = colors.HexColor("#f1f5f9")
GRID = colors.HexColor("#cbd5e1")

_styles = getSampleStyleSheet()
TITLE = ParagraphStyle("ReportTitle", parent=_styles["Title"], fontSize=16, leading=20, alignment=0, spaceAfter=2)
META = ParagraphStyle("ReportMeta", parent=_styles["Normal"], fontSize=9, leading=12, textColor=colors.HexColor("#334155"))
HEADING = ParagraphStyle(
    "ReportHeading", parent=_styles["Heading3"], fontName="Helvetica-Bold", fontSize=11, leading=14,
    spaceBefore=6, spaceAfter=4,
)
CELL = ParagraphStyle("Cell", parent=_styles["Normal"], fontSize=7.5, leading=9)
HEAD_CELL = ParagraphStyle("HeadCell", parent=CELL, fontName="Helvetica-Bold", textColor=colors.white)
NOTE = ParagraphStyle("Note", parent=META, textColor=colors.HexColor("#9a3412"))


def _p(text: str | None, style: ParagraphStyle = CELL) -> Paragraph:
    # User-supplied text must be escaped: Paragraph interprets XML-like markup.
    return Paragraph(escape(text or ""), style)


class _NumberedCanvas(Canvas):
    """Defers page output so the footer can show the total page count."""

    footer_text = ""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._pages: list[dict] = []

    def showPage(self):  # noqa: N802 (ReportLab API)
        self._pages.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        total = len(self._pages)
        for state in self._pages:
            self.__dict__.update(state)
            self._draw_footer(total)
            super().showPage()
        super().save()

    def _draw_footer(self, total: int) -> None:
        self.saveState()
        self.setFont("Helvetica", 8)
        self.setFillColor(colors.HexColor("#64748b"))
        self.drawString(MARGIN, 7 * mm, self.footer_text)
        self.drawRightString(PAGE_SIZE[0] - MARGIN, 7 * mm, f"Page {self._pageNumber} of {total}")
        self.restoreState()


def _columns(include_complainant: bool) -> list[tuple[str, float]]:
    usable = PAGE_SIZE[0] - 2 * MARGIN - 2 * FRAME_PADDING
    cols = [
        ("Reference", 27 * mm),
        ("Subject", 0),  # takes the remaining width
        ("Category", 28 * mm),
        ("Department", 30 * mm),
        ("Priority", 21 * mm),
        ("Status", 19 * mm),
    ]
    if include_complainant:
        cols.append(("Complainant", 28 * mm))
    cols += [("Created (IST)", 21 * mm), ("Resolved / closed (IST)", 21 * mm)]
    fixed = sum(width for _, width in cols)
    return [(name, width or usable - fixed) for name, width in cols]


def _summary_table(pairs: list[tuple[str, int]], heading: str) -> Table:
    data = [[_p(heading, HEAD_CELL), _p("Count", HEAD_CELL)]] + [[_p(label), str(count)] for label, count in pairs]
    table = Table(data, colWidths=[55 * mm, 20 * mm], hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), HEADER_BG),
                ("GRID", (0, 0), (-1, -1), 0.4, GRID),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("ALIGN", (1, 1), (1, -1), "RIGHT"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]
        )
    )
    return table


# Default Table cell paddings (left/right 6pt) plus the top/bottom padding set below.
CELL_PAD_X = 6
CELL_PAD_Y = 3
PLAIN_LEADING = 9
BODY_FONT, BODY_SIZE = "Helvetica", 7.5
FRAME_PADDING = 6  # SimpleDocTemplate frames have 6pt padding on every side
PAGE_FILL = 0.95
CELL_DATE = "%d %b %Y\n%H:%M"  # two lines keep the date columns narrow  # keep a safety margin so a page-sized chunk never needs splitting


def _wrap(text: str | None, width: float) -> str:
    """Pre-wrapped plain text. Much faster than Paragraph cells, and drawn literally (no markup)."""
    return "\n".join(simpleSplit(text or "", BODY_FONT, BODY_SIZE, width - 2 * CELL_PAD_X))


def _row_height(cells: list, widths: list[float]) -> float:
    height = PLAIN_LEADING
    for cell, width in zip(cells, widths):
        if isinstance(cell, Paragraph):
            height = max(height, cell.wrap(width - 2 * CELL_PAD_X, 10_000)[1])
        else:
            height = max(height, (str(cell).count("\n") + 1) * PLAIN_LEADING)
    return height + 2 * CELL_PAD_Y


def _flowable_height(flowable, width: float, height: float) -> float:
    return flowable.wrap(width, height)[1] + flowable.getSpaceBefore() + flowable.getSpaceAfter()


def _paginate(rows: list[list], header: list, widths: list[float], first_page: float, page: float) -> list[list[list]]:
    """Split rows into page-sized chunks.

    One huge table that ReportLab splits page by page re-measures all remaining
    rows on every page (quadratic: ~50 s for 5000 rows). Measuring each row once
    and emitting one table per page keeps large exports fast. An empty first
    chunk means the table starts on a new page.
    """
    header_height = _row_height(header, widths)
    budget = first_page * PAGE_FILL
    chunks: list[list[list]] = [[]]
    used = header_height
    for cells in rows:
        height = _row_height(cells, widths)
        if used + height > budget and (chunks[-1] or budget < page * PAGE_FILL):
            chunks.append([])
            used, budget = header_height, page * PAGE_FILL
        chunks[-1].append(cells)
        used += height
    return chunks


def _complaint_table(header: list, rows: list[list], widths: list[float], *, empty: bool = False) -> Table:
    # repeatRows keeps the header if an estimate is ever off and a chunk must split.
    table = Table([header, *rows], colWidths=widths, repeatRows=1)
    style = [
        ("BACKGROUND", (0, 0), (-1, 0), HEADER_BG),
        ("GRID", (0, 0), (-1, -1), 0.4, GRID),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("FONTNAME", (0, 1), (-1, -1), BODY_FONT),
        ("FONTSIZE", (0, 1), (-1, -1), BODY_SIZE),
        ("LEADING", (0, 1), (-1, -1), PLAIN_LEADING),
        ("TOPPADDING", (0, 0), (-1, -1), CELL_PAD_Y),
        ("BOTTOMPADDING", (0, 0), (-1, -1), CELL_PAD_Y),
    ]
    style += [("BACKGROUND", (0, i), (-1, i), STRIPE_BG) for i in range(2, len(rows) + 1, 2)]
    if empty:
        style.append(("SPAN", (0, 1), (-1, 1)))
    table.setStyle(TableStyle(style))
    return table


def build_pdf(report: ReportData) -> bytes:
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=PAGE_SIZE,
        leftMargin=MARGIN,
        rightMargin=MARGIN,
        topMargin=MARGIN,
        bottomMargin=14 * mm,
        title=report.title,
        author="ResolveAI",
        subject="Complaint report",
    )

    generated = format_ist(report.generated_at, "%d %b %Y %H:%M IST")
    story: list = [
        _p(report.title, TITLE),
        _p(f"Generated: {generated}", META),
        _p(f"Scope: {report.scope_label}", META),
    ]
    filters = "; ".join(f"{label}: {value}" for label, value in report.filters) or "None (all complaints in scope)"
    story.append(_p(f"Filters: {filters}", META))
    story.append(_p(f"Matching complaints: {report.total_matching:,}. Rows in this report: {len(report.rows):,}.", META))
    if report.truncation_note:
        story.append(_p(report.truncation_note, NOTE))

    story.append(Spacer(1, 4 * mm))
    summary = Table(
        [[_summary_table(report.status_counts, "Status"), _summary_table(report.category_counts or [("-", 0)], "Category")]],
        hAlign="LEFT",
    )
    summary.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0)]))
    story += [_p("Summary", HEADING), summary]
    story.append(Spacer(1, 4 * mm))
    story.append(_p("Complaints", HEADING))

    columns = _columns(report.include_complainant)
    widths = [w for _, w in columns]
    header = [_p(name, HEAD_CELL) for name, _ in columns]
    rows: list[list] = []
    width_of = dict(columns)
    for row in report.rows:
        cells = [
            row.reference_number,
            _wrap(row.subject, width_of["Subject"]),
            _wrap(row.category, width_of["Category"]),
            _wrap(row.department or "Unassigned", width_of["Department"]),
            PRIORITY_LABELS.get(row.priority, row.priority or ""),
            STATUS_LABELS.get(row.status, row.status),
        ]
        if report.include_complainant:
            cells.append(_wrap(row.complainant, width_of["Complainant"]))
        cells += [format_ist(row.created_at, CELL_DATE), format_ist(row.resolved_at or row.closed_at, CELL_DATE)]
        rows.append(cells)

    if not rows:
        story.append(_complaint_table(header, [[_p("No complaints match these filters.")] + [""] * (len(columns) - 1)],
                                      widths, empty=True))
    else:
        frame_width, frame_height = doc.width - 2 * FRAME_PADDING, doc.height - 2 * FRAME_PADDING
        used = sum(_flowable_height(f, frame_width, frame_height) for f in story)
        chunks = _paginate(rows, header, widths, frame_height - used, frame_height)
        if not chunks[0]:  # not even one row fits under the summary: start on a new page
            chunks = chunks[1:]
            story.append(PageBreak())
        for index, chunk in enumerate(chunks):
            if index > 0:
                story.append(PageBreak())
            story.append(_complaint_table(header, chunk, widths))

    # A per-report subclass keeps the footer text local to this request.
    canvas_cls = type("_ReportCanvas", (_NumberedCanvas,), {"footer_text": f"{report.title} - generated {generated}"})
    doc.build(story, canvasmaker=canvas_cls)
    return buffer.getvalue()
