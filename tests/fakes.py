"""테스트용 fake 메시지 헬퍼 — sensor_msgs 임포트 없이 ROS 메시지 형태를 흉내.

AGENTS.md 규칙: 단위 테스트는 rclpy/sensor_msgs 없이 실행 가능해야 한다.
"""

from __future__ import annotations

from types import SimpleNamespace

import numpy as np


def make_image(encoding: str, width: int, height: int, *, padding: int = 0):
    """sensor_msgs/msg/Image 형태의 fake 메시지를 만든다.

    픽셀 값은 (row, col, channel)에 따라 결정론적으로 채운다:
    value = (row * 7 + col * 3 + channel * 11) % 256
    padding > 0 이면 row stride에 여분 바이트(가비지 0xAB)를 넣는다.
    """
    bpp = {"rgb8": 3, "bgr8": 3, "rgba8": 4, "bgra8": 4, "mono8": 1}[encoding]
    row_bytes = width * bpp + padding
    buf = np.full((height, row_bytes), 0xAB, dtype=np.uint8)
    pixels = buf[:, : width * bpp].reshape(height, width, bpp)
    for c in range(bpp):
        channel_view = pixels[..., c]
        channel_view[:] = (
            np.arange(height)[:, None] * 7 + np.arange(width)[None, :] * 11 + c * 17
        ) % 256
    return SimpleNamespace(
        data=buf.tobytes(),
        encoding=encoding,
        width=width,
        height=height,
        step=row_bytes,
    )


def expected_rgb(encoding: str, width: int, height: int) -> np.ndarray:
    """make_image가 넣은 픽셀 패턴의 기대 RGB 결과를 계산한다."""
    rgb = np.zeros((height, width, 3), dtype=np.uint8)
    for c in range(3):
        rgb[..., c] = (
            np.arange(height)[:, None] * 7 + np.arange(width)[None, :] * 11 + c * 17
        ) % 256
    if encoding == "bgr8":
        rgb = rgb[..., ::-1]
    if encoding in ("mono8", "8UC1"):
        # 단일 채널(c=0 패턴)이 3채널로 반복된다
        rgb[..., 1] = rgb[..., 0]
        rgb[..., 2] = rgb[..., 0]
    return np.ascontiguousarray(rgb)
