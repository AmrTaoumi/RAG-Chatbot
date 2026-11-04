from sentence_transformers import SentenceTransformer

# loaded once when the service starts; loading takes a few seconds
model = SentenceTransformer("all-MiniLM-L6-v2")


def embed(texts):
    # same model and normalisation as retrieval, so scores are comparable
    return model.encode(texts, normalize_embeddings=True).tolist()