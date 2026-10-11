import json
import os
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")


def generate_text(
    prompt: str,
    external_context: Any = None,
) -> dict[str, str]:
    """Genera una respuesta con el modelo de lenguaje."""
    api_key = os.getenv("GEMINI_API_KEY") or GEMINI_API_KEY
    if not api_key:
        raise RuntimeError(
            "Falta configurar GEMINI_API_KEY para generar respuestas."
        )

    if external_context:
        prompt += (
            "\n\nContexto adicional:\n"
            + json.dumps(external_context, indent=2, ensure_ascii=False)
        )

    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"{GEMINI_MODEL}:generateContent"
    )
    response = requests.post(
        url,
        headers={
            "Content-Type": "application/json",
            "x-goog-api-key": api_key,
        },
        json={"contents": [{"parts": [{"text": prompt}]}]},
        timeout=60,
    )
    response.raise_for_status()

    data = response.json()
    try:
        output = data["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError, TypeError) as error:
        raise RuntimeError(
            "La respuesta del modelo no contiene texto utilizable."
        ) from error
    return {"respuesta": output}
