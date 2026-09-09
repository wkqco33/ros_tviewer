"""ROS 2 런타임(rclpy) 부트스트랩.

rclpy는 pip로 설치할 수 없고 ROS 2 시스템 설치(/opt/ros/<distro>)에 존재한다.
uv로 생성된 격리 가상환경에서는 PYTHONPATH/LD_LIBRARY_PATH가 ROS 쪽을 가리키지
않기 때문에, 필요하면 환경 변수를 구성한 뒤 동일한 argv로 프로세스를 재실행(re-exec)
하여 rclpy를 로드 가능한 상태로 만든다.

전제 조건(권장): 실행 전 `source /opt/ros/<distro>/setup.bash`를 수행하면
재실행 없이 바로 동작한다.
"""

from __future__ import annotations

import os
import pathlib
import sys

_REEXEC_MARKER = "ROS_TVIEWER_REEXEC"

_HELP_MESSAGE = (
    "rclpy를 찾을 수 없습니다. 다음 중 하나를 시도하세요:\n"
    "  1. ROS 2 환경을 source 한 뒤 다시 실행: source /opt/ros/<distro>/setup.bash\n"
    "  2. ROS 2 설치 여부 확인: ls /opt/ros/\n"
)


def _ros_site_dirs() -> list[pathlib.Path]:
    """설치된 ROS 2 디스트로의 python site-packages 경로를 우선순위로 반환."""
    version = f"python{sys.version_info.major}.{sys.version_info.minor}"
    roots = [pathlib.Path("/opt/ros")]
    # 개발/커스텀 설치 경로 지원 (예: /home/.../ros/jazzy)
    home_ros = pathlib.Path.home() / "ros"
    if home_ros.is_dir():
        roots.append(home_ros)

    candidates: list[pathlib.Path] = []
    fallback: list[pathlib.Path] = []
    for root in roots:
        if not root.is_dir():
            continue
        for distro in sorted(p for p in root.iterdir() if p.is_dir()):
            site = distro / "lib" / version / "site-packages"
            if (site / "rclpy").is_dir():
                candidates.append(site)
                continue
            # Python 버전이 다른 디스트로는 후순위 (ABI 불일치 가능성)
            for alt in distro.glob("lib/python*/site-packages"):
                if (alt / "rclpy").is_dir():
                    fallback.append(alt)
    return candidates + fallback


def _reexec_with_ros_env(site_dir: pathlib.Path) -> None:
    """ROS 환경 변수를 설정하고 동일한 argv로 프로세스를 재실행한다."""
    prefix = site_dir.parents[2]  # .../<distro>/lib/pythonX.Y -> .../<distro>
    env = os.environ.copy()

    def _prepend(name: str, value: str) -> None:
        parts = [p for p in env.get(name, "").split(":") if p]
        env[name] = ":".join([value, *parts]) if parts else value

    _prepend("PYTHONPATH", str(site_dir))
    _prepend("LD_LIBRARY_PATH", str(prefix / "lib"))
    _prepend("AMENT_PREFIX_PATH", str(prefix))
    env["ROS_DISTRO"] = env.get("ROS_DISTRO") or prefix.name
    env[_REEXEC_MARKER] = "1"
    os.execve(sys.executable, [sys.executable, *sys.argv], env)


def _try_import_rclpy() -> bool:
    """rclpy 임포트 가능 여부 확인 (시스템 ROS에만 존재하는 지연 임포트)."""
    from importlib.util import find_spec

    return find_spec("rclpy") is not None


def ensure_rclpy() -> None:
    """rclpy를 사용 가능하게 만든다. 실패 시 명확한 안내와 함께 RuntimeError."""
    if _try_import_rclpy():
        return

    candidates = _ros_site_dirs()
    if not candidates:
        raise RuntimeError(_HELP_MESSAGE)

    # 1) LD_LIBRARY_PATH는 이미 살아있지만 PYTHONPATH만 빠진 경우: sys.path 주입으로 해결
    site_dir = candidates[0]
    if str(site_dir) not in sys.path:
        sys.path.append(str(site_dir))
    if _try_import_rclpy():
        return
    sys.path.remove(str(site_dir))

    # 2) 환경 변수가 통째로 빠진 경우: 재실행으로 해결 (execve는 반환되지 않음)
    if not os.environ.get(_REEXEC_MARKER):
        _reexec_with_ros_env(site_dir)

    raise RuntimeError(_HELP_MESSAGE)
