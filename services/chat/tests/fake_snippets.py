# services/chat/tests/fake_snippets.py
# Hard-coded snippets in the exact shape retrieval's GET /search returns (docs/architecture/contracts.md).

UG_DOC_ID = "3b5d5c3712955042212316173ccf37be"   # fake MD5 of the URL (32 hex chars)
UG_URL = "https://www.lancaster.ac.uk/media/.../UG-Assess-Regs.pdf"
UG_TITLE = "Undergraduate Assessment Regulations"

FAKE_SNIPPETS = [
    {   # [1] best match
        "chunk_id": f"{UG_DOC_ID}-p12-c0",
        "doc_id": UG_DOC_ID,
        "title": UG_TITLE,
        "url": UG_URL,
        "page": 12,
        "text": "A student who misses an examination without good cause will receive a mark of zero for that assessment.",
        "score": 0.91,
    },
    {   # [2] SAME document and SAME page as [1], next chunk → tests duplicate citations
        "chunk_id": f"{UG_DOC_ID}-p12-c1",
        "doc_id": UG_DOC_ID,
        "title": UG_TITLE,
        "url": UG_URL,
        "page": 12,
        "text": "Students who fail an assessment may be offered one resit opportunity in the summer resit period.",
        "score": 0.87,
    },
    {   # [3] DIFFERENT document → tests mapping to the right metadata
        "chunk_id": "9e107d9d372bb6826bd81d3542a419d6-p5-c0",
        "doc_id": "9e107d9d372bb6826bd81d3542a419d6",
        "title": "General Regulations",
        "url": "https://www.lancaster.ac.uk/media/.../General-Regs.pdf",
        "page": 5,
        "text": "Mitigating circumstances, such as illness, must be reported with evidence within five working days.",
        "score": 0.74,
    },
    
]