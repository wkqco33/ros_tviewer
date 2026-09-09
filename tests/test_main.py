"""main.py CLI 구조 테스트 — rclpy 불필요, 항상 실행."""

from __future__ import annotations

import pathlib

from ros_tviewer.main import build_root


def _subcommands(root):
    return {c.name: c for c in root.commands}


def test_build_root_has_viewer_commands():
    root = build_root()
    names = set(_subcommands(root))
    assert {"play", "topics", "config", "version"} <= names


def test_play_declares_flags():
    root = build_root()
    play = _subcommands(root)["play"]
    names = {f.name for f in play.flags}
    assert {"fps", "rotate", "stretch", "compressed", "timeout", "frames"} <= names


def test_play_rotate_has_choices():
    root = build_root()
    play = _subcommands(root)["play"]
    rotate = next(f for f in play.flags if f.name == "rotate")
    assert rotate.choices is not None
    assert set(rotate.choices) == {0, 90, 180, 270}


def test_config_defaults_include_camera_keys():
    root = build_root()
    settings = root._config_settings
    assert settings is not None
    defaults = settings.defaults or {}
    assert defaults["camera"]["topic"] == "/camera/image_raw"
    assert defaults["camera"]["fps"] == 30
    assert defaults["camera"]["timeout"] == 5.0


def test_play_invokes_run_viewer_with_parsed_flags(monkeypatch):
    import ros_tviewer.node as node_mod
    import ros_tviewer.ros_env as ros_env_mod

    calls = {}

    monkeypatch.setattr(ros_env_mod, "ensure_rclpy", lambda: None)

    def fake_run_viewer(**kwargs):
        calls.update(kwargs)
        return 0

    monkeypatch.setattr(node_mod, "run_viewer", fake_run_viewer)

    root = build_root()
    rc = root.execute(["play", "/cam/img", "--fps", "10", "--rotate", "90", "--stretch", "-z"])
    assert rc == 0
    assert calls["topic"] == "/cam/img"
    assert calls["fps"] == 10
    assert calls["rotate"] == 90
    assert calls["stretch"] is True
    assert calls["compressed"] is True


def test_play_passes_max_frames(monkeypatch):
    import ros_tviewer.node as node_mod
    import ros_tviewer.ros_env as ros_env_mod

    calls = {}
    monkeypatch.setattr(ros_env_mod, "ensure_rclpy", lambda: None)

    def fake_run_viewer(**kwargs):
        calls.update(kwargs)
        return 0

    monkeypatch.setattr(node_mod, "run_viewer", fake_run_viewer)
    root = build_root()
    rc = root.execute(["play", "/t", "--frames", "5"])
    assert rc == 0
    assert calls["max_frames"] == 5


def test_play_compressed_is_tri_state(monkeypatch):
    """compressed 미지정 시 None(자동감지)이 전달되어야 한다 — bool 강제 금지."""
    import ros_tviewer.node as node_mod
    import ros_tviewer.ros_env as ros_env_mod

    calls = {}
    monkeypatch.setattr(ros_env_mod, "ensure_rclpy", lambda: None)

    def fake_run_viewer(**kwargs):
        calls.update(kwargs)
        return 0

    monkeypatch.setattr(node_mod, "run_viewer", fake_run_viewer)
    root = build_root()
    rc = root.execute(["play", "/t"])
    assert rc == 0
    assert calls["compressed"] is None  # 자동 감지


def test_play_compressed_forced_by_config(monkeypatch):
    import ros_tviewer.node as node_mod
    import ros_tviewer.ros_env as ros_env_mod

    calls = {}
    monkeypatch.setattr(ros_env_mod, "ensure_rclpy", lambda: None)
    monkeypatch.setattr(ros_env_mod, "_cfg_get", lambda ctx, key, default: True, raising=False)

    def fake_run_viewer(**kwargs):
        calls.update(kwargs)
        return 0

    monkeypatch.setattr(node_mod, "run_viewer", fake_run_viewer)
    # config.toml의 camera.compressed=true를 시뮬레이션: 임시 config 파일 주입
    cfg = pathlib.Path("tests/_tmp_compressed.toml")
    cfg.write_text("[camera]\ncompressed = true\n")
    try:
        root = build_root()
        rc = root.execute(["play", "/t", "--config", str(cfg)])
    finally:
        cfg.unlink(missing_ok=True)
    assert rc == 0
    assert calls["compressed"] is True


def test_version_reports_app_and_dependencies(capsys):
    root = build_root()
    rc = root.execute(["version"])
    assert rc == 0


def test_version_output_contains_runtime_report(capsys):
    root = build_root()
    rc = root.execute(["version"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "ros-tviewer" in out
    assert "0.1.0" in out  # 앱 버전 (importlib.metadata 기반)
    assert "python" in out
    assert "tcamviewer" in out  # 핵심 의존성 버전 리포트
    assert "terminal" in out


def test_version_missing_dependency_shows_placeholder(monkeypatch, capsys):
    from importlib.metadata import PackageNotFoundError

    def raise_missing(name):
        raise PackageNotFoundError(name)

    monkeypatch.setattr("importlib.metadata.version", raise_missing)
    root = build_root()
    rc = root.execute(["version"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "not installed" in out  # 누락된 의존성도 안정적으로 리포트


def test_play_topic_falls_back_to_config(monkeypatch):
    import ros_tviewer.node as node_mod
    import ros_tviewer.ros_env as ros_env_mod

    calls = {}
    monkeypatch.setattr(ros_env_mod, "ensure_rclpy", lambda: None)

    def fake_run_viewer(**kwargs):
        calls.update(kwargs)
        return 0

    monkeypatch.setattr(node_mod, "run_viewer", fake_run_viewer)

    root = build_root()
    rc = root.execute(["play"])
    assert rc == 0
    assert calls["topic"] == "/camera/image_raw"


def test_topics_invokes_list_camera_topics(monkeypatch):
    import ros_tviewer.node as node_mod
    import ros_tviewer.ros_env as ros_env_mod

    monkeypatch.setattr(ros_env_mod, "ensure_rclpy", lambda: None)
    monkeypatch.setattr(
        node_mod,
        "list_camera_topics",
        lambda timeout=5.0: [("/a", "Image"), ("/b", "CompressedImage")],
    )

    root = build_root()
    rc = root.execute(["topics"])
    assert rc == 0


def test_topics_on_empty_ros_still_succeeds(monkeypatch):
    import ros_tviewer.node as node_mod
    import ros_tviewer.ros_env as ros_env_mod

    monkeypatch.setattr(ros_env_mod, "ensure_rclpy", lambda: None)
    monkeypatch.setattr(node_mod, "list_camera_topics", lambda timeout=5.0: [])
    root = build_root()
    assert root.execute(["topics"]) == 0
