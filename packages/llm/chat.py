from langchain_openai import ChatOpenAI
from apps.config import Settings


def build_chat(settings: Settings) -> ChatOpenAI:
    return ChatOpenAI(
        model=settings.openai_chat_model,
        temperature=settings.openai_chat_temperature,
        openai_api_key=settings.openai_api_key,
    )
