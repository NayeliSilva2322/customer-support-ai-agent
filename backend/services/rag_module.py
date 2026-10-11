from pathlib import Path

KB_DIR = Path(__file__).resolve().parents[1] / "data" / "knowledge_base"
SAMPLE_KB = KB_DIR / "sample_kb.txt"


def ensure_index() -> Path:
    """Prepara una base de conocimiento de ejemplo."""
    KB_DIR.mkdir(parents=True, exist_ok=True)
    if not SAMPLE_KB.exists():
        SAMPLE_KB.write_text(
            "Guía de ejemplo: diagnóstico de errores de dispositivos y "
            "soluciones habituales.",
            encoding="utf-8",
        )
    return SAMPLE_KB


def query_kb(query: str) -> list[str]:
    """Obtiene el contenido de la base de conocimiento."""
    if not query.strip():
        return []
    path = ensure_index()
    return [path.read_text(encoding="utf-8")]
