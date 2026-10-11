import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

LTM_DIR = Path(__file__).resolve().parents[1] / "data" / "ltm"
LTM_FILE = LTM_DIR / "sample_failed_solutions.json"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def ensure_ltm_storage() -> Path:
    """Prepara el archivo de memoria a largo plazo."""
    LTM_DIR.mkdir(parents=True, exist_ok=True)
    if not LTM_FILE.exists():
        LTM_FILE.write_text("[]", encoding="utf-8")
    return LTM_FILE


def load_ltm_data() -> list[dict[str, Any]]:
    """Carga los registros de memoria."""
    path = ensure_ltm_storage()
    with path.open("r", encoding="utf-8") as file:
        data = json.load(file)
    if not isinstance(data, list):
        raise ValueError("El archivo de memoria debe contener una lista.")
    return data


def save_ltm_data(data: list[dict[str, Any]]) -> None:
    """Guarda los registros de memoria."""
    path = ensure_ltm_storage()
    with path.open("w", encoding="utf-8") as file:
        json.dump(data, file, indent=2, ensure_ascii=False)


def store_failed_solution(
    session_id: str,
    text: str,
    solution_summary: str,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Guarda una solución que no resolvió el problema."""
    data = load_ltm_data()
    record = {
        "id": str(uuid.uuid4()),
        "type": "failure",
        "session_id": session_id,
        "text": text,
        "solution_summary": solution_summary,
        "metadata": metadata or {},
        "timestamp": _now_iso(),
    }
    data.append(record)
    save_ltm_data(data)
    return record


def query_ltm(text: str) -> list[dict[str, Any]]:
    """Busca problemas y soluciones anteriores."""
    query_text = text.strip().casefold()
    if not query_text:
        return []

    return [
        record
        for record in load_ltm_data()
        if query_text in str(record.get("text", "")).casefold()
        or query_text
        in str(
            record.get("solution_summary", record.get("summary", ""))
        ).casefold()
    ]


def store_feedback(
    session_id: str,
    user_id: str | None,
    feedback_text: str,
    rating: int | None = None,
) -> dict[str, Any]:
    """Guarda la opinión del usuario."""
    data = load_ltm_data()
    record = {
        "id": str(uuid.uuid4()),
        "type": "feedback",
        "session_id": session_id,
        "user_id": user_id,
        "feedback_text": feedback_text,
        "rating": rating,
        "timestamp": _now_iso(),
    }
    data.append(record)
    save_ltm_data(data)
    return record


def query_feedback(
    session_id: str | None = None,
    user_id: str | None = None,
    query: str | None = None,
) -> list[dict[str, Any]]:
    """Busca comentarios por sesión, usuario o texto."""
    query_text = (query or "").strip().casefold()
    return [
        record
        for record in load_ltm_data()
        if record.get("type") == "feedback"
        and (not session_id or record.get("session_id") == session_id)
        and (not user_id or record.get("user_id") == user_id)
        and (
            not query_text
            or query_text
            in str(record.get("feedback_text", record.get("feedback", ""))).casefold()
        )
    ]


def summarize_ltm_activity(
    session_id: str | None = None,
) -> dict[str, int]:
    """Resume la actividad de memoria."""
    records = load_ltm_data()
    if session_id:
        records = [
            record
            for record in records
            if record.get("session_id") == session_id
        ]

    return {
        "total_records": len(records),
        "failed_solutions": sum(
            record.get("type") == "failure" for record in records
        ),
        "handoffs": sum(
            record.get("type") == "handoff" for record in records
        ),
        "feedbacks": sum(
            record.get("type") == "feedback" for record in records
        ),
    }


def store_handoff(
    session_id: str,
    issue_text: str,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Guarda una solicitud de atención humana."""
    data = load_ltm_data()
    record = {
        "id": str(uuid.uuid4()),
        "type": "handoff",
        "session_id": session_id,
        "issue": issue_text,
        "metadata": metadata or {},
        "timestamp": _now_iso(),
    }
    data.append(record)
    save_ltm_data(data)
    return record


def query_handoffs(
    session_id: str | None = None,
) -> list[dict[str, Any]]:
    """Busca solicitudes de atención humana."""
    return [
        record
        for record in load_ltm_data()
        if record.get("type") == "handoff"
        and (not session_id or record.get("session_id") == session_id)
    ]
