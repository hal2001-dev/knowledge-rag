from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from packages.code.models import ScoredChunk

SYSTEM_PROMPT = (
    "You are a helpful assistant that answers questions based on the provided context.\n"
    "Answer in the same language as the question (Korean or English).\n"
    "If the context does not contain enough information to answer, say so clearly.\n"
    "Do not fabricate information.\n"
    "Use the prior conversation to resolve references (e.g., pronouns, follow-up questions)."
)


def generate(
    llm: ChatOpenAI,
    question: str,
    chunks: list[ScoredChunk],
    history: list[dict] | None = None,
) -> str:
    """
    history: [{"role": "user"|"assistant", "content": "..."}] — 시간 오름차순.
    """
    context = "\n\n---\n\n".join(
        f"[{c.metadata.get('content_type', 'text')}] {c.content}" for c in chunks
    )

    messages = [SystemMessage(content=SYSTEM_PROMPT)]
    for turn in history or []:
        role = turn.get("role")
        content = turn.get("content", "")
        if role == "user":
            messages.append(HumanMessage(content=content))
        elif role == "assistant":
            messages.append(AIMessage(content=content))

    messages.append(
        HumanMessage(content=f"Context:\n{context}\n\nQuestion: {question}\n\nAnswer:")
    )

    response = llm.invoke(messages)
    return response.content
