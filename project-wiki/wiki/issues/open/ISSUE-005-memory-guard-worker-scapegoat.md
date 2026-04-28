---
name: ISSUE-005 메모리 가드가 idle worker를 누명으로 SIGTERM
description: 시스템 used% 임계로 worker만 SIGTERM하는 가드 로직이 idle 워커를 두 차례 죽인 사건. 워커 RSS는 평탄, 폭주 주체는 다른 프로세스. 진짜 범인 미식별.
type: issue
---

# ISSUE-005: 메모리 가드 worker 누명 SIGTERM

**상태**: open · 후순위
**발생일**: 2026-04-27
**해결일**: -
**관련 기능**: [ingestion.md](../../features/ingestion.md)
**관련 이슈**: [ISSUE-003](../resolved/ISSUE-003-ingest-memory-spike-system-freeze.md), [ISSUE-004](ISSUE-004-docling-parse-longtail.md)

---

## 증상

2026-04-27 오전, 사용자에게 "메모리 올라와서 worker가 죽었다"고 보고된 사건. 그러나 DB 큐를 점검하니 done 175 외 pending/in_progress/failed = 0. 인덱싱 잡이 폭주의 원인일 수 없는 상황.

가드 로그 두 건 발견:

| 시각 (KST) | PID | 시스템 used% | 임계 | 결과 |
|---|---|---|---|---|
| 10:21:54 | 2755 | 59% > 50% | system-wide | SIGTERM |
| 10:35:19 | 65063 | 70% > 50% | system-wide | SIGTERM (재기동본도 즉살) |

`logs/indexer_worker.log`는 4/26 19:13:49 이후 갱신 0 — 즉 두 워커 모두 **새 잡을 처리한 흔적 없이 idle 상태로 죽음**.

## 원인 분석

`data/diag/worker_rss_20260426T194024.log` 마지막 30초가 결정적:

```
10:21:34  RSS=7055MB  sys_free=92%   ← 워커 평탄
10:21:39  RSS=6432MB  sys_free=79%   ← 시스템 free 13%p 추락
10:21:44  RSS=6415MB  sys_free=65%
10:21:49  RSS=635MB   sys_free=55%   ← 워커 RSS 오히려 감소
10:21:54  RSS=2153MB  sys_free=41%   >> threshold — SIGTERM 발사
10:22:05  DEAD
```

워커 RSS는 평탄(또는 감소) 상태인데 시스템 free%가 92→41%로 50pt 추락. **다른 프로세스가 메모리를 폭식**했고, 가드는 시스템 전체 임계로 worker만 죽임.

가드 로직 결함:
1. 시스템 used%만 보고 죽일 대상은 항상 worker로 고정
2. 자식·손자 프로세스(docling이 fork한 ONNX runtime 등) 미고려
3. RSS top 프로세스(진짜 범인) 식별·종료 로직 없음

진짜 범인 후보 (미확인):
- 어제 종료된 워커가 fork한 좀비 docling 자식
- NextJS dev (TASK-019 Phase B 진행 중, `web.log` 1.94MB까지 부풀어 있었음)
- Streamlit / Uvicorn dev
- IDE 확장 / 다른 시스템 데몬

오늘 19:00 시점 점검: 3000/8000/8501 LISTEN 모두 없음, knowledge-rag 디렉토리 내 프로세스 indexer_worker 외 0건. 사후 추적이라 단서 부족.

## 운영 조치 (2026-04-27 19:08)

- worker 재기동: `python -m apps.indexer_worker` (pid 79071, RSS 667MB로 폴링 시작)
- 강화 모니터 가동: `/tmp/krag_monitor.py` (pid 79207)
  - 5초 간격 RSS / 시스템 used% 기록, **매 줄 `flush + os.fsync`** — freeze 직전까지 마지막 상태 보존
  - used% ≥ 60% 도달 시 `ps aux`(RSS top 30) + `vm_stat` 전체 → `data/diag/snapshot_warn_used<NN>_<ts>.log` 즉시 fsync
  - worker 사망 시 사후 snapshot 자동 dump
  - **자동 SIGTERM 미적용** — 누명 방지, 관찰 전용
- 로그: `data/diag/worker_monitor_20260427T100827Z.log`

19:46 시점 38분 안정: RSS 667MB 평탄, used 9%, 임계 snapshot 미발생, Load Avg 1m=2.69.

### 가동 15시간 결과 (2026-04-28 10:10 종료)

- 가동 19:08(4/27) → SIGTERM 10:10(4/28), 총 **15h 02m**
- 그 사이 잡 45건 처리(20:06부터 잡 #176~#220) — 잡 처리 중 RSS 6~13GB 피크, 시스템 used max 30%
- **임계 60% snapshot 발생 0건** — 강화 모니터 가동 내내 가드 임계 미도달, 즉 이번 가동에서는 ISSUE-005 누명 시나리오 재발 없음
- worker SIGTERM → 7초 graceful shutdown 정상, 사후 snapshot 자동 dump 확인: `data/diag/snapshot_worker_dead_20260428T101037.log`(17KB, RSS top 30 + vm_stat 보존)

**결론**: 본 이슈의 진짜 범인은 이번 가동 중에는 활동 안 함(NextJS dev 등을 띄우지 않은 환경). 진짜 폭주 주체 식별은 다음 발생 시 모니터 snapshot으로 재시도.

### 후속 운영 인프라 도입 (2026-04-28, TASK-021 / ADR-031)

ISSUE-005 강화 모니터(`/tmp/krag_monitor.py`)가 워커 lifecycle에 묶여 워커 SIGTERM(04-28 10:10)과 함께 종료된 한계 보완. **launchd fork 모델로 PID 의존 0**의 정기 모니터링 + 워커 한정 가드 도입:

- `scripts/krag_snapshot.py` — 5분 주기 정기 관찰(전용), `data/diag/snapshot/YYYYMMDD.log`
- `scripts/krag_guard.py` — 30초 주기, **`apps.indexer_worker`만** RSS ≥ 14GB 시 그 PID에 SIGTERM. 본 이슈 누명 결함(시스템 used% + 워커 고정)을 정반대로 뒤집음
- LaunchAgents 2개: `~/Library/LaunchAgents/com.knowledge-rag.{snapshot,guard}.plist`
- 운영 가이드: [wiki/deployment/monitoring.md](../../deployment/monitoring.md)

**남은 본 이슈 해결 사항**: 시스템 used% 폭주의 진짜 범인 식별 + 시스템 wide RSS top 식별 기반 재설계는 본 가드 범위 밖, 별건 후속(다음 사건 발생 시 신규 모니터 snapshot으로 단서 확보 후 진입).

## 해결 방향 (후순위, 미합의)

1. **가드 로직 개선** — 시스템 used% 임계 도달 시 worker 고정 SIGTERM이 아니라 **RSS top 프로세스 식별** 후 종료 (또는 알림만)
2. **pid 트리 SIGTERM** — worker만이 아니라 worker가 fork한 자식 프로세스 그룹 전체 종료
3. **worker idle 누수 모니터링 누적값** — 어제 ISSUE-004에서 7→12GB 추세 관찰됐으나 오늘 idle 38분 평탄. 누수 가설은 추가 관찰 필요
4. **dev 서버 가동 시 메모리 정책** — NextJS dev / Streamlit를 worker와 동시 가동할 때의 합산 메모리 가이드 명시

## 우선순위 근거

- 이번 사건은 인덱싱 폭주가 아니므로 ISSUE-003/004와 별개
- 진짜 범인 미식별 상태에서 가드 로직만 손대면 어떤 프로세스를 죽일지 결정할 수 없음
- 관찰 모니터 가동 중 — 다음 발생 시 `snapshot_warn_used*` + `worker_monitor_*` 로그로 범인 식별 후 본격 대응

## 출처

- 가드 로그: `data/diag/auto_kill_guard_20260426T194024.log`, `data/diag/auto_kill_mem_guard_20260427T103519.log`
- 워커 RSS 추적: `data/diag/worker_rss_20260426T194024.log`
- 관찰 모니터(현재 가동): `data/diag/worker_monitor_20260427T100827Z.log`, `/tmp/krag_monitor.py`
- 트리거: 사용자 보고 "메모리 올라와서 worker 죽음" — DB 큐 점검 결과 인덱싱 잡 0건 → 누명 가설 도출 (2026-04-27 세션)
