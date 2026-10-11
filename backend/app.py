import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from core.conversation_store import (
    get_conversation_details,
    list_conversations,
)
from core.graph_pipeline import (
    create_session,
    run_diagnostics_chain,
    run_multimodal_session,
)
from services.ltm_module import (
    query_feedback,
    query_handoffs,
    query_ltm,
    store_failed_solution,
    store_feedback,
    store_handoff,
    summarize_ltm_activity,
)

app = FastAPI(title="API de agente de soporte multimodal")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("shutdown")
def flush_observability() -> None:
    from core.observability import flush_langfuse

    flush_langfuse()


class SessionRequest(BaseModel):
    session_id: str = "student"
    user_id: str | None = None
    initial_text: str = ""


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _request_user_id(payload: SessionRequest) -> str:
    return payload.user_id or payload.session_id


def _diagnostics_response(report: dict[str, Any]) -> dict[str, Any]:
    return {
        **report,
        "timestamp": report.get("timestamp", _now_iso()),
    }


@app.post("/start_session")
def start_session(payload: SessionRequest) -> dict[str, str]:
    """Inicia una sesión de usuario."""
    session_id = create_session(_request_user_id(payload), payload.initial_text)
    return {"session_id": session_id, "created_at": _now_iso()}


@app.get("/conversations")
def conversations_route(
    user_id: str = Query(..., min_length=1),
    limit: int = Query(default=100, ge=1, le=500),
) -> dict[str, Any]:
    """Lista las conversaciones del usuario para la vista de observabilidad."""
    normalized_user_id = user_id.strip()
    if not normalized_user_id:
        raise HTTPException(
            status_code=422,
            detail="Se requiere un user_id no vacío.",
        )
    conversations = list_conversations(normalized_user_id, limit)
    return {
        "user_id": normalized_user_id,
        "conversations": conversations,
        "total": len(conversations),
    }


@app.get("/conversations/{session_id}")
def conversation_details_route(
    session_id: str,
    user_id: str = Query(..., min_length=1),
) -> dict[str, Any]:
    """Devuelve el detalle y los turnos de una conversación del usuario."""
    normalized_user_id = user_id.strip()
    if not normalized_user_id:
        raise HTTPException(
            status_code=422,
            detail="Se requiere un user_id no vacío.",
        )
    conversation = get_conversation_details(session_id, normalized_user_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversación no encontrada.")
    return conversation


@app.post("/analyze")
def analyze(
    session_id: str = Form(...),
    input_text: str | None = Form(None),
    text: str | None = Form(None),
    file: UploadFile | None = File(None),
) -> dict[str, Any]:
    """Procesa el texto y entrega la imagen al módulo de visión."""
    vision_output = None
    if file is not None and file.filename:
        suffix = Path(file.filename).suffix or ".jpg"
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                image_path = Path(temp_dir) / f"imagen{suffix}"
                with image_path.open("wb") as image_file:
                    shutil.copyfileobj(file.file, image_file)

                # La carga del modelo se aplaza hasta que se recibe una imagen.
                from services.vision_module import caption_image

                vision_output = caption_image(str(image_path))
            if vision_output.get("error"):
                raise HTTPException(
                    status_code=503,
                    detail=f"No se pudo procesar la imagen: {vision_output['error']}",
                )
        except HTTPException:
            raise
        except Exception as error:
            raise HTTPException(
                status_code=500,
                detail=f"Error al procesar la imagen: {error}",
            ) from error
        finally:
            file.file.close()

    try:
        return run_multimodal_session(
            sid=session_id,
            text=input_text if input_text is not None else text,
            vision_output=vision_output,
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Error en el flujo de análisis: {error}",
        ) from error


@app.post("/run_diagnostics")
def run_diagnostics(payload: SessionRequest) -> dict[str, Any]:
    """Ejecuta las comprobaciones del sistema."""
    report = run_diagnostics_chain(
        {"user_id": _request_user_id(payload)}
    )
    return _diagnostics_response(report)


@app.post("/store_failed_solution")
def store_failed_solution_route(payload: dict[str, Any]) -> dict[str, Any]:
    """Guarda una solución fallida."""
    session_id = payload.get("session_id")
    text = payload.get("text")
    solution_summary = payload.get("solution_summary")
    if not session_id or not text or not solution_summary:
        raise HTTPException(
            status_code=422,
            detail="Se requieren session_id, text y solution_summary.",
        )
    record = store_failed_solution(
        session_id,
        text,
        solution_summary,
        payload.get("metadata"),
    )
    return {"status": "stored", "session_id": session_id, "record": record}


@app.post("/query_ltm")
def query_ltm_route(payload: dict[str, Any]) -> dict[str, Any]:
    """Busca registros de problemas anteriores."""
    query = str(payload.get("query_text", payload.get("query", "")))
    matches = query_ltm(query)
    return {"query_text": query, "matches": matches, "count": len(matches)}


@app.post("/ltm_query")
def ltm_query_route(q: str = Query(default="")) -> dict[str, Any]:
    """Busca registros mediante un parámetro de consulta."""
    matches = query_ltm(q)
    return {"query_text": q, "matches": matches, "count": len(matches)}


@app.post("/store_feedback")
@app.post("/submit_feedback")
def store_feedback_route(payload: dict[str, Any]) -> dict[str, Any]:
    """Guarda la opinión del usuario."""
    session_id = payload.get("session_id")
    if not session_id:
        raise HTTPException(
            status_code=422,
            detail="Se requiere session_id para guardar la opinión.",
        )
    record = store_feedback(
        session_id,
        payload.get("user_id"),
        payload.get("feedback_text", ""),
        payload.get("rating"),
    )
    return {"status": "stored", "session_id": session_id, "record": record}


@app.post("/query_feedback")
def query_feedback_route(payload: dict[str, Any]) -> dict[str, Any]:
    """Busca opiniones por sesión, usuario o texto."""
    session_id = payload.get("session_id")
    user_id = payload.get("user_id")
    query = payload.get("query")
    matches = query_feedback(session_id, user_id, query)
    return {
        "session_id": session_id,
        "query": query,
        "matches": matches,
        "count": len(matches),
    }


@app.post("/summarize_ltm_activity")
def summarize_ltm_activity_route(
    payload: dict[str, Any],
) -> dict[str, Any]:
    """Resume la actividad de memoria."""
    session_id = payload.get("session_id")
    return {
        "session_id": session_id,
        "summary": summarize_ltm_activity(session_id),
    }


@app.post("/store_handoff")
def store_handoff_route(payload: dict[str, Any]) -> dict[str, Any]:
    """Registra una solicitud de atención humana."""
    session_id = payload.get("session_id")
    if not session_id:
        raise HTTPException(
            status_code=422,
            detail="Se requiere session_id para registrar la solicitud.",
        )
    record = store_handoff(
        session_id,
        payload.get("issue", ""),
        {"reason": payload.get("reason", "Se solicita revisión manual.")},
    )
    return {"status": "handoff_stored", "record": record}


@app.post("/query_handoffs")
def query_handoffs_route(
    payload: dict[str, Any],
) -> dict[str, Any]:
    """Busca solicitudes de atención humana."""
    handoffs = query_handoffs(payload.get("session_id"))
    return {"handoffs": handoffs, "total": len(handoffs)}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)
