# 용어 사전 (Glossary)

**상태**: active
**마지막 업데이트**: 2026-04-17

팀 내에서 혼용되는 용어를 통일합니다.
새 용어가 코드/문서에 등장하면 여기에 먼저 정의하세요.

---

## RAG 핵심 용어

| 용어 | 정의 | 우리 프로젝트에서의 의미 |
|------|------|--------------------------|
| **Chunk** | 문서를 분할한 단위 | 기본 512 tokens, overlap 50 (→ [[architecture/decisions.md]] ADR-002) |
| **Embedding** | 텍스트를 벡터로 변환한 것 | [[features/embedding.md]] 참고 |
| **Vector Store** | 임베딩 벡터를 저장하는 DB | 현재 FAISS 사용 (→ ADR-001) |
| **Retrieval** | 쿼리와 유사한 chunk를 찾는 과정 | Top-K 방식, K=3 기본값 |
| **Generation** | 검색된 context로 LLM이 답변 생성 | [[features/generation.md]] 참고 |
| **Context Window** | LLM에 입력되는 전체 텍스트 길이 | 프롬프트 + retrieved chunks |
| **Reranking** | 1차 검색 결과를 재정렬하는 과정 | (미구현, 추후 검토) |
| **Hallucination** | LLM이 사실과 다른 내용을 생성하는 현상 | evaluation에서 주요 체크 항목 |
| **Score Threshold** | retrieval 결과 필터링 기준값 | 현재 미정 (→ 실험 중) |
| **Docstore** | FAISS와 별도로 원본 텍스트를 저장하는 저장소 | pickle로 함께 저장 필수 |

---

## 시스템 용어

| 용어 | 정의 |
|------|------|
| **Ingest** | 새 문서를 파이프라인에 넣는 전체 과정 |
| **Pipeline** | 문서 입력부터 답변 생성까지의 처리 흐름 |
| **Index** | FAISS 벡터 인덱스 (≠ wiki/index.md) |
| **Raw source** | 원본 문서 (raw/ 폴더, 수정 불가) |

---

## 평가 용어

| 용어 | 정의 |
|------|------|
| **Precision@K** | 상위 K개 결과 중 관련 있는 비율 |
| **Recall@K** | 전체 관련 문서 중 K개 안에 포함된 비율 |
| **MRR** | Mean Reciprocal Rank — 첫 번째 정답의 순위 역수 평균 |
| **LLM-as-judge** | LLM이 다른 LLM의 답변 품질을 평가하는 방식 |

---

> 용어 추가 요청: "glossary에 XXX 추가해줘"
