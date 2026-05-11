import numpy as np
from openai import AsyncOpenAI
from typing import List, Optional
from tenacity import retry, stop_after_attempt, wait_exponential
from app.core.config import settings
import structlog

log = structlog.get_logger()

_client: Optional[AsyncOpenAI] = None


def get_openai_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        _client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
    return _client


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
async def generate_embedding(text: str) -> List[float]:
    client = get_openai_client()
    text = text.strip().replace("\n", " ")[:8000]
    response = await client.embeddings.create(
        model=settings.OPENAI_EMBEDDING_MODEL,
        input=text,
    )
    return response.data[0].embedding


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
async def generate_embeddings_batch(texts: List[str]) -> List[List[float]]:
    client = get_openai_client()
    cleaned = [t.strip().replace("\n", " ")[:8000] for t in texts]
    response = await client.embeddings.create(
        model=settings.OPENAI_EMBEDDING_MODEL,
        input=cleaned,
    )
    return [item.embedding for item in sorted(response.data, key=lambda x: x.index)]


def cosine_similarity(a: List[float], b: List[float]) -> float:
    va = np.array(a)
    vb = np.array(b)
    denom = np.linalg.norm(va) * np.linalg.norm(vb)
    if denom == 0:
        return 0.0
    return float(np.dot(va, vb) / denom)


def compute_centroid(embeddings: List[List[float]]) -> List[float]:
    if not embeddings:
        return []
    arr = np.array(embeddings)
    centroid = arr.mean(axis=0)
    norm = np.linalg.norm(centroid)
    if norm > 0:
        centroid = centroid / norm
    return centroid.tolist()
