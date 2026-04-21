import os
import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path

# 테스트 환경변수 설정 (실제 API 호출 방지)
os.environ.setdefault("OPENAI_API_KEY", "sk-test-dummy")
os.environ.setdefault("QDRANT_URL", "http://localhost:6333")
os.environ.setdefault("POSTGRES_URL", "postgresql://raguser:ragpass@localhost:5432/ragdb_test")


@pytest.fixture
def sample_pdf_path():
    fixtures = Path(__file__).parent / "fixtures"
    fixtures.mkdir(exist_ok=True)
    pdf_path = fixtures / "sample.txt"
    if not pdf_path.exists():
        pdf_path.write_text("This is a sample document.\n테스트 문서입니다.\n\nTable:\n| A | B |\n|---|---|\n| 1 | 2 |")
    return str(pdf_path)


@pytest.fixture
def mock_embeddings():
    with patch("langchain_openai.OpenAIEmbeddings") as mock:
        instance = MagicMock()
        instance.embed_documents.return_value = [[0.1] * 1536]
        instance.embed_query.return_value = [0.1] * 1536
        mock.return_value = instance
        yield instance


@pytest.fixture
def mock_llm():
    with patch("langchain_openai.ChatOpenAI") as mock:
        instance = MagicMock()
        instance.invoke.return_value = MagicMock(content="테스트 답변입니다.")
        mock.return_value = instance
        yield instance
