import pytest
from unittest.mock import MagicMock, patch
from packages.loaders.docling_loader import DoclingDocumentLoader, _infer_content_type


def test_infer_content_type_text():
    assert _infer_content_type({}, "일반 텍스트 내용입니다.") == "text"


def test_infer_content_type_table_by_markdown():
    content = "| A | B |\n|---|---|\n| 1 | 2 |"
    assert _infer_content_type({}, content) == "table"


def test_infer_content_type_table_by_metadata():
    meta = {"dl_meta": {"doc_items": [{"label": "table"}]}}
    assert _infer_content_type(meta, "some content") == "table"


def test_infer_content_type_image_by_metadata():
    meta = {"dl_meta": {"doc_items": [{"label": "picture"}]}}
    assert _infer_content_type(meta, "some content") == "image"


@patch("packages.loaders.docling_loader._DoclingLoader")
def test_load_returns_documents(mock_loader_class):
    from langchain_core.documents import Document as LCDocument

    mock_instance = MagicMock()
    mock_instance.load.return_value = [
        LCDocument(page_content="첫 번째 청크", metadata={"page": 1}),
        LCDocument(page_content="| A | B |\n|---|---|\n| 1 | 2 |", metadata={"page": 2}),
    ]
    mock_loader_class.return_value = mock_instance

    loader = DoclingDocumentLoader()
    docs = loader.load("dummy.pdf", "doc-id-1", "테스트 문서")

    assert len(docs) == 2
    assert docs[0].metadata["doc_id"] == "doc-id-1"
    assert docs[0].metadata["content_type"] == "text"
    assert docs[1].metadata["content_type"] == "table"
