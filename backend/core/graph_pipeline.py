import json
import time
import uuid
from datetime import datetime, timezone
from typing import Any

from agents.planner_agent import generate_troubleshooting_plan
from agents.triage_node import triage_node
from core.conversation_store import (
    create_conversation,
    get_conversation,
    record_conversation_turn,
)
from services.ltm_module import (
    query_ltm,
    store_failed_solution,
    store_feedback,
    store_handoff,
)
from core.observability import (
    capture_content_enabled,
    trace_conversation,
    trace_step,
    update_observation,
)
from services.rag_module import query_kb
from services.text_module import GEMINI_MODEL, generate_text
from services.tools_diagnostic import (
    call_external_diagnostic,
    check_drivers,
    check_power,
    collect_system_info,
    run_memory_check,
)
from services.tools_external import fetch_recent_logs, fetch_user_config

SESSION_STORE: dict[str, dict[str, Any]] = {}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def create_session(user_id: str, initial_text: str = "") -> str:
    """Crea una sesión de usuario."""
    session_id = str(uuid.uuid4())
    create_conversation(session_id, user_id)
    SESSION_STORE[session_id] = {
        "user_id": user_id,
        "history": [],
        "state": {
            "text": initial_text,
            "vision_output": None,
            "user_config": None,
            "user_logs": None,
        },
    }
    return session_id


def _run_check(function: Any, *args: Any, **kwargs: Any) -> dict[str, Any]:
    """Ejecuta una comprobación y registra su resultado."""
    started = time.monotonic()
    try:
        result = function(*args, **kwargs)
    except Exception as error:
        result = {"status": "FAIL", "message": str(error)}

    return {
        "tool": function.__name__,
        "status": result.get("status", "OK"),
        "message": result.get("message"),
        "evidence": result.get("evidence"),
        "duration_s": round(time.monotonic() - started, 2),
        "ts": _now_iso(),
    }


def hardware_diagnostics_subgraph(
    params: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Ejecuta las comprobaciones de hardware."""
    params = params or {}
    return [
        _run_check(collect_system_info, params),
        _run_check(check_power, params),
        _run_check(run_memory_check, params),
    ]


def software_diagnostics_subgraph(
    user_id: str | None = None,
) -> list[dict[str, Any]]:
    """Ejecuta las comprobaciones de software."""
    return [
        _run_check(check_drivers, {}),
        _run_check(
            call_external_diagnostic,
            user_id=user_id,
            fetch_logs_fn=fetch_recent_logs,
        ),
    ]


def run_diagnostics_chain(
    session_state: dict[str, Any],
    params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Ejecuta y resume las comprobaciones del sistema."""
    steps = hardware_diagnostics_subgraph(params)
    steps.extend(software_diagnostics_subgraph(session_state.get("user_id")))

    statuses = {step["status"] for step in steps}
    if statuses & {"FAIL", "FATAL"}:
        overall_status = "FAIL"
        recommendation = "Se recomienda escalar el caso al soporte humano."
    elif "WARN" in statuses:
        overall_status = "WARN"
        recommendation = "Revise las acciones recomendadas y supervise el sistema."
    else:
        overall_status = "OK"
        recommendation = "El sistema está estable; continúe con el uso normal."

    return {
        "overall_status": overall_status,
        "timestamp": _now_iso(),
        "steps": steps,
        "recommendation": recommendation,
    }


def run_multimodal_session(
    sid: str,
    text: str | None,
    vision_output: dict[str, Any] | None,
    user_id: str | None = None,
    user_feedback: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Procesa una consulta de usuario de principio a fin."""
    session = SESSION_STORE.get(sid)
    if session is None:
        persisted_session = get_conversation(sid)
        if persisted_session is None:
            raise ValueError("El identificador de sesión no es válido.")
        session = {
            "user_id": persisted_session["user_id"],
            "history": [],
            "state": {
                "text": "",
                "vision_output": None,
                "user_config": None,
                "user_logs": None,
            },
        }
        SESSION_STORE[sid] = session

    state = session["state"]
    text = text if text is not None else state.get("text", "")
    state["text"] = text
    state["vision_output"] = vision_output

    session_user_id = user_id or session["user_id"]
    with trace_conversation(
        sid,
        {
            "message_length": len(text),
            "has_image": bool(vision_output),
        },
    ) as trace:
        with trace_step("context.fetch_user_data") as observation:
            user_config = fetch_user_config(session_user_id)
            user_logs = fetch_recent_logs(session_user_id)
            state["user_config"] = user_config
            state["user_logs"] = user_logs
            update_observation(
                observation,
                output={
                    "has_user_config": bool(user_config),
                    "has_recent_logs": bool(user_logs),
                },
            )

        with trace_step(
            "context.retrieve_knowledge",
            {"query_length": len(text)},
        ) as observation:
            docs = query_kb(text) if text.strip() else []
            ltm_hits = query_ltm(text)
            state["ltm_hits"] = ltm_hits
            update_observation(
                observation,
                output={"kb_hits": len(docs), "ltm_hits": len(ltm_hits)},
            )

        with trace_step(
            "triage.classify",
            {"has_image": bool(vision_output), "kb_hits": len(docs)},
        ) as observation:
            triage_result = triage_node(text, vision_output, docs)
            state["triage_result"] = triage_result
            update_observation(
                observation,
                output={"decision": triage_result["decision"]},
            )

        with trace_step("diagnostics.run") as observation:
            diagnostic_report = run_diagnostics_chain(
                session,
                params={"memory_usage": 70},
            )
            update_observation(
                observation,
                output={
                    "status": diagnostic_report["overall_status"],
                    "check_count": len(diagnostic_report["steps"]),
                },
            )

        should_handoff = (
            diagnostic_report["overall_status"] == "FAIL"
            or triage_result["decision"] == "escalation"
        )
        handoff = None
        if diagnostic_report["overall_status"] == "FAIL":
            with trace_step("memory.store_failed_solution") as observation:
                store_failed_solution(
                    session_id=sid,
                    text=text,
                    solution_summary=diagnostic_report["recommendation"],
                    metadata={"user": session_user_id},
                )
                update_observation(observation, output={"stored": True})
        if should_handoff:
            reason = (
                diagnostic_report["recommendation"]
                if diagnostic_report["overall_status"] == "FAIL"
                else triage_result["rationale"]
            )
            with trace_step("handoff.store") as observation:
                handoff = store_handoff(sid, text, {"reason": reason})
                update_observation(observation, output={"stored": True})

        with trace_step("planner.create_plan") as observation:
            planner_output = generate_troubleshooting_plan(
                user_issue=text,
                diagnostics=diagnostic_report,
                ltm_hits=ltm_hits,
                kb_hits=docs,
                feedback_context=(
                    user_feedback.get(
                        "feedback_text",
                        user_feedback.get("text", ""),
                    )
                    if user_feedback
                    else None
                ),
            )
            update_observation(
                observation,
                output={"plan_created": bool(planner_output)},
            )

        plan = planner_output["troubleshooting_plan"]
        if isinstance(plan, dict):
            plan = plan.get("respuesta", "")

        prompt_parts = [
            "Eres un asistente multimodal de soporte técnico.",
            f"Problema del usuario: {text}",
            f"Resultado del triaje: {triage_result['decision']} "
            f"({triage_result['rationale']}).",
            f"Diagnóstico: {diagnostic_report['overall_status']}. "
            f"{diagnostic_report['recommendation']}",
            f"Plan de solución: {plan}",
        ]
        if vision_output and vision_output.get("caption"):
            prompt_parts.append(
                f"Descripción de la imagen: {vision_output['caption']}"
            )
        if docs:
            prompt_parts.append("Base de conocimiento:\n" + "\n".join(docs))
        if ltm_hits:
            summaries = [
                hit.get("solution_summary", hit.get("summary", ""))
                for hit in ltm_hits
            ]
            prompt_parts.append(
                "Soluciones fallidas anteriores:\n" + "\n".join(summaries)
            )

        with trace_step(
            "response.generate",
            {"prompt": "\n\n".join(prompt_parts)},
            as_type="generation",
            model=GEMINI_MODEL,
        ) as observation:
            response = generate_text(
                "\n\n".join(prompt_parts),
                external_context={
                    "configuracion_usuario": user_config,
                    "registros_recientes": user_logs,
                },
            )
            update_observation(
                observation,
                output=(
                    response
                    if capture_content_enabled()
                    else {"response_length": len(str(response))}
                ),
            )

        if user_feedback:
            feedback_text = user_feedback.get(
                "feedback_text",
                user_feedback.get("text", ""),
            )
            with trace_step("feedback.store") as observation:
                store_feedback(
                    sid,
                    session_user_id,
                    feedback_text,
                    user_feedback.get("rating"),
                )
                update_observation(
                    observation,
                    output={"rating_received": user_feedback.get("rating") is not None},
                )
            if user_feedback.get("rating", 5) <= 2:
                with trace_step("planner.replan") as observation:
                    planner_output = {
                        "initial_plan": planner_output,
                        "replanned_strategy": generate_troubleshooting_plan(
                            user_issue=(
                                f"{text} (El usuario indica que no se resolvió.)"
                            ),
                            diagnostics=diagnostic_report,
                            ltm_hits=ltm_hits,
                            kb_hits=docs,
                            feedback_context=feedback_text,
                        ),
                    }
                    update_observation(
                        observation,
                        output={"replanned": True},
                    )

        result = {
            "session_id": sid,
            "status": "handoff_triggered" if should_handoff else "success",
            "manual_handoff_required": should_handoff,
            "handoff": handoff,
            "handoff_reason": handoff["metadata"]["reason"] if handoff else None,
            "response": response,
            "kb_hit": docs,
            "kb_hits": docs,
            "planner_output": planner_output,
            "ltm_hits": ltm_hits,
            "triage_result": triage_result,
            "user_config": user_config,
            "user_logs": user_logs,
            "diagnostic_report": diagnostic_report,
            "feedback": user_feedback or {},
        }
        record_conversation_turn(
            sid,
            text,
            str(response.get("respuesta", response)),
            result["status"],
        )
        session["history"].append(
            {
                "text": text,
                "planner_output": planner_output,
                "prompt": prompt_parts,
                "response": response,
                "diagnostic_report": diagnostic_report,
            }
        )
        update_observation(
            trace,
            output={
                "status": result["status"],
                "response_length": len(str(response)),
                "handoff_required": should_handoff,
            },
            metadata={
                "kb_hits": len(docs),
                "ltm_hits": len(ltm_hits),
                "diagnostic_status": diagnostic_report["overall_status"],
            },
        )
        return result
