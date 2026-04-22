# 개발 환경 셋업 (Onboarding)

**상태**: active
**마지막 업데이트**: 2026-04-17
**관련 페이지**: `environments.md` _(미작성)_, `dependencies.md` _(미작성)_, [security.md](../../security.md)

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

## 변경 이력

| 날짜 | 변경 내용 |
|------|-----------|
| 2026-04-17 | 초안 작성 |
