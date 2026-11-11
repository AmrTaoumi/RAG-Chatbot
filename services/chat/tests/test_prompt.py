from prompt import FALLBACK_ANSWER, build_messages, build_response, extract_citations
from tests.fake_snippets import FAKE_SNIPPETS

# Expected citations for the fake snippets: [1] and [2] are the same page, [3] is a different document.
UG_PAGE_12 = {
    "title": FAKE_SNIPPETS[0]["title"],
    "url": FAKE_SNIPPETS[0]["url"],
    "page": 12,
}
GENERAL_PAGE_5 = {
    "title": FAKE_SNIPPETS[2]["title"],
    "url": FAKE_SNIPPETS[2]["url"],
    "page": 5,
}
FALLBACK_RESPONSE = {"answer": FALLBACK_ANSWER, "citations": []}


# --- build_messages ------------------------------------------------------

def test_build_messages_returns_system_then_user():
    messages = build_messages("What happens if I miss an exam?", FAKE_SNIPPETS)

    assert [m["role"] for m in messages] == ["system", "user"]


def test_build_messages_numbers_snippets_in_order():
    messages = build_messages("What happens if I miss an exam?", FAKE_SNIPPETS)
    user_content = messages[1]["content"]

    for number, snippet in enumerate(FAKE_SNIPPETS, start=1):
        assert f"[{number}] {snippet['text']}" in user_content
    assert "Question: What happens if I miss an exam?" in user_content


def test_system_prompt_restricts_citations_and_has_fallback():
    system_content = build_messages("q", FAKE_SNIPPETS)[0]["content"]

    assert "Only use numbers that appear in the context" in system_content
    assert FALLBACK_ANSWER in system_content


# --- extract_citations ---------------------------------------------------

def test_extract_citations_maps_number_to_right_metadata():
    assert extract_citations("Report it in time [3].", FAKE_SNIPPETS) == [GENERAL_PAGE_5]


def test_extract_citations_removes_duplicate_pages():
    assert extract_citations("Zero marks [1]. One resit [2].", FAKE_SNIPPETS) == [UG_PAGE_12]


def test_extract_citations_keeps_order_of_first_mention():
    assert extract_citations("Report it [3]. Zero marks [1].", FAKE_SNIPPETS) == [GENERAL_PAGE_5, UG_PAGE_12]


def test_extract_citations_ignores_invented_numbers():
    assert extract_citations("A [0]. B [4]. C [99].", FAKE_SNIPPETS) == []


def test_extract_citations_logs_invented_numbers(caplog):
    extract_citations("A [7].", FAKE_SNIPPETS)

    assert "number=7" in caplog.text


# --- build_response ------------------------------------------------------

def test_build_response_removes_invalid_markers_and_keeps_valid():
    response = build_response("Zero marks [1][7].", FAKE_SNIPPETS)

    assert response == {"answer": "Zero marks [1].", "citations": [UG_PAGE_12]}


def test_build_response_falls_back_when_no_valid_citations():
    assert build_response("You will be expelled [9].", FAKE_SNIPPETS) == FALLBACK_RESPONSE


def test_build_response_falls_back_when_answer_has_no_citations():
    assert build_response("You will be expelled.", FAKE_SNIPPETS) == FALLBACK_RESPONSE


def test_build_response_falls_back_on_fallback_reply():
    assert build_response(FALLBACK_ANSWER, FAKE_SNIPPETS) == FALLBACK_RESPONSE

def test_build_response_renumbers_markers_to_match_sources():
    response = build_response("Report it [3]. Zero marks [1].", FAKE_SNIPPETS)

    assert response == {
        "answer": "Report it [1]. Zero marks [2].",
        "citations": [GENERAL_PAGE_5, UG_PAGE_12],
    }


def test_build_response_same_page_markers_share_a_number():
    response = build_response("Zero marks [1]. One resit [2].", FAKE_SNIPPETS)

    assert response == {
        "answer": "Zero marks [1]. One resit [1].",
        "citations": [UG_PAGE_12],
    }