"""config_io (TOML 읽기/쓰기 헬퍼) 단위 테스트. rclpy 불필요."""

from __future__ import annotations

import pathlib

from ros_tviewer.config_io import parse_toml_value, read_toml, write_toml


def test_parse_toml_value_unquoted_string_falls_back_to_str():
    assert parse_toml_value("/camera/image_raw") == "/camera/image_raw"


def test_parse_toml_value_quoted_string():
    assert parse_toml_value('"/cam/x"') == "/cam/x"


def test_parse_toml_value_numbers_and_bool():
    assert parse_toml_value("60") == 60
    assert parse_toml_value("5.5") == 5.5
    assert parse_toml_value("true") is True
    assert parse_toml_value("false") is False


def test_write_then_read_roundtrip(tmp_path: pathlib.Path):
    data = {
        "app": {"name": "ros-tviewer"},
        "camera": {
            "topic": "/camera/image_raw",
            "fps": 30,
            "rotate": 0,
            "stretch": False,
            "compressed": False,
            "timeout": 5.0,
            "frames": 0,
        },
    }
    path = tmp_path / "config.toml"
    write_toml(path, data, header="# test")
    assert read_toml(path) == data
    text = path.read_text(encoding="utf-8")
    assert text.startswith("# test")


def test_write_toml_creates_parent_dirs(tmp_path: pathlib.Path):
    path = tmp_path / "deep" / "nested" / "config.toml"
    write_toml(path, {"camera": {"fps": 1}})
    assert read_toml(path) == {"camera": {"fps": 1}}


def test_set_nested_key_helper():
    # config set 구현이 쓸 헬퍼: 중첩 경로에 값 주입
    from ros_tviewer.config_io import set_nested

    data: dict = {"camera": {"fps": 30}}
    out = set_nested(data, "camera.topic", "/new")
    assert out["camera"]["topic"] == "/new"
    assert out["camera"]["fps"] == 30

    out2 = set_nested({}, "logging.level", "DEBUG")
    assert out2 == {"logging": {"level": "DEBUG"}}


# rclpy 불필요 — 순수 TOML 헬퍼 테스트
