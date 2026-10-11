import random
from datetime import datetime, timezone
from typing import Any


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def check_power(params: dict[str, Any] | None = None) -> dict[str, Any]:
    """Comprueba de forma simulada el estado de alimentación."""
    if params and params.get("force_power_fail"):
        return {
            "status": "FAIL",
            "code": 501,
            "message": "No se detectó la fuente de alimentación.",
            "evidence": "Adaptador de corriente no conectado.",
            "ts": _now_iso(),
        }
    if random.random() < 0.05:
        return {
            "status": "WARN",
            "code": 210,
            "message": "Se detectó una fluctuación de voltaje.",
            "evidence": "Voltaje detectado: 11,1 V.",
            "ts": _now_iso(),
        }
    return {
        "status": "OK",
        "code": 200,
        "message": "La alimentación es estable.",
        "evidence": "Voltaje nominal.",
        "ts": _now_iso(),
    }


def run_memory_check(
    params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Comprueba el uso de memoria simulado."""
    usage = (
        params.get("memory_usage", random.randint(30, 95))
        if params
        else random.randint(30, 95)
    )
    if usage >= 95:
        return {
            "status": "FATAL",
            "code": 601,
            "message": "El uso de memoria es crítico.",
            "evidence": f"Uso de memoria: {usage} %.",
            "ts": _now_iso(),
        }
    if usage >= 80:
        return {
            "status": "WARN",
            "code": 211,
            "message": "El uso de memoria es elevado.",
            "evidence": f"Uso de memoria: {usage} %.",
            "ts": _now_iso(),
        }
    return {
        "status": "OK",
        "code": 201,
        "message": "El uso de memoria está dentro del límite.",
        "evidence": f"Uso de memoria: {usage} %.",
        "ts": _now_iso(),
    }


def check_drivers(params: dict[str, Any] | None = None) -> dict[str, Any]:
    """Comprueba de forma simulada el estado de los controladores."""
    if params and params.get("force_driver_issue"):
        return {
            "status": "FAIL",
            "code": 502,
            "message": "Se encontró un controlador de red desactualizado.",
            "evidence": "Versión detectada 1.2; se requiere la versión 2.0.",
            "ts": _now_iso(),
        }
    if random.random() < 0.1:
        return {
            "status": "WARN",
            "code": 212,
            "message": "Uno o más controladores requieren actualización.",
            "evidence": "Se detectó un controlador gráfico desactualizado.",
            "ts": _now_iso(),
        }
    return {
        "status": "OK",
        "code": 202,
        "message": "Los controladores parecen estar actualizados.",
        "evidence": "Todos los controladores están vigentes.",
        "ts": _now_iso(),
    }


def collect_system_info(
    params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Recopila información básica del sistema."""
    params = params or {}
    info = {
        "os": params.get("os", "linux"),
        "hostname": params.get("hostname", "demo-host"),
        "uptime_minutes": params.get("uptime", 123),
    }
    return {
        "status": "OK",
        "code": 210,
        "message": "Se recopiló la información del sistema.",
        "evidence": info,
        "ts": _now_iso(),
    }


def call_external_diagnostic(
    user_id: str | None = None,
    params: dict[str, Any] | None = None,
    fetch_logs_fn: Any = None,
) -> dict[str, Any]:
    """Analiza los registros recientes disponibles."""
    if fetch_logs_fn is None:
        return {
            "status": "OK",
            "code": 203,
            "message": "No hay una fuente externa de registros configurada.",
            "evidence": None,
            "ts": _now_iso(),
        }

    try:
        logs = fetch_logs_fn(user_id)
    except Exception as error:
        return {
            "status": "WARN",
            "code": "EXT_ERR",
            "message": "No se pudieron consultar los registros externos.",
            "evidence": str(error),
            "ts": _now_iso(),
        }

    if any(
        "ERROR" in str(log.get("level", "")).upper()
        for log in logs
        if isinstance(log, dict)
    ):
        return {
            "status": "WARN",
            "code": 213,
            "message": "Los registros externos contienen errores.",
            "evidence": logs[:3],
            "ts": _now_iso(),
        }
    return {
        "status": "OK",
        "code": 203,
        "message": "No se encontraron errores en los registros externos.",
        "evidence": logs[:3],
        "ts": _now_iso(),
    }
