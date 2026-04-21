import pytest
from unittest.mock import MagicMock, patch
from packages.code.models import ScoredChunk
from packages.rag.generator import generate


def _make_chunk(content: str, content_type: str = "text") -> ScoredChunk:
    return ScoredChunk(
        content=content,
        metadata={"content_type": content_type, "doc_id": "doc-1"},
        score=0.9,
    )


def test_generate_calls_llm():
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = MagicMock(content="답변입니다.")

    chunks = [_make_chunk("컨텍스트 내용")]
    result = generate(llm=mock_llm, question="질문은?", chunks=chunks)

    assert result == "답변입니다."
    mock_llm.invoke.assert_called_once()


def test_generate_includes_table_context():
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = MagicMock(content="테이블 답변")

    chunks = [_make_chunk("| A | B |\n|---|---|\n| 1 | 2 |", "table")]
    result = generate(llm=mock_llm, question="표에서 B의 값은?", chunks=chunks)
    assert result == "테이블 답변"


def test_generate_empty_chunks():
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = MagicMock(content="정보 없음")

    result = generate(llm=mock_llm, question="질문", chunks=[])
    assert result == "정보 없음"
