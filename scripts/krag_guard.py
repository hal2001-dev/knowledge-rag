#!/usr/bin/env python3
"""
워커 RSS 가드 (TASK-021, ADR-031).

launchd가 30초 주기로 fork-exec하는 단발 실행 스크립트.
대상 = `apps.indexer_worker` 한정. RSS ≥ 임계 시 그 PID에만 SIGTERM + macOS 알림 + 사후 dump.

ISSUE-005 누명 결함 정반대로 뒤집기:
- 시스템 used% 단일 트리거 (X) → 프로세스별 RSS (O)
- 죽일 대상 워커 고정 (X) → 그 워커의 RSS가 임계를 넘었을 때만 그 워커 종료 (O)
- 다른 프로세스는 관찰만 (X 자동 kill)

토글:
  --observe-only  관찰 전용 (kill 없음, 로그만)
  KRAG_GUARD_RSS_GB  임계 조정 (기본 14)
"""
from __future__ import annotations

import argparse
import datetime as dt
import os
import signal
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
LOG_DIR = ROOT / "data" / "diag" / "guard"
SNAPSHOT_DIR = ROOT / "data" / "diag" / "snapshot"
WORKER_KEY = "apps.indexer_worker"
DEFAULT_RSS_GB = 14.0


def now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def write_line(line: str) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    today = dt.datetime.now().strftime("%Y%m%d")
    path = LOG_DIR / f"{today}.log"
    with path.open("a", encoding="utf-8") as f:
        f.write(line + "\n")
        f.flush()
        os.fsync(f.fileno())


def find_worker_pids(self_pid: int) -> list[tuple[int, int, str]]:
    """apps.indexer_worker 프로세스 목록. self_pid 제외.

    Returns: [(pid, rss_mb, cmd), ...]
    """
    out = subprocess.run(
        ["ps", "axo", "pid=,rss=,command="],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    matched: list[tuple[int, int, str]] = []
    for line in out.splitlines():
        parts = line.strip().split(None, 2)
        if len(parts) < 3:
            continue
        try:
            pid = int(parts[0])
            rss_kb = int(parts[1])
        except ValueError:
            continue
        cmd = parts[2]
        if pid == self_pid:
            continue
        if WORKER_KEY in cmd:
            matched.append((pid, rss_kb // 1024, cmd))
    return matched


def macos_notify(title: str, body: str) -> None:
    try:
        # 따옴표 이스케이프 방지: shlex 안 쓰고 안전한 인자만 통과
        safe_title = title.replace('"', "'")[:120]
        safe_body = body.replace('"', "'")[:240]
        subprocess.run(
            [
                "osascript",
                "-e",
                f'display notification "{safe_body}" with title "{safe_title}"',
            ],
            check=False,
            timeout=3,
        )
    except Exception:
        pass


def dump_post_kill_snapshot(pid: int, rss_mb: int) -> str:
    """가드 발사 직후 시스템 상태 dump."""
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    ts = dt.datetime.now().strftime("%Y%m%dT%H%M%S")
    path = SNAPSHOT_DIR / f"guard_kill_pid{pid}_{ts}.log"
    try:
        ps = subprocess.run(
            ["ps", "auxm"], capture_output=True, text=True, timeout=5
        ).stdout
    except Exception as e:
        ps = f"ps failed: {e}"
    try:
        vm = subprocess.run(
            ["vm_stat"], capture_output=True, text=True, timeout=3
        ).stdout
    except Exception as e:
        vm = f"vm_stat failed: {e}"
    with path.open("w", encoding="utf-8") as f:
        f.write(f"=== guard kill snapshot ===\n")
        f.write(f"ts={now_iso()} target_pid={pid} rss_mb={rss_mb}\n\n")
        f.write("== ps auxm ==\n")
        f.write(ps)
        f.write("\n== vm_stat ==\n")
        f.write(vm)
        f.flush()
        os.fsync(f.fileno())
    return str(path)


def main() -> int:
    parser = argparse.ArgumentParser(description="apps.indexer_worker RSS 가드")
    parser.add_argument(
        "--observe-only",
        action="store_true",
        help="관찰 전용 (kill 없음, 임계 도달 시 로그만)",
    )
    args = parser.parse_args()

    threshold_gb = float(os.environ.get("KRAG_GUARD_RSS_GB", DEFAULT_RSS_GB))
    threshold_mb = int(threshold_gb * 1024)

    self_pid = os.getpid()
    workers = find_worker_pids(self_pid)

    if not workers:
        write_line(f"{now_iso()} no-op: worker not running (threshold={threshold_gb}GB)")
        return 0

    actions = []
    for pid, rss_mb, cmd in workers:
        if rss_mb >= threshold_mb:
            if args.observe_only:
                actions.append(
                    f"OBSERVE pid={pid} rss={rss_mb}MB >= {threshold_mb}MB (--observe-only)"
                )
            else:
                snapshot_path = dump_post_kill_snapshot(pid, rss_mb)
                try:
                    os.kill(pid, signal.SIGTERM)
                    actions.append(
                        f"KILL pid={pid} rss={rss_mb}MB SIGTERM sent, "
                        f"dump={Path(snapshot_path).name}"
                    )
                    macos_notify(
                        "knowledge-rag worker killed",
                        f"pid={pid} rss={rss_mb}MB ≥ {threshold_gb}GB SIGTERM",
                    )
                except ProcessLookupError:
                    actions.append(f"KILL pid={pid} already gone")
                except PermissionError as e:
                    actions.append(f"KILL pid={pid} FAILED: {e}")
        else:
            actions.append(f"ok pid={pid} rss={rss_mb}MB < {threshold_mb}MB")

    write_line(f"{now_iso()} threshold={threshold_gb}GB workers={len(workers)} | {' ; '.join(actions)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
