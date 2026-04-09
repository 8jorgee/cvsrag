from sentence_transformers import SentenceTransformer
from app.config import settings
import logging
import threading

logger = logging.getLogger(__name__)

_model: SentenceTransformer | None = None
_model_lock = threading.Lock()


def get_model() -> SentenceTransformer:
    global _model
    with _model_lock:  # Acquire lock before checking/initializing
        if _model is None:
            logger.info(f"Loading embedding model: {settings.embedding_model}")
            _model = SentenceTransformer(settings.embedding_model)
    return _model


def generate_embedding(text: str) -> list[float]:
    model = get_model()
    embedding = model.encode(text, normalize_embeddings=True)
    return embedding.tolist()
