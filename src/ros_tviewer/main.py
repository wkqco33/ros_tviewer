from __future__ import annotations

import json
import pathlib

from wconfig import user_config_dir
from wpycli import Command, ConfigSettings, LoggingSettings

from . import get_version
from .config_io import parse_toml_value, read_toml, set_nested, write_toml

APP_NAME = "ros-tviewer"
DEFAULT_TOPIC = "/camera/image_raw"

# 실제로 읽히는 키만 둔다. app.name/app.default_topic 등은 어디서도 읽지 않아 제거했다.
_CONFIG_DEFAULTS: dict[str, dict[str, object]] = {
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
}

_CONFIG_HEADER = """\
# ros-tviewer 사용자 설정
# 우선순위: CLI 플래그 > 환경변수(ROS_TVIEWER_*) > 이 파일 > 기본값
# 키 수정은 `ros-tviewer config set <key> <value>` 를 권장한다.
"""


def user_config_path() -> pathlib.Path:
    """플랫폼별 사용자 설정 파일 경로 (존재 여부와 무관하게 반환)."""
    return user_config_dir(APP_NAME) / "config.toml"


def _discover_config_files() -> tuple[str, ...]:
    """로드할 config.toml 후보. 나중 파일이 우선하므로 (user, cwd) 순서다.

    - 사용자 경로: uvx 등 임의 cwd에서 실행해도 유지되는 영구 설정
      (Linux: ~/.config, macOS: ~/Library/Application Support, Windows: %APPDATA%)
    - cwd: 개발 트리/프로젝트 로컬 오버라이드
    - --config 플래그: ConfigSettings가 마지막에 추가 (최우선)
    """
    files: list[str] = []
    user = user_config_path()
    if user.is_file():
        files.append(str(user))
    cwd_file = pathlib.Path("config.toml")
    if cwd_file.is_file():
        files.append(str(cwd_file))
    return tuple(files)


def build_root() -> Command:
    # 기본 설정 파일은 존재할 때만 로드한다 — wconfig는 누락 파일을 오류로 처리한다.
    # 플랫폼 사용자 경로 + cwd config.toml을 순서대로 로드하고, 명시적 --config
    # 플래그는 그대로 전달하며(최우선), 누락 시 오류가 맞다.
    config_files = _discover_config_files()
    dotenv = ".env" if pathlib.Path(".env").is_file() else None

    root = Command(
        use="ros-tviewer",
        short="ROS 2 카메라 토픽을 터미널에서 재생하는 뷰어",
        long="sensor_msgs/Image, CompressedImage 토픽을 tcamviewer Half-Block "
        "TrueColor 렌더러로 터미널에 실시간 재생한다.",
        version=get_version(),
    )
    root.add_persistent_string_flag("config", help="추가 config.toml 경로", shorthand="c")
    root.add_persistent_string_flag("dotenv", help="추가 .env 경로")
    root.add_persistent_string_flag("log-level", help="로그 레벨 override")
    root.add_persistent_string_flag("log-file", help="로그 파일 경로 override")
    root.configure_runtime(
        config=ConfigSettings(
            defaults=_CONFIG_DEFAULTS,
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
    config_cmd = Command(
        use="config",
        short="설정을 조회·관리한다.",
        long="서브커맨드 없이 실행하면 병합된 현재 설정을 JSON으로 출력한다(=show).",
        run=run_config,
    )
    show = Command(use="show", short="병합된 현재 설정을 JSON으로 출력한다.", run=run_config_show)
    path_cmd = Command(
        use="path", short="설정 파일 후보 경로와 실제 로드된 파일을 표시한다.", run=run_config_path
    )
    init = Command(
        use="init",
        short="사용자 설정 파일을 생성한다.",
        long="플랫폼별 사용자 경로(또는 --config 지정 경로)에 기본 설정을 쓴다.",
        run=run_config_init,
    )
    init.add_bool_flag("force", help="이미 존재해도 덮어쓴다")
    set_cmd = Command(
        use="set <key> <value>",
        short="설정 키 값을 사용자 설정 파일에 저장한다.",
        long="값은 TOML 리터럴로 해석한다: 60 → int, 5.0 → float, true → bool,\n"
        "따옴표 없는 토픽 경로 같은 텍스트는 문자열로 저장한다.\n"
        "저장 위치는 --config 플래그 또는 플랫폼 사용자 경로다.",
        run=run_config_set,
    )
    config_cmd.add_command(show, path_cmd, init, set_cmd)
    version = Command(use="version", short="앱·의존성·런타임 버전을 출력한다.", run=run_version)
    root.add_command(play, topics, config_cmd, version)
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


def _render_config_json(ctx) -> int:
    rendered = json.dumps(ctx.config.as_dict(), indent=2, sort_keys=True)
    print(ctx.terminal.pretty_json(rendered))
    return 0


def run_config(ctx):
    """(하위호환) 서브커맨드 없는 `config` = show."""
    return _render_config_json(ctx)


def run_config_show(ctx) -> int:
    return _render_config_json(ctx)


def run_config_path(ctx) -> int:
    """설정 파일 후보 경로와 실제 로드된 파일을 표시한다."""
    user = user_config_path()
    cwd_file = pathlib.Path("config.toml")
    for label, path in (("user", user), ("cwd", cwd_file)):
        state = "ok" if path.is_file() else "없음"
        print(f"{label:<4} {path} ({state})")
    loaded = [
        source.origin for source in ctx.config.sources() if source.kind == "file" and source.origin
    ]
    if loaded:
        print("loaded:")
        for origin in loaded:
            print(f"  - {origin}")
    return 0


def _config_target(ctx) -> pathlib.Path:
    """init/set의 대상 파일. --config 플래그가 있으면 그 경로, 없으면 사용자 경로."""
    override = ctx.flags.get("config")
    if override:
        return pathlib.Path(str(override))
    return user_config_path()


def run_config_init(ctx) -> int:
    target = _config_target(ctx)
    if target.exists() and not ctx.flags.get("force"):
        print(
            ctx.terminal.message(
                "error", "config", f"이미 존재한다: {target} (--force 로 덮어쓸 수 있다)"
            )
        )
        return 1
    write_toml(target, _CONFIG_DEFAULTS, header=_CONFIG_HEADER)
    print(f"설정 파일을 생성했다: {target}")
    return 0


def run_config_set(ctx) -> int:
    if len(ctx.args) != 2:
        print(
            ctx.terminal.message(
                "error",
                "config",
                "사용법: ros-tviewer config set <key> <value> "
                "(예: config set camera.fps 60 | config set camera.topic /cam)",
            )
        )
        return 1
    key, raw = ctx.args
    if not all(part for part in key.split(".")):
        print(ctx.terminal.message("error", "config", f"잘못된 키: {key!r}"))
        return 1
    target = _config_target(ctx)
    if target.is_file():
        data = read_toml(target)
    else:
        data = {section: dict(values) for section, values in _CONFIG_DEFAULTS.items()}
    value = parse_toml_value(raw)
    set_nested(data, key, value)
    write_toml(target, data, header=_CONFIG_HEADER)
    print(f"저장했다: {key} = {value!r} -> {target}")
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

    app_version = get_version()

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
