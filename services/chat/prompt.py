import re
import logging

logger = logging.getLogger(__name__)

FALLBACK_ANSWER = "I'm not certain based on the available documents."

SYSTEM_PROMPT = (
    "Answer ONLY using the numbered context provided. "
    "Cite every fact with its source number in square brackets, like [1] or [2][3]. "
    "Only use numbers that appear in the context. "
    "Do not give personal advice or recommendations; only state what the regulations say. "
    f'If the context does not contain the answer, reply exactly: "{FALLBACK_ANSWER}"'
)


def build_messages(question, snippets):

    
    lines = []

    for number, snippet in enumerate(snippets , start=1):
        lines.append(f"[{number}] {snippet['text']}")

    context = "\n".join(lines)

    user_content = f"Context:\n{context}\n\nQuestion: {question}"

    system_message = {"role": "system", "content": SYSTEM_PROMPT}
    user_message = {"role": "user", "content": user_content}

    return [system_message, user_message]


CITATION_PATTERN = r"\[(\d+)\]"


def extract_citations(answer, snippets):
    citations = []
    seen = set()  

    for number_text in re.findall(CITATION_PATTERN, answer):
        n = int(number_text)                    

        if not 1 <= n <= len(snippets):
            logger.warning("Ignored invented citation number=%d snippets=%d", n, len(snippets))
            continue
        snippet = snippets[n - 1]       

        key = (snippet["title"], snippet["url"], snippet["page"])

        if key in seen:
            continue
 
        seen.add(key)

        citations.append({
            "title": snippet["title"],
            "url": snippet["url"],
            "page": snippet["page"],
        })
    
    return citations


def remove_invalid_markers(answer, snippet_count):

    def keep_or_remove(match):
        n = int(match.group(1))   

        if 1 <= n <= snippet_count:
            return match.group(0)

        return ""

    return re.sub(CITATION_PATTERN, keep_or_remove, answer)


def build_response(answer, snippets):
    """Turn the raw LLM reply into the /chat response shape from docs/contracts.md."""
    citations = extract_citations(answer, snippets)

    if not citations:
        return {"answer": FALLBACK_ANSWER, "citations":[]}

    cleaned = remove_invalid_markers(answer, len(snippets))
    return {"answer": cleaned, "citations": citations}


if __name__ == "__main__":
    import sys
    from client import ask
    from tests.fake_snippets import FAKE_SNIPPETS

    logging.basicConfig(stream=sys.stdout, level=logging.INFO)
    logging.getLogger("httpx").setLevel(logging.WARNING)

    messages = build_messages("What happens if I miss an exam?", FAKE_SNIPPETS)
    print(build_response(ask(messages), FAKE_SNIPPETS))
