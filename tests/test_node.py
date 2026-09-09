"""node.py 헬퍼(프레임 슬롯/레이트리미터) 테스트 — rclpy 불필요.

run_viewer의 rclpy 경로는 test_ros2_e2e.py(서브프로세스)에서 검증한다.
"""

from __future__ import annotations

import numpy as np
import pytest

from ros_tviewer.node import FrameSlot, RateLimiter, _message_to_rgb


class TestFrameSlot:
    def test_empty_slot_returns_none(self):
        slot = FrameSlot()
        assert slot.pop() is None

    def test_put_then_pop_returns_frame_and_seq(self):
        slot = FrameSlot()
        frame = object()
        slot.put(frame, seq=1)
        assert slot.pop() == (frame, 1)

    def test_pop_clears_slot(self):
        slot = FrameSlot()
        slot.put("f1", seq=1)
        slot.pop()
        assert slot.pop() is None

    def test_newer_frame_overwrites_older(self):
        slot = FrameSlot()
        slot.put("old", seq=1)
        slot.put("new", seq=2)
        assert slot.pop() == ("new", 2)

    def test_out_of_order_frame_is_dropped(self):
        # 렌더가 느려 뒤늦게 도착한 구 프레임은 무시한다 (최신 프레임 우선 정책)
        slot = FrameSlot()
        slot.put("new", seq=2)
        slot.put("old", seq=1)
        assert slot.pop() == ("new", 2)


class TestRateLimiter:
    def test_first_call_always_allowed(self):
        clock = [0.0]
        rl = RateLimiter(min_interval=0.1, clock=lambda: clock[0])
        assert rl.try_acquire() is True

    def test_call_within_interval_blocked(self):
        clock = [0.0]
        rl = RateLimiter(min_interval=0.1, clock=lambda: clock[0])
        rl.try_acquire()
        clock[0] += 0.05
        assert rl.try_acquire() is False

    def test_call_after_interval_allowed(self):
        clock = [0.0]
        rl = RateLimiter(min_interval=0.1, clock=lambda: clock[0])
        rl.try_acquire()
        clock[0] += 0.11
        assert rl.try_acquire() is True

    def test_zero_interval_never_blocks(self):
        rl = RateLimiter(min_interval=0.0, clock=lambda: 0.0)
        assert rl.try_acquire() is True
        assert rl.try_acquire() is True

    def test_negative_interval_treated_as_zero(self):
        with pytest.raises(ValueError):
            RateLimiter(min_interval=-1.0, clock=lambda: 0.0)


class TestMessageToRgb:
    """_message_to_rgb 디스패치 — rclpy 없이 fake 메시지로 검증한다."""

    def test_raw_image_uses_encoding_fields(self):
        from fakes import make_image

        msg = make_image("bgr8", 4, 3)
        out = _message_to_rgb(msg, "raw")
        assert out.shape == (3, 4, 3)
        assert out.dtype == np.uint8

    def test_compressed_uses_format_field(self):
        from types import SimpleNamespace

        import cv2
        import numpy as np

        src = np.zeros((6, 8, 3), dtype=np.uint8)
        ok, buf = cv2.imencode(".jpg", src)
        assert ok
        msg = SimpleNamespace(data=buf.tobytes(), format="jpeg")
        out = _message_to_rgb(msg, "compressed")
        assert out.shape == (6, 8, 3)
        assert out.dtype == np.uint8
