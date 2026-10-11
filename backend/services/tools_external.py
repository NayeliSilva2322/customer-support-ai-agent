import json
import logging
from pathlib import Path
from typing import Any

import requests

logger = logging.getLogger(__name__)
MOCK_DIR = Path(__file__).resolve().parents[1] / "data" / "mock_external"


def _get_mock_data(path: Path, default: Any) -> Any:
    """Carga datos simulados o devuelve el valor predeterminado."""
    if not path.exists():
        return default
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def fetch_user_config(user_id: str) -> dict[str, Any]:
    """Obtiene la configuración del usuario."""
    api_url = f"https://api.example.com/user_config/{user_id}"
    try:
        response = requests.get(api_url, timeout=3)
        response.raise_for_status()
        return response.json()
    except (requests.RequestException, ValueError) as error:
        logger.warning(
            "No se obtuvo la configuración externa; se usará el archivo local: %s",
            error,
        )

    mock_path = MOCK_DIR / f"user_config_{user_id}.json"
    return _get_mock_data(
        mock_path,
        {
            "user_id": user_id,
            "version": "1.0",
            "settings": {"auto_update": True, "theme": "dark"},
            "note": "Configuración simulada del usuario.",
        },
    )


def fetch_recent_logs(user_id: str, limit: int = 5) -> list[dict[str, Any]]:
    """Obtiene los registros recientes del usuario."""
    api_url = f"https://api.example.com/user_logs/{user_id}?limit={limit}"
    try:
        response = requests.get(api_url, timeout=3)
        response.raise_for_status()
        logs = response.json()
        if not isinstance(logs, list):
            raise ValueError("La respuesta de registros no es una lista.")
        return logs
    except (requests.RequestException, ValueError) as error:
        logger.warning(
            "No se obtuvieron registros externos; se usará la fuente local: %s",
            error,
        )

    mock_path = MOCK_DIR / f"logs_{user_id}.json"
    logs = _get_mock_data(
        mock_path,
        [
            {
                "ts": "2025-10-29T09:00:00Z",
                "level": "INFO",
                "msg": "Se inició el sistema.",
            },
            {
                "ts": "2025-10-29T09:10:00Z",
                "level": "ERROR",
                "msg": "El dispositivo no pudo conectarse.",
            },
            {
                "ts": "2025-10-29T09:15:00Z",
                "level": "WARN",
                "msg": "Se detectó poca memoria disponible.",
            },
        ],
    )
    return logs[:limit]
