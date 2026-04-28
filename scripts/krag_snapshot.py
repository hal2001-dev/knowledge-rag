#!/usr/bin/env python3
"""
프로젝트 프로세스 정기 스냅샷 (TASK-021, ADR-031).

launchd가 5분 주기로 fork-exec하는 단발 실행 스크립트.
관찰 전용 — 어떤 프로세스도 종료하지 않는다.

수집 항목:
- 시각, 시스템 used%/free%/load1/load5
- knowledge-rag 관련 프로세스 (cwd 또는 cmdline에 'knowledge-rag' 포함) — PID/RSS/%CPU/etime/cmd
- 시스템 전체 RSS top 10
- 인기 포트(3000/8000/8501) LISTEN 카운트

저장: data/diag/snapshot/YYYYMMDD.log — 일자별 단일 파일, 매 줄 fsync, append
회전: 7일 이상 된 .log 파일은 .log.gz로 압축 (스크립트 자가 처리)
"""
from __future__ import annotations

import datetime as dt
import gzip
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
LOG_DIR = ROOT / "data" / "diag" / "snapshot"
PROJECT_KEY = "knowledge-rag"
WATCHED_PORTS = (3000, 8000, 8501)
RETENTION_DAYS = 7


def now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def system_stats() -> dict:
    used_pct = free_pct = None
    try:
        vm = subprocess.run(["vm_stat"], capture_output=True, text=True, check=True).stdout
        page_size = 16384  # macOS Apple Silicon 기본
        for line in vm.splitlines():
            if "page size of" in line:
                try:
                    page_size = int(line.split("page size of")[1].split("bytes")[0].strip())
                except Exception:
                    pass
        counts: dict[str, int] = {}
        for line in vm.splitlines():
            if ":" in line and "Pages" in line:
                k, v = line.split(":", 1)
                v = v.strip().rstrip(".")
                if v.isdigit():
                    counts[k.strip()] = int(v)
        free = counts.get("Pages free", 0) + counts.get("Pages speculative", 0)
        active = counts.get("Pages active", 0)
        inactive = counts.get("Pages inactive", 0)
        wired = counts.get("Pages wired down", 0)
        compressor = counts.get("Pages occupied by compressor", 0)
        used = active + wired + compressor
        total = used + free + inactive
        if total > 0:
            used_pct = round(used * 100 / total, 1)
            free_pct = round(free * 100 / total, 1)
    except Exception as e:
        return {"used_pct": None, "free_pct": None, "load": None, "err": f"vm_stat:{e}"}

    load1 = load5 = None
    try:
        upt = subprocess.run(["uptime"], capture_output=True, text=True, check=True).stdout
        if "load averages:" in upt:
            tail = upt.split("load averages:")[1].strip().split()
            load1 = float(tail[0])
            load5 = float(tail[1])
        elif "load average:" in upt:
            tail = upt.split("load average:")[1].strip().replace(",", "").split()
            load1 = float(tail[0])
            load5 = float(tail[1])
    except Exception:
        pass

    return {"used_pct": used_pct, "free_pct": free_pct, "load1": load1, "load5": load5}


def ps_aux() -> list[dict]:
    """ps aux를 dict 리스트로. RSS는 KB → MB 변환."""
    out = subprocess.run(
        ["ps", "axo", "pid=,rss=,pcpu=,etime=,command="],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    rows = []
    for line in out.splitlines():
        parts = line.strip().split(None, 4)
        if len(parts) < 5:
            continue
        try:
            pid = int(parts[0])
            rss_kb = int(parts[1])
            pcpu = float(parts[2])
        except ValueError:
            continue
        rows.append(
            {
                "pid": pid,
                "rss_mb": rss_kb // 1024,
                "pcpu": pcpu,
                "etime": parts[3],
                "cmd": parts[4],
            }
        )
    return rows


def cwd_for_pid(pid: int) -> str:
    try:
        out = subprocess.run(
            ["lsof", "-a", "-d", "cwd", "-Fn", "-p", str(pid)],
            capture_output=True,
            text=True,
            timeout=2,
        ).stdout
        for line in out.splitlines():
            if line.startswith("n"):
                return line[1:]
    except Exception:
        return ""
    return ""


def project_procs(rows: list[dict]) -> list[dict]:
    """cwd 또는 cmdline에 PROJECT_KEY 포함된 프로세스만."""
    matched = []
    for r in rows:
        if PROJECT_KEY in r["cmd"]:
            matched.append(r)
            continue
        cwd = cwd_for_pid(r["pid"])
        if cwd and PROJECT_KEY in cwd:
            r2 = dict(r)
            r2["cwd"] = cwd
            matched.append(r2)
    return matched


def listen_count(port: int) -> int:
    try:
        out = subprocess.run(
            ["lsof", "-nP", f"-iTCP:{port}", "-sTCP:LISTEN"],
            capture_output=True,
            text=True,
            timeout=3,
        ).stdout
        lines = [l for l in out.splitlines() if l]
        # 헤더 1줄 제외 (출력 없으면 0)
        return max(0, len(lines) - 1)
    except Exception:
        return -1


def rotate_old_logs() -> None:
    """RETENTION_DAYS 이상 된 .log를 .log.gz로 압축."""
    if not LOG_DIR.exists():
        return
    cutoff = dt.date.today() - dt.timedelta(days=RETENTION_DAYS)
    for p in LOG_DIR.glob("*.log"):
        try:
            stem = p.stem  # YYYYMMDD
            if len(stem) != 8 or not stem.isdigit():
                continue
            file_date = dt.date(int(stem[:4]), int(stem[4:6]), int(stem[6:8]))
            if file_date <= cutoff:
                gz = p.with_suffix(".log.gz")
                with p.open("rb") as src, gzip.open(gz, "wb") as dst:
                    shutil.copyfileobj(src, dst)
                p.unlink()
        except Exception:
            continue


def write_line(line: str) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    today = dt.datetime.now().strftime("%Y%m%d")
    path = LOG_DIR / f"{today}.log"
    with path.open("a", encoding="utf-8") as f:
        f.write(line + "\n")
        f.flush()
        os.fsync(f.fileno())


def main() -> int:
    ts = now_iso()
    sys_st = system_stats()
    rows = ps_aux()
    proj = project_procs(rows)
    top10 = sorted(rows, key=lambda r: r["rss_mb"], reverse=True)[:10]

    write_line(f"=== snapshot ts={ts} ===")
    write_line(
        f"sys used%={sys_st['used_pct']} free%={sys_st['free_pct']} "
        f"load1={sys_st.get('load1')} load5={sys_st.get('load5')}"
    )
    write_line(f"project procs ({len(proj)}):")
    for r in proj:
        cwd_str = f" cwd={r['cwd']}" if r.get("cwd") else ""
        write_line(
            f"  pid={r['pid']} rss={r['rss_mb']}MB cpu={r['pcpu']}% "
            f"etime={r['etime']} cmd={r['cmd'][:120]}{cwd_str}"
        )
    write_line("top10 RSS (system-wide):")
    for r in top10:
        write_line(
            f"  pid={r['pid']} rss={r['rss_mb']}MB cpu={r['pcpu']}% cmd={r['cmd'][:100]}"
        )
    listens = " ".join(f"{p}={listen_count(p)}" for p in WATCHED_PORTS)
    write_line(f"listen ports: {listens}")
    write_line("")

    rotate_old_logs()
    return 0


if __name__ == "__main__":
    sys.exit(main())
