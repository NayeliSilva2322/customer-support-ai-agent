from typing import Any

from services.text_module import generate_text


def generate_troubleshooting_plan(
    user_issue: str,
    diagnostics: dict[str, Any] | None,
    ltm_hits: list[dict[str, Any]] | None = None,
    kb_hits: list[str] | None = None,
    feedback_context: str | None = None,
) -> dict[str, Any]:
    """Genera un plan de solución a partir del contexto disponible."""
    prompt_parts = [
        "Eres un agente que diseña planes de diagnóstico y solución.",
        f"Problema del usuario: {user_issue}",
    ]

    if diagnostics:
        prompt_parts.append(
            "Resumen del diagnóstico: "
            f"{diagnostics.get('overall_status', 'Desconocido')} - "
            f"{diagnostics.get('recommendation', '')}"
        )
        failed_steps = [
            step.get("tool", "herramienta desconocida")
            for step in diagnostics.get("steps", [])
            if step.get("status") in ("FAIL", "FATAL")
        ]
        if failed_steps:
            prompt_parts.append(
                "Comprobaciones fallidas: " + ", ".join(failed_steps)
            )

    if ltm_hits:
        summaries = [
            str(hit.get("solution_summary", hit.get("summary", "")))
            for hit in ltm_hits
        ]
        prompt_parts.append(
            "Soluciones anteriores que fallaron: " + " | ".join(summaries)
        )
    if kb_hits:
        prompt_parts.append(
            "Contexto de la base de conocimiento: "
            + " ".join(kb_hits[:2])
        )
    if feedback_context:
        prompt_parts.append("Opinión del usuario: " + feedback_context)

    prompt_parts.append(
        "Propón pasos concretos y priorizados que eviten las soluciones "
        "fallidas anteriores."
    )
    prompt = "\n".join(prompt_parts)
    return {
        "planner_prompt": prompt,
        "troubleshooting_plan": generate_text(prompt),
    }
