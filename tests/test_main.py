"""main.py CLI 구조 테스트 — rclpy 불필요, 항상 실행."""

from __future__ import annotations

import pathlib

from ros_tviewer.config_io import read_toml
from ros_tviewer.main import build_root


def _subcommands(root):
    return {c.name: c for c in root.commands}


def _isolate_user_config(monkeypatch, tmp_path: pathlib.Path) -> pathlib.Path:
    """user_config_dir를 tmp로 격리해 개발 머신의 실제 설정을 읽지 않게 한다."""
    import ros_tviewer.main as main_mod

    user_dir = tmp_path / "usercfg"
    monkeypatch.setattr(main_mod, "user_config_dir", lambda name: user_dir / name)
    return user_dir


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
    assert "app" not in defaults  # 어디서도 읽지 않는 app.* 키는 제거했다


def test_config_has_management_subcommands():
    root = build_root()
    config_cmd = root.find_subcommand("config")
    assert config_cmd is not None
    names = {child.name for child in config_cmd.commands}
    assert {"show", "path", "init", "set"} <= names


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
    assert pyproject_version() in out  # 앱 버전 — pyproject.toml 단일 소스
    assert "python" in out
    assert "tcamviewer" in out  # 핵심 의존성 버전 리포트
    assert "terminal" in out


def pyproject_version() -> str:
    import tomllib

    data = tomllib.loads(pathlib.Path("pyproject.toml").read_text(encoding="utf-8"))
    return str(data["project"]["version"])


def test_version_has_no_hardcoded_constant():
    """버전은 pyproject.toml 단일 소스다 — 코드 상수로 복제하지 않는다."""
    import ros_tviewer

    assert ros_tviewer.__version__ == pyproject_version()
    src = (pathlib.Path("src/ros_tviewer/main.py")).read_text(encoding="utf-8")
    assert "VERSION = " not in src


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


def test_cli_works_without_config_and_env(monkeypatch, tmp_path):
    """config.toml/.env 없는 환경(클론 직후/PyPI 설치)에서 CLI가 실패하지 않아야 한다."""
    monkeypatch.chdir(tmp_path)  # 두 파일 모두 없는 디렉터리
    _isolate_user_config(monkeypatch, tmp_path)  # 사용자 경로도 비어 있게 격리
    root = build_root()
    settings = root._config_settings
    assert settings is not None
    assert settings.files == ()
    assert settings.dotenv is None
    assert root.execute(["config"]) == 0


def test_default_config_files_loaded_when_present(tmp_path, monkeypatch):
    """파일이 있으면 기존처럼 로드되고, 설정이 플래그 기본값을 이긴다."""
    import ros_tviewer.node as node_mod
    import ros_tviewer.ros_env as ros_env_mod

    _isolate_user_config(monkeypatch, tmp_path)  # cwd config.toml만 후보가 되도록
    (tmp_path / "config.toml").write_text('[camera]\ntopic = "/cfg/topic"\n')
    (tmp_path / ".env").write_text("ROS_TVIEWER_CAMERA__FPS=7\n")
    monkeypatch.chdir(tmp_path)

    calls = {}
    monkeypatch.setattr(ros_env_mod, "ensure_rclpy", lambda: None)
    monkeypatch.setattr(node_mod, "run_viewer", lambda **kwargs: calls.update(kwargs) or 0)

    root = build_root()
    settings = root._config_settings
    assert settings is not None
    assert settings.files == ("config.toml",)
    assert settings.dotenv == ".env"
    assert root.execute(["play"]) == 0
    assert calls["topic"] == "/cfg/topic"
    assert calls["fps"] == 7


def test_user_platform_config_loaded(tmp_path, monkeypatch):
    """플랫폼 사용자 경로의 config.toml을 로드한다 (uvx 등 임의 cwd 환경)."""
    import ros_tviewer.node as node_mod
    import ros_tviewer.ros_env as ros_env_mod

    user_dir = _isolate_user_config(monkeypatch, tmp_path)
    user_file = user_dir / "ros-tviewer" / "config.toml"
    user_file.parent.mkdir(parents=True)
    user_file.write_text('[camera]\ntopic = "/user/topic"\n')
    monkeypatch.chdir(tmp_path)  # cwd에는 config.toml 없음

    calls = {}
    monkeypatch.setattr(ros_env_mod, "ensure_rclpy", lambda: None)
    monkeypatch.setattr(node_mod, "run_viewer", lambda **kwargs: calls.update(kwargs) or 0)

    root = build_root()
    settings = root._config_settings
    assert settings is not None
    assert settings.files == (str(user_file),)
    assert root.execute(["play"]) == 0
    assert calls["topic"] == "/user/topic"


def test_cwd_config_overrides_user_config(tmp_path, monkeypatch):
    """cwd의 config.toml이 사용자 설정을 이긴다(로컬 오버라이드). --config가 최우선."""
    import ros_tviewer.node as node_mod
    import ros_tviewer.ros_env as ros_env_mod

    user_dir = _isolate_user_config(monkeypatch, tmp_path)
    user_file = user_dir / "ros-tviewer" / "config.toml"
    user_file.parent.mkdir(parents=True)
    user_file.write_text('[camera]\ntopic = "/user/topic"\nfps = 11\n')
    (tmp_path / "config.toml").write_text('[camera]\ntopic = "/cwd/topic"\n')
    monkeypatch.chdir(tmp_path)

    calls = {}
    monkeypatch.setattr(ros_env_mod, "ensure_rclpy", lambda: None)
    monkeypatch.setattr(node_mod, "run_viewer", lambda **kwargs: calls.update(kwargs) or 0)

    root = build_root()
    settings = root._config_settings
    assert settings is not None
    assert settings.files == (str(user_file), "config.toml")
    assert root.execute(["play"]) == 0
    assert calls["topic"] == "/cwd/topic"  # cwd가 user를 이긴다
    assert calls["fps"] == 11  # cwd에 없는 키는 user에서 보충


def test_config_init_creates_user_config(tmp_path, monkeypatch):
    _isolate_user_config(monkeypatch, tmp_path)
    monkeypatch.chdir(tmp_path)
    root = build_root()
    assert root.execute(["config", "init"]) == 0
    target = tmp_path / "usercfg" / "ros-tviewer" / "config.toml"
    assert target.is_file()
    data = read_toml(target)
    assert data["camera"]["topic"] == "/camera/image_raw"


def test_config_init_refuses_existing_without_force(tmp_path, monkeypatch):
    _isolate_user_config(monkeypatch, tmp_path)
    monkeypatch.chdir(tmp_path)
    root = build_root()
    assert root.execute(["config", "init"]) == 0
    assert root.execute(["config", "init"]) == 1  # 이미 존재
    assert root.execute(["config", "init", "--force"]) == 0  # 덮어쓰기 허용


def test_config_set_writes_typed_values(tmp_path, monkeypatch):
    _isolate_user_config(monkeypatch, tmp_path)
    monkeypatch.chdir(tmp_path)
    root = build_root()
    assert root.execute(["config", "init"]) == 0
    assert root.execute(["config", "set", "camera.fps", "60"]) == 0
    assert root.execute(["config", "set", "camera.topic", "/new/topic"]) == 0
    assert root.execute(["config", "set", "camera.stretch", "true"]) == 0
    data = read_toml(tmp_path / "usercfg" / "ros-tviewer" / "config.toml")
    assert data["camera"]["fps"] == 60  # int로 해석
    assert data["camera"]["topic"] == "/new/topic"  # 문자열로 해석
    assert data["camera"]["stretch"] is True


def test_config_set_requires_two_args(tmp_path, monkeypatch, capsys):
    _isolate_user_config(monkeypatch, tmp_path)
    monkeypatch.chdir(tmp_path)
    root = build_root()
    assert root.execute(["config", "set", "camera.fps"]) == 1
    assert "사용법" in capsys.readouterr().out


def test_config_show_and_path_run_clean(tmp_path, monkeypatch, capsys):
    _isolate_user_config(monkeypatch, tmp_path)
    monkeypatch.chdir(tmp_path)
    root = build_root()
    assert root.execute(["config", "show"]) == 0
    assert "camera" in capsys.readouterr().out
    assert root.execute(["config", "path"]) == 0
    out = capsys.readouterr().out
    assert "user" in out and "cwd" in out
