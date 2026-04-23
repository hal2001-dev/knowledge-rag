# 개발 환경 셋업 (Onboarding)

**상태**: active
**마지막 업데이트**: 2026-04-23
**관련 페이지**: `environments.md` _(미작성)_, `dependencies.md` _(미작성)_, [security.md](../../security.md), [spec.md](../data/spec.md) (PDF 처리 프로세스)

---

## 사전 요구사항

| 항목 | 버전 | 확인 방법 |
|------|------|-----------|
| Python | 3.10+ | `python --version` |
| pip | 최신 | `pip --version` |
| git | 최신 | `git --version` |

---

## 1. 저장소 클론

```bash
git clone <repo-url>
cd <project-name>
```

---

## 2. 가상환경 생성

```bash
python -m venv .venv
source .venv/bin/activate      # macOS/Linux
.venv\Scripts\activate         # Windows
```

---

## 3. 의존성 설치

```bash
pip install -r requirements.txt
```

주요 패키지 → `dependencies.md` _(미작성)_ 참고

---

## 4. 환경변수 설정

```bash
cp .env.example .env
# .env 파일 열어서 API 키 입력
```

필요한 키 목록 → [security.md](../../security.md) 참고

---

## 5. 첫 실행

```bash
# 개발 서버 실행
python main.py

# 또는
uvicorn app.main:app --reload
```

---

## 6. 동작 확인

```bash
# 샘플 문서 인덱싱
python scripts/ingest_sample.py

# 테스트 쿼리
python scripts/test_query.py "질문을 입력하세요"
```

---

## 자주 발생하는 셋업 문제

→ [common.md](../troubleshooting/common.md) 참고

---

## IDE 권장 설정

| IDE | 추천 플러그인 |
|-----|--------------|
| VSCode | Python, Pylance, GitLens |
| PyCharm | 기본 제공 |

---

## 대량 문서 색인 (TASK-010)

폴더 단위로 여러 문서를 한 번에 등록하려면 `scripts/bulk_ingest.py`를 사용한다. 하위 폴더 포함 재귀 탐색이 기본이며, L1 중복 감지(SHA-256)로 **재실행 시 이미 등록된 파일은 자동으로 409로 스킵**된다.

```bash
# API 서버가 떠 있어야 함
uvicorn apps.main:app &

# 기본: 하위 폴더 포함 재귀
python scripts/bulk_ingest.py --dir ./my_docs

# 업로드 전 대상 확인만
python scripts/bulk_ingest.py --dir ./my_docs --dry-run

# 최상위 폴더만, 특정 패턴 제외
python scripts/bulk_ingest.py --dir ./my_docs --no-recursive --exclude "draft_"

# 마크다운만
python scripts/bulk_ingest.py --dir ./notes --include "*.md"

# 제목을 상대 경로로 (중복 제목 회피)
python scripts/bulk_ingest.py --dir ./docs --title-from relpath

# 첫 실패 시 중단
python scripts/bulk_ingest.py --dir ./docs --fail-fast
```

결과는 `data/eval_runs/bulk_ingest_<timestamp>.json`에 저장:
```json
{
  "total": 10, "ok": 8, "duplicate": 1, "failed": 1, "skipped_too_large": 0,
  "results": [
    {"path": "sub/a.pdf", "status": "ok", "doc_id": "...", "chunk_count": 42},
    {"path": "sub/b.pdf", "status": "duplicate", "doc_id": "..."},
    {"path": "sub/c.pdf", "status": "failed", "http_status": 500, "error": "..."}
  ],
  "elapsed_sec": 125.3
}
```

**주의**:
- 스캔 PDF는 OCR 자동 실행 — 파일당 수 분~수십 분 소요 가능 (LangSmith `rag.ingest` 트레이스로 진행 모니터링)
- 동시 실행 금지 — 같은 파일이 두 실행에 걸리면 L1 UNIQUE 충돌 가능
- 크기 초과(`MAX_UPLOAD_SIZE_MB`) 파일은 `skipped_too_large`로 분류되며 실패 아님
- `--workers 2+`는 Docling 모델 메모리 2~3배 증가. 기본 순차(1) 권장

상세 옵션: `python scripts/bulk_ingest.py --help` · 기획 배경: [roadmap.md TASK-010](../../roadmap.md) · 결정: ADR-022

---

## 변경 이력

| 날짜 | 변경 내용 |
|------|-----------|
| 2026-04-23 | "대량 문서 색인 (TASK-010)" 섹션 추가 |
| 2026-04-17 | 초안 작성 |
