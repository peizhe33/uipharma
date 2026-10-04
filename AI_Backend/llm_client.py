"""
Ollama LLM client for SmartPharma RAG.
"""
import requests
from config import OLLAMA_URL, OLLAMA_MODEL


def call_ollama(
    prompt: str,
    model: str = OLLAMA_MODEL,
    temperature: float = 0.2,
    max_new_tokens: int = 1500,
    num_ctx: int = 6144,
) -> str:
    """
    Send a prompt to the local Ollama instance and return the generated text.

    Defaults are sized for the unified single-call architecture:
      - max_new_tokens=1200 fits per-drug sections for up to ~6 drugs
      - num_ctx=6144 fits the unified prompt (system primer + patient + verdicts +
        retrieved evidence) without truncation
    """
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": temperature,
            "num_predict": max_new_tokens,
            "num_ctx": num_ctx,
        },
    }

    try:
        response = requests.post(OLLAMA_URL, json=payload, timeout=600)
        if response.status_code != 200:
            try:
                error = response.json().get("error")
            except Exception:
                error = response.text
            raise RuntimeError(f"Ollama error {response.status_code}: {error}")
        data = response.json()
        return data.get("response") or data.get("content") or str(data)
    except requests.exceptions.RequestException as e:
        raise RuntimeError(f"Failed to connect to Ollama: {e}")