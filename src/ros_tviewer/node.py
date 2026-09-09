"""ROS 2 카메라 구독 + tcamviewer 렌더 루프.

rclpy/sensor_msgs는 ros_env.ensure_rclpy()가 통과한 뒤에만 함수 내부에서 import한다
(AGENTS.md §2 모듈 계약 — 모듈 레벨 임포트 금지).

최신 메시지 우선(drop) 정책과 모노토닉 스로틀은 이 모듈의 FrameSlot/RateLimiter가 담당한다.
픽셀 변환은 렌더 직전에만 수행한다 — 수신률이 렌더율보다 높을 때 변환 비용을 렌더량에
비례하도록 제한한다 (수신 프레임마다 변환하면 렌더되지 않는 프레임에 CPU를 낭비한다).
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Callable, cast

from tcamviewer import TerminalRenderer, get_terminal_size

from .convert import FrameDecodeError, UnsupportedEncodingError

if TYPE_CHECKING:
    import numpy as np

__all__ = ["FrameSlot", "RateLimiter", "run_viewer", "list_camera_topics"]


class FrameSlot:
    """최신 메시지만 유지하는 단일 슬롯 (drop 정책).

    렌더가 느려도 메시지가 큐에 쌓이지 않도록, 새 메시지가 오면 이전 것을 덮어쓰고
    구 메시지(seq가 작거나 같은)는 버린다. 슬롯에는 변환 전 원본 메시지가 저장되며,
    변환은 렌더 직전에만 수행된다.
    """

    def __init__(self) -> None:
        self._frame: object | None = None
        self._seq: int = 0
        self._has: bool = False

    def put(self, message: object, seq: int) -> None:
        if self._has and seq <= self._seq:
            return  # out-of-order / 구 메시지 무시
        self._frame = message
        self._seq = seq
        self._has = True

    def pop(self) -> tuple[object, int] | None:
        if not self._has:
            return None
        frame, seq = self._frame, self._seq
        self._frame = None
        self._has = False
        return frame, seq


class RateLimiter:
    """모노토닉 클럭 기반 스로틀. time.sleep을 쓰지 않는다 (AGENTS.md §7)."""

    def __init__(self, min_interval: float, clock: Callable[[], float] = time.monotonic) -> None:
        if min_interval < 0:
            raise ValueError("min_interval은 0 이상이어야 한다")
        self._min_interval = min_interval
        self._clock = clock
        self._last: float | None = None

    def try_acquire(self) -> bool:
        now = self._clock()
        if (
            self._last is not None
            and self._min_interval > 0
            and now - self._last < self._min_interval
        ):
            return False
        self._last = now
        return True


def _detect_type(node, topic: str, compressed: bool | None, timeout: float) -> str:
    """토픽 타입을 결정한다: 명시 지정 > 디스커버리 자동감지 > 기본 raw Image."""
    if compressed is not None:
        return "compressed" if compressed else "raw"
    # 자동 감지: 토픽이 광고될 때까지 timeout 동안 폴링
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        for name, types in node.get_topic_names_and_types():
            if name != topic:
                continue
            for t in types:
                if "CompressedImage" in t:
                    return "compressed"
                if "Image" in t:
                    return "raw"
        time.sleep(0.2)
    return "raw"  # 발견 실패 시 raw로 시도 (구독 오류 메시지가 안내)


def _message_to_rgb(msg, kind: str):
    """구독 메시지를 RGB24 numpy로 변환한다 (kind: "raw" | "compressed")."""
    from . import convert

    if kind == "compressed":
        return convert.compressed_to_rgb(msg.data, getattr(msg, "format", ""))
    return convert.image_to_rgb(msg.data, msg.encoding, msg.width, msg.height, msg.step)


def run_viewer(
    topic: str,
    fps: int | None = None,
    rotate: int = 0,
    stretch: bool = False,
    compressed: bool | None = None,
    timeout: float = 5.0,
    max_frames: int | None = None,
    logger=None,
) -> int:
    """토픽을 구독하며 터미널에 렌더링한다. Ctrl+C로 종료. 반환값은 프로세스 exit code.

    max_frames를 지정하면 해당 개수만큼 렌더 후 정상 종료한다 (테스트/데모용).
    """
    import rclpy  # type: ignore[import-not-found]
    from rclpy.node import Node  # type: ignore[import-not-found]
    from rclpy.qos import qos_profile_sensor_data  # type: ignore[import-not-found]
    from sensor_msgs.msg import CompressedImage, Image  # type: ignore[import-not-found]

    rclpy.init(args=None)
    node: Node | None = None
    renderer: TerminalRenderer | None = None
    try:
        probe = Node("ros_tviewer")
        node = probe
        kind = _detect_type(probe, topic, compressed, timeout)
        msg_type = CompressedImage if kind == "compressed" else Image
        slot = FrameSlot()
        limiter = RateLimiter(1.0 / fps if fps and fps > 0 else 0.0)

        seq = 0

        def on_frame(msg) -> None:
            # 변환 없이 원본 메시지만 보관 — 변환은 렌더 직전에만 (수신률 > 렌더율 대비)
            nonlocal seq
            seq += 1
            slot.put(msg, seq)

        probe.create_subscription(msg_type, topic, on_frame, qos_profile_sensor_data)

        cols, rows = get_terminal_size()
        rend = TerminalRenderer(
            cols=cols,
            rows=rows,
            use_diff=True,
            alt_screen=True,
            hide_cursor=True,
            rotation=rotate,
            keep_aspect_ratio=not stretch,
        )
        renderer = rend

        rendered = 0
        bad_frames = 0
        try:
            while rclpy.ok():
                rclpy.spin_once(probe, timeout_sec=0.05)
                item = slot.pop()
                if item is None:
                    continue
                msg, _ = item
                if not limiter.try_acquire():
                    continue
                new_cols, new_rows = get_terminal_size()
                if (new_cols, new_rows) != (rend.cols, rend.rows):
                    rend.resize(new_cols, new_rows)
                try:
                    arr = cast("np.ndarray", _message_to_rgb(msg, kind))
                except (FrameDecodeError, UnsupportedEncodingError):
                    bad_frames += 1  # 손상 프레임은 건너뛰고 다음 프레임으로 계속
                    continue
                rend.render_rgb(arr, width=arr.shape[1], height=arr.shape[0])
                rendered += 1
                if max_frames is not None and rendered >= max_frames:
                    break
        except KeyboardInterrupt:
            pass

        if logger is not None:
            logger.info(
                "viewer finished",
                extra={"topic": topic, "rendered": rendered, "bad_frames": bad_frames},
            )
        return 0
    finally:
        if renderer is not None:
            renderer.close()
        if node is not None:
            node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


def list_camera_topics(timeout: float = 5.0) -> list[tuple[str, str]]:
    """현재 광고 중인 sensor_msgs 카메라 토픽을 반환한다."""
    import rclpy  # type: ignore[import-not-found]
    from rclpy.node import Node  # type: ignore[import-not-found]

    rclpy.init(args=None)
    node: Node | None = None
    try:
        probe = Node("ros_tviewer_probe")
        node = probe
        deadline = time.monotonic() + timeout
        topics: dict[str, str] = {}
        while time.monotonic() < deadline:
            for name, types in probe.get_topic_names_and_types():
                for t in types:
                    if "Image" in t or "CompressedImage" in t:
                        topics.setdefault(name, t)
            if topics:
                break
            time.sleep(0.2)
        return sorted(topics.items())
    finally:
        if node is not None:
            node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
