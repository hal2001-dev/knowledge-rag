# 코드 리뷰 패턴 & 팀 컨벤션

**마지막 업데이트**: 2026-04-23
**관련 페이지**: [decisions.md](../architecture/decisions.md)

리뷰에서 반복되는 지적이나 팀이 합의한 규칙을 누적합니다.
새 코드를 작성하기 전에 이 파일을 먼저 확인하세요.

---

## RAG 파이프라인 컨벤션

> 리뷰를 거치면서 채워집니다.

### 임베딩
- (예시) 임베딩 함수는 항상 batch 처리, 단건 호출 금지

### 벡터 저장 / 로드
- (예시) FAISS 인덱스 저장 시 메타데이터(docstore)도 반드시 함께 저장

### Retrieval
- (예시) retrieval 결과에 score threshold 적용 — 기준값은 `retrieval.md` _(미작성)_ 참고

### Chunking
- (예시) chunk 생성 후 empty string 필터링 누락 주의

---

## 자주 지적되는 패턴

| 횟수 | 패턴 | 처음 발견 | 해결책 |
|------|------|-----------|--------|
| (리뷰 후 채워짐) | | | |

---

## 합의된 팀 규칙

| 규칙 | 결정일 | 배경 |
|------|--------|------|
| (리뷰 후 채워짐) | | |

---

## 리뷰 체크리스트 (PR 올리기 전)

- [ ] 임베딩 batch 처리 확인
- [ ] 벡터 저장 시 메타데이터 포함 확인
- [ ] score threshold 적용 확인
- [ ] empty chunk 필터링 확인
- [ ] 에러 처리 (파일 없음, 모델 로드 실패 등)
- [ ] 단위 테스트 또는 간단한 smoke test 포함

> 이 체크리스트도 리뷰를 거치면서 업데이트합니다.

---

## 커밋 체크리스트 (`/rag-commit` 스킬로 자동화됨)

개인 로컬 스킬 `.claude/skills/rag-commit.md`가 아래 항목을 자동 검사한다. 수동 실행 시에도 같은 기준을 따를 것.

1. **금지 동작 차단**: `--no-verify`, `git push --force origin main`, `--no-gpg-sign` 등
2. **민감 정보 스캔**: `sk-proj-...`, `sk-...`, `lsv2_pt_...`, `AIza...` 패턴이 stage된 diff에 있으면 즉시 중단 (2026-04-22 재발 이력)
3. **`.env` stage 방지**: gitignore 이중 체크
4. **`data/` 하위 ignore 검증**: `qdrant_storage`·`pg_data`·`uploads`·`markdown`은 ignore, `eval_runs`만 커밋 대상
5. **위키 정합성 lint**: 남은 위키링크, 깨진 `.md` 링크, ADR 정의 vs 참조, changelog 내림차순, index.md 페이지 수 일치 (5개 체크 전부 통과)
6. **위키 동반 갱신**: 코드 변경 시 roadmap·overview·log·changelog·ADR 함께 수정됐는지 확인 (순수 hotfix·위키 단독 수정 제외)
7. **메시지 템플릿**: `feat(TASK-NNN): ... (ADR-XXX, changelog [X.Y.Z])` + Co-Authored-By + HEREDOC 전달
8. **push는 별도 단계**: 사용자가 명시 지시하기 전엔 자동 push 금지. main 대상 force push는 거부

스킬 자체는 `.gitignore` 대상(`.claude/`)이라 저장소에 올라가지 않음. 본인만 사용.

---

## 로컬 스킬 카탈로그

개인 로컬 스킬은 `.claude/skills/*.md`에 저장되며 `.gitignore` 대상(저장소 미반영, 본인 환경에서만 동작). 트리거 문구는 스킬 frontmatter의 `description` 참고.

| 스킬 파일 | 트리거 문구 | 역할 | 호출 시점 |
|---|---|---|---|
| `rag-commit.md` | `/rag-commit`, "커밋해줘", "push해줘" | 커밋 전 체크리스트 자동 실행(8항목 — API 키·**PII 이메일**·`.env`·`data/`·위키 정합성·동반 갱신·메시지 템플릿·push 분리) | TASK 완료·위키 단독 수정 직후 |
| `rag-task-start.md` | `/rag-task-start`, "태스크 등록", "태스크 착수" | 다음 TASK/ADR 번호 산출, roadmap 실행 큐·overview·log `queue` 동반 갱신, 범위·의도적 제외·완료 기준 합의 | 새 작업 의도 발화 또는 직전 TASK 완료 직후 |
| `rag-lint.md` | `/rag-lint`, "lint 해줘", "위키 점검" | 커밋 없이 위키 정합성(8항목 — 위키링크·깨진 링크·ADR 정의vs참조·changelog 순서·index 페이지 수·index·overview 날짜 정합·**PII 이메일 평문 노출**) 단독 점검 | 위키 수정 중간·커밋 직전 예비 점검 |

### 각 스킬의 상호 관계

```
rag-task-start  ──(등록)──▶  [실제 구현 · ADR · 코드]  ──(직전 점검)──▶  rag-lint  ──(OK)──▶  rag-commit  ──(사용자 "push해줘")──▶  push
```

- `rag-commit` 4단계는 `rag-lint`와 동일한 스크립트. `rag-lint`는 커밋 상황과 무관하게 단독 호출 가능.
- `rag-task-start`는 **등록까지만**. 사용자 "진행해줘" 지시 후 실제 구현 턴은 별도.
- 세 스킬 모두 main 브랜치 force push 거부·`.env` 커밋 거부 등 **안전 원칙은 공통**.

### 신규 스킬 추가 기준

로컬 스킬로 승격할 것:
- 3회 이상 동일한 절차로 반복 수행 중
- 누락·실수 여지가 있는 다단계(체크리스트)
- 이 프로젝트 특유 규칙(예: ADR 결번 018, 민감 키 패턴)을 내포

단순 1회성 명령·사용자 판단이 핵심인 작업은 스킬화하지 말 것.
