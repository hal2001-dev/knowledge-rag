# 운영 모니터링 — 정기 스냅샷 + 워커 RSS 가드

**상태**: active
**마지막 업데이트**: 2026-04-28
**관련 페이지**: [runbook.md](runbook.md), [features/ingestion.md](../features/ingestion.md), [issues/open/ISSUE-005](../issues/open/ISSUE-005-memory-guard-worker-scapegoat.md), [issues/open/ISSUE-004](../issues/open/ISSUE-004-docling-parse-longtail.md), [architecture/decisions.md ADR-031](../architecture/decisions.md)

## 요약

macOS launchd가 5분 주기로 프로젝트 프로세스 스냅샷을 dump하고, 30초 주기로 `apps.indexer_worker` RSS를 점검해 임계(기본 14GB) 초과 시 그 워커만 SIGTERM한다. ISSUE-005 누명 사건(다른 범인을 잡는 가드 결함)을 구조적으로 차단한 운영 인프라(TASK-021, ADR-031).

## 구성

| 컴포넌트 | 주기 | 역할 | 대상 | 동작 |
|---|---|---|---|---|
| `scripts/krag_snapshot.py` | 5분 | 정기 관찰(전용) | knowledge-rag 관련 프로세스 + 시스템 전체 | dump → 종료 |
| `scripts/krag_guard.py` | 30초 | RSS 가드 | `apps.indexer_worker` 한정 | 임계 ≥ 14GB 시 SIGTERM + 알림 + dump |

두 컴포넌트 모두 launchd가 fork — 데몬 상시 가동 없음, Claude Code/셸 lifecycle 무관.

## 등록·해제

```bash
# 등록 (1회)
launchctl load ~/Library/LaunchAgents/com.knowledge-rag.snapshot.plist
launchctl load ~/Library/LaunchAgents/com.knowledge-rag.guard.plist

# 등록 확인
launchctl list | grep knowledge-rag
# com.knowledge-rag.guard      0   <PID 또는 -.>
# com.knowledge-rag.snapshot   0   <PID 또는 -.>

# 해제 (회귀)
launchctl unload ~/Library/LaunchAgents/com.knowledge-rag.guard.plist
launchctl unload ~/Library/LaunchAgents/com.knowledge-rag.snapshot.plist
```

`RunAtLoad=true`라 `load` 직후 첫 실행이 즉시 발생한다.

## 로그 위치

```
data/diag/snapshot/YYYYMMDD.log         # 5분마다 추가, 7일 후 .log.gz로 자동 압축
data/diag/snapshot/launchd.stdout.log   # launchd 자체 stdout (보통 비어 있음)
data/diag/snapshot/launchd.stderr.log   # launchd 자체 stderr (스크립트 에러 시 여기)
data/diag/guard/YYYYMMDD.log            # 30초마다 1줄 추가
data/diag/guard/launchd.stdout.log
data/diag/guard/launchd.stderr.log
data/diag/snapshot/guard_kill_pid<N>_<ts>.log  # 가드 SIGTERM 발사 직후 dump (ps auxm + vm_stat)
```

스냅샷 1회 형식 예시:
```
=== snapshot ts=2026-04-28T10:46:56Z ===
sys used%=9.3 free%=86.1 load1=3.18 load5=4.02
project procs (9):
  pid=71943 rss=1493MB cpu=18.8% etime=38:39 cmd=claude cwd=...
  pid=79071 rss=667MB cpu=0.0% etime=00:00 cmd=python -m apps.indexer_worker
  ...
top10 RSS (system-wide):
  pid=71943 rss=1493MB cpu=18.8% cmd=claude
  ...
listen ports: 3000=0 8000=0 8501=0
```

## 임계 조정

LaunchAgents plist의 환경변수 또는 스크립트 직접 실행 시 환경변수로 조정:

```bash
# plist 수정
~/Library/LaunchAgents/com.knowledge-rag.guard.plist
# <key>KRAG_GUARD_RSS_GB</key>
# <string>16</string>
# 변경 후 unload → load 재기동 필요

# 또는 수동 1회 실행
KRAG_GUARD_RSS_GB=16 python scripts/krag_guard.py
```

**현재 기본값 14GB 근거**: ISSUE-004 측정 idle RSS 13.18GB 평탄(2026-04-27→04-28 워커 15시간 가동) + 1GB 여유. 운영 데이터로 16GB 등 조정 검토 가능.

## 관찰 전용 모드 (회귀)

가드 SIGTERM 정책이 의심스러우면 `--observe-only` 토글로 임계 도달 시 로그만 남기고 kill하지 않게 할 수 있다. plist의 `ProgramArguments`에 `--observe-only`를 추가하고 unload → load.

## 모의 테스트 (등록 후 검증용)

decoy 프로세스로 가드 SIGTERM이 실제로 발사되는지 검증:

```bash
# decoy: cmdline에 'apps.indexer_worker' 포함된 sleep
bash -c 'exec -a "python -m apps.indexer_worker --decoy" sleep 300' &

# 임계 0GB로 강제 트리거 — observe-only 먼저
KRAG_GUARD_RSS_GB=0 python scripts/krag_guard.py --observe-only
# 로그: OBSERVE pid=NNN rss=NNNMB >= 0MB (--observe-only)

# 진짜 SIGTERM
KRAG_GUARD_RSS_GB=0 python scripts/krag_guard.py
# 로그: KILL pid=NNN rss=NNNMB SIGTERM sent, dump=guard_kill_pid<N>_<ts>.log
# decoy 프로세스 사라짐 확인
```

## 가드 결정 사양

| 항목 | 값 | 근거 |
|---|---|---|
| 대상 | `apps.indexer_worker` 한정 | NextJS dev/Streamlit/Uvicorn 자동 kill 회피 (TASK-019 진행 중) |
| 임계 | RSS ≥ **14GB** | ISSUE-004 idle 13.18GB + 1GB 여유 |
| 시그널 | SIGTERM only | ISSUE-005 7초 graceful 검증, SIGKILL 미사용 |
| 자동 재기동 | 없음 | 사람이 상태 보고 결정 (누수 패턴 추적용) |
| 알림 | macOS osascript | 외부 키 0 (Slack/이메일 합의 시 별건) |
| 자기 PID 제외 | 명시 로직 | 가드 cmdline 우연 일치 시 자살 방지 |

## 한계

- **launchd 사용자 영역 한정**: 로그아웃 시 가드 정지. 재로그인 시 자동 재개. macOS 재부팅도 자동 복귀.
- **Claude Code/셸 lifecycle 무관**: launchd fork 모델이라 Claude Code 재시작·터미널 종료에 영향 없음. 등록 1회 후 독립 동작.
- **macOS 알림 권한**: 첫 실행 시 권한 다이얼로그. 거부되어도 무음 kill은 발생(로그엔 남음, 사후 추적 가능).
- **외부 알림 없음**: Slack/이메일 미적용 — 비용·키 합의 규칙(`feedback_cost_keys`).
- **워커 외 프로세스 가드 없음**: NextJS dev/Streamlit/Uvicorn은 관찰만. 추후 합의 시 화이트리스트 확장.
- **임계 14GB 빠듯함**: ISSUE-004 idle 13.18GB가 상시 패턴이면 false positive 가능. 운영 데이터로 16GB 조정 또는 "2회 연속 트리거" 컷 보강 검토(별건).

## 관련 후속

- ISSUE-005 본격 해결: 시스템 used% 가드를 RSS top 식별 + 사용자 화이트리스트 기반으로 재설계 — 별건
- ISSUE-004 후속 5번 `INDEXER_MAX_JOBS` 자가 종료 — 별건, 본 모니터링과 보완 관계
- 임계 조정: 2~4주 운영 데이터 축적 후 14→16GB 또는 트리거 정책 보강

## 출처

- 결정: [decisions.md ADR-031](../architecture/decisions.md)
- 트리거 사건: [ISSUE-005](../issues/open/ISSUE-005-memory-guard-worker-scapegoat.md), [ISSUE-004](../issues/open/ISSUE-004-docling-parse-longtail.md)
- 코드: `scripts/krag_snapshot.py`, `scripts/krag_guard.py`
- launchd: `~/Library/LaunchAgents/com.knowledge-rag.snapshot.plist`, `com.knowledge-rag.guard.plist`
