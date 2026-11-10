"""LangSmith opcional: `pydantic-settings` lee `.env`, pero LangSmith solo mira `os.environ`."""

import os
import warnings
from collections.abc import Callable
from typing import Any

from docs_agent.config import Settings

# `wrap_openai` serializa con `model_dump()` la respuesta de `chat.completions.parse`; el `ParsedChatCompletion`
# del SDK declara `parsed` con un TypeVar cuyo default es None, y pydantic avisa en cada llamada estructurada
# (`Expected `none` ... field_name='parsed'`). El valor que llega a la traza es correcto: es solo ruido.
PARSED_SERIALIZER_WARNING = (
    r"Pydantic serializer warnings:\s+PydanticSerializationUnexpectedValue\(Expected `none` - serialized value may "
    r"not be as expected \[field_name='parsed'"
)


def configure_tracing(settings: Settings) -> bool:
    """Copia la configuración de LangSmith a `os.environ` si el tracing está activo y hay key."""
    api_key = settings.langsmith_api_key.get_secret_value()
    if not (settings.langsmith_tracing and api_key):
        return False
    os.environ["LANGSMITH_TRACING"] = "true"
    os.environ["LANGSMITH_API_KEY"] = api_key
    os.environ["LANGSMITH_PROJECT"] = settings.langsmith_project
    return True


def load_openai_wrapper() -> Callable[[Any], Any]:
    """`wrap_openai`, para llamar una vez al arrancar y solo con tracing activo (D34).

    Import perezoso: con tracing apagado no se carga `langsmith.wrappers`, cuyo `__init__` (0.14.17) importa un
    módulo deprecado y emite un DeprecationWarning ajeno a este código. Instala además, para todo el proceso, un
    filtro acotado por mensaje, categoría y módulo para el aviso de serialización de `parsed` (ver arriba); no
    oculta ningún otro warning.
    """
    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore", message=r"langsmith\.wrappers\._openai_agents is deprecated", category=DeprecationWarning
        )
        from langsmith.wrappers import wrap_openai
    install_tracing_warning_filters()
    return wrap_openai


def install_tracing_warning_filters() -> None:
    warnings.filterwarnings("ignore", message=PARSED_SERIALIZER_WARNING, category=UserWarning, module=r"pydantic\.main")
