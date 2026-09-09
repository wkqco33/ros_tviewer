"""E2E용 더미 카메라 퍼블리셔 — ROS 환경에서 실행한다.

사용: python dummy_publisher.py --topic /camera/image_raw --count 80 --hz 20 [--compressed]
이동하는 컬러 그라디언트 패턴을 sensor_msgs/Image(rgb8) 또는 CompressedImage(jpeg)로 발행한다.
"""

from __future__ import annotations

import argparse
import time

import numpy as np


def build_pattern(i: int, h: int, w: int) -> np.ndarray:
    x = np.linspace(0, 255, w, dtype=np.uint8)
    y = np.linspace(0, 255, h, dtype=np.uint8)
    frame = np.zeros((h, w, 3), dtype=np.uint8)
    frame[..., 0] = np.roll(x, i % w)[None, :]  # R: 수평 이동 그라디언트
    frame[..., 1] = np.roll(x, (i * 3) % w)[None, :]  # G: 다른 속도로 이동
    frame[..., 2] = y[:, None]  # B: 수직 그라디언트
    return frame


def main() -> None:
    parser = argparse.ArgumentParser(description="더미 카메라 퍼블리셔")
    parser.add_argument("--topic", default="/camera/image_raw")
    parser.add_argument("--count", type=int, default=60)
    parser.add_argument("--hz", type=float, default=15.0)
    parser.add_argument("--width", type=int, default=64)
    parser.add_argument("--height", type=int, default=48)
    parser.add_argument("--compressed", action="store_true")
    args = parser.parse_args()

    import rclpy  # type: ignore[import-not-found]
    from rclpy.node import Node  # type: ignore[import-not-found]
    from rclpy.qos import qos_profile_sensor_data  # type: ignore[import-not-found]
    from sensor_msgs.msg import CompressedImage, Image  # type: ignore[import-not-found]

    rclpy.init(args=None)
    node = Node("dummy_publisher")
    qos = qos_profile_sensor_data
    if args.compressed:
        pub = node.create_publisher(CompressedImage, args.topic, qos)
    else:
        pub = node.create_publisher(Image, args.topic, qos)

    interval = 1.0 / args.hz if args.hz > 0 else 0.0
    try:
        for i in range(args.count):
            pattern = build_pattern(i, args.height, args.width)
            if args.compressed:
                import cv2

                msg = CompressedImage()
                ok, buf = cv2.imencode(".jpg", pattern[..., ::-1])  # BGR 기준
                if not ok:
                    raise RuntimeError("JPEG 인코딩 실패")
                msg.format = "jpeg"
                msg.data = buf.tobytes()
            else:
                msg = Image()
                msg.encoding = "rgb8"
                msg.width = args.width
                msg.height = args.height
                msg.step = args.width * 3
                msg.is_bigendian = 0
                msg.data = pattern.tobytes()
            pub.publish(msg)
            time.sleep(interval)
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
