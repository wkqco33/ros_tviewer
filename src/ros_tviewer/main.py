from __future__ import annotations

import json
import pathlib

from wpycli import Command, ConfigSettings, LoggingSettings

APP_NAME = "ros-tviewer"
VERSION = "0.1.0"
DEFAULT_TOPIC = "/camera/image_raw"


def build_root() -> Command:
    # 기본 설정 파일(config.toml/.env)은 존재할 때만 로드한다 — wconfig는 누락 파일을
    # 오류로 처리하므로, 없는 환경(PyPI 설치/클론 직후)에서 CLI 전체가 실패한다.
    # 명시적 --config/--dotenv 플래그는 그대로 전달하며, 누락 시 오류가 맞다.
    config_files = ("config.toml",) if pathlib.Path("config.toml").is_file() else ()
    dotenv = ".env" if pathlib.Path(".env").is_file() else None

    root = Command(
        use="ros-tviewer",
        short="ROS 2 카메라 토픽을 터미널에서 재생하는 뷰어",
        long="sensor_msgs/Image, CompressedImage 토픽을 tcamviewer Half-Block "
        "TrueColor 렌더러로 터미널에 실시간 재생한다.",
        version=VERSION,
    )
    root.add_persistent_string_flag("config", help="추가 config.toml 경로", shorthand="c")
    root.add_persistent_string_flag("dotenv", help="추가 .env 경로")
    root.add_persistent_string_flag("log-level", help="로그 레벨 override")
    root.add_persistent_string_flag("log-file", help="로그 파일 경로 override")
    root.configure_runtime(
        config=ConfigSettings(
            defaults={
                "app": {
                    "name": APP_NAME,
                    "default_topic": DEFAULT_TOPIC,
                },
                "logging": {"level": "WARNING", "file": None},
                "camera": {
                    "topic": DEFAULT_TOPIC,
                    "fps": 30,
                    "rotate": 0,
                    "stretch": False,
                    "compressed": False,
                    "timeout": 5.0,
                    "frames": 0,
                },
            },
            files=config_files,
            dotenv=dotenv,
            env_prefix="ROS_TVIEWER",
            file_flag="config",
            dotenv_flag="dotenv",
        ),
        logging=LoggingSettings(
            logger_name="ros_tviewer",
            level_flag="log-level",
            log_file_flag="log-file",
        ),
    )

    play = Command(use="play [topic]", short="카메라 토픽을 터미널에서 재생한다.", run=run_play)
    play.add_int_flag("fps", help="렌더 FPS 상한 (0=무제한)", shorthand="f")
    play.add_int_flag("rotate", help="시계방향 회전(도)", shorthand="r", choices=[0, 90, 180, 270])
    play.add_bool_flag("stretch", help="종횡비 무시하고 터미널 전체 채우기", shorthand="s")
    play.add_bool_flag("compressed", help="CompressedImage 토픽으로 구독한다", shorthand="z")
    play.add_float_flag("timeout", help="토픽 자동감지 대기 시간(초)", shorthand="t")
    play.add_int_flag(
        "frames", help="지정 개수 프레임 렌더 후 종료 (0=무제한, 테스트/데모용)", shorthand="n"
    )
    topics = Command(use="topics", short="광고 중인 카메라 토픽을 나열한다.", run=run_topics)
    topics.add_float_flag("timeout", help="디스커버리 대기 시간(초)", shorthand="t")
    config = Command(use="config", short="현재 설정을 출력한다.", run=run_config)
    version = Command(use="version", short="앱·의존성·런타임 버전을 출력한다.", run=run_version)
    root.add_command(play, topics, config, version)
    return root


def _cfg_or_flag(ctx, flag: str, key: str, default):
    """CLI 플래그 > config 순서로 값을 읽는다 (None 플래그 = 미지정)."""
    value = ctx.flags.get(flag)
    if value is not None:
        return value
    return ctx.config.get(key, default)


def _to_int(ctx, flag: str, key: str, default: int) -> int:
    raw = _cfg_or_flag(ctx, flag, key, default)
    try:
        return int(raw)
    except (TypeError, ValueError) as exc:
        raise RuntimeError(f"{key} 값이 정수가 아닙니다: {raw!r}") from exc


def _to_float(ctx, flag: str, key: str, default: float) -> float:
    raw = _cfg_or_flag(ctx, flag, key, default)
    try:
        return float(raw)
    except (TypeError, ValueError) as exc:
        raise RuntimeError(f"{key} 값이 숫자가 아닙니다: {raw!r}") from exc


def _resolve_compressed(ctx) -> bool | None:
    """compressed 구독 결정: 플래그/설정이 true면 강제, 미지정이면 None(자동 감지).

    bool로 강제하면 CompressedImage 토픽에 Image로 구독하는 타입 미스매치가
    발생하므로, 미지정 시 반드시 None을 전달한다 (E2E 회귀 방지).
    """
    if bool(ctx.flags.get("compressed")) or bool(ctx.config.get("camera.compressed", False)):
        return True
    return None


def run_play(ctx):
    topic = ctx.args[0] if ctx.args else str(ctx.config.get("camera.topic", DEFAULT_TOPIC))
    fps = _to_int(ctx, "fps", "camera.fps", 30)
    rotate = _to_int(ctx, "rotate", "camera.rotate", 0)
    stretch = bool(ctx.flags.get("stretch") or ctx.config.get("camera.stretch", False))
    compressed = _resolve_compressed(ctx)
    timeout = _to_float(ctx, "timeout", "camera.timeout", 5.0)
    max_frames = _to_int(ctx, "frames", "camera.frames", 0) or None

    if ctx.logger is not None:
        ctx.logger.info("play started", extra={"topic": topic, "fps": fps, "rotate": rotate})

    from .node import run_viewer
    from .ros_env import ensure_rclpy

    ensure_rclpy()
    return run_viewer(
        topic=topic,
        fps=fps or None,
        rotate=rotate,
        stretch=stretch,
        compressed=compressed,
        timeout=timeout,
        max_frames=max_frames,
        logger=ctx.logger,
    )


def run_topics(ctx):
    timeout = _to_float(ctx, "timeout", "camera.timeout", 5.0)

    # pi-lens-ignore: Pyright:reportMissingImports
    from .node import list_camera_topics
    from .ros_env import ensure_rclpy

    ensure_rclpy()
    found = list_camera_topics(timeout=timeout)
    if not found:
        print(ctx.terminal.message("warning", "topics", "광고 중인 카메라 토픽이 없습니다."))
        return 0
    for name, msg_type in found:
        print(f"{name:<44} {msg_type}")
    return 0


def run_config(ctx):
    rendered = json.dumps(ctx.config.as_dict(), indent=2, sort_keys=True)
    print(ctx.terminal.pretty_json(rendered))
    return 0


_REPORT_PACKAGES = (
    ("tcamviewer", "tcamviewer"),
    ("wpycli", "wpycli"),
    ("wpyconf", "wpyconf"),
    ("wpylog", "wpylog"),
    ("numpy", "numpy"),
    ("opencv", "opencv-python-headless"),
)


def _dep_version(package: str) -> str:
    from importlib.metadata import PackageNotFoundError
    from importlib.metadata import version as pkg_version

    try:
        return pkg_version(package)
    except PackageNotFoundError:
        return "not installed"


def _ros_distro_line() -> str:
    """rclpy 임포트 없이 파일시스템만으로 설치된 ROS 디스트로를 탐지한다."""
    from .ros_env import _ros_site_dirs

    candidates = _ros_site_dirs()
    if not candidates:
        return "not found (rclpy는 실행 시 자동 부트스트랩)"
    prefix = candidates[0].parents[2]
    return f"{prefix.name} ({prefix})"


def run_version(ctx) -> int:
    """앱·의존성·런타임 환경 리포트. 문제 보고 시 그대로 붙여넣어 사용한다."""
    import os
    import platform
    from importlib.metadata import PackageNotFoundError
    from importlib.metadata import version as pkg_version

    app_version = VERSION
    try:
        app_version = pkg_version(APP_NAME)
    except PackageNotFoundError:
        app_version = VERSION  # 개발 트리 등 메타데이터 없음 → 상수 fallback

    def _row(label: str, value: str) -> None:
        print(f"{label:<12} {value}")

    print(f"{APP_NAME} {app_version}")
    _row("python", f"{platform.python_version()} ({platform.python_implementation()})")
    for display, package in _REPORT_PACKAGES:
        _row(display, _dep_version(package))
    _row("ros", _ros_distro_line())

    # pi-lens-ignore: Pyright:reportMissingImports
    from tcamviewer import get_terminal_size

    cols, rows = get_terminal_size()
    colorterm = os.environ.get("COLORTERM", "")
    truecolor = "truecolor" if colorterm in ("truecolor", "24bit") else "none"
    _row("terminal", f"{cols}x{rows} colorterm={colorterm or 'unset'} ({truecolor})")
    return 0


def main() -> int:
    return build_root().execute()


if __name__ == "__main__":
    raise SystemExit(main())
