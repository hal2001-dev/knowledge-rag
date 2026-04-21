import io
import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    with patch("apps.dependencies.get_pipeline") as mock_pipeline_dep, \
         patch("apps.dependencies.get_db") as mock_db_dep:

        mock_pipeline = MagicMock()
        mock_pipeline.ingest.return_value = MagicMock(
            doc_id="test-doc-id",
            title="테스트 문서",
            status="done",
            chunk_count=5,
            has_tables=True,
            has_images=False,
        )
        mock_pipeline_dep.return_value = mock_pipeline

        mock_db = MagicMock()
        from packages.code.models import DocRecord
        from packages.db.repository import create_document
        mock_db_dep.return_value = iter([mock_db])

        with patch("packages.db.repository.create_document") as mock_create:
            from packages.db.models import DocumentRecord
            from datetime import datetime
            mock_db_record = MagicMock(spec=DocumentRecord)
            mock_db_record.doc_id = "test-doc-id"
            mock_db_record.title = "테스트 문서"
            mock_db_record.source = "test.pdf"
            mock_db_record.file_type = "pdf"
            mock_db_record.chunk_count = 5
            mock_db_record.has_tables = True
            mock_db_record.has_images = False
            mock_db_record.indexed_at = datetime.now()
            mock_db_record.status = "done"
            mock_create.return_value = mock_db_record

            from apps.main import app
            with TestClient(app) as c:
                yield c


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
