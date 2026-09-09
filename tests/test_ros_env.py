"""ros_env.py 부트스트랩 테스트.

중요: os.execve는 반드시 monkeypatch로 가로챈다 (AGENTS.md §3 — 테스트 프로세스 교체 방지).
"""

from __future__ import annotations

import os
import pathlib
import sys

import pytest

import ros_tviewer.ros_env as ros_env

ROS_ROOT = pathlib.Path("/opt/ros")


def test_try_import_rclpy_when_ros_site_in_path(monkeypatch):
    """ROS site-packages가 sys.path에 있으면 find_spec이 rclpy를 찾는다."""
    candidates = ros_env._ros_site_dirs()
    if not candidates:
        pytest.skip("ROS 2가 설치되지 않은 환경")
    monkeypatch.syspath_prepend(str(candidates[0]))
    assert ros_env._try_import_rclpy() is True


@pytest.mark.skipif(not ROS_ROOT.is_dir(), reason="ROS 2가 설치되지 않은 환경")
def test_ros_site_dirs_finds_installed_distro():
    candidates = ros_env._ros_site_dirs()
    assert candidates, "ROS_ROOT가 있는데 site-packages 후보가 비어 있음"
    assert any((c / "rclpy").is_dir() for c in candidates)


def test_ensure_rclpy_returns_when_importable(monkeypatch):
    monkeypatch.setattr(ros_env, "_try_import_rclpy", lambda: True)
    assert ros_env.ensure_rclpy() is None  # 재실행 없이 즉시 반환


def test_ensure_rclpy_no_candidates_raises(monkeypatch):
    monkeypatch.setattr(ros_env, "_try_import_rclpy", lambda: False)
    monkeypatch.setattr(ros_env, "_ros_site_dirs", lambda: [])
    with pytest.raises(RuntimeError, match="rclpy"):
        ros_env.ensure_rclpy()


def test_ensure_rclpy_attempts_reexec_then_raises(monkeypatch):
    calls = []
    monkeypatch.setattr(ros_env, "_try_import_rclpy", lambda: False)
    fake_site = pathlib.Path("/opt/ros/fake/lib/python3.99/site-packages")
    monkeypatch.setattr(ros_env, "_ros_site_dirs", lambda: [fake_site])
    monkeypatch.setattr(ros_env, "_reexec_with_ros_env", lambda site: calls.append(site))
    with pytest.raises(RuntimeError, match="rclpy"):
        ros_env.ensure_rclpy()
    assert calls == [fake_site]


def test_ensure_rclpy_marker_prevents_second_reexec(monkeypatch):
    calls = []
    monkeypatch.setattr(ros_env, "_try_import_rclpy", lambda: False)
    monkeypatch.setattr(ros_env, "_ros_site_dirs", lambda: [])
    monkeypatch.setattr(ros_env, "_reexec_with_ros_env", lambda site: calls.append(site))
    monkeypatch.setenv("ROS_TVIEWER_REEXEC", "1")
    with pytest.raises(RuntimeError, match="rclpy"):
        ros_env.ensure_rclpy()
    assert calls == []  # 마커가 있으면 재실행 시도하지 않음


def test_reexec_env_composition(monkeypatch):
    recorded = {}
    fake_site = pathlib.Path("/opt/ros/fake/lib/python3.99/site-packages")

    def fake_execve(path, argv, env):
        recorded["path"] = path
        recorded["argv"] = argv
        recorded["env"] = env
        raise SystemExit(0)  # execve는 정상적으로는 반환하지 않는다

    monkeypatch.setattr(os, "execve", fake_execve)
    monkeypatch.setenv("LD_LIBRARY_PATH", "/preexisting")
    monkeypatch.setenv("PYTHONPATH", "")

    with pytest.raises(SystemExit):
        ros_env._reexec_with_ros_env(fake_site)

    env = recorded["env"]
    assert env["ROS_TVIEWER_REEXEC"] == "1"
    assert env["PYTHONPATH"].startswith(str(fake_site))
    assert env["LD_LIBRARY_PATH"].startswith("/opt/ros/fake/lib")
    assert "/preexisting" in env["LD_LIBRARY_PATH"]
    assert env["AMENT_PREFIX_PATH"].startswith("/opt/ros/fake")
    assert recorded["argv"][1:] == sys.argv  # 동일 argv로 재실행
    assert recorded["path"] == sys.executable
