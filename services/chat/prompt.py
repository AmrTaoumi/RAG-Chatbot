import re
import logging

logger = logging.getLogger(__name__)

FALLBACK_ANSWER = "not certain / no source found"

SYSTEM_PROMPT = (
    "Answer ONLY using the numbered context provided. "
    "Cite every fact with its source number in square brackets, like [1] or [2][3]. "
    "Only use numbers that appear in the context. "
    "Do not give personal advice or recommendations; only state what the regulations say. "
    "If the context covers the topic but not the exact detail asked (for example a specific number "
    "or time period), state what the context does say and note that it does not give that detail. "
    f'Reply exactly "{FALLBACK_ANSWER}" only if the context has nothing relevant to the question.'
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


def renumber_markers(answer, snippets, citations):
    position = {}
    for number, citation in enumerate(citations, start=1):
        key = (citation["title"], citation["url"], citation["page"])
        position[key] = number

    
    def replace(match):
        n = int(match.group(1))

        if not 1 <= n <= len(snippets):
            return ""                          

        snippet = snippets[n - 1]
        key = (snippet["title"], snippet["url"], snippet["page"])
        return f"[{position[key]}]"

    return re.sub(CITATION_PATTERN, replace, answer)

def build_response(answer, snippets):
    """Turn the raw LLM reply into the /chat response shape from docs/contracts.md."""
    citations = extract_citations(answer, snippets)

    if not citations:
        return {"answer": FALLBACK_ANSWER, "citations":[]}

    cleaned = renumber_markers(answer, snippets, citations)
    return {"answer": cleaned, "citations": citations}


if __name__ == "__main__":
    import sys
    from client import ask
    from tests.fake_snippets import FAKE_SNIPPETS

    logging.basicConfig(stream=sys.stdout, level=logging.INFO)
    logging.getLogger("httpx").setLevel(logging.WARNING)

    messages = build_messages("What happens if I miss an exam?", FAKE_SNIPPETS)
    print(build_response(ask(messages), FAKE_SNIPPETS))
