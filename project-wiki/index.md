# Wiki Index

**마지막 업데이트**: 2026-04-22 (TASK-001~005 완료 + ADR-012~017. 다음 대기: ISSUE-001 + 관리자 UI 2단계)
**총 페이지 수**: 19

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
| `pipeline.md` _(미작성)_ | RAG 파이프라인 전체 흐름 | - |
| `stack.md` _(미작성)_ | 기술 스택 및 선택 이유 | - |

---

## Features (기능)

| 페이지 | 설명 | 상태 |
|--------|------|------|
| `ingestion.md` _(미작성)_ | 문서 수집 및 전처리 | - |
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
| [spec.md](wiki/data/spec.md) | 입력 문서 스펙, 지원 형식 | draft |
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
| `monitoring.md` _(미작성)_ | 모니터링 지표, 알림 기준 | - |

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
| [ISSUE-001](wiki/issues/open/ISSUE-001-mobile-file-uploader-no-preview.md) | 모바일 파일 업로더 선택 후 파일명 미표시 | open | 2026-04-22 |

---

> `-` 상태 = 아직 미작성. 해당 기능 개발 시작 시 생성.
