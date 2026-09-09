# ros-tviewer

[![CI](https://github.com/wkqco33/ros_tviewer/actions/workflows/ci.yml/badge.svg)](https://github.com/wkqco33/ros_tviewer/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/ros-tviewer)](https://pypi.org/project/ros-tviewer/)
[![Python](https://img.shields.io/badge/python-3.12%2B-blue)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

ROS 2 카메라 토픽을 터미널에서 재생하는 CLI 뷰어.

[sensor_msgs/msg/Image](https://docs.ros.org/) 및 `sensor_msgs/msg/CompressedImage` 토픽을
[tcamviewer](https://pypi.org/project/tcamviewer/)의 Half-Block TrueColor(24-bit ANSI) 렌더러로
터미널에 실시간(30~60+ FPS) 재생한다.

```text
uv run ros-tviewer play /camera/image_raw
▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀
```

## 요구 사항

| 항목 | 설명 |
| --- | --- |
| OS | Linux |
| Python | 3.12 (ROS 2 Jazzy ABI 매칭) |
| ROS 2 | Jazzy/Humble (`rclpy`는 시스템 ROS에서 로드 — pip 설치 불가) |
| 빌드 도구 | `cmake`, FFmpeg dev 라이브러리 (`libavcodec-dev` 등) — tcamviewer sdist 빌드용 |
| 터미널 | TrueColor 지원 (`echo $COLORTERM` → `truecolor`/`24bit`) |

## 시작하기

### 설치

```bash
# uv tool (권장)
uv tool install ros-tviewer

# 또는 pipx / pip
pipx install ros-tviewer
pip install ros-tviewer
```

PyPI 배포 전 개발 트리에서는 저장소 클론 후 실행한다:

### 개발 트리에서 실행

```bash
uv sync

# 1) 광고 중인 카메라 토픽 확인
uv run ros-tviewer topics

# 2) 재생 (ROS 환경 미 source 시 자동 감지·재실행)
source /opt/ros/jazzy/setup.bash   # 권장 — 미실행 시 자동 부트스트랩이 시도됨
uv run ros-tviewer play /camera/image_raw

# 옵션 예시
uv run ros-tviewer play /camera/image_raw/compressed --fps 30 --rotate 90 --stretch
uv run ros-tviewer play /camera/image_raw --frames 100   # 100 프레임 렌더 후 종료 (테스트/데모)
uv run ros-tviewer config                                # 현재 설정 출력 (= config show)
uv run ros-tviewer config init                           # 플랫폼 사용자 설정 파일 생성
uv run ros-tviewer config set camera.fps 60              # 사용자 설정 파일에 저장
uv run ros-tviewer config path                           # 설정 파일 후보 경로 표시
uv run ros-tviewer version                               # 앱·의존성·런타임 리포트
```

- `q`/`Ctrl+C`로 종료 (터미널 상태 자동 복구).
- `--compressed` 미지정 시 토픽 타입을 자동 감지한다.
- 설정 우선순위: **CLI 플래그 > `.env` > cwd `config.toml` > 사용자 `config.toml` > 기본값**.
- 설정 파일 후보: cwd `./config.toml` + 플랫폼별 사용자 경로의 `config.toml`
  (Linux: `~/.config/ros-tviewer/`, macOS: `~/Library/Application Support/ros-tviewer/`,
  Windows: `%APPDATA%\\ros-tviewer/`). uvx로 임의 디렉터리에서 실행해도
  사용자 경로 설정이 유지된다. `--config/-c` 플래그가 지정되면 최우선으로 로드되며,
  `config init`/`config set`의 저장 대상도 된다.

## E2E 테스트

```bash
uv run pytest                 # 단위 테스트 (ROS 미설치 환경에서도 실행 가능, ROS 테스트는 skip)
bash tests/e2e.sh             # 더미 퍼블리셔 → play 60프레임 데모
uv run pytest tests/test_ros2_e2e.py -v   # 실제 rclpy 구독 + 렌더 E2E
```

## 구성

| 모듈 | 책임 |
| --- | --- |
| `main.py` | wpycli 커맨드 (`play`/`topics`/`config`), 플래그·설정 파싱 |
| `config_io.py` | TOML 읽기/쓰기 헬퍼 (config init/set가 사용, rclpy 무의존) |
| `ros_env.py` | rclpy 부트스트랩 (시스템 ROS 탐지 → sys.path 주입 → re-exec) |
| `node.py` | 구독(QoS sensor_data), 최신 메시지 유지(drop), FPS 스로틀, 렌더 직전 변환 루프 |
| `convert.py` | Image/CompressedImage → RGB24 numpy (numpy/opencv만 사용, cv_bridge 없이) |

## 개발

- 아키텍처·TDD 규칙·컨벤션: **[AGENTS.md](AGENTS.md)** — 코드 변경 전 필독.
- 린트: `uv run ruff check .`
- 타입 체크: `uvx pyright --project .`
- 테스트: `uv run pytest`

## 기여 및 보안

- 기여 방법: [CONTRIBUTING.md](CONTRIBUTING.md)
- 취약점 보고: [SECURITY.md](SECURITY.md) — 공개 이슈로 보고하지 마세요.
- 변경 이력: [CHANGELOG.md](CHANGELOG.md)
- 라이선스: [MIT](LICENSE)
