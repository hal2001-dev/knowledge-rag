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
