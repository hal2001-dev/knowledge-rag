import pytest
from packages.code.models import Document
from packages.rag.chunker import chunk_documents, CHUNK_SIZE


def _make_doc(content: str, content_type: str = "text") -> Document:
    return Document(
        content=content,
        metadata={"doc_id": "test-id", "chunk_index": 0, "content_type": content_type},
    )


def test_short_document_not_split():
    doc = _make_doc("짧은 문서입니다.")
    result = chunk_documents([doc])
    assert len(result) == 1
    assert result[0].content == "짧은 문서입니다."


def test_long_document_is_split():
    content = "가나다라마바사아자차카타파하 " * 100  # 약 1400자
    doc = _make_doc(content)
    result = chunk_documents([doc])
    assert len(result) > 1
    for chunk in result:
        assert len(chunk.content) <= CHUNK_SIZE + 50  # 약간의 여유


def test_chunk_preserves_metadata():
    doc = _make_doc("테이블 내용입니다.\n| A | B |\n|---|---|\n| 1 | 2 |", "table")
    result = chunk_documents([doc])
    for chunk in result:
        assert chunk.metadata["doc_id"] == "test-id"
        assert chunk.metadata["content_type"] == "table"


def test_multiple_documents():
    docs = [_make_doc(f"문서 {i} 내용") for i in range(5)]
    result = chunk_documents(docs)
    assert len(result) == 5
