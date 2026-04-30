import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

from docling_core.transforms.chunker.hybrid_chunker import HybridChunker
from langchain_docling import DoclingLoader as _DoclingLoader
from langchain_docling.loader import ExportType

from packages.code.models import Document
from packages.code.logger import get_logger
from packages.loaders.base import BaseLoader

logger = get_logger(__name__)


# 단어 중간 하이픈-줄바꿈 복구 ("robot-\nics" → "robotics")
_HYPHEN_LINEBREAK_RE = re.compile(r"(\w)-\s*\n\s*(\w)")
# 숫자 1~4자리만 단독으로 있는 줄 = 페이지 번호로 간주
_PAGE_NUMBER_LINE_RE = re.compile(r"(?m)^[ \t]*\d{1,4}[ \t]*$")
# 테이블 정렬용 2+연속 공백 (마크다운 테이블 행 `|` 내부도 포함됨 — 단일 공백으로 압축해도 파이프 구분자는 유지됨)
_MULTI_SPACE_RE = re.compile(r" {2,}")
# 3+ 개 연속 개행 → 빈 줄 하나로 정규화
_MULTI_NEWLINE_RE = re.compile(r"\n{3,}")
# NBSP / thin space / 0-width space 등 문제 공백 문자
_WEIRD_SPACES_RE = re.compile(r"[\u00A0\u2000-\u200B\u202F\u205F\u3000]")


def _normalize(text: str) -> str:
    """Docling 마크다운/청크 텍스트의 전형적 아티팩트 정리."""
    if not text:
        return text
    text = unicodedata.normalize("NFC", text)
    text = _WEIRD_SPACES_RE.sub(" ", text)
    text = _HYPHEN_LINEBREAK_RE.sub(r"\1\2", text)
    text = _PAGE_NUMBER_LINE_RE.sub("", text)
    text = _MULTI_SPACE_RE.sub(" ", text)
    text = _MULTI_NEWLINE_RE.sub("\n\n", text)
    return text.strip()


class DoclingDocumentLoader(BaseLoader):
    """
    Docling 기반 로더. PDF의 텍스트, 테이블, 이미지를 모두 추출한다.
    markdown_save_dir 지정 시 파싱 결과를 {doc_id}.md 파일로 저장한다.

    `force_full_page_ocr=True` 인 경우 macOS Vision(ocrmac)으로 페이지 전체 OCR.
    스캔본 PDF(텍스트 레이어 없음) 재색인용 — 일반 디지털 PDF에는 불필요(시간만 소모).
    """

    def __init__(
        self,
        markdown_save_dir: str | None = None,
        force_full_page_ocr: bool = False,
        ocr_lang: tuple[str, ...] = ("ko-KR", "en-US"),
    ):
        self._markdown_save_dir = markdown_save_dir
        self._force_full_page_ocr = force_full_page_ocr
        self._ocr_lang = ocr_lang

    def _build_ocr_converter(self):
        """OCR 활성 시 사용할 Docling DocumentConverter."""
        from docling.datamodel.base_models import InputFormat
        from docling.datamodel.pipeline_options import OcrMacOptions, PdfPipelineOptions
        from docling.document_converter import DocumentConverter, PdfFormatOption

        opts = PdfPipelineOptions(
            do_ocr=True,
            do_table_structure=True,
            ocr_options=OcrMacOptions(
                lang=list(self._ocr_lang),
                force_full_page_ocr=True,
            ),
        )
        return DocumentConverter(
            format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=opts)}
        )

    def load(self, file_path: str, doc_id: str, title: str) -> list[Document]:
        logger.info(
            f"Docling 파싱 시작: {file_path}"
            + (" [OCR 모드]" if self._force_full_page_ocr else "")
        )

        if self._markdown_save_dir:
            self._save_markdown(file_path, doc_id, title)

        # HybridChunker 설정을 강화해 heading 경로를 청크에 항상 포함.
        #   merge_peers=True          : 같은 부모 heading 아래 작은 청크 병합
        #   always_emit_headings=True : 모든 청크에 heading 경로 emit
        #   omit_header_on_overflow=False : 긴 청크에서도 heading 생략 안 함
        # 토크나이저에 max_tokens를 명시해 512 초과 경고 제거 (TASK-009, ADR-021).
        # 480은 512 한계에 안전 마진 32토큰을 둔 값 — breadcrumb·heading prepend 여유.
        try:
            from docling_core.transforms.chunker.tokenizer.huggingface import HuggingFaceTokenizer
            from transformers import AutoTokenizer
            tokenizer = HuggingFaceTokenizer(
                tokenizer=AutoTokenizer.from_pretrained("sentence-transformers/all-MiniLM-L6-v2"),
                max_tokens=480,
            )
            chunker = HybridChunker(
                tokenizer=tokenizer,
                merge_peers=True,
                always_emit_headings=True,
                omit_header_on_overflow=False,
            )
        except Exception as e:
            logger.warning(f"토크나이저 max_tokens 설정 실패, 기본 사용: {e}")
            chunker = HybridChunker(
                merge_peers=True,
                always_emit_headings=True,
                omit_header_on_overflow=False,
            )
        loader_kwargs = {
            "file_path": file_path,
            "export_type": ExportType.DOC_CHUNKS,
            "chunker": chunker,
        }
        if self._force_full_page_ocr:
            loader_kwargs["converter"] = self._build_ocr_converter()
        lc_docs = _DoclingLoader(**loader_kwargs).load()

        documents: list[Document] = []
        indexed_at = datetime.now(timezone.utc).isoformat()

        for idx, lc_doc in enumerate(lc_docs):
            raw_meta = lc_doc.metadata or {}
            dl_meta = raw_meta.get("dl_meta", {})
            content_type = _infer_content_type(raw_meta, lc_doc.page_content)
            page_no = _extract_page_no(dl_meta)
            heading_path = _extract_heading_path(dl_meta)

            # 테이블은 구조(파이프·대시) 보존 위해 normalize 생략
            body = (
                lc_doc.page_content
                if content_type == "table"
                else _normalize(lc_doc.page_content)
            )
            if not body:
                continue

            # HybridChunker의 contextualize가 이미 heading 라인을 본문 앞에 넣어두므로,
            # 같은 텍스트가 breadcrumb과 중복되지 않도록 앞부분을 정렬해 제거한다.
            body = _strip_leading_headings(body, heading_path)

            # 전체 heading 경로를 breadcrumb로 prepend — 청크 단독으로 "어느 장·어느 절인지" 파악 가능.
            breadcrumb = " > ".join(heading_path) if heading_path else ""
            content = f"{breadcrumb}\n\n{body}" if breadcrumb else body

            doc = Document(
                content=content,
                metadata={
                    "doc_id": doc_id,
                    "title": title,
                    "source": file_path,
                    "page": page_no,
                    "heading_path": heading_path,
                    "chunk_index": idx,
                    "indexed_at": indexed_at,
                    "language": "auto",
                    "content_type": content_type,
                    **raw_meta,
                },
            )
            documents.append(doc)

        has_tables = any(d.metadata.get("content_type") == "table" for d in documents)
        has_images = any(d.metadata.get("content_type") == "image" for d in documents)
        logger.info(
            f"파싱 완료: {len(documents)}개 청크 "
            f"(테이블: {has_tables}, 이미지: {has_images})"
        )
        return documents

    def _save_markdown(self, file_path: str, doc_id: str, title: str) -> None:
        save_dir = Path(self._markdown_save_dir)
        save_dir.mkdir(parents=True, exist_ok=True)
        md_path = save_dir / f"{doc_id}.md"

        md_kwargs = {"file_path": file_path, "export_type": ExportType.MARKDOWN}
        if self._force_full_page_ocr:
            md_kwargs["converter"] = self._build_ocr_converter()
        md_docs = _DoclingLoader(**md_kwargs).load()
        # 페이지별 Markdown을 이어붙인 뒤 한 번만 normalize.
        # 테이블 구조는 페이지 내부에서 완결되므로 파편별 cleanup은 안전.
        markdown_content = _normalize_markdown(
            "\n\n".join(d.page_content for d in md_docs)
        )

        md_path.write_text(
            f"# {title}\n\n{markdown_content}",
            encoding="utf-8",
        )
        logger.info(f"마크다운 저장: {md_path}")


def _normalize_markdown(text: str) -> str:
    """마크다운 저장용: 테이블 행(`|` 포함)의 공백은 건드리지 않고 그 외만 정규화."""
    if not text:
        return text
    out_lines = []
    for line in unicodedata.normalize("NFC", text).split("\n"):
        stripped = line.strip()
        if stripped.startswith("|") and stripped.endswith("|"):
            out_lines.append(line)  # 테이블 행 원본 유지
        else:
            line = _WEIRD_SPACES_RE.sub(" ", line)
            if _PAGE_NUMBER_LINE_RE.fullmatch(line) is not None:
                continue
            line = _MULTI_SPACE_RE.sub(" ", line)
            out_lines.append(line)
    joined = "\n".join(out_lines)
    # 하이픈-줄바꿈 복구는 테이블 바깥에서만 의미가 있고, 위 루프는 파이프 행을 건드리지 않음
    joined = _HYPHEN_LINEBREAK_RE.sub(r"\1\2", joined)
    joined = _MULTI_NEWLINE_RE.sub("\n\n", joined)
    return joined.strip()


def _extract_page_no(dl_meta: dict) -> int:
    """청크에 걸친 doc_items의 첫 prov.page_no를 반환 (없으면 0)."""
    for item in dl_meta.get("doc_items", []):
        for prov in item.get("prov", []):
            page = prov.get("page_no")
            if isinstance(page, int):
                return page
    return 0


def _strip_leading_headings(body: str, heading_path: list[str]) -> str:
    """HybridChunker가 본문 앞에 prepend한 heading 라인을 잘라낸다.

    heading_path 순서대로 본문 앞 줄과 일치하는 만큼만 제거한다.
    일치하지 않으면 중단해 본문 내용은 손상시키지 않는다.
    """
    if not heading_path:
        return body
    lines = body.split("\n")
    cut = 0
    for h in heading_path:
        if cut < len(lines) and lines[cut].strip() == h.strip():
            cut += 1
        else:
            break
    return "\n".join(lines[cut:]).lstrip()


def _extract_heading_path(dl_meta: dict) -> list[str]:
    """HybridChunker의 heading 경로를 리스트로 반환 (상위 → 하위).

    Docling은 `headings` 필드에 청크가 속한 heading 계층을 담는다.
    HybridChunker(omit_header_on_overflow=False)에서는 전체 경로가 유지된다.
    """
    headings = dl_meta.get("headings") or []
    return [h for h in headings if isinstance(h, str) and h.strip()]


def _infer_content_type(metadata: dict, content: str) -> str:
    dl_meta = metadata.get("dl_meta", {})
    doc_items = dl_meta.get("doc_items", [])

    for item in doc_items:
        label = item.get("label", "").lower()
        if "table" in label:
            return "table"
        if "picture" in label or "figure" in label or "image" in label:
            return "image"

    if "|" in content and "---" in content:
        return "table"

    return "text"
