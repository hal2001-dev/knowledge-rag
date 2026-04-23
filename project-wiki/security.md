# 보안 (Security)

**상태**: active
**마지막 업데이트**: 2026-04-23
**관련 페이지**: `environments.md` _(미작성)_, [setup.md](wiki/onboarding/setup.md)

---

## API 키 관리

### 규칙
- API 키는 절대 코드에 하드코딩 금지
- `.env` 파일은 `.gitignore`에 반드시 포함
- CI/CD 환경변수로만 주입

### 사용하는 API 키 목록

| 키 이름 | 용도 | 환경변수명 | 보관 위치 |
|---------|------|------------|-----------|
| OpenAI API Key | 임베딩, LLM 호출 | `OPENAI_API_KEY` | .env (로컬), Secret Manager (운영) |
| LangSmith API Key | 트레이스 업로드 | `LANGCHAIN_API_KEY` | .env (로컬), Secret Manager (운영) |

**사고 대응**: 키가 채팅·PR·로그에 평문 노출된 경우 **즉시 발급처에서 revoke하고 새 키 발급**. LangSmith는 https://smith.langchain.com → Settings → API Keys 에서 삭제.

---

## 개인정보(PII) 공개 범위 정책 — 2026-04-23 추가

공개 저장소이므로 아래 항목은 **위키·커밋 메시지·코드 주석·PR 본문·changelog 어디에도 평문 금지**.

| 항목 | 금지 위치 | 허용 위치 | 플레이스홀더 |
|---|---|---|---|
| 실 이메일 (OAuth·알림·ACL 대상) | 위키·커밋·코드·로그 | `.env`(gitignore), Cloudflare Zero Trust 대시보드 | `HAL2001`, `<admin-email>` |
| 실명(한국어/영어) | 위키·커밋 본문·Author 필드 노출 주의 | 로컬 시스템 계정명만 | `HAL2001` |
| 전화번호·주소·생년월일 | 전부 | (사용 금지) | — |
| 내부 IP·사설 도메인 | 위키 본문 | 내부 문서 전용(별도 저장소) | `<internal-host>` |

### 사고 발생 시
1. 즉시 대응: 해당 커밋·파일에서 평문 제거 + 재커밋
2. 이미 push된 경우: 정보 성격에 따라 ① 그대로 두고 관련 계정/시스템 교체(이메일·키 등), ② `git filter-repo`로 히스토리 재작성 + force push(파괴적, 사용자 명시 지시 후)
3. 위키 `log.md`에 `[YYYY-MM-DD] incident` 엔트리 기록

### 평상시 점검
`/rag-lint` 확장 또는 수동 grep:
```
grep -rniE "miru2001|@gmail\.com|@naver|010-[0-9]{4}|실제이름패턴" project-wiki/
```
TASK-012(Cloudflare Access) 착수 시 실 이메일을 Cloudflare 대시보드에만 입력하고 위키는 `HAL2001` 플레이스홀더 유지.

### .env 파일 예시 (`.env.example` 으로 커밋)
```
OPENAI_API_KEY=sk-...
VECTOR_STORE_PATH=./data/faiss_index
LOG_LEVEL=INFO
```

---

## 민감 데이터 처리

### 입력 문서
- PII(개인정보) 포함 가능성이 있는 문서는 수집 전 검토
- 개인정보가 포함된 경우 익명화 또는 마스킹 후 저장
- 처리된 문서는 `raw/data/` 에만 보관, 외부 유출 금지

### 벡터 저장소
- FAISS 인덱스 파일은 공개 저장소에 커밋 금지
- 운영 인덱스는 접근 제한된 스토리지에 보관

---

## 의존성 보안

- `pip audit` 또는 `safety check` 로 주기적 취약점 점검
- 주요 라이브러리 보안 업데이트 시 즉시 반영 → `dependencies.md` _(미작성)_

---

## 알려진 보안 이슈

| 이슈 | 심각도 | 상태 | 비고 |
|------|--------|------|------|
| Streamlit `enableXsrfProtection=false`, `enableCORS=false` | 중 | 개발 환경에서만 허용 | 운영 배포 시 리버스 프록시(Nginx) + HTTPS 뒤로 이동하고 재활성화 필수 |
| Streamlit HTTP 평문 (외부 IP `203.x.x.x:8501` 접속 시) | 중 | 개발 환경 | 운영은 TLS(Let's Encrypt) 필수, 민감 자료 업로드 금지 |
