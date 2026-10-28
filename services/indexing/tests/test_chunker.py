
from pathlib import Path

import pytest
import tiktoken

from chunker import chunk_pages


enc = tiktoken.get_encoding("cl100k_base")

def make_page(text, page_number=1):
    return {"page": page_number, "text": text}


def make_chunks(text, chunk_size=10, overlap=2, page_number=1):
    return chunk_pages(
        pages=[make_page(text, page_number)],
        doc_id="doc1",
        title="Test Document",
        url="https://example.com",
        chunk_size=chunk_size,
        overlap=overlap,
    )


def test_short_page_gives_one_chunk():
    text = "This is a short page."

    chunks = make_chunks(text, chunk_size=50)

    assert len(chunks) == 1
    assert chunks[0]["text"] == text


@pytest.mark.parametrize("text", ["", "   ", "\n\t  "])
def test_empty_or_whitespace_page_gives_zero_chunks(text):
    chunks = make_chunks(text)

    assert len(chunks) == 0


def test_long_page_gives_several_chunks_within_size():
    text = " ".join(f"word{i}" for i in range(100))

    chunks = make_chunks(text, chunk_size=10, overlap=2)

    assert len(chunks) > 1

    for chunk in chunks:
        token_ids = enc.encode(chunk["text"])
        assert len(token_ids) <= 10


def test_chunks_have_correct_overlap():
    text = " ".join(
        ["red", "blue", "green", "yellow", "orange",
         "purple", "black", "white", "pink", "brown"]
    )

    overlap = 2
    chunks = make_chunks(text, chunk_size=5, overlap=overlap)

    assert len(chunks) > 1

    for i in range(len(chunks) - 1):
        current_tokens = enc.encode(chunks[i]["text"])
        next_tokens = enc.encode(chunks[i + 1]["text"])

        assert current_tokens[-overlap:] == next_tokens[:overlap]


def test_chunks_do_not_mix_pages():
    pages = [
        make_page("apple banana cherry " * 20, page_number=1),
        make_page("tiger lion zebra " * 20, page_number=2),
    ]

    chunks = chunk_pages(
        pages=pages,
        doc_id="doc1",
        title="Test Document",
        url="https://example.com",
        chunk_size=10,
        overlap=2,
    )

    page_one_chunks = [c for c in chunks if c["page"] == 1]
    page_two_chunks = [c for c in chunks if c["page"] == 2]

    assert page_one_chunks
    assert page_two_chunks

    for chunk in page_one_chunks:
        assert "apple" in chunk["text"]
        assert "tiger" not in chunk["text"]

    for chunk in page_two_chunks:
        assert "tiger" in chunk["text"]
        assert "apple" not in chunk["text"]


def test_every_chunk_has_six_correct_fields():
    chunks = make_chunks("hello world", page_number=7)

    expected_fields = {
        "chunk_id", "doc_id", "title", "url", "page", "text"
    }

    assert chunks

    for chunk in chunks:
        assert set(chunk.keys()) == expected_fields
        assert chunk["doc_id"] == "doc1"
        assert chunk["title"] == "Test Document"
        assert chunk["url"] == "https://example.com"
        assert chunk["page"] == 7
        assert isinstance(chunk["text"], str)


def test_chunk_ids_format_restart_and_uniqueness():
    pages = [
        make_page("apple banana cherry " * 20, page_number=1),
        make_page("tiger lion zebra " * 20, page_number=2),
    ]

    chunks = chunk_pages(
        pages=pages,
        doc_id="doc1",
        title="Test Document",
        url="https://example.com",
        chunk_size=10,
        overlap=2,
    )

    page_one_chunks = [c for c in chunks if c["page"] == 1]
    page_two_chunks = [c for c in chunks if c["page"] == 2]
    ids = [chunk["chunk_id"] for chunk in chunks]

    assert page_one_chunks[0]["chunk_id"] == "doc1-p1-c0"
    assert page_two_chunks[0]["chunk_id"] == "doc1-p2-c0"

    for index, chunk in enumerate(page_one_chunks):
        assert chunk["chunk_id"] == f"doc1-p1-c{index}"

    for index, chunk in enumerate(page_two_chunks):
        assert chunk["chunk_id"] == f"doc1-p2-c{index}"

    assert len(ids) == len(set(ids))


def test_overlap_equal_to_or_greater_than_chunk_size_raises_value_error():
    with pytest.raises(ValueError):
        make_chunks("hello world", chunk_size=5, overlap=5)

    with pytest.raises(ValueError):
        make_chunks("hello world", chunk_size=5, overlap=6)


def test_sample_page_chunks_without_errors():
    fixture_path = (
        Path(__file__).parent / "fixtures" / "sample_page.txt"
    )
    text = fixture_path.read_text(encoding="utf-8")

    chunks = make_chunks(text, chunk_size=100, overlap=10)

    if text.strip():
        assert chunks
        assert all(chunk["text"] for chunk in chunks)
    else:
        assert chunks == []
