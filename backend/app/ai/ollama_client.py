import logging
import httpx
from typing import List, Optional
from backend.app.config import settings

logger = logging.getLogger(__name__)

class OllamaClient:
    def __init__(self, host: str = None, embed_model: str = None, chat_model: str = None):
        self.host = (host or settings.OLLAMA_HOST).rstrip("/")
        self.embed_model = embed_model or settings.OLLAMA_EMBED_MODEL
        self.chat_model = chat_model or settings.OLLAMA_CHAT_MODEL
        self.timeout = 30.0

    async def get_embedding(self, text: str) -> Optional[List[float]]:
        """Generate 1024-dim embedding via Ollama (bge-m3)."""
        if not text or not text.strip():
            return None
        # truncate text for embedding if very long
        clean_text = text.strip()[:3000]
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(
                    f"{self.host}/api/embeddings",
                    json={"model": self.embed_model, "prompt": clean_text}
                )
                if resp.status_code == 200:
                    data = resp.json()
                    embedding = data.get("embedding")
                    if embedding and len(embedding) == 1024:
                        return embedding
                logger.warning(f"Ollama embedding response: {resp.status_code}")
        except Exception as e:
            logger.warning(f"Ollama embedding generation failed: {e}")
        return None

    async def generate_json(self, prompt: str, system_prompt: str = "") -> Optional[str]:
        """Generate structured text/JSON from Ollama LLM."""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                payload = {
                    "model": self.chat_model,
                    "prompt": prompt,
                    "system": system_prompt,
                    "stream": False,
                    "format": "json"
                }
                resp = await client.post(f"{self.host}/api/generate", json=payload)
                if resp.status_code == 200:
                    return resp.json().get("response")
        except Exception as e:
            logger.warning(f"Ollama generate failed: {e}")
        return None

ollama_client = OllamaClient()
