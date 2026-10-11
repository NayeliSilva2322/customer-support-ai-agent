import logging
import os
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from dotenv import load_dotenv
from langfuse import get_client, propagate_attributes

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

logger = logging.getLogger(__name__)
_configuration_warning_logged = False
_disabled_notice_logged = False


def _client() -> Any | None:
    global _configuration_warning_logged, _disabled_notice_logged
    public_key = os.getenv("LANGFUSE_PUBLIC_KEY")
    secret_key = os.getenv("LANGFUSE_SECRET_KEY")
    if not public_key or not secret_key:
        if (public_key or secret_key) and not _configuration_warning_logged:
            logger.warning(
                "Langfuse está deshabilitado: configure LANGFUSE_PUBLIC_KEY y "
                "LANGFUSE_SECRET_KEY."
            )
            _configuration_warning_logged = True
        elif not _disabled_notice_logged:
            logger.info(
                "Langfuse deshabilitado: configure sus claves para habilitar "
                "la observabilidad."
            )
            _disabled_notice_logged = True
        return None
    return get_client()


def _capture_content() -> bool:
    return os.getenv("LANGFUSE_CAPTURE_CONTENT", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def capture_content_enabled() -> bool:
    return _capture_content()


@contextmanager
def trace_conversation(
    session_id: str,
    input_summary: dict[str, Any],
) -> Iterator[Any | None]:
    client = _client()
    if client is None:
        yield None
        return

    trace_input = input_summary
    with client.start_as_current_observation(
        as_type="span",
        name="support.conversation",
        input=trace_input,
        metadata={"session_id": session_id},
    ) as observation:
        with propagate_attributes(session_id=session_id):
            yield observation


@contextmanager
def trace_step(
    name: str,
    input_data: Any = None,
    *,
    as_type: str = "span",
    model: str | None = None,
) -> Iterator[Any | None]:
    client = _client()
    if client is None:
        yield None
        return

    observation_options: dict[str, Any] = {
        "as_type": as_type,
        "name": name,
    }
    if _capture_content() and input_data is not None:
        observation_options["input"] = input_data
    if model:
        observation_options["model"] = model

    with client.start_as_current_observation(**observation_options) as observation:
        yield observation


def update_observation(observation: Any | None, **values: Any) -> None:
    if observation is not None:
        observation.update(**values)


def flush_langfuse() -> None:
    client = _client()
    if client is not None:
        client.flush()
