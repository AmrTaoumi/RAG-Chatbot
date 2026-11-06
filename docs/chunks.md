
# Chunking Strategy

## Page boundaries
we split each document page by page, and a chunk never spans two pages. Every chunk therefore belongs to exactly one page, so when the chatbot cites a source it can point to the exact page the answer came from. 

## Chunk size
Each chunk is around 200 tokens long. we chose this size because our embedding model, all-MiniLM-L6-v2, only reads the first 256 tokens of any text and silently ignores the rest. Anything past that limit would be stored but never searchable. 
we count tokens with tiktoken, which is close to MiniLM's own tokenizer but not identical, so we stay at 200 to leave a safe margin. 

## Overlap
Neighbouring chunks overlap by 40 tokens, about 20%. Because we cut at fixed token positions, a sentence can be split between two chunks. The overlap means that sentence also appears whole, or mostly whole, in the next chunk, so important information isn't lost at the edges. 

## Why tiktoken
We count real tokens rather than words because models read tokens, not words, and the ratio between the two varies with the text. Chunk size and overlap are parameters, so we can tune them later if retrieval quality suggests different values.
We chose tiktoken over MiniLM's own tokenizer because MiniLM's tokenizer lowercases text and alters punctuation when converting tokens back to text, while tiktoken reproduces the original text exactly. this is important because chunk text is shown to users in citations.

## Implementation 
Where the code is: services/indexing/chunker.py, function chunk_pages(pages, doc_id, title, url, chunk_size=200, overlap=40).
The chunk_id format: {doc_id}-p{page}-c{index}, with the index restarting at 0 on each page, matching contracts.md.
Empty pages: pages with no text, or only whitespace, are skipped.
Tokenizer: `tiktoken` with the `cl100k_base` encoding

## tests 
How to run the tests: cd services/indexing && python -m pytest -v