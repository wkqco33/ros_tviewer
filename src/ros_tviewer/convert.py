"""sensor_msgs 메시지를 tcamviewer가 요구하는 RGB24 numpy 배열로 변환.

cv_bridge(rclpy 생태계 전용 의존성)를 사용하지 않고 numpy/opencv만으로 처리한다.
채널 재배치는 cv2.cvtColor(SIMD 최적화, numpy 슬라이스 복사 대비 수십 배 빠름)를 사용한다.
"""

from __future__ import annotations

import numpy as np

# encoding -> (bytes_per_pixel, 변환 함수명)
_SUPPORTED_ENCODINGS: dict[str, tuple[int, str]] = {
    "rgb8": (3, "rgb8"),
    "bgr8": (3, "bgr8"),
    "rgba8": (4, "rgba8"),
    "bgra8": (4, "bgra8"),
    "mono8": (1, "mono8"),
    "8uc1": (1, "mono8"),
    "8uc3": (3, "rgb8"),
    "8uc4": (4, "rgba8"),
}


class UnsupportedEncodingError(ValueError):
    """지원하지 않는 sensor_msgs/Image encoding."""


class FrameDecodeError(ValueError):
    """프레임 데이터 손상/크기 불일치."""


def image_to_rgb(data, encoding: str, width: int, height: int, step: int = 0) -> np.ndarray:
    """sensor_msgs/msg/Image (rgb8/bgr8/rgba8/bgra8/mono8/8UC*)를 HxWx3 RGB로 변환."""
    key = str(encoding).lower()
    if key not in _SUPPORTED_ENCODINGS:
        raise UnsupportedEncodingError(f"지원하지 않는 encoding: {encoding!r}")

    bpp, layout = _SUPPORTED_ENCODINGS[key]
    if width <= 0 or height <= 0:
        raise FrameDecodeError(f"잘못된 이미지 크기: {width}x{height}")

    buf = np.frombuffer(data, dtype=np.uint8)
    row_bytes = width * bpp
    if step == 0:
        step = row_bytes
    if len(buf) < height * step:
        raise FrameDecodeError(
            f"데이터 부족: {len(buf)} bytes < {height}x{step} (encoding={encoding})"
        )

    rows = buf[: height * step].reshape(height, step)[:, :row_bytes]

    import cv2  # 지연 임포트 (AGENTS.md §2 — 모듈 로드 시점 비용 회피)

    if layout == "rgb8":
        return np.ascontiguousarray(rows.reshape(height, width, 3))
    if layout == "bgr8":
        return cv2.cvtColor(rows.reshape(height, width, 3), cv2.COLOR_BGR2RGB)
    if layout == "rgba8":
        return cv2.cvtColor(rows.reshape(height, width, 4), cv2.COLOR_RGBA2RGB)
    if layout == "bgra8":
        return cv2.cvtColor(rows.reshape(height, width, 4), cv2.COLOR_BGRA2RGB)
    if layout == "mono8":
        return cv2.cvtColor(rows.reshape(height, width), cv2.COLOR_GRAY2RGB)
    raise UnsupportedEncodingError(f"지원하지 않는 encoding: {encoding!r}")  # pragma: no cover


def _decode_compressed_bytes(data: bytes):
    """JPEG/PNG 등 압축 프레임을 BGR로 디코딩한다 (opencv)."""
    import cv2

    array = np.frombuffer(data, dtype=np.uint8)
    bgr = cv2.imdecode(array, cv2.IMREAD_COLOR)
    if bgr is None:
        raise FrameDecodeError("압축 프레임 디코딩 실패 (jpeg/png 아님?)")
    return bgr


def compressed_to_rgb(data, format: str = "") -> np.ndarray:
    """sensor_msgs/msg/CompressedImage를 HxWx3 RGB로 변환."""
    del format  # cv2.imdecode가 자체 판별
    import cv2  # 지연 임포트 (AGENTS.md §2)

    bgr = _decode_compressed_bytes(bytes(data))
    return cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
