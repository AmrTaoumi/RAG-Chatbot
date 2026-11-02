


FALLBACK_ANSWER = "I'm not certain based on the available documents."

SYSTEM_PROMPT = (
    "Answer ONLY using the numbered context provided. "
    "Cite every fact with its source number in square brackets, like [1] or [2][3]. "
    "Only use numbers that appear in the context. "
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


if __name__ == "__main__":
    from tests.fake_snippets import FAKE_SNIPPETS

    messages = build_messages("What happens if I miss an exam?", FAKE_SNIPPETS)
    for m in messages:
        print("---", m["role"])
        print(m["content"])

