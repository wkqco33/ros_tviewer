__all__ = ["__version__", "get_version"]


def get_version() -> str:
    """앱 버전. 단일 소스는 pyproject.toml이다 — 코드에 상수로 두지 않는다.

    설치된 패키지 메타데이터에서 우선 읽고, 메타데이터가 없는 개발 트리에서는
    소스 트리의 pyproject.toml을 직접 파싱한다.
    """
    try:
        from importlib.metadata import PackageNotFoundError
        from importlib.metadata import version as pkg_version

        # 배포명 정규화상 "ros-tviewer"/"ros_tviewer"는 동일하게 해석된다.
        return str(pkg_version("ros-tviewer"))
    except PackageNotFoundError:
        pass
    import tomllib
    from pathlib import Path

    # src 레이아웃: src/ros_tviewer/__init__.py → parents[2] = 저장소 루트
    pyproject = Path(__file__).resolve().parents[2] / "pyproject.toml"
    if pyproject.is_file():
        data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
        return str(data["project"]["version"])
    return "unknown"  # pyproject도 없는 비정상 설치


__version__ = get_version()
