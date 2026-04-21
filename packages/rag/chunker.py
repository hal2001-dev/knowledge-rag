from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document as LCDocument

from packages.code.models import Document

# HybridChunker가 토큰 예산(기본 ~512토큰) 기반으로 청크를 만들므로
# 상한을 여유 있게 두어 정상 청크는 통과시키고, 극단적으로 긴 것만 방어적으로 재분할한다.
CHUNK_SIZE = 2000
CHUNK_OVERLAP = 100


def chunk_documents(documents: list[Document]) -> list[Document]:
    """
    HybridChunker가 만든 구조 인식 청크를 그대로 사용하고,
    문자 수가 지나치게 긴 청크만 방어적으로 재분할한다 (heading 경계가 깨지는 케이스 예방).
    """
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=["\n\n", "\n", ".", " ", ""],
    )

    result: list[Document] = []
    for doc in documents:
        if len(doc.content) <= CHUNK_SIZE:
            result.append(doc)
            continue

        # 긴 청크 재분할
        lc_doc = LCDocument(page_content=doc.content, metadata=doc.metadata.copy())
        sub_docs = splitter.split_documents([lc_doc])
        for sub_idx, sub in enumerate(sub_docs):
            meta = sub.metadata.copy()
            meta["chunk_index"] = f"{doc.metadata.get('chunk_index', 0)}.{sub_idx}"
            result.append(Document(content=sub.page_content, metadata=meta))

    return result
