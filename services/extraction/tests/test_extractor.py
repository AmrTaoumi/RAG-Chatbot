from pathlib import Path

import pytest
from pdfminer.pdfparser import PDFSyntaxError

from extractor import clean_pages, extract_pages, join_wrapped_lines, table_text

SAMPLE = Path(__file__).parent / "fixtures" / "sample.pdf"
TABLE = Path(__file__).parent / "fixtures" / "table.pdf"


def test_extract_pages_returns_numbered_pages():
    pages, page_count = extract_pages(SAMPLE.read_bytes())
    assert page_count == 2
    assert [p["page"] for p in pages] == [1, 2]
    assert pages[0]["text"] == "Page one text"
    assert pages[1]["text"] == "Page two text"


def test_extract_pages_rejects_non_pdf():
    with pytest.raises(PDFSyntaxError):
        extract_pages(b"not a pdf")


def line(text, top, x1=500, x0=72):
    return {"text": text, "x0": x0, "x1": x1, "top": top, "bottom": top + 10}


def page(number, *lines):
    return {"page": number, "lines": list(lines)}


def body_page(number, text="Body text of the page."):
    return page(
        number,
        line("Acme Handbook", 20),
        line(text, 100),
        line(f"Page {number} of 5", 760),
    )


def test_clean_pages_strips_repeated_header_and_footer_with_changing_numbers():
    pages = [body_page(n, f"Unique content {n}.") for n in range(1, 6)]
    cleaned = clean_pages(pages)
    assert [p["text"] for p in cleaned] == [f"Unique content {n}." for n in range(1, 6)]


def test_clean_pages_keeps_text_when_too_few_pages_to_spot_repeats():
    cleaned = clean_pages([body_page(1), body_page(2)])
    assert "Acme Handbook" in cleaned[0]["text"]


def test_clean_pages_drops_contents_page_but_keeps_page_numbers():
    contents = page(2, *[line(f"Section {i} {'.' * 30} {i}", 100 + 12 * i) for i in range(6)])
    cleaned = clean_pages([body_page(1, "Cover."), contents, body_page(3, "Real text.")])
    assert [p["page"] for p in cleaned] == [1, 3]


def test_clean_pages_omits_page_without_text():
    cleaned = clean_pages([page(1), body_page(2, "Some text.")])
    assert [p["page"] for p in cleaned] == [2]


def test_join_wrapped_lines_joins_full_width_lines():
    text = join_wrapped_lines(
        [line("The quick brown fox jumps", 100), line("over the lazy dog.", 112, x1=300)]
    )
    assert text == "The quick brown fox jumps over the lazy dog."


def test_join_wrapped_lines_breaks_after_short_line():
    text = join_wrapped_lines(
        [line("A short heading", 100, x1=200), line("Body starts here and runs on", 112)]
    )
    assert text == "A short heading\nBody starts here and runs on"


def test_join_wrapped_lines_breaks_on_list_markers():
    text = join_wrapped_lines(
        [
            line("Items include:", 100),
            line("(a) first item that is long", 112),
            line("• second item that is long", 124),
        ]
    )
    assert text.split("\n") == [
        "Items include:",
        "(a) first item that is long",
        "• second item that is long",
    ]


def test_join_wrapped_lines_breaks_on_larger_vertical_gap():
    text = join_wrapped_lines(
        [line("First paragraph line", 100), line("continues here", 112), line("Second paragraph", 140)]
    )
    assert text.split("\n") == ["First paragraph line continues here", "Second paragraph"]


def test_extract_pages_reads_table_as_rows_after_the_text_above_it():
    pages, _ = extract_pages(TABLE.read_bytes())
    assert pages[0]["text"] == "Grades are shown below.\nGrade | Score\nA | 24\nB | 17"


def test_table_text_skips_empty_cells_and_joins_multiline_cells():
    rows = [["Grade", None, "Score"], ["A+\nA", None, "24\n21"]]
    assert table_text(rows) == "Grade | Score\nA+ A | 24 21"


def test_table_text_merges_rows_that_continue_the_cell_above():
    rows = [
        ["Award", "FTE period of", "Credit"],
        [None, "study", "value"],
        ["Masters", "1 year", "180"],
    ]
    assert table_text(rows) == "Award | FTE period of study | Credit value\nMasters | 1 year | 180"


def test_table_text_ignores_single_cell_boxes():
    assert table_text([["Boxed note"], ["more"]]) == ""


def test_join_wrapped_lines_keeps_table_between_paragraphs():
    table = {"text": "A | 1\nB | 2", "x0": 72, "x1": 500, "top": 120, "bottom": 150, "table": True}
    text = join_wrapped_lines(
        [line("Before the table", 100, x1=200), table, line("After the table", 160, x1=200)]
    )
    assert text == "Before the table\nA | 1\nB | 2\nAfter the table"
