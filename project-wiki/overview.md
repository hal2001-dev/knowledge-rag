# Project Overview

**상태**: active
**마지막 업데이트**: 2026-04-22
**관련 페이지**: `pipeline.md` _(미작성)_, `stack.md` _(미작성)_

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
| 검색 + 재순위 | `done` | Qdrant top-20 → **BGE-reranker-v2-m3** 재순위 top-3 (2026-04-22 채택, ADR-012). 토글로 flashrank 회귀 가능 |
| LLM 연동 | `done` | gpt-4o-mini, 한국어/영어 자동 감지 |
| 대화 히스토리 | `done` | Postgres 영속화, 최근 20턴 컨텍스트 주입 |
| 관측 (LangSmith) | `done` | `rag.ingest`/`rag.query` 트레이스, 세션 태그, 단계별 타이머 |
| 모바일 접근 | `done` | XSRF/CORS off (개발), 업로드 상한 200MB |
| 평가 | `done` | Phase 1 Retrieval 벤치 + Phase 2 Ragas. 기반선 확보 (ADR-015, 2026-04-22) |
| 배포 | `todo` | |

---

## 기술 스택 요약

| 역할 | 선택 | 결정 이유 |
|------|------|-----------|
| 언어 | Python 3.12.2 | venv 기반 |
| 문서 파싱 | Docling 2.x | 텍스트·테이블·이미지 지원 |
| 벡터 DB | Qdrant (Docker) | [decisions.md](wiki/architecture/decisions.md) 참고 |
| 메타데이터 DB | PostgreSQL (Docker) | SQLAlchemy ORM |
| 임베딩 모델 | OpenAI text-embedding-3-small (기본) | `EMBEDDING_BACKEND`로 BGE-M3 토글 가능 (ADR-016) |
| LLM | gpt-4o-mini (기본) | ADR-013 유지 결정. `.env`의 `LLM_BACKEND`로 openai/glm/custom 토글 가능 (ADR-014) |
| Reranking | BGE-reranker-v2-m3 (다국어, 로컬) | 한↔영 크로스 대응 (ADR-012). flashrank 토글 가능 |
| 프레임워크 | LangChain 0.3.x | |
| API 서버 | FastAPI | |
| UI | Streamlit | |

---

## 열린 이슈

| ID | 제목 | 우선순위 |
|----|------|---------|
| [ISSUE-001](wiki/issues/open/ISSUE-001-mobile-file-uploader-no-preview.md) | 모바일 파일 업로더가 선택된 파일을 표시하지 않음 | 중 · **🛑 보류 (사용자 지시 대기)** |

---

## 최근 주요 결정

> [decisions.md](wiki/architecture/decisions.md) 참고

- **ADR-016 (2026-04-22)**: Embedding — OpenAI 기본 유지, BGE-M3 토글. TASK-004 프레임워크로 A/B 실시 결과 동률·소폭 하락, 전환 이득 없음. 토글 인프라만 확보
- **ADR-015 (2026-04-22)**: 평가 프레임워크 — Ragas + 자체 Retrieval 벤치. 기반선(Hit@3=1.000, faithfulness=0.886) 수립. 이후 모든 품질 ADR은 before/after 수치 첨부 원칙
- **ADR-014 (2026-04-22)**: LLM 백엔드 토글 인프라 구축. `LLM_BACKEND=openai|glm|custom` 한 줄 변경으로 공급자 전환 가능. 기본 유지는 ADR-013 결론 준수
- **ADR-013 (2026-04-22)**: LLM은 gpt-4o-mini 유지. GLM 계열은 컨텍스트 준수·안전 필터·생태 안정성에서 현재 유리하지 않음. 비용/데이터 주권 이슈가 생기면 `.env` 토글 패턴으로 1시간 내 교체 가능 구조를 유지
- **ADR-012 (2026-04-22)**: Reranker를 `flashrank` → **`bge-m3`** (BGE-reranker-v2-m3)로 채택. 한↔영 크로스 실패 해소, 토글로 회귀 가능

---

## 다음 할 일

**실행 원칙**: 태스크는 **순서대로** 진행, 병렬 금지. 앞 태스크(문서화 포함) 종료 후 다음 착수.

1. ~~TASK-001 BGE-reranker-v2-m3 도입~~ — ✅ 완료 2026-04-22 (ADR-012)
2. ~~TASK-003 LLM 백엔드 토글~~ — ✅ 완료 2026-04-22 (ADR-014)
3. ~~TASK-004 평가 프레임워크 (Ragas + 자체 벤치)~~ — ✅ 완료 2026-04-22 (ADR-015). 기반선 Hit@3=1.000 / faithfulness=0.886
4. ~~TASK-002 BGE-M3 임베딩 토글 + A/B~~ — ✅ 완료 2026-04-22 (ADR-016). OpenAI 기본 유지, BGE-M3 토글 확보
5. ~~TASK-005 관리자 UI 1단계~~ — ✅ 완료 2026-04-22 (ADR-017). 5개 탭 + 청크 미리보기
6. **🛑 보류 (사용자 지시 대기): ISSUE-001 + 관리자 UI 2단계** — HTTPS 리버스 프록시 배포 + `/admin` 분리 + `ADMIN_PASSWORD`. 사용자가 지시할 때까지 자동 진행 금지
2. 임베딩 모델 512 토큰 초과 청크(5~10%) 대응 — HybridChunker에 토큰 기반 상한 설정 옵션 확인
3. 평가 지표(Precision@K, Recall@K, MRR) 기반선 측정 — 재순위 모델 교체 시 A/B 비교용
4. 하이브리드 검색(BM25 + 벡터) 설계 — 이때 형태소 분석(Kiwi) 도입 재검토
5. DELETE 시 원본 파일·마크다운 동반 삭제 여부 결정 (현재 미삭제로 고아 파일 누적 가능)

---

## 알려진 한계 / 기술 부채

- 중복 감지는 L1(바이트 해시)만 적용 — 포맷만 다른 동일 내용, 리비전 차이는 감지 불가
- 도입 이전 문서들은 `content_hash=NULL`로 감지 대상 외 (백필 스크립트 미작성)
- 대화 히스토리는 최근 20턴만 주입 — 긴 세션의 초기 문맥 유실 가능
- ~~FlashRank 영어 전용 한계~~ — ✅ 2026-04-22 BGE-reranker-v2-m3로 해결 (ADR-012)
- **마크다운 fallback으로 재인덱싱한 문서**(현재 6건 전부)는 `page=0`만 보유 — 원본 PDF 재업로드 시 해결
- HybridChunker가 만든 청크 5~10%가 임베딩 모델 512 토큰 상한을 초과 (경고 로그)
- DELETE 시 `data/uploads/`·`data/markdown/` 원본 파일이 자동 정리되지 않음
