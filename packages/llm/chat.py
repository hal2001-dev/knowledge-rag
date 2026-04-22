"""
LLM 백엔드 토글 (ADR-014).

`LLM_BACKEND` 환경변수로 OpenAI / GLM / 기타 OpenAI-호환 공급자를 전환한다.
모든 backend가 OpenAI 호환 API를 제공하므로 `ChatOpenAI` 클래스 하나로 처리한다
(타입 힌트·LangChain 생태·LangSmith 트레이스 호환성 유지).
"""
from dataclasses import dataclass

from langchain_openai import ChatOpenAI

from apps.config import Settings
from packages.code.logger import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class _BackendDefaults:
    base_url: str
    model: str


# backend별 기본값 — 사용자가 .env에서 빈 값으로 두면 이걸 적용한다.
_BACKENDS: dict[str, _BackendDefaults] = {
    "openai": _BackendDefaults(
        base_url="https://api.openai.com/v1",
        model="gpt-4o-mini",
    ),
    "glm": _BackendDefaults(
        base_url="https://open.bigmodel.cn/api/paas/v4/",
        model="glm-4-flash",
    ),
    "custom": _BackendDefaults(
        base_url="",  # custom은 반드시 LLM_BASE_URL을 지정해야 함
        model="",
    ),
}


def _resolve(settings: Settings) -> tuple[str, str, str, float, str]:
    """(backend, base_url, api_key, temperature, model)을 결정한다.

    우선순위:
      LLM_*  →  (openai backend 한정) OPENAI_*  →  backend 기본값
    """
    backend = (settings.llm_backend or "openai").lower()
    if backend not in _BACKENDS:
        raise ValueError(
            f"알 수 없는 LLM_BACKEND: {backend!r} (허용: {list(_BACKENDS)})"
        )
    defaults = _BACKENDS[backend]

    base_url = settings.llm_base_url or defaults.base_url
    model = settings.llm_model or defaults.model or settings.openai_chat_model
    # llm_temperature는 str이고 빈 문자열이면 legacy fallback
    raw_temp = (settings.llm_temperature or "").strip()
    temperature = float(raw_temp) if raw_temp else settings.openai_chat_temperature

    if backend == "openai":
        api_key = settings.llm_api_key or settings.openai_api_key
    else:
        api_key = settings.llm_api_key

    if not base_url:
        raise ValueError(f"LLM backend={backend!r}에 base_url이 필요합니다 (LLM_BASE_URL).")
    if not api_key:
        raise ValueError(f"LLM backend={backend!r}에 API 키가 필요합니다 (LLM_API_KEY).")
    if not model:
        raise ValueError(f"LLM backend={backend!r}에 model이 필요합니다 (LLM_MODEL).")

    return backend, base_url, api_key, temperature, model


def build_chat(settings: Settings) -> ChatOpenAI:
    backend, base_url, api_key, temperature, model = _resolve(settings)
    logger.info(f"LLM backend 선택: {backend} · model={model} · temp={temperature}")
    return ChatOpenAI(
        model=model,
        temperature=temperature,
        openai_api_key=api_key,
        openai_api_base=base_url,
    )
