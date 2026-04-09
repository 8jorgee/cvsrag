from sentence_transformers import SentenceTransformer
import threading
import structlog

from app.config import settings

logger = structlog.get_logger()

_model: SentenceTransformer | None = None
_model_lock = threading.Lock()


def get_model() -> SentenceTransformer:
    global _model
    with _model_lock:  # Acquire lock before checking/initializing
        if _model is None:
            logger.info("Loading embedding model", model=settings.embedding_model)
            _model = SentenceTransformer(settings.embedding_model)
    return _model


def generate_embedding(text: str, collection=None) -> list[float]:
    """Generate embedding with cache lookup.

    Args:
        text: The text to embed
        collection: Optional VectorCollection instance for cache access

    Returns:
        Embedding as list[float]
    """
    # Try cache first
    if collection:
        cached = collection.get_cached_embedding(text)
        if cached:
            logger.info("Embedding cache hit", query_preview=text[:50])
            return cached

    # Cache miss: generate and store
    model = get_model()
    embedding = model.encode(text, normalize_embeddings=True).tolist()

    if collection:
        collection.set_cached_embedding(text, embedding)
        logger.info("Embedding cached", query_preview=text[:50])

    return embedding
