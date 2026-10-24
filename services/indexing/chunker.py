'''
notes and justification 
- page boundaries: every chunk has exactly one page number, so citations point to the right page.
- 200 tokens: all-MiniLM-L6-v2 only reads 256 tokens, so 200 leaves a margin. tiktoken counts slightly differently from MiniLM's own tokenizer.
- 40 token overlap : a sentence cut at a chunk boundary still appears whole in one of the chunks.
- tiktoken: real token counts instead of guessing from words, and it's on the permitted list.
'''

import tiktoken


def chunk_pages(pages, doc_id, title, url, chunk_size=200, overlap=40):
    if overlap >= chunk_size:
      raise ValueError("overlap must be smaller than chunk_size")

    enc = tiktoken.get_encoding("cl100k_base")
    chunks = []

    for page in pages:  #pages is a list of dictionaries
        page_number = page["page"]
        page_text= page["text"]
        if not page_text.strip():
           continue
        ids = enc.encode(page_text) # returns a list of token ids
        
        

        step = chunk_size - overlap
        index = 0

        for start in range(0, len(ids), step):  #It produces the starting positions for the chunks
            window = ids[start:start + chunk_size]
            chunk_text = enc.decode(window)

            chunk = {
                    "chunk_id": f"{doc_id}-p{page_number}-c{index}",
                    "doc_id": doc_id,
                    "title": title,
                    "url": url,
                    "page": page_number,
                    "text": chunk_text,
                }

            chunks.append(chunk)
            index += 1

            if start + chunk_size >= len(ids):
                break

    return chunks
       
    
      






   
