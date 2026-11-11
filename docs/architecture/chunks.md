
# Chunking Strategy

## Page boundaries
we split each document page by page, and a chunk never spans two pages. Every chunk therefore belongs to exactly one page, so when the chatbot cites a source it can point to the exact page the answer came from. 

## Chunk size
Each chunk is at most 200 tokens, counted with tiktoken. Our embedding model, `BAAI/bge-small-en-v1.5`, reads at most 512 tokens of its own tokenizer (WordPiece) and silently ignores the rest, so anything past that limit would be stored but never searchable.

The two tokenizers count differently. On our test page (`services/indexing/tests/fixtures/sample_page.txt`), 200 tiktoken tokens are 311 WordPiece tokens, so a 200-token chunk stays well under 512.

We keep chunks well below the limit so that each one covers a single point of a regulation. Citations then point to a focused passage, and the prompt stays short when chat sends 8 chunks to the LLM. `SCORE_THRESHOLD` (0.6) was tuned on these chunks, so changing the size means re-indexing and re-tuning it.

History: 200 was first chosen for `all-MiniLM-L6-v2`, which reads only 256 tokens. Measured later, 200 tiktoken tokens come to about 311 for MiniLM's tokenizer, so MiniLM cut off the end of most chunks. Switching to bge on 8 Nov removed that problem.

## Overlap
Neighbouring chunks overlap by 40 tokens, about 20%. Because we cut at fixed token positions, a sentence can be split between two chunks. The overlap means that sentence also appears whole, or mostly whole, in the next chunk, so important information isn't lost at the edges. 

## Why tiktoken
We count real tokens rather than words because models read tokens, not words, and the ratio between the two varies with the text. Chunk size and overlap are parameters, so we can tune them later if retrieval quality suggests different values.
We chose tiktoken over bge's own tokenizer because bge's tokenizer lowercases text and splits punctuation when turning tokens back into text ("Section 4.2" comes back as "section 4. 2"), while tiktoken reproduces the original text exactly. This matters because the chunk text is what `/search` returns and what the LLM reads and quotes from.

## Implementation 
Where the code is: services/indexing/chunker.py, function chunk_pages(pages, doc_id, title, url, chunk_size=200, overlap=40).
The chunk_id format: {doc_id}-p{page}-c{index}, with the index restarting at 0 on each page, matching contracts.md.
Empty pages: pages with no text, or only whitespace, are skipped.
Tokenizer: `tiktoken` with the `cl100k_base` encoding

## tests 
How to run the tests: cd services/indexing && python -m pytest -v