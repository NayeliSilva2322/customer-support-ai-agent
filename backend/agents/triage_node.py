from typing import Any


def triage_node(
    text: str | None,
    vision_output: dict[str, Any] | None = None,
    kb_hits: list[str] | None = None,
) -> dict[str, str]:
    """Clasifica la consulta para orientar su atención."""
    normalized_text = (text or "").casefold()
    caption = ""
    if vision_output and vision_output.get("caption"):
        caption = str(vision_output["caption"]).casefold()
    combined_text = f"{normalized_text} {caption}".strip()

    decision = "self_help"
    rationale = "La consulta puede atenderse con autoayuda."
    if any(
        word in combined_text
        for word in ("error", "fallo", "falla", "problema", "incidencia")
    ):
        decision = "technical_support"
        rationale = "Se identificó un problema técnico."
    elif any(
        word in combined_text
        for word in ("pregunta", "como", "cómo", "qué", "que", "por qué", "porque")
    ):
        decision = "self_help"
        rationale = "La consulta puede atenderse con autoayuda."

    if kb_hits is not None and not kb_hits and decision != "diagnostic":
        decision = "escalation"
        rationale = "No se encontró una solución en la base de conocimiento."

    return {"decision": decision, "rationale": rationale}
