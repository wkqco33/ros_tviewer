#!/usr/bin/env bash
# 수동 E2E 데모: 더미 퍼블리셔로 카메라 토픽을 발행하고 play로 재생한다.
# 사용: bash tests/e2e.sh [topic] [frames]
set -euo pipefail

TOPIC="${1:-/camera/image_raw}"
FRAMES="${2:-60}"

# 1) ROS 환경 로드 (첫 발견된 디스트로)
ROS_SETUP=""
for setup in /opt/ros/*/setup.bash; do
  [ -f "$setup" ] && ROS_SETUP="$setup" && break
done
if [ -z "$ROS_SETUP" ]; then
  echo "ERROR: /opt/ros/*/setup.bash 를 찾을 수 없습니다. ROS 2 설치를 확인하세요." >&2
  exit 1
fi
# shellcheck disable=SC1090
source "$ROS_SETUP"
echo "ROS env: $ROS_SETUP"

# 2) 퍼블리셔 백그라운드 실행 (60 프레임 @ 15Hz)
uv run python tests/tools/dummy_publisher.py --topic "$TOPIC" --count 60 --hz 15 &
PUB_PID=$!
trap 'kill $PUB_PID 2>/dev/null || true' EXIT

# 3) 재생 (FRAMES 프레임 렌더 후 자동 종료)
uv run ros-tviewer play "$TOPIC" --fps 15 --frames "$FRAMES" --timeout 5
echo "E2E demo done: topic=$TOPIC frames=$FRAMES"
