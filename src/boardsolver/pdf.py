"""Plan Markdown -> PDF, reading the docwriter's output only.

Reads a generated plan folder (README.md + images/*.png) and renders a
printable PDF: headings, paragraphs, Markdown tables, and every diagram
image in place, in order. It never touches the docwriter, renderer, or
any plan-generation code -- it is a pure post-processing step.

Optional dependency: reportlab (pure Python). It is NOT a hard runtime
dependency of the package and is NOT added to pyproject.toml; install it
into the fork's .venv (``.venv/bin/pip install reportlab``) before
running ``./run.sh pdf <project>``. DejaVuSans / DejaVuSans-Bold from
the system font directory are registered so Unicode fractions
(1/4, 1/2, 3/4, superscript fractions), prime marks, and dashes render
correctly. Warning levels and types arrive from the MD already as
words (ERROR/WARNING/NOTE, "Ghost Boards", etc.); this module renders
them faithfully and does not transform their content.
"""

import argparse
import os
import re
import sys

from PIL import Image as PILImage

FONT_DIR_CANDIDATES = (
    "/usr/share/fonts/truetype/dejavu",
    "/usr/local/share/fonts/truetype/dejavu",
    # DejaVuSans-Oblique lives here on this VM; without it, <i> maps
    # to the normal font and italics do not actually slant in the PDF.
    "/usr/share/matplotlib/mpl-data/fonts/ttf",
)


def _find_font(name):
    for d in FONT_DIR_CANDIDATES:
        p = os.path.join(d, name)
        if os.path.exists(p):
            return p
    return None


def _xml_escape(text):
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def md_inline_to_xml(text):
    """Convert a small Markdown subset to ReportLab paragraph markup.

    No content transformation, except one: every warning glyph gets a
    yellow background, bold, wherever it appears — headings, body
    paragraphs, and table cells alike. The MD is otherwise the visual
    representation, so levels and types already arrive as words
    (ERROR/WARNING/NOTE, "Ghost Boards", etc.) from document.py.
    This function only handles bold/italic/code markup otherwise.
    """
    text = _xml_escape(text)
    # Bold first, then italic, then inline code.
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"`([^`]+)`", r'<font face="DejaVuSansMono">\1</font>', text)
    # Remaining single-* spans (whole-line italics are handled by the caller
    # stripping the outer pair first, so this only catches inline italics).
    text = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<i>\1</i>", text)
    text = re.sub(
        r"⚠\ufe0f?",
        '<font backColor="#FFFF00"><b>⚠</b></font>',
        text)
    return text


def parse_md(path):
    """Yield ('h1'|'h2'|'h3'|'p'|'table'|'image', value) blocks, in order."""
    with open(path, encoding="utf-8") as fh:
        lines = fh.read().splitlines()
    i = 0
    while i < len(lines):
        line = lines[i].rstrip()
        if not line.strip():
            i += 1
            continue
        if line.startswith("# "):
            yield ("h1", line[2:].strip())
            i += 1
            continue
        if line.startswith("## "):
            yield ("h2", line[3:].strip())
            i += 1
            continue
        if line.startswith("### "):
            yield ("h3", line[4:].strip())
            i += 1
            continue
        img = re.match(r"!\[([^\]]*)\]\(([^)]+)\)", line)
        if img:
            yield ("image", (img.group(1), img.group(2)))
            i += 1
            continue
        if line.startswith("|"):
            rows = []
            while i < len(lines) and lines[i].startswith("|"):
                cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                # Skip the | --- | separator row.
                if all(set(c) <= set("-: ") and "-" in c for c in cells):
                    i += 1
                    continue
                rows.append(cells)
                i += 1
            if rows:
                yield ("table", rows)
            continue
        # Paragraph: whole-line *italic* or _italic_ notes lose their markers.
        text = line.strip()
        if len(text) >= 2 and text[0] == text[-1] and text[0] in "*_":
            text = text[1:-1]
        yield ("p", text)
        i += 1


def build_pdf(md_path, out_path, finished_width_in: float = 2.1):
    """Render a plan MD folder to PDF.

    ``finished_width_in`` is the desired display width, in inches, of
    the Finished board pattern image only. At the old behaviour it
    scaled to the full page width (about 7.3") and about 7" tall --
    almost an entire page for a pattern overview. Other diagrams keep
    the old behaviour (full available width, capped by height, never
    upscaled). Pass a larger value to scale the finished board up,
    a smaller value to scale it down.
    """
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import LETTER
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.platypus import (
        BaseDocTemplate,
        Frame,
        Image as RLImage,
        PageBreak,
        PageTemplate,
        Paragraph,
        Spacer,
        Table,
        TableStyle,
    )

    for family, fname in (
        ("DejaVuSans", "DejaVuSans.ttf"),
        ("DejaVuSans-Bold", "DejaVuSans-Bold.ttf"),
        ("DejaVuSansMono", "DejaVuSansMono.ttf"),
        ("DejaVuSans-Oblique", "DejaVuSans-Oblique.ttf"),
    ):
        path = _find_font(fname)
        if path:
            pdfmetrics.registerFont(TTFont(family, path))
    if "DejaVuSans-Bold" in pdfmetrics.getRegisteredFontNames():
        italic = ("DejaVuSans-Oblique"
                  if "DejaVuSans-Oblique" in pdfmetrics.getRegisteredFontNames()
                  else "DejaVuSans")
        pdfmetrics.registerFontFamily(
            "DejaVuSans", normal="DejaVuSans", bold="DejaVuSans-Bold",
            italic=italic, boldItalic="DejaVuSans-Bold",
        )
    base_font = "DejaVuSans" if "DejaVuSans" in pdfmetrics.getRegisteredFontNames() else "Helvetica"

    page_w, page_h = LETTER
    avail_w = page_w - 1.2 * inch
    styles = {
        "h1": ParagraphStyle("h1", fontName=base_font + "-Bold" if base_font != "Helvetica" else "Helvetica-Bold",
                             fontSize=20, leading=24, spaceAfter=10, leftIndent=0, rightIndent=0),
        "h2": ParagraphStyle("h2", fontName=base_font + "-Bold" if base_font != "Helvetica" else "Helvetica-Bold",
                             fontSize=14, leading=17, spaceBefore=14, spaceAfter=6, leftIndent=0, rightIndent=0),
        "h3": ParagraphStyle("h3", fontName=base_font + "-Bold" if base_font != "Helvetica" else "Helvetica-Bold",
                             fontSize=11.5, leading=14, spaceBefore=10, spaceAfter=4, leftIndent=0, rightIndent=0),
        "p": ParagraphStyle("p", fontName=base_font, fontSize=10, leading=13.5, spaceAfter=6, leftIndent=0, rightIndent=0),
        "cell": ParagraphStyle("cell", fontName=base_font, fontSize=8.5, leading=11),
        "cellhead": ParagraphStyle("cellhead", fontName=base_font + "-Bold" if base_font != "Helvetica" else "Helvetica-Bold",
                                   fontSize=8.5, leading=11),
    }

    md_dir = os.path.dirname(os.path.abspath(md_path))
    story = []

    def _img_size(alt, img_path):
        with PILImage.open(img_path) as im:
            iw, ih = im.size
        if alt == "Finished board" and finished_width_in:
            w = min(finished_width_in * inch, avail_w)
            h = w * ih / iw
        else:
            scale = min(avail_w / iw, 8.0 * inch / ih, 1.0)
            w, h = iw * scale, ih * scale
        if alt.startswith("Panel face"):
            # Panel faces display at 75% of their current size in the PDF
            # (native image files are unchanged).
            w, h = w * 0.75, h * 0.75
        return w, h

    def _flush_images(group):
        """Render a run of consecutive images: a single image as before,
        a run as flow rows that pack left to right, wrapping when the
        next item would exceed the available width. A legend image in
        the run is rendered centered below the flow rows, not in them.
        Left-aligned rows (not centered) keep crosscut bars and other
        wide primitives aligned with the tables above them."""
        if not group:
            return
        legends = [(a, p) for a, p in group if "legend" in a.lower()]
        items = [(a, p) for a, p in group if "legend" not in a.lower()]
        if len(items) == 1 and not legends:
            alt, img_path = items[0]
            if not os.path.exists(img_path):
                story.append(Paragraph(f"[missing image: {alt}]", styles["p"]))
                return
            w, h = _img_size(alt, img_path)
            story.append(RLImage(img_path, width=w, height=h))
            story.append(Spacer(1, 8))
            return
        # Flow rows. No gap between images of the same type: each
        # primitive already carries its own pad margin inside the image
        # (white, so it bleeds into the page), and an extra inter-image
        # gap on top of that reads as too much white space.
        gap = 0
        row, row_w = [], 0
        rows = []
        for alt, img_path in items:
            if not os.path.exists(img_path):
                story.append(Paragraph(f"[missing image: {alt}]", styles["p"]))
                continue
            w, h = _img_size(alt, img_path)
            need = w + (gap if row else 0)
            if row and row_w + need > avail_w:
                rows.append(row)
                row, row_w = [], 0
                need = w
            row.append((img_path, w, h))
            row_w += need
        if row:
            rows.append(row)
        for row in rows:
            cells = [RLImage(p, width=w, height=h) for p, w, h in row]
            widths = [w + (gap if i < len(row) - 1 else 0) for i, (_, w, _) in enumerate(row)]
            # Panel end-grain and panel-face rows are centered; all
            # other flow rows (crosscut, cut boards) stay left-aligned.
            _alts = [a for a, _ in items]
            _center = all(a.startswith("Panel —") or a.startswith("Panel face") for a in _alts)
            t = Table([cells], colWidths=widths, hAlign="CENTER" if _center else "LEFT")
            t.setStyle(TableStyle([
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ]))
            story.append(t)
        for alt, img_path in legends:
            if not os.path.exists(img_path):
                continue
            w, h = _img_size(alt, img_path)
            img = RLImage(img_path, width=w, height=h)
            img.hAlign = "CENTER"
            story.append(img)
            story.append(Spacer(1, 8))

    _img_group: list = []
    for kind, value in parse_md(md_path):
        if kind == "image":
            _alt, _rel = value
            _img_group.append((_alt, os.path.join(md_dir, _rel)))
            continue
        _flush_images(_img_group)
        _img_group = []
        if kind == "h1":
            story.append(Paragraph(md_inline_to_xml(value), styles["h1"]))
        elif kind == "h2":
            story.append(Paragraph(md_inline_to_xml(value), styles["h2"]))
        elif kind == "h3":
            story.append(Paragraph(md_inline_to_xml(value), styles["h3"]))
        elif kind == "p":
            story.append(Paragraph(md_inline_to_xml(value), styles["p"]))
        elif kind == "table":
            rows = value
            ncols = max(len(r) for r in rows)
            rows = [r + [""] * (ncols - len(r)) for r in rows]
            # Column widths must always sum to the available page width --
            # a table wider than the page is what made earlier PDFs look
            # oddly shaped. Each column starts at its longest single token
            # (so e.g. "small_margin" and "WARNING" do not wrap), capped so
            # one long column cannot eat the page; remaining width is shared
            # proportionally to longest-cell length. If even the capped
            # minimums exceed the page, scale everything down proportionally
            # rather than overflowing -- wrapping a long token is better
            # than a table running off the page.
            from reportlab.pdfbase.pdfmetrics import stringWidth
            font = styles["cell"].fontName
            min_w = []
            for c in range(ncols):
                longest_token = max(
                    (stringWidth(tok, font, 8.5) for r in rows for tok in r[c].split()),
                    default=0,
                )
                min_w.append(min(1.6 * inch, max(0.45 * inch, longest_token + 10)))
            maxlen = [max(len(r[c]) for r in rows) for c in range(ncols)]
            total = sum(maxlen) or 1
            remaining = avail_w - sum(min_w)
            if remaining > 0:
                widths = [m + remaining * (l / total) for m, l in zip(min_w, maxlen)]
                # Cap any single column, then renormalise to the page width.
                widths = [min(w, 2.8 * inch) for w in widths]
                s = sum(widths)
                if s > 0:
                    widths = [w * avail_w / s for w in widths]
            else:
                s = sum(min_w)
                widths = [w * avail_w / s for w in min_w] if s > 0 else min_w
            data = []
            for ri, row in enumerate(rows):
                style = styles["cellhead"] if ri == 0 else styles["cell"]
                data.append([Paragraph(md_inline_to_xml(c), style) for c in row])
            t = Table(data, colWidths=widths, repeatRows=1, hAlign="LEFT")
            t.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e8e8e8")),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#999999")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]))
            story.append(t)
            story.append(Spacer(1, 8))

    _flush_images(_img_group)

    # Frame padding must be 0: the default 6 pt padding (used by
    # SimpleDocTemplate) left tables starting 6 pt left of titles
    # and body text, and text wrapping short of tables on the right.
    # With padding 0, tables, titles, and body text all share the
    # same 0.6 in left and right margins.
    doc = BaseDocTemplate(
        out_path, pagesize=LETTER,
        leftMargin=0.6 * inch, rightMargin=0.6 * inch,
        topMargin=0.6 * inch, bottomMargin=0.6 * inch,
        title=os.path.basename(md_dir) or "Cut Plan",
    )
    frame = Frame(0.6 * inch, 0.6 * inch, avail_w, page_h - 1.2 * inch,
                  id="main", leftPadding=0, rightPadding=0,
                  topPadding=0, bottomPadding=0)
    doc.addPageTemplates([PageTemplate(id="main", frames=[frame], pagesize=LETTER)])
    doc.build(story)
    return out_path


def main(argv=None):
    ap = argparse.ArgumentParser(description="Render a generated plan MD folder to PDF.")
    ap.add_argument("--md", help="path to plan README.md")
    ap.add_argument("--project", help="project dir containing plan/README.md")
    ap.add_argument("--out", required=True, help="output PDF path")
    ap.add_argument("--finished-width-inches", type=float, default=2.1,
                    help="display width in inches of the Finished board pattern (default 2.1)")
    args = ap.parse_args(argv)
    if args.md:
        md_path = args.md
    elif args.project:
        md_path = os.path.join(args.project, "plan", "README.md")
    else:
        ap.error("one of --md or --project is required")
    if not os.path.exists(md_path):
        print(f"error: no plan MD at {md_path}", file=sys.stderr)
        return 2
    try:
        import reportlab  # noqa: F401
    except ImportError:
        print("error: reportlab is not installed; run .venv/bin/pip install reportlab",
              file=sys.stderr)
        return 2
    out_dir = os.path.dirname(os.path.abspath(args.out))
    os.makedirs(out_dir, exist_ok=True)
    build_pdf(md_path, args.out, finished_width_in=args.finished_width_inches)
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
