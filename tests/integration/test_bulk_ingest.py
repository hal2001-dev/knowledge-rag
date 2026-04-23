"""TASK-010: bulk_ingest.py 스모크 — 탐색·필터·dry-run 검증.

실제 API 호출은 검증 범위 밖. 로컬 파일 탐색 로직이 하위 폴더 포함·확장자 필터·
정규식 exclude를 올바르게 적용하는지 dry-run으로 확인한다.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).parent.parent.parent
SCRIPT = REPO_ROOT / "scripts" / "bulk_ingest.py"


def _run(args: list[str]) -> subprocess.CompletedProcess:
    cmd = [
        str(REPO_ROOT / ".venv/bin/python"),
        str(SCRIPT),
        *args,
    ]
    return subprocess.run(cmd, capture_output=True, text=True, cwd=REPO_ROOT)


@pytest.fixture
def sample_tree(tmp_path: Path) -> Path:
    """샘플 디렉터리 구조:
        tmp/
          top.txt
          readme.md
          draft_skip.txt    (exclude 테스트)
          unsupported.log   (확장자 필터)
          sub_a/inner.txt
          sub_b/deep/nested.txt
          sub_b/archive/old.txt  (exclude 테스트)
    """
    (tmp_path / "top.txt").write_text("top")
    (tmp_path / "readme.md").write_text("readme")
    (tmp_path / "draft_skip.txt").write_text("draft")
    (tmp_path / "unsupported.log").write_text("log")
    (tmp_path / "sub_a").mkdir()
    (tmp_path / "sub_a" / "inner.txt").write_text("inner")
    (tmp_path / "sub_b" / "deep").mkdir(parents=True)
    (tmp_path / "sub_b" / "deep" / "nested.txt").write_text("nested")
    (tmp_path / "sub_b" / "archive").mkdir()
    (tmp_path / "sub_b" / "archive" / "old.txt").write_text("old")
    return tmp_path


def test_dry_run_recursive_default(sample_tree: Path):
    """기본 재귀 탐색 — 지원 확장자 모두 발견, 비지원(.log) 제외."""
    r = _run(["--dir", str(sample_tree), "--dry-run"])
    assert r.returncode == 0, r.stderr
    out = r.stdout
    # 지원 확장자만: top.txt, readme.md, draft_skip.txt, inner.txt, nested.txt, old.txt
    assert "대상 파일  : 6개" in out
    assert "unsupported.log" not in out  # 확장자 필터


def test_dry_run_no_recursive(sample_tree: Path):
    """--no-recursive: 최상위 파일만 (txt 2 + md 1 = 3)."""
    r = _run(["--dir", str(sample_tree), "--no-recursive", "--dry-run"])
    assert r.returncode == 0, r.stderr
    assert "대상 파일  : 3개" in r.stdout
    assert "sub_a/inner.txt" not in r.stdout  # 하위 폴더 제외


def test_dry_run_exclude_regex(sample_tree: Path):
    """--exclude: draft_ 와 archive/ 제외."""
    r = _run([
        "--dir", str(sample_tree),
        "--exclude", "draft_",
        "--exclude", "archive/",
        "--dry-run",
    ])
    assert r.returncode == 0, r.stderr
    out = r.stdout
    # top.txt, readme.md, inner.txt, nested.txt = 4개
    assert "대상 파일  : 4개" in out
    assert "draft_skip.txt" not in out
    assert "archive/old.txt" not in out


def test_dry_run_include_filter(sample_tree: Path):
    """--include '*.md' : 마크다운만."""
    r = _run([
        "--dir", str(sample_tree),
        "--include", "*.md",
        "--dry-run",
    ])
    assert r.returncode == 0, r.stderr
    out = r.stdout
    assert "대상 파일  : 1개" in out
    assert "readme.md" in out
    assert "top.txt" not in out


def test_missing_dir_exits_nonzero(tmp_path: Path):
    """존재하지 않는 폴더 → exit code 2."""
    r = _run(["--dir", str(tmp_path / "does_not_exist"), "--dry-run"])
    assert r.returncode == 2
    assert "찾을 수 없음" in r.stdout


def test_empty_dir_exits_zero(tmp_path: Path):
    """빈 폴더 → 정상 종료, 대상 0개."""
    r = _run(["--dir", str(tmp_path), "--dry-run"])
    assert r.returncode == 0
    assert "대상 파일  : 0개" in r.stdout or "대상 파일 없음" in r.stdout
