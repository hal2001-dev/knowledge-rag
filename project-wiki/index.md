# Wiki Index

**마지막 업데이트**: 2026-04-28 (TASK-021 운영 인프라 도입 — launchd 5분 스냅샷 + 30초 워커 RSS 가드, ADR-031, monitoring.md 신설. 이전: 워커 15h 가동·#189 reset·ISSUE-005 갱신)
**총 페이지 수**: 34 (루트 9 + wiki/ 17 + issues/open/ 7 + issues/resolved/ 1)

---

## 프로젝트 개요

| 페이지 | 설명 | 상태 |
|--------|------|------|
| [overview.md](overview.md) | 전체 요약, 현재 진행 상황 | draft |
| [roadmap.md](roadmap.md) | 단기/장기 계획, 마일스톤 | active |
| [changelog.md](changelog.md) | 버전별 변경 이력 | active |
| [glossary.md](glossary.md) | 용어 사전 | active |
| [references.md](references.md) | 참고 논문, 블로그, 오픈소스 | active |
| [security.md](security.md) | API 키 관리, 민감 데이터 처리 | active |

---

## Requirements (기획)

| 페이지 | 설명 | 상태 |
|--------|------|------|
| [features.md](wiki/requirements/features.md) | 기능 명세, 유저 스토리 | draft |
| `acceptance.md` _(미작성)_ | 수용 조건 (Acceptance Criteria) | - |

---

## Architecture (설계)

| 페이지 | 설명 | 상태 |
|--------|------|------|
| [decisions.md](wiki/architecture/decisions.md) | ADR — 설계 결정 기록 | active |
| [structure.md](wiki/architecture/structure.md) | 전체 프로젝트 디렉터리 구조 + 논리 계층도 + 런타임 토폴로지 | active |
| `pipeline.md` _(미작성)_ | RAG 파이프라인 전체 흐름 | - |
| [stack.md](wiki/architecture/stack.md) | 기술 스택 및 선택 이유 (백엔드 + NextJS + Streamlit + 인증) | active |

---

## Features (기능)

| 페이지 | 설명 | 상태 |
|--------|------|------|
| [ingestion.md](wiki/features/ingestion.md) | 문서 수집 및 전처리 (bulk_ingest.py 사용법) | active |
| `embedding.md` _(미작성)_ | 임베딩 모델 및 벡터 저장 | - |
| `retrieval.md` _(미작성)_ | 검색 로직 (FAISS, 유사도) | - |
| `generation.md` _(미작성)_ | LLM 연동 및 답변 생성 | - |
| [evaluation.md](wiki/features/evaluation.md) | 성능 평가 지표 및 실험 기록 | active |
| [admin_ui.md](wiki/features/admin_ui.md) | 관리자 UI 기능 명세 (1·2·3단계) | draft |

---

## API

| 페이지 | 설명 | 상태 |
|--------|------|------|
| [endpoints.md](wiki/api/endpoints.md) | 엔드포인트 스펙, 입출력 형식 | draft |

---

## Data (데이터)

| 페이지 | 설명 | 상태 |
|--------|------|------|
| [spec.md](wiki/data/spec.md) | 입력 문서 스펙, 지원 형식, PDF 처리 프로세스 | active |
| [schema.md](wiki/data/schema.md) | PostgreSQL + Qdrant + 파일시스템 DB 구조 | active |
| `pipeline.md` _(미작성)_ | 데이터 흐름 (수집→전처리→저장) | - |
| `quality.md` _(미작성)_ | 품질 기준 및 검증 | - |

---

## Testing (테스트)

| 페이지 | 설명 | 상태 |
|--------|------|------|
| [strategy.md](wiki/testing/strategy.md) | 테스트 전략 및 범위 | draft |
| `cases.md` _(미작성)_ | 주요 테스트 케이스 | - |

---

## Config (설정)

| 페이지 | 설명 | 상태 |
|--------|------|------|
| `environments.md` _(미작성)_ | dev/staging/prod 설정 | - |
| `dependencies.md` _(미작성)_ | 라이브러리 버전 및 호환성 | - |

---

## Deployment (배포)

| 페이지 | 설명 | 상태 |
|--------|------|------|
| [runbook.md](wiki/deployment/runbook.md) | 배포 절차, 롤백 방법 | draft |
| [monitoring.md](wiki/deployment/monitoring.md) | 운영 모니터링 — 정기 스냅샷(launchd 5분) + 워커 RSS 가드(30초, 14GB 임계) | active |

---

## Onboarding

| 페이지 | 설명 | 상태 |
|--------|------|------|
| [setup.md](wiki/onboarding/setup.md) | 개발 환경 셋업, 처음 실행법 | active |

---

## Troubleshooting

| 페이지 | 설명 | 상태 |
|--------|------|------|
| [common.md](wiki/troubleshooting/common.md) | 자주 발생하는 에러 + 해결법 | active |

---

## Reviews (코드 리뷰)

| 페이지 | 설명 | 상태 |
|--------|------|------|
| [patterns.md](wiki/reviews/patterns.md) | 반복 패턴 & 팀 컨벤션 | active |

---

## Meetings (회의록)

| 페이지 | 설명 | 날짜 |
|--------|------|------|
| (없음) | | |

---

## Issues

| ID | 제목 | 상태 | 날짜 |
|----|------|------|------|
| [ISSUE-001](wiki/issues/open/ISSUE-001-mobile-file-uploader-no-preview.md) | 모바일 파일 업로더 선택 후 파일명 미표시 | open · 보류 | 2026-04-22 |
| [ISSUE-002](wiki/issues/open/ISSUE-002-suggestion-badge-click-unresponsive.md) | 후속 질문 배지 두 번째 이후 클릭 무반응 (모바일 특정 의심) | open · 보류 | 2026-04-22 |
| [ISSUE-003](wiki/issues/resolved/ISSUE-003-ingest-memory-spike-system-freeze.md) | 인덱싱 중 메모리 폭발로 시스템 freeze (qdrant_store.add_documents 미배치 임베딩) | resolved · 2026-04-26 (후속 노트 추가) | 2026-04-26 |
| [ISSUE-004](wiki/issues/open/ISSUE-004-docling-parse-longtail.md) | Docling 파싱 단계 메모리·시간 long-tail (큰 PDF에서 RSS 12GB·8분) | open · 후순위 | 2026-04-26 |
| [ISSUE-005](wiki/issues/open/ISSUE-005-memory-guard-worker-scapegoat.md) | 메모리 가드가 idle worker를 누명으로 SIGTERM (시스템 used% 폭주의 진짜 범인 미식별) | open · 관찰 중 | 2026-04-27 |
| [ISSUE-006](wiki/issues/open/ISSUE-006-empty-state-suggestion-source-confusion.md) | EmptyState가 활성 스코프(doc_filter/category/series_filter) 인지 0 — 책 선택해도 본문 화면 고정 | open · WIP (ScopedEmptyState 적용, 사용자 검증 전) | 2026-04-28 |
| [ISSUE-007](wiki/issues/open/ISSUE-007-overview-suggested-questions-mismatch.md) | /index/overview suggested_questions ↔ retrieval 정합 불일치 | open · 합의됨, 코드 보류 | 2026-04-28 |
| [ISSUE-008](wiki/issues/open/ISSUE-008-scope-residue-on-switch.md) | 스코프 전환 시 이전 URL state 잔류 — 헤더 칩과 본문 표시 불일치 | open · 합의됨, 코드 보류 | 2026-04-28 |

---

> `-` 상태 = 아직 미작성. 해당 기능 개발 시작 시 생성.
