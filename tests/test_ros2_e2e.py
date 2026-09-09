"""ROS 2 E2E — 실제 rclpy 구독 + tcamviewer 렌더.

rclpy의 C 확장은 LD_LIBRARY_PATH를 프로세스 시작 시점에 읽으므로, 서브프로세스로
ROS 환경을 구성해 실행한다 (AGENTS.md §3). ROS 미설치 환경에서는 skip.
"""

from __future__ import annotations

import os
import pathlib
import subprocess
import sys

import pytest

import ros_tviewer.ros_env as ros_env

ROOT = pathlib.Path(__file__).resolve().parents[1]
PUBLISHER = ROOT / "tests" / "tools" / "dummy_publisher.py"


_DOMAIN_SEQ = iter(range(41, 60))


def _ros_env(domain_id: int | None = None) -> dict[str, str] | None:
    """ROS 환경을 구성한다. 테스트별 고유 ROS_DOMAIN_ID로 DDS 간섭을 차단한다."""
    candidates = ros_env._ros_site_dirs()
    if not candidates:
        return None
    site = candidates[0]
    prefix = site.parents[2]
    env = os.environ.copy()
    env["ROS_DOMAIN_ID"] = str(domain_id if domain_id is not None else next(_DOMAIN_SEQ))

    def _prepend(name: str, value: str) -> None:
        parts = [p for p in env.get(name, "").split(":") if p]
        env[name] = ":".join([value, *parts]) if parts else value

    _prepend("PYTHONPATH", str(site))
    _prepend("LD_LIBRARY_PATH", str(prefix / "lib"))
    _prepend("AMENT_PREFIX_PATH", str(prefix))
    return env


@pytest.mark.skipif(not pathlib.Path("/opt/ros").is_dir(), reason="ROS 2 미설치 환경")
def test_play_renders_frames_from_live_topic():
    env = _ros_env()
    assert env is not None, "ROS_ROOT는 있으나 site-packages를 찾지 못했다"
    topic = "/tviewer/e2e/image"

    pub = subprocess.Popen(
        [sys.executable, str(PUBLISHER), "--topic", topic, "--count", "120", "--hz", "20"],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        # play가 자체 디스커버리 폴링(--timeout)으로 대기하므로 고정 sleep 불필요
        res = subprocess.run(
            [
                sys.executable,
                "-m",
                "ros_tviewer.main",
                "play",
                topic,
                "--fps",
                "20",
                "--frames",
                "10",
                "--timeout",
                "5",
            ],
            env=env,
            capture_output=True,
            text=True,
            timeout=60,
            cwd=str(ROOT),
        )
    finally:
        pub.wait(timeout=30)

    assert res.returncode == 0, f"stderr: {res.stderr[-2000:]}"
    # Half-Block 문자 또는 ANSI 이스케이프가 실제 렌더 출력으로 나와야 한다
    assert "\x1b[" in res.stdout or "▀" in res.stdout, f"stdout: {res.stdout[-2000:]}"


@pytest.mark.skipif(not pathlib.Path("/opt/ros").is_dir(), reason="ROS 2 미설치 환경")
def test_topics_lists_advertised_camera_topic():
    env = _ros_env()
    assert env is not None
    topic = "/tviewer/e2e/probe"

    pub = subprocess.Popen(
        [sys.executable, str(PUBLISHER), "--topic", topic, "--count", "40", "--hz", "20"],
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        res = subprocess.run(
            [sys.executable, "-m", "ros_tviewer.main", "topics", "--timeout", "5"],
            env=env,
            capture_output=True,
            text=True,
            timeout=60,
            cwd=str(ROOT),
        )
    finally:
        pub.wait(timeout=30)

    assert res.returncode == 0, f"stderr: {res.stderr[-2000:]}"
    assert topic in res.stdout


@pytest.mark.skipif(not pathlib.Path("/opt/ros").is_dir(), reason="ROS 2 미설치 환경")
def test_play_renders_compressed_frames():
    """CompressedImage 토픽 자동 감지 + jpeg 디코딩 경로."""
    env = _ros_env()
    assert env is not None
    topic = "/tviewer/e2e/image/compressed"

    pub = subprocess.Popen(
        [
            sys.executable,
            str(PUBLISHER),
            "--topic",
            topic,
            "--count",
            "120",
            "--hz",
            "20",
            "--compressed",
        ],
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        res = subprocess.run(
            [
                sys.executable,
                "-m",
                "ros_tviewer.main",
                "play",
                topic,
                "--fps",
                "20",
                "--frames",
                "10",
                "--timeout",
                "5",
            ],
            env=env,
            capture_output=True,
            text=True,
            timeout=60,
            cwd=str(ROOT),
        )
    finally:
        pub.wait(timeout=30)

    assert res.returncode == 0, f"stderr: {res.stderr[-2000:]}"
    assert "\x1b[" in res.stdout or "▀" in res.stdout, f"stdout: {res.stdout[-2000:]}"
