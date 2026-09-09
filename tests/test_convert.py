"""convert.py 순수 함수 테스트 — rclpy 불필요, 항상 실행 (AGENTS.md §3)."""

from __future__ import annotations

import numpy as np
import pytest

from ros_tviewer.convert import (
    FrameDecodeError,
    UnsupportedEncodingError,
    compressed_to_rgb,
    image_to_rgb,
)


def test_rgb8_exact():
    msg = _img("rgb8", width=6, height=4)
    out = image_to_rgb(msg.data, msg.encoding, msg.width, msg.height, msg.step)
    assert out.shape == (4, 6, 3)
    assert out.dtype == np.uint8
    np.testing.assert_array_equal(out, _expected("rgb8", 6, 4))


def test_rgb8_with_row_padding():
    # step > width*3: 패딩 바이트(0xAB)가 섞여도 무시되어야 한다
    msg = _img("rgb8", width=5, height=3, padding=4)
    out = image_to_rgb(msg.data, msg.encoding, msg.width, msg.height, msg.step)
    np.testing.assert_array_equal(out, _expected("rgb8", 5, 3))


def test_bgr8_reversed_channels():
    msg = _img("bgr8", width=4, height=3)
    out = image_to_rgb(msg.data, msg.encoding, msg.width, msg.height, msg.step)
    np.testing.assert_array_equal(out, _expected("bgr8", 4, 3))


def test_bgr8_with_row_padding():
    # step > width*3인 bgr8도 패딩을 무시하고 정확히 변환되어야 한다
    msg = _img("bgr8", width=5, height=3, padding=4)
    out = image_to_rgb(msg.data, msg.encoding, msg.width, msg.height, msg.step)
    np.testing.assert_array_equal(out, _expected("bgr8", 5, 3))


def test_rgba8_alpha_dropped():
    msg = _img("rgba8", width=3, height=2)
    out = image_to_rgb(msg.data, msg.encoding, msg.width, msg.height, msg.step)
    np.testing.assert_array_equal(out, _expected("rgb8", 3, 2))


def test_bgra8_bgr_to_rgb_and_alpha_dropped():
    msg = _img("bgra8", width=3, height=2)
    out = image_to_rgb(msg.data, msg.encoding, msg.width, msg.height, msg.height and msg.step)
    np.testing.assert_array_equal(out, _expected("bgr8", 3, 2))


def test_mono8_repeated_to_rgb():
    msg = _img("mono8", width=4, height=2)
    out = image_to_rgb(msg.data, msg.encoding, msg.width, msg.height, msg.step)
    assert out.shape == (2, 4, 3)
    # mono8: 각 픽셀의 3채널이 동일해야 한다
    np.testing.assert_array_equal(out[..., 0], out[..., 1])
    np.testing.assert_array_equal(out[..., 1], out[..., 2])


def test_mono8_exact():
    msg = _img("mono8", width=5, height=3)
    out = image_to_rgb(msg.data, msg.encoding, msg.width, msg.height, msg.step)
    np.testing.assert_array_equal(out, _expected("mono8", 5, 3))


def test_8uc3_alias_of_rgb8():
    msg = _img("rgb8", width=4, height=2)
    out = image_to_rgb(msg.data, "8UC3", msg.width, msg.height, msg.step)
    np.testing.assert_array_equal(out, _expected("rgb8", 4, 2))


def test_step_zero_defaults_to_row_bytes():
    msg = _img("rgb8", width=4, height=2)
    out = image_to_rgb(msg.data, msg.encoding, msg.width, msg.height, 0)
    np.testing.assert_array_equal(out, _expected("rgb8", 4, 2))


def test_insufficient_data_raises():
    with pytest.raises(FrameDecodeError):
        image_to_rgb(b"\x00" * 5, "rgb8", width=10, height=10, step=0)


def test_bad_dimensions_raise():
    with pytest.raises(FrameDecodeError):
        image_to_rgb(b"\x00" * 12, "rgb8", width=0, height=1, step=0)


def test_unsupported_encoding_raises():
    msg = _img("rgb8", width=2, height=2)
    with pytest.raises(UnsupportedEncodingError):
        image_to_rgb(msg.data, "32FC1", msg.width, msg.height, msg.step)
    with pytest.raises(UnsupportedEncodingError):
        image_to_rgb(msg.data, "16UC1", msg.width, msg.height, msg.step)


def test_compressed_jpeg_roundtrip():
    import cv2

    src = _expected("rgb8", 8, 6)
    ok, bgr = cv2.imencode(".jpg", src[..., ::-1])  # cv2는 BGR 기준
    assert ok
    out = compressed_to_rgb(bgr.tobytes(), format="jpeg")
    assert out.shape == (6, 8, 3)
    assert out.dtype == np.uint8
    # JPEG는 유손실 → 평균 오차로 완화 비교
    assert float(np.mean(np.abs(out.astype(int) - src.astype(int)))) < 10.0


def test_compressed_invalid_data_raises():
    with pytest.raises(FrameDecodeError):
        compressed_to_rgb(b"not-an-image", format="jpeg")


# ---- 헬퍼 ----


def _img(encoding: str, width: int, height: int, padding: int = 0):
    from fakes import make_image

    return make_image(encoding, width, height, padding=padding)


def _expected(encoding: str, width: int, height: int):
    from fakes import expected_rgb

    return expected_rgb(encoding, width, height)
