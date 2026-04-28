---
name: ISSUE-004 Docling 파싱 단계 메모리·시간 long-tail
description: 큰 PDF(80~110MB) 단일 잡 처리만으로 워커 RSS가 5~12GB까지 부풀고 처리 시간의 90%+가 Docling 파싱에 묶이는 구조적 비용. freeze 자체는 단일 워커에서 발생하지 않지만 동시 워커 트리거의 메모리 곱셈기.
type: issue
---

# ISSUE-004: Docling 파싱 단계 메모리·시간 long-tail

**상태**: open · 후순위
**발생일**: 2026-04-26
**해결일**: -
**관련 기능**: [ingestion.md](../../features/ingestion.md), [packages/loaders/docling_loader.py](../../../../packages/loaders/docling_loader.py)
**관련 이슈**: [ISSUE-003](../resolved/ISSUE-003-ingest-memory-spike-system-freeze.md) (임베딩 단계 캡은 해결됨, 파싱 단계는 미해결)

---

## 증상

단일 워커로 80~110MB PDF 한 건 처리 중:

- 워커 RSS가 **5~12GB**까지 천천히 부풀음 (잡 시작 직후 +1.5~2.8GB 급등 → 평탄 → 잡 종료 직전 회수)
- 잡 처리 총 시간의 **90~96%가 Docling 파싱**(`_DoclingLoader.load()`)에 묶임
- 청크 수와 RSS 피크는 강한 상관 없음 — **PDF 페이지·테이블·이미지 그래프 자체가 메모리 비용**의 주된 driver
- macOS sys_free 90~97% 유지로 freeze는 발생하지 않음 (단일 워커 한정)

## 측정값 (2026-04-26 단일 워커, 16코어 macOS)

| job | 파일 | 청크 | 총 시간 | 파싱 비중 | RSS 피크 |
|---|---|---|---|---|---|
| #41 | 2001 스페이스 오디세이 (55MB) | 991 | 273s | 93% | 5.7GB |
| #42 | 2010 스페이스 오디세이 (70MB) | 668 | 191s | 92% | 6.0GB |
| #43 | 2061 스페이스 오디세이 (46MB) | 652 | 178s | 92% | 5.7GB |
| #44 | C++ 프로그래밍의 이해 (97MB) | 1782 | 514s | 94% | **8.7GB** |
| #45 | CODE 하드웨어와 소프트웨어 (106MB) | 1629 | 459s | 94% | 8.5GB |
| #47 | Design Patterns | 902 | 483s | 96% | **9.99GB** |
| #66 | 심연 위의 불길 1 | 1442 | 323s | 92% | 10.7GB |
| #82 | 종말일기 Z | 72 | 293s | 99% | **11.07GB** |
| #86 | 파이썬 데이터 주무르기 (99MB) | 757 | 334s | 96% | 11.7GB |
| #88 | 하루하루 종말 2 | 1442 | 322s | 92% | **12.62GB** |

**관찰**:
- 청크가 적어도(72, 5, 12) RSS 10GB+ 도달 가능 — 청크 수가 아닌 페이지·테이블 그래프 비용
- 워커 가동 ~3시간 동안 RSS가 7→12GB 추세로 천천히 증가 (누수 또는 메모리 fragmentation 의심)
- CPU는 Docling 내부 ONNX runtime이 1~5 코어를 진동 사용 (16코어 시스템 기준 6~30%, 가드 임계 800%까지 충분)

### 추가 측정 (2026-04-27 → 04-28 동일 워커, 가동 15시간)

- 워커 pid 79071 가동 시작 19:08 (4/27) → 종료 10:10 (4/28), 총 **15시간 02분**
- 잡 처리: 잡 #176~#220 중 1건(#189) 영구 실패 외 44건 정상 완료 → 마지막 잡 #220 완료 시각 00:48 (4/28)
- 종료 시점 RSS **13167MB**, 종료 직전 9시간 22분(00:48~10:10) 동안 **idle 상태에서도 RSS 13.18GB 유지**
- 모니터 5초 간격 fsync 로그(`data/diag/worker_monitor_20260427T100827Z.log`) 종료 직전 5분간 RSS 13167MB로 평탄 — 폴링 sleep 중에도 메모리 회수 없음
- 시스템 used 30% / free 43%로 안정 (단일 워커 + 가드 임계 50% 여유 20pt)

**보강 가설**: idle 상태에서 RSS 13GB 평탄 유지는 누수보다 **메모리 fragmentation + ONNX/Docling 모델 잔여 텐서**일 가능성이 큼. 잡 처리 중 7~13GB 피크 후 회수가 부분적으로만 일어나고 다음 잡까지 13GB가 그대로 보존되는 구조.

**해결 방향 보강**: 5번 `INDEXER_MAX_JOBS` 자가 종료가 본 누수 패턴을 가장 직접 차단함. 예: `MAX_JOBS=20`이면 20잡마다 워커 재기동 → fragmentation 누적 차단.

### 자동 차단 안전망 도입 (2026-04-28, TASK-021 / ADR-031)

본 이슈의 직접 해결은 아니지만 idle RSS 13.18GB 평탄 패턴이 14GB를 넘어 시스템에 영향 주기 전에 **자동 차단**하는 안전망이 가동됐다:

- `scripts/krag_guard.py` — 30초 주기, `apps.indexer_worker` RSS ≥ **14GB** 시 SIGTERM + macOS 알림 + 사후 dump
- 운영 가이드: [wiki/deployment/monitoring.md](../../deployment/monitoring.md), 결정: [ADR-031](../../architecture/decisions.md)

본 이슈의 해결 방향 5번(`INDEXER_MAX_JOBS` 자가 종료)을 **일부만 충족**한 상태. 가드는 외부에서 강제 종료하는 안전판이고, 자가 종료는 워커 내부에서 정해진 잡 수마다 graceful 재기동하는 방식이라 결이 다르다. 둘은 보완 관계 — 가드가 발사되기 전에 자가 종료가 fragmentation을 끊으면 더 좋다.

## 원인 분석

[packages/loaders/docling_loader.py:83-87](../../../../packages/loaders/docling_loader.py#L83-L87)의 `_DoclingLoader(file_path, export_type=DOC_CHUNKS, chunker=...).load()`가 다음을 모두 메모리에 동시 보유:

1. PDF 전체 페이지의 layout/OCR 분석 그래프 (TableFormer + layout 모델 출력)
2. 모든 페이지의 텍스트·테이블·이미지 메타데이터
3. HybridChunker 결과 청크 리스트

페이지 단위 streaming 옵션이 없고, 라이브러리가 문서 통째로 처리하는 구조. ISSUE-003에서 임베딩 단계는 64청크 캡으로 해결됐지만 **파싱 단계는 캡할 지점이 없음**.

추가로 [packages/loaders/docling_loader.py:54-55, 146-149](../../../../packages/loaders/docling_loader.py#L146-L149)의 `_save_markdown`이 켜져 있으면(기본값) 같은 PDF Docling 두 번 호출 → 시간·메모리 사실상 2배.

## 해결 방향 (후순위, 모두 미검증)

1. **`_save_markdown` 이중 파싱 제거** — 본 파싱의 `lc_docs`에서 markdown export 재사용. 검증 비용 낮음, 효과 ~½.
2. **Docling page-batch 파싱** — `_DoclingLoader`를 page range 분할 호출로 감싸 페이지 단위 RSS 캡. Docling 라이브러리 page-range API 검토 필요.
3. **OCR off 옵션** — 텍스트 PDF에 한해 OCR 모델 로드 우회. 라이브러리 옵션 확인 필요.
4. **다른 PDF 라이브러리 비교** — pypdf / pdfplumber / Marker 등 메모리 footprint 측정 후 대안 검토.
5. **워커 N잡 후 자가 종료** (`INDEXER_MAX_JOBS`) — 누적 RSS 증가 추세 차단. 본 이슈의 직접 해결은 아니지만 운영 안전망.

## 우선순위 근거

- **freeze 직접 트리거 아님** — 동시 워커 차단(P0 가드)으로 시스템 멈춤은 막힘
- **단일 워커 + 12GB RAM 여유** 환경이면 안정 운행 (이번 진단 175잡 100% 완료)
- 라이브러리 외부 의존성이라 우회 비용·리스크가 큼

따라서 **freeze 차단(워커 동시 기동 가드, ISSUE-003 후속)이 먼저**, 본 이슈는 그 뒤 별도 검토.

## 출처

- 측정 로그: `data/diag/worker_rss_20260426T194024.log`, `data/diag/worker_cpu_20260426T194024.log`, `data/diag/jobs_progress_20260426T194024.log`
- 코드: [packages/loaders/docling_loader.py](../../../../packages/loaders/docling_loader.py)
- 트리거: 사용자 보고 후속 진단 — 워커 동시 기동 freeze 원인 분석 중 발견 (2026-04-26 세션)
