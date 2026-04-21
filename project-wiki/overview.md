# Project Overview

**상태**: active
**마지막 업데이트**: 2026-04-21
**관련 페이지**: [[architecture/pipeline.md]], [[architecture/stack.md]]

---

## 프로젝트 한 줄 요약

> PDF·TXT·DOCX 문서를 Docling으로 파싱(테이블·이미지 포함)하고, Qdrant 벡터 검색 + FlashRank reranking + gpt-4o-mini로 자연어 질의에 답하는 RAG 시스템

---

## 현재 진행 상황

| 단계 | 상태 | 비고 |
|------|------|------|
| 문서 수집 & 전처리 | `done` | Docling + 파싱 후 정규화 + 원본 영구 보관 (재인덱싱 가능) |
| 청킹 | `done` | HybridChunker + 전체 heading 경로 breadcrumb 주입, 1619→800청크(−51%) |
| 중복 업로드 방지 (L1) | `done` | SHA-256 파일 해시 기반, 409 응답 |
| 임베딩 & 벡터 저장 | `done` | OpenAI text-embedding-3-small + Qdrant |
| 검색 + 재순위 | `done` | Qdrant top-20 → FlashRank 재순위 top-5 (2026-04-21 실제 활성화). **한↔영 크로스 약점 관찰됨** |
| LLM 연동 | `done` | gpt-4o-mini, 한국어/영어 자동 감지 |
| 대화 히스토리 | `done` | Postgres 영속화, 최근 20턴 컨텍스트 주입 |
| 관측 (LangSmith) | `done` | `rag.ingest`/`rag.query` 트레이스, 세션 태그, 단계별 타이머 |
| 모바일 접근 | `done` | XSRF/CORS off (개발), 업로드 상한 200MB |
| 평가 | `todo` | |
| 배포 | `todo` | |

---

## 기술 스택 요약

| 역할 | 선택 | 결정 이유 |
|------|------|-----------|
| 언어 | Python 3.12.2 | venv 기반 |
| 문서 파싱 | Docling 2.x | 텍스트·테이블·이미지 지원 |
| 벡터 DB | Qdrant (Docker) | [[architecture/decisions.md]] 참고 |
| 메타데이터 DB | PostgreSQL (Docker) | SQLAlchemy ORM |
| 임베딩 모델 | OpenAI text-embedding-3-small | |
| LLM | gpt-4o-mini | |
| Reranking | FlashRank (로컬) | API키 불필요 |
| 프레임워크 | LangChain 0.3.x | |
| API 서버 | FastAPI | |
| UI | Streamlit | |

---

## 열린 이슈

| ID | 제목 | 우선순위 |
|----|------|---------|
| (없음) | | |

---

## 최근 주요 결정

> [[architecture/decisions.md]] 참고

---

## 다음 할 일

1. **TASK-001: BGE-reranker-v2-m3 도입 (재순위 다국어화)** — 상세 서브태스크는 [[roadmap.md]] 참고. 재인덱싱 불필요, 토글(`RERANKER_BACKEND`)로 A/B 비교 가능하게. 한↔영 크로스 약점 직접 해결 목표 (ADR-011)
2. 임베딩 모델 512 토큰 초과 청크(5~10%) 대응 — HybridChunker에 토큰 기반 상한 설정 옵션 확인
3. 평가 지표(Precision@K, Recall@K, MRR) 기반선 측정 — 재순위 모델 교체 시 A/B 비교용
4. 하이브리드 검색(BM25 + 벡터) 설계 — 이때 형태소 분석(Kiwi) 도입 재검토
5. DELETE 시 원본 파일·마크다운 동반 삭제 여부 결정 (현재 미삭제로 고아 파일 누적 가능)

---

## 알려진 한계 / 기술 부채

- 중복 감지는 L1(바이트 해시)만 적용 — 포맷만 다른 동일 내용, 리비전 차이는 감지 불가
- 도입 이전 문서들은 `content_hash=NULL`로 감지 대상 외 (백필 스크립트 미작성)
- 대화 히스토리는 최근 20턴만 주입 — 긴 세션의 초기 문맥 유실 가능
- **FlashRank `ms-marco-MiniLM-L-12-v2`는 영어 전용** — 한↔영 크로스 재순위 품질 낮음 (ADR-011)
- **마크다운 fallback으로 재인덱싱한 문서**(현재 6건 전부)는 `page=0`만 보유 — 원본 PDF 재업로드 시 해결
- HybridChunker가 만든 청크 5~10%가 임베딩 모델 512 토큰 상한을 초과 (경고 로그)
- DELETE 시 `data/uploads/`·`data/markdown/` 원본 파일이 자동 정리되지 않음
