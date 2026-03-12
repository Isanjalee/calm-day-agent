import html
import math
import subprocess
from datetime import datetime
from pathlib import Path
from textwrap import wrap


BROWSER_CANDIDATES = [
    Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
    Path(r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"),
    Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
]
HTML_FIRST_PAGE_HEIGHT_LIMIT = 495
HTML_OTHER_PAGE_HEIGHT_LIMIT = 640
RUNTIME_TEMP_DIR = Path(__file__).resolve().parent / ".runtime-pdf"
LEGACY_PAGE_WIDTH = 595
LEGACY_PAGE_HEIGHT = 842
LEGACY_MARGIN = 54
LEGACY_BODY_BOTTOM = 76
LEGACY_FIRST_PAGE_TOP = 680
LEGACY_OTHER_PAGE_TOP = 760
LEGACY_LINE_HEIGHT = 18
LEGACY_COLOR_INK = (0.114, 0.169, 0.165)
LEGACY_COLOR_MUTED = (0.376, 0.451, 0.42)
LEGACY_COLOR_TEAL = (0.114, 0.498, 0.451)
LEGACY_COLOR_LINE = (0.87, 0.89, 0.875)


def _escape_pdf_text(value: str) -> str:
    sanitized = (value or "").replace("\r\n", "\n").replace("\r", "\n")
    sanitized = sanitized.encode("latin-1", "replace").decode("latin-1")
    return sanitized.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _color_cmd(color: tuple[float, float, float], stroke: bool = False) -> str:
    return f"{color[0]:.3f} {color[1]:.3f} {color[2]:.3f} {'RG' if stroke else 'rg'}"


def _draw_line(x1: float, y1: float, x2: float, y2: float, color: tuple[float, float, float], width: float = 1.0) -> str:
    return f"{_color_cmd(color, stroke=True)} {width:.2f} w {x1:.2f} {y1:.2f} m {x2:.2f} {y2:.2f} l S"


def _draw_rect_stroke(x: float, y: float, width: float, height: float, color: tuple[float, float, float], line_width: float) -> str:
    return f"{_color_cmd(color, stroke=True)} {line_width:.2f} w {x:.2f} {y:.2f} {width:.2f} {height:.2f} re S"


def _text_line(
    text: str,
    x: float,
    y: float,
    *,
    font: str = "F1",
    size: int = 12,
    color: tuple[float, float, float] = LEGACY_COLOR_INK,
) -> str:
    return f"BT {_color_cmd(color)} /{font} {size} Tf 1 0 0 1 {x:.2f} {y:.2f} Tm ({_escape_pdf_text(text)}) Tj ET"


def _legacy_content_items(content: str) -> list[tuple[str, str, bool]]:
    items: list[tuple[str, str, bool]] = []
    for block in _content_to_blocks(content):
        separator_before = bool(block["summary"])
        for part in wrap(str(block["heading"]), width=52) or [""]:
            items.append((part, "F2", separator_before))
            separator_before = False
        for line in block["lines"]:
            for part in wrap(str(line), width=68) or [""]:
                items.append((part, "F1", False))
        items.append(("", "F1", False))
    if items and items[-1][0] == "":
        items.pop()
    return items


def _paginate_legacy_items(items: list[tuple[str, str, bool]]) -> list[list[tuple[str, str, bool]]]:
    first_limit = int((LEGACY_FIRST_PAGE_TOP - LEGACY_BODY_BOTTOM) / LEGACY_LINE_HEIGHT)
    other_limit = int((LEGACY_OTHER_PAGE_TOP - LEGACY_BODY_BOTTOM) / LEGACY_LINE_HEIGHT)
    if not items:
        return [[]]

    pages: list[list[tuple[str, str, bool]]] = []
    current: list[tuple[str, str, bool]] = []
    limit = first_limit
    used = 0.0

    for item in items:
        item_cost = 0.6 if not item[0] else 1.0
        if current and used + item_cost > limit:
            pages.append(current)
            current = []
            used = 0.0
            limit = other_limit
        current.append(item)
        used += item_cost

    if current:
        pages.append(current)
    return pages


def _legacy_footer(page_number: int, page_count: int) -> list[str]:
    footer_y = 46
    return [
        _draw_line(LEGACY_MARGIN, footer_y + 18, LEGACY_PAGE_WIDTH - LEGACY_MARGIN, footer_y + 18, LEGACY_COLOR_LINE, 0.8),
        _text_line("Calm Day Studio", LEGACY_MARGIN, footer_y, font="F2", size=10, color=LEGACY_COLOR_TEAL),
        _text_line(f"Learning Note | Page {page_number} of {page_count}", LEGACY_PAGE_WIDTH - LEGACY_MARGIN - 120, footer_y, font="F1", size=9, color=LEGACY_COLOR_MUTED),
    ]


def _legacy_page_commands(
    page_items: list[tuple[str, str, bool]],
    *,
    page_number: int,
    page_count: int,
    title: str,
    author_name: str,
    partner_name: str,
    generated_at: datetime,
) -> list[str]:
    commands = [
        _draw_rect_stroke(18, 18, LEGACY_PAGE_WIDTH - 36, LEGACY_PAGE_HEIGHT - 36, LEGACY_COLOR_TEAL, 0.25),
    ]

    if page_number == 1:
        commands.extend(
            [
                _text_line("CALM DAY STUDIO | Learning Note", LEGACY_MARGIN, 786, font="F2", size=11, color=LEGACY_COLOR_TEAL),
                _draw_line(LEGACY_MARGIN, 770, LEGACY_PAGE_WIDTH - LEGACY_MARGIN, 770, LEGACY_COLOR_LINE, 0.8),
                _text_line(title or "Learning Note", LEGACY_MARGIN, 738, font="F2", size=18, color=LEGACY_COLOR_INK),
                _text_line(
                    f"Prepared by {author_name} | Shared with {partner_name} | {generated_at.strftime('%B %d, %Y at %I:%M %p')}",
                    LEGACY_MARGIN,
                    714,
                    font="F1",
                    size=9,
                    color=LEGACY_COLOR_MUTED,
                ),
                _draw_line(LEGACY_MARGIN, 696, LEGACY_PAGE_WIDTH - LEGACY_MARGIN, 696, LEGACY_COLOR_LINE, 0.8),
            ]
        )

    y = LEGACY_FIRST_PAGE_TOP if page_number == 1 else LEGACY_OTHER_PAGE_TOP
    for text, font, separator_before in page_items:
        if separator_before:
            commands.append(_draw_line(LEGACY_MARGIN, y + 6, LEGACY_PAGE_WIDTH - LEGACY_MARGIN, y + 6, LEGACY_COLOR_LINE, 0.8))
            y -= LEGACY_LINE_HEIGHT * 0.45
        if text:
            size = 13 if font == "F2" else 12
            commands.append(_text_line(text, LEGACY_MARGIN, y, font=font, size=size))
            y -= LEGACY_LINE_HEIGHT
        else:
            y -= LEGACY_LINE_HEIGHT * 0.6

    commands.extend(_legacy_footer(page_number, page_count))
    return commands


def _build_stream(commands: list[str]) -> bytes:
    stream = "\n".join(commands).encode("latin-1")
    return b"<< /Length %d >>\nstream\n%s\nendstream" % (len(stream), stream)


def _build_pdf(page_streams: list[bytes]) -> bytes:
    objects: list[bytes] = []

    def add_object(content: bytes) -> int:
        objects.append(content)
        return len(objects)

    font_regular_id = add_object(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    font_bold_id = add_object(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >>")
    pages_id = add_object(b"")
    page_ids: list[int] = []

    for stream in page_streams:
        content_id = add_object(stream)
        page_id = add_object(
            (
                f"<< /Type /Page /Parent {pages_id} 0 R /MediaBox [0 0 {LEGACY_PAGE_WIDTH} {LEGACY_PAGE_HEIGHT}] "
                f"/Resources << /Font << /F1 {font_regular_id} 0 R /F2 {font_bold_id} 0 R >> >> "
                f"/Contents {content_id} 0 R >>"
            ).encode("latin-1")
        )
        page_ids.append(page_id)

    kids = " ".join(f"{page_id} 0 R" for page_id in page_ids)
    objects[pages_id - 1] = f"<< /Type /Pages /Count {len(page_ids)} /Kids [{kids}] >>".encode("latin-1")
    catalog_id = add_object(f"<< /Type /Catalog /Pages {pages_id} 0 R >>".encode("latin-1"))

    output = bytearray(b"%PDF-1.4\n%\xE2\xE3\xCF\xD3\n")
    offsets = [0]
    for index, content in enumerate(objects, start=1):
        offsets.append(len(output))
        output.extend(f"{index} 0 obj\n".encode("latin-1"))
        output.extend(content)
        output.extend(b"\nendobj\n")

    xref_offset = len(output)
    output.extend(f"xref\n0 {len(objects) + 1}\n".encode("latin-1"))
    output.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        output.extend(f"{offset:010d} 00000 n \n".encode("latin-1"))

    output.extend(
        (
            f"trailer\n<< /Size {len(objects) + 1} /Root {catalog_id} 0 R >>\n"
            f"startxref\n{xref_offset}\n%%EOF"
        ).encode("latin-1")
    )
    return bytes(output)


def _build_learning_note_pdf_legacy(
    *,
    title: str,
    content: str,
    author_name: str,
    partner_name: str,
    generated_at: datetime,
) -> bytes:
    items = _legacy_content_items(content)
    pages = _paginate_legacy_items(items)
    streams: list[bytes] = []
    for index, page_items in enumerate(pages, start=1):
        commands = _legacy_page_commands(
            page_items,
            page_number=index,
            page_count=len(pages),
            title=title,
            author_name=author_name,
            partner_name=partner_name,
            generated_at=generated_at,
        )
        streams.append(_build_stream(commands))
    return _build_pdf(streams)


def _available_browsers() -> list[Path]:
    return [candidate for candidate in BROWSER_CANDIDATES if candidate.exists()]


def _is_summary_heading(value: str) -> bool:
    normalized = " ".join((value or "").lower().split())
    return normalized.startswith("small tips for remembering")


def _content_to_blocks(value: str) -> list[dict[str, object]]:
    blocks: list[dict[str, object]] = []
    paragraphs = (value or "").replace("\r\n", "\n").replace("\r", "\n").split("\n\n")

    for paragraph in paragraphs:
        lines = [line.strip() for line in paragraph.split("\n") if line.strip()]
        if not lines:
            continue
        blocks.append(
            {
                "heading": lines[0],
                "lines": lines[1:],
                "summary": _is_summary_heading(lines[0]),
            }
        )
    return blocks


def _wrapped_line_count(value: str, width: int) -> int:
    return len(wrap(value, width=width) or [""])


def _estimate_block_height(block: dict[str, object]) -> int:
    heading = str(block["heading"])
    lines = [str(line) for line in block["lines"]]
    height = 0.0
    height += _wrapped_line_count(heading, width=52) * 18.0
    height += 4.0
    for line in lines:
        height += _wrapped_line_count(line, width=66) * 17.0
        height += 2.0
    if block["summary"]:
        height += 12.0
    height += 10.0
    return math.ceil(height)


def _paginate_html_blocks(blocks: list[dict[str, object]]) -> list[list[dict[str, object]]]:
    if not blocks:
        return [[]]

    pages: list[list[dict[str, object]]] = []
    current_page: list[dict[str, object]] = []
    current_height = 0
    limit = HTML_FIRST_PAGE_HEIGHT_LIMIT

    for block in blocks:
        block_height = _estimate_block_height(block)
        if current_page and current_height + block_height > limit:
            pages.append(current_page)
            current_page = []
            current_height = 0
            limit = HTML_OTHER_PAGE_HEIGHT_LIMIT
        current_page.append(block)
        current_height += block_height

    if current_page:
        pages.append(current_page)
    return pages


def _render_html_note_block(block: dict[str, object]) -> str:
    lines_html = "".join(f"<p>{html.escape(str(line))}</p>" for line in block["lines"])
    separator_html = '<div class="summary-separator"></div>' if block["summary"] else ""
    return (
        f"{separator_html}<section class=\"note-block\">"
        f"<h3>{html.escape(str(block['heading']))}</h3>"
        f"{lines_html}</section>"
    )


def _build_learning_note_html(
    *,
    title: str,
    content: str,
    author_name: str,
    partner_name: str,
    generated_at: datetime,
) -> str:
    blocks = _content_to_blocks(content)
    page_blocks = _paginate_html_blocks(blocks)
    metadata = " | ".join(
        [
            f"Prepared by {author_name}",
            f"Shared with {partner_name}",
            generated_at.strftime("%B %d, %Y at %I:%M %p"),
        ]
    )

    page_html: list[str] = []
    page_count = len(page_blocks)
    for index, blocks_on_page in enumerate(page_blocks, start=1):
        content_html = "".join(_render_html_note_block(block) for block in blocks_on_page)
        if not content_html:
            content_html = '<section class="note-block"><p></p></section>'

        header_html = ""
        if index == 1:
            header_html = (
                '<div class="topline">CALM DAY STUDIO | Learning Note</div>'
                '<div class="separator"></div>'
                f'<h1 class="title">{html.escape(title or "Learning Note")}</h1>'
                f'<div class="meta">{html.escape(metadata)}</div>'
                '<div class="meta-separator"></div>'
            )

        page_html.append(
            f"""
    <section class="page">
      <div class="page-frame">
        <div class="page-body">
          {header_html}
          <div class="content">{content_html}</div>
        </div>
        <div class="footer">
          <div class="footer-brand"><span class="footer-mark"></span><span>Calm Day Studio</span></div>
          <div>Learning Note | Page {index} of {page_count}</div>
        </div>
      </div>
    </section>"""
        )

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>{html.escape(title or "Learning Note")}</title>
  <style>
    @page {{
      size: A4;
      margin: 0;
    }}
    * {{
      box-sizing: border-box;
    }}
    html, body {{
      margin: 0;
      padding: 0;
      background: #edf1ec;
      color: #1d2b2a;
      font-family: "Nirmala UI", "Segoe UI", "Segoe UI Symbol", sans-serif;
      font-size: 12pt;
      line-height: 1.45;
      -webkit-font-smoothing: antialiased;
    }}
    .page {{
      width: 210mm;
      min-height: 297mm;
      padding: 12mm;
      background: #fdfbf8;
      break-after: page;
      page-break-after: always;
    }}
    .page:last-child {{
      break-after: auto;
      page-break-after: auto;
    }}
    .page-frame {{
      border: 0.25pt solid #1d7f73;
      padding: 12mm 10mm 10mm 10mm;
      min-height: 273mm;
      display: flex;
      flex-direction: column;
      background: #fdfbf8;
    }}
    .page-body {{
      flex: 1 1 auto;
    }}
    .topline {{
      font-size: 11pt;
      font-weight: 700;
      color: #12594f;
      white-space: nowrap;
      letter-spacing: 0.01em;
      margin-bottom: 10px;
    }}
    .separator {{
      border-top: 0.75pt solid #dbe2dc;
      margin: 0 0 22px 0;
    }}
    .title {{
      font-size: 22pt;
      line-height: 1.2;
      font-weight: 700;
      margin: 0 0 10px 0;
      color: #1d2b2a;
    }}
    .meta {{
      font-size: 9pt;
      color: #5e736b;
      white-space: nowrap;
      margin: 0 0 12px 0;
    }}
    .meta-separator {{
      border-top: 0.75pt solid #dbe2dc;
      margin: 0;
    }}
    .content {{
      margin-top: 0;
      padding-top: 8pt;
    }}
    .note-block {{
      margin: 0 0 14pt 0;
      break-inside: avoid;
      page-break-inside: avoid;
    }}
    .summary-separator {{
      border-top: 0.75pt solid #dbe2dc;
      margin: 0 0 8pt 0;
    }}
    .note-block h3 {{
      margin: 0 0 4px 0;
      font-size: 14pt;
      line-height: 1.3;
      font-weight: 700;
      color: #1d2b2a;
    }}
    .note-block p {{
      margin: 0 0 2px 0;
      color: #263635;
    }}
    .footer {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-top: 12pt;
      padding-top: 8pt;
      border-top: 0.75pt solid #dbe2dc;
      color: #5e736b;
      font-size: 9pt;
    }}
    .footer-brand {{
      display: flex;
      align-items: center;
      gap: 8px;
      color: #12594f;
      font-weight: 600;
    }}
    .footer-mark {{
      position: relative;
      width: 18px;
      height: 12px;
      flex: 0 0 18px;
    }}
    .footer-mark::before,
    .footer-mark::after {{
      content: "";
      position: absolute;
      border-radius: 999px;
    }}
    .footer-mark::before {{
      width: 9px;
      height: 9px;
      left: 0;
      top: 1px;
      background: #ecc55d;
    }}
    .footer-mark::after {{
      width: 8px;
      height: 8px;
      left: 9px;
      top: 2px;
      background: #cfe1ec;
      box-shadow: 3px 0 0 #fdfbf8;
    }}
  </style>
</head>
<body>
  {''.join(page_html)}
</body>
</html>"""


def build_learning_note_pdf(
    *,
    title: str,
    content: str,
    author_name: str,
    partner_name: str,
    generated_at: datetime | None = None,
) -> bytes:
    browsers = _available_browsers()
    can_fallback_legacy = True
    try:
        "".join([title or "", content or "", author_name or "", partner_name or ""]).encode("latin-1")
    except UnicodeEncodeError:
        can_fallback_legacy = False

    if not browsers:
        if can_fallback_legacy:
            return _build_learning_note_pdf_legacy(
                title=title,
                content=content,
                author_name=author_name,
                partner_name=partner_name,
                generated_at=generated_at or datetime.now(),
            )
        raise RuntimeError("Microsoft Edge or Google Chrome is required to generate the PDF.")

    html_text = _build_learning_note_html(
        title=title,
        content=content,
        author_name=author_name,
        partner_name=partner_name,
        generated_at=generated_at or datetime.now(),
    )

    RUNTIME_TEMP_DIR.mkdir(exist_ok=True)
    html_path = RUNTIME_TEMP_DIR / "learning-note.html"
    pdf_path = RUNTIME_TEMP_DIR / "learning-note.pdf"

    try:
        html_path.write_text(html_text, encoding="utf-8")
        errors: list[str] = []
        for browser in browsers:
            profile_dir = RUNTIME_TEMP_DIR / f"{browser.stem.lower()}-profile"
            profile_dir.mkdir(exist_ok=True)
            pdf_path.unlink(missing_ok=True)
            result = subprocess.run(
                [
                    str(browser),
                    "--headless",
                    "--disable-gpu",
                    "--disable-crash-reporter",
                    "--disable-breakpad",
                    "--no-first-run",
                    "--no-default-browser-check",
                    "--no-pdf-header-footer",
                    f"--user-data-dir={profile_dir}",
                    f"--print-to-pdf={pdf_path}",
                    html_path.resolve().as_uri(),
                ],
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
            if result.returncode == 0 and pdf_path.exists():
                return pdf_path.read_bytes()

            stderr = (result.stderr or result.stdout or "").strip() or str(result.returncode)
            errors.append(f"{browser.name}: {stderr}")

        if can_fallback_legacy:
            return _build_learning_note_pdf_legacy(
                title=title,
                content=content,
                author_name=author_name,
                partner_name=partner_name,
                generated_at=generated_at or datetime.now(),
            )

        raise RuntimeError("PDF rendering failed: " + " | ".join(errors))
    finally:
        html_path.unlink(missing_ok=True)
        pdf_path.unlink(missing_ok=True)
