"""config.toml 읽기/쓰기 헬퍼.

tomllib는 읽기 전용이므로 최소한의 TOML 직렬화를 직접 구현한다.
스칼라/문자열 리스트/중첩 테이블만 지원하면 ros-tviewer 설정에 충분하다.
순수 함수로 유지하고, rclpy 의존은 금지한다.
"""

from __future__ import annotations

import json
import tomllib
from collections.abc import Mapping
from pathlib import Path
from typing import Any

__all__ = ["parse_toml_value", "read_toml", "set_nested", "write_toml"]


def parse_toml_value(raw: str) -> Any:
    """문자열을 TOML 값으로 해석한다.

    `v = <raw>` 조각을 파싱해 `60`→int, `true`→bool, `'"text"'`→str 처럼
    TOML 리터럴이면 그 타입으로 변환한다. 리터럴이 아니면(따옴표 없이 쓴
    토픽 경로 등) 원문 문자열을 그대로 돌려준다.
    """
    try:
        parsed = tomllib.loads(f"v = {raw}")
    except tomllib.TOMLDecodeError:
        return raw
    return parsed["v"]


def read_toml(path: Path) -> dict[str, Any]:
    """TOML 파일을 읽어 dict로 반환한다."""
    with Path(path).open("rb") as handle:
        return tomllib.load(handle)


def set_nested(data: dict[str, Any], key: str, value: Any) -> dict[str, Any]:
    """`a.b.c` 점 경로에 값을 주입한다. 중간 테이블을 자동 생성한다."""
    parts = [part for part in key.split(".") if part]
    if not parts:
        raise ValueError("빈 설정 키입니다")
    node = data
    for part in parts[:-1]:
        child = node.get(part)
        if not isinstance(child, dict):
            child = {}
            node[part] = child
        node = child
    node[parts[-1]] = value
    return data


def write_toml(path: Path, data: Mapping[str, Any], *, header: str = "") -> None:
    """dict를 TOML로 직렬화해 기록한다. 부모 디렉터리를 자동 생성한다.

    톱레벨 스칼라를 먼저 쓰고, dict 값은 `[테이블]` 섹션으로 내린다.
    None 값은 기록하지 않는다(주석이 없는 최소 TOML이 생성된다).
    """
    lines: list[str] = []
    if header:
        lines.extend(header.rstrip("\n").splitlines())
        lines.append("")

    def _emit(table: Mapping[str, Any], parent: str) -> None:
        scalars = [(k, v) for k, v in table.items() if not isinstance(v, Mapping)]
        tables = [(k, v) for k, v in table.items() if isinstance(v, Mapping)]
        for name, value in scalars:
            if value is None:
                continue
            lines.append(f"{name} = {_format_value(value)}")
        for name, value in tables:
            full = f"{parent}.{name}" if parent else name
            if lines and lines[-1] != "":
                lines.append("")
            lines.append(f"[{full}]")
            _emit(value, full)

    _emit(data, "")
    text = "\n".join(lines) + "\n"
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")


def _format_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return repr(value)
    if isinstance(value, str):
        # TOML basic string의 이스케이프 규격이 JSON 문자열과 호환된다.
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, (list, tuple)):
        return "[" + ", ".join(_format_value(item) for item in value) + "]"
    raise TypeError(f"TOML로 직렬화할 수 없는 값: {type(value).__name__}")
