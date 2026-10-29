import io
import re
import statistics
from collections import Counter

import pdfplumber

DOT_LEADERS = re.compile(r"(\.\s?){6,}")
# list items: bullets, "(a)", "iv.", "1)", "2.3"
LIST_MARKER = re.compile(r"^([•\-–*▪◦]|\(?\w{1,4}[.)]|\d+(\.\d+)+)\s")
EDGE_LINES = 3  # lines at the top and bottom of a page checked for headers and footers
# all 3 picked by eye and only checked against the MARP PDFs
REPEAT_SHARE = 0.6 # # share of pages a top/bottom line must repeat on to be a header or footer
SHORT_LINE_SHARE = 0.15  # a line ending this far short of the right edge ends its paragraph
PARAGRAPH_GAP = 1.5  # a vertical gap this many times the usual line gap starts a new paragraph


def extract_pages(pdf_bytes):
    # page_count is the PDF's real length, before cleanup drops any pages
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        raw = [
            {"page": n, "lines": page_lines(page)}
            for n, page in enumerate(pdf.pages, start=1)
        ]
    return clean_pages(raw), len(raw)


def page_lines(page):
    # text lines of a page, with each table as one entry in reading order
    tables = []
    for table in page.find_tables():
        text = table_text(table.extract())
        if text:
            tables.append((table.bbox, text))
    if tables:
        # keep table cells out of the line extraction, they are added back as rows
        page = page.filter(
            lambda obj: obj["object_type"] != "char"
            or not any(inside(obj, bbox) for bbox, _ in tables)
        )
    lines = page.extract_text_lines(strip=True, return_chars=False)
    for (x0, top, x1, bottom), text in tables:
        lines.append(
            {"text": text, "x0": x0, "x1": x1, "top": top, "bottom": bottom, "table": True}
        )
    return sorted(lines, key=lambda l: l["top"])


def inside(char, bbox):
    x0, top, x1, bottom = bbox
    center_x = (char["x0"] + char["x1"]) / 2
    center_y = (char["top"] + char["bottom"]) / 2
    return x0 <= center_x <= x1 and top <= center_y <= bottom


def table_text(rows):
    # one line per row with the cells split by " | "; merged cells come back empty, so skipped
    lines = []
    for row in merge_continuation_rows(rows):
        cells = [" ".join((cell or "").split()) for cell in row]
        lines.append(" | ".join(c for c in cells if c))
    lines = [l for l in lines if l]
    has_columns = any(" | " in l for l in lines)
    if len(lines) < 2 or not has_columns:
        return ""
    return "\n".join(lines)


def merge_continuation_rows(rows):
    # a cell that wraps over several lines can come back as extra rows starting with None
    merged = []
    for row in rows:
        if merged and row and row[0] is None:
            for i, cell in enumerate(row):
                if cell and i < len(merged[-1]):
                    merged[-1][i] = f"{merged[-1][i] or ''} {cell}"
        else:
            merged.append(list(row))
    return merged


def clean_pages(pages):
    # drops headers, footers and contents pages, and rejoins wrapped lines;
    # page numbers stay as in the PDF, so a dropped page leaves a gap
    headers = repeated_keys(pages, top_lines)
    footers = repeated_keys(pages, bottom_lines)
    cleaned = []
    for page in pages:
        lines = [l for l in page["lines"] if l["text"].strip()]
        if sum(1 for l in lines if DOT_LEADERS.search(l["text"])) >= 5:
            continue  # contents page
        text = join_wrapped_lines(strip_running_lines(lines, headers, footers))
        if text:
            cleaned.append({"page": page["page"], "text": text})
    return cleaned


def line_key(line):
    # page numbers change from page to page, so digits are masked
    return re.sub(r"\d+", "#", line["text"].strip()).lower()


def top_lines(lines):
    # at most half the page, so a short page's body is never taken for a header
    return lines[: min(EDGE_LINES, len(lines) // 2)]


def bottom_lines(lines):
    # same half-page cap as top_lines
    return lines[len(lines) - min(EDGE_LINES, len(lines) // 2) :]


def repeated_keys(pages, pick):
    # needs a few pages before "repeated" means anything
    if len(pages) < 3:
        return set()
    counts = Counter()
    for page in pages:
        lines = [l for l in page["lines"] if l["text"].strip()]
        counts.update({line_key(l) for l in pick(lines)})
    return {key for key, n in counts.items() if n >= len(pages) * REPEAT_SHARE}


def strip_running_lines(lines, headers, footers):
    start, end = 0, len(lines)
    for line in top_lines(lines):
        if line_key(line) not in headers:
            break
        start += 1
    for line in reversed(bottom_lines(lines)):
        if line_key(line) not in footers:
            break
        end -= 1
    return lines[start:end]


def join_wrapped_lines(lines):
    # tables stay as they are, and only the text between them is rejoined
    parts, run = [], []
    for line in lines:
        if line.get("table"):
            parts += [join_text_lines(run), line["text"]]
            run = []
        else:
            run.append(line)
    parts.append(join_text_lines(run))
    return "\n".join(p for p in parts if p)


def join_text_lines(lines):
    if not lines:
        return ""
    left = min(l["x0"] for l in lines)
    right = max(l["x1"] for l in lines)
    gaps = [b["top"] - a["bottom"] for a, b in zip(lines, lines[1:]) if b["top"] > a["bottom"]]
    usual_gap = statistics.median(gaps) if gaps else 0

    paragraphs = [lines[0]["text"].strip()]
    for prev, line in zip(lines, lines[1:]):
        text = line["text"].strip()
        short = prev["x1"] < right - SHORT_LINE_SHARE * (right - left)
        gap = usual_gap > 0 and line["top"] - prev["bottom"] > usual_gap * PARAGRAPH_GAP
        if short or gap or LIST_MARKER.match(text):
            paragraphs.append(text)
        else:
            paragraphs[-1] += " " + text
    return "\n".join(paragraphs)
