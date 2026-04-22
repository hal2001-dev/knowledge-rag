# 배포 Runbook

**상태**: draft
**마지막 업데이트**: 2026-04-17
**관련 페이지**: `environments.md` _(미작성)_, `monitoring.md` _(미작성)_

---

## 배포 전 체크리스트

- [ ] 테스트 전체 통과 확인 (`pytest tests/`)
- [ ] `.env.example` 최신 상태 확인
- [ ] `requirements.txt` 업데이트 확인
- [ ] `wiki/changelog.md` 항목 추가
- [ ] `wiki/config/dependencies.md` 버전 동기화

---

## 배포 절차 (개발 → 운영)

```bash
# 1. 최신 코드 pull
git pull origin main

# 2. 의존성 업데이트
pip install -r requirements.txt

# 3. 환경변수 확인
cat .env | grep -v "^#"

# 4. 서버 재시작
# (운영 환경 명령어 — 결정 후 업데이트 예정)
```

---

## 롤백 절차

```bash
# 이전 버전으로 되돌리기
git log --oneline -10          # 커밋 목록 확인
git checkout <commit-hash>     # 롤백

# FAISS 인덱스 롤백 (백업본 사용)
cp backups/index_<date>.faiss data/index.faiss
cp backups/docstore_<date>.pkl data/docstore.pkl
```

---

## 환경별 설정

→ `environments.md` _(미작성)_ 참고

---

## 인덱스 재구축

전체 문서를 다시 인덱싱해야 할 때:

```bash
python scripts/rebuild_index.py
# 완료 후 서버 재시작
```

주의: 재구축 중 검색 응답 품질 저하 가능 → 유지보수 시간 고려

---

## 장애 대응

| 증상 | 1차 확인 | 조치 |
|------|---------|------|
| 쿼리 응답 없음 | 서버 프로세스 상태 | 재시작 |
| 임베딩 오류 | OpenAI API 상태 | API 키/할당량 확인 |
| 검색 결과 없음 | 인덱스 파일 존재 여부 | 인덱스 재구축 |

→ 상세 에러별 해결: [common.md](../troubleshooting/common.md)
