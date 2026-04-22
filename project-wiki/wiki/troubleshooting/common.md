# 트러블슈팅 (Troubleshooting)

**상태**: active
**마지막 업데이트**: 2026-04-22
**관련 페이지**: `issues/`, [setup.md](../onboarding/setup.md)

이슈가 해결될 때마다 여기에 누적합니다.
"또 이 에러다" 싶으면 여기서 먼저 찾아보세요.

---

## 형식

```markdown
### [에러명 또는 증상]
**발생 상황**: 언제 발생하는지
**에러 메시지**: (있다면)
**원인**: 왜 발생하는지
**해결**: 어떻게 고치는지
**관련 이슈**: `issues/resolved/ISSUE-NNN.md`
```

---

## 환경 셋업

### ModuleNotFoundError: No module named 'faiss'
**발생 상황**: `import faiss` 실행 시
**원인**: faiss-cpu 미설치 또는 가상환경 미활성화
**해결**:
```bash
pip install faiss-cpu
# GPU 환경이면
pip install faiss-gpu
```

### OpenAI API 인증 오류 (AuthenticationError)
**발생 상황**: 임베딩 또는 LLM 호출 시
**원인**: `.env` 파일에 API 키 미설정 또는 키 만료
**해결**:
```bash
# .env 파일 확인
cat .env | grep OPENAI_API_KEY
# 키 재발급: https://platform.openai.com/api-keys
```

---

## 인덱싱 (Ingestion)

### PDF 파싱 결과가 빈 문자열
**발생 상황**: 스캔된 PDF (이미지 기반) 처리 시
**원인**: 텍스트 레이어 없는 이미지 PDF
**해결**: OCR 전처리 필요 (현재 미지원) → [roadmap.md](../../roadmap.md) 참고

### FAISS 인덱스 저장 후 로드 시 오류
**발생 상황**: `faiss.read_index()` 실행 시
**원인**: 인덱스 파일만 저장하고 docstore pickle 미저장
**해결**:
```python
# 저장 시 반드시 함께 저장
faiss.write_index(index, "index.faiss")
with open("docstore.pkl", "wb") as f:
    pickle.dump(docstore, f)

# 로드 시
index = faiss.read_index("index.faiss")
with open("docstore.pkl", "rb") as f:
    docstore = pickle.load(f)
```
**참고**: [patterns.md](../reviews/patterns.md)

---

## 검색 (Retrieval)

### 검색 결과가 항상 같은 문서만 나옴
**발생 상황**: 다양한 질문에도 동일 결과 반환
**원인**: 청크 크기가 너무 크거나 임베딩 품질 문제
**해결**: chunk_size 줄이거나 임베딩 모델 변경 → [evaluation.md](../features/evaluation.md) 실험 기록 참고

---

## LLM 호출

### RateLimitError
**발생 상황**: 짧은 시간에 많은 요청 시
**해결**:
```python
import time
time.sleep(1)  # 요청 간 딜레이 추가
# 또는 배치 크기 줄이기
```

---

---

## UI (Streamlit)

### 모바일에서 파일 선택 후 선택된 파일이 표시되지 않음
**발생 상황**: 모바일(iOS Safari / Android Chrome 등)에서 `http://<LAN|WAN IP>:8501` 접속, "파일 선택" → 피커에서 파일 선택 후 돌아왔을 때 위젯이 비어 보이고 업로드가 안 됨
**원인(가설)**:
- HTTP 평문 + WebSocket mixed-content로 모바일이 업로드 XHR을 조용히 드롭
- 또는 Streamlit 1.56.0의 모바일 회귀
- 또는 모바일 파일 피커의 MIME 정책으로 "선택한 듯 보이나 실제로는 전달 안 됨"
**임시 회피**: PC에서 업로드, 모바일은 `/query`만 사용
**근본 해결 방향**: HTTPS 리버스 프록시 배포 후 재확인
**관련 이슈**: [ISSUE-001-mobile-file-uploader-no-preview.md](../issues/open/ISSUE-001-mobile-file-uploader-no-preview.md)

### `/ingest` 업로드 시 타임아웃 발생
**발생 상황**: Streamlit UI에서 문서 업로드 후 처리 대기 중 연결 끊김
**에러 메시지**: `requests.exceptions.ReadTimeout`
**원인 1**: Docling 첫 실행 시 AI 모델(TableFormer 등) 다운로드로 수 분 소요
**원인 2**: 대용량 PDF 파싱 시간이 기본 타임아웃(120초) 초과
**해결**: `ui/app.py` 34번째 줄 `timeout` 값을 600으로 변경
```python
# 변경 전
timeout=120
# 변경 후
timeout=600
```
**참고**: Docling 모델은 최초 1회 다운로드 후 캐시됨. 이후 실행은 빠름.

---

> 새 에러 해결 시 여기에 추가: "troubleshooting에 추가해줘"
