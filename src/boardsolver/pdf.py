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
correctly; the colour-emoji level markers in the warnings table are
replaced with coloured bullets, which DejaVu does cover.
"""

import argparse
import os
import re
import sys

from PIL import Image as PILImage

FONT_DIR_CANDIDATES = (
    "/usr/share/fonts/truetype/dejavu",
    "/usr/local/share/fonts/truetype/dejavu",
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
    """Convert a small Markdown subset to ReportLab paragraph markup."""
    text = _xml_escape(text)
    # Colour-emoji level markers -> semantic words (DejaVu has no emoji,
    # and a colour alone is not a meaningful label). The coloured bullet
    # is kept only as a secondary visual cue; the word carries the meaning.
    text = text.replace("\U0001f534", '<font color="#c00000">\u25cf</font> ERROR')
    text = text.replace("\U0001f7e1", '<font color="#b88600">\u25cf</font> WARNING')
    # Bold first, then italic, then inline code.
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"`([^`]+)`", r'<font face="DejaVuSansMono">\1</font>', text)
    # Remaining single-* spans (whole-line italics are handled by the caller
    # stripping the outer pair first, so this only catches inline italics).
    text = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<i>\1</i>", text)
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


def build_pdf(md_path, out_path):
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import LETTER
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.platypus import (
        Image as RLImage,
        PageBreak,
        Paragraph,
        SimpleDocTemplate,
        Spacer,
        Table,
        TableStyle,
    )

    for family, fname in (
        ("DejaVuSans", "DejaVuSans.ttf"),
        ("DejaVuSans-Bold", "DejaVuSans-Bold.ttf"),
        ("DejaVuSansMono", "DejaVuSansMono.ttf"),
    ):
        path = _find_font(fname)
        if path:
            pdfmetrics.registerFont(TTFont(family, path))
    if "DejaVuSans-Bold" in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFontFamily(
            "DejaVuSans", normal="DejaVuSans", bold="DejaVuSans-Bold",
            italic="DejaVuSans", boldItalic="DejaVuSans-Bold",
        )
    base_font = "DejaVuSans" if "DejaVuSans" in pdfmetrics.getRegisteredFontNames() else "Helvetica"

    page_w, page_h = LETTER
    avail_w = page_w - 1.2 * inch
    styles = {
        "h1": ParagraphStyle("h1", fontName=base_font + "-Bold" if base_font != "Helvetica" else "Helvetica-Bold",
                             fontSize=20, leading=24, spaceAfter=10),
        "h2": ParagraphStyle("h2", fontName=base_font + "-Bold" if base_font != "Helvetica" else "Helvetica-Bold",
                             fontSize=14, leading=17, spaceBefore=14, spaceAfter=6),
        "h3": ParagraphStyle("h3", fontName=base_font + "-Bold" if base_font != "Helvetica" else "Helvetica-Bold",
                             fontSize=11.5, leading=14, spaceBefore=10, spaceAfter=4),
        "p": ParagraphStyle("p", fontName=base_font, fontSize=10, leading=13.5, spaceAfter=6),
        "cell": ParagraphStyle("cell", fontName=base_font, fontSize=8.5, leading=11),
        "cellhead": ParagraphStyle("cellhead", fontName=base_font + "-Bold" if base_font != "Helvetica" else "Helvetica-Bold",
                                   fontSize=8.5, leading=11),
    }

    md_dir = os.path.dirname(os.path.abspath(md_path))
    story = []
    for kind, value in parse_md(md_path):
        if kind == "h1":
            story.append(Paragraph(md_inline_to_xml(value), styles["h1"]))
        elif kind == "h2":
            story.append(Paragraph(md_inline_to_xml(value), styles["h2"]))
        elif kind == "h3":
            story.append(Paragraph(md_inline_to_xml(value), styles["h3"]))
        elif kind == "p":
            story.append(Paragraph(md_inline_to_xml(value), styles["p"]))
        elif kind == "image":
            alt, rel = value
            img_path = os.path.join(md_dir, rel)
            if not os.path.exists(img_path):
                story.append(Paragraph(f"[missing image: {alt} ({rel})]", styles["p"]))
                continue
            with PILImage.open(img_path) as im:
                iw, ih = im.size
            scale = min(avail_w / iw, 8.0 * inch / ih, 1.0)
            # Do not upscale small diagrams; cap tall diagrams by height.
            w, h = iw * scale, ih * scale
            story.append(RLImage(img_path, width=w, height=h))
            story.append(Spacer(1, 8))
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
            t = Table(data, colWidths=widths, repeatRows=1)
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

    doc = SimpleDocTemplate(
        out_path, pagesize=LETTER,
        leftMargin=0.6 * inch, rightMargin=0.6 * inch,
        topMargin=0.6 * inch, bottomMargin=0.6 * inch,
        title=os.path.basename(md_dir) or "Cut Plan",
    )
    doc.build(story)
    return out_path


def main(argv=None):
    ap = argparse.ArgumentParser(description="Render a generated plan MD folder to PDF.")
    ap.add_argument("--md", help="path to plan README.md")
    ap.add_argument("--project", help="project dir containing plan/README.md")
    ap.add_argument("--out", required=True, help="output PDF path")
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
    build_pdf(md_path, args.out)
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
