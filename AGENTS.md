# AGENTS.md — ros-tviewer 개발 가이드

ROS 2 카메라 토픽을 터미널에서 재생하는 CLI 뷰어. 이 문서는 에이전트(및 개발자)가
**일관성 있게** 개발하기 위한 아키텍처 명세와 TDD 규칙이다. 코드 변경 전 반드시 읽는다.

---

## 1. 프로젝트 개요

| 항목 | 내용 |
| --- | --- |
| 목적 | ROS 2 `sensor_msgs/msg/Image`, `CompressedImage` 토픽을 터미널(ANSI TrueColor Half-Block)로 실시간 재생 |
| 렌더링 | [tcamviewer](https://pypi.org/project/tcamviewer/) `>=0.2.3` (C-ABI 코어 + ctypes 바인딩, PyPI 배포됨) |
| CLI | `wpycli` (cobra 스타일 Command), 설정 `wpyconf`, 로깅 `wpylog` |
| 버전 | **단일 소스 = `pyproject.toml`**. 런타임은 `ros_tviewer.__init__.get_version()` (메타데이터 → pyproject 파싱 fallback). 코드에 VERSION 상수로 두지 않는다. CHANGELOG는 릴리스마다 수동 갱신 |
| 실행 | `uv run ros-tviewer play /camera/image_raw` 또는 ROS env source 후 `uvx ros-tviewer ...` |
| Python | 3.12 (ROS 2 Jazzy ABI 매칭 — `requires-python = ">=3.12"`) |
| 테스트 | `pytest` (단위), E2E는 ROS 환경에서 `bash tests/e2e.sh` |

## 2. 아키텍처

```text
                      ┌──────────────────────────────┐
                      │  main.py (wpycli Command)    │  play / topics / config
                      └──────┬───────────────────────┘
                             │ 1) ros_env.ensure_rclpy()   ← 반드시 가장 먼저
                             ▼
                      ┌──────────────────────────────┐
                      │  ros_env.py                  │  rclpy 부트스트랩
                      │  (시스템 ROS 탐지 + re-exec) │  (pip 설치 불가 → 시스템 전용)
                      └──────┬───────────────────────┘
                             ▼
                      ┌──────────────────────────────┐
                      │  node.py (CameraViewer)      │  rclpy 구독 + 스로틀 + 렌더 루프
                      │  - 최신 프레임만 유지(Drop)  │  QoS: sensor_data (depth 1)
                      └──────┬───────────────────────┘
                             ▼
        ┌────────────────────┴────────────────────┐
        ▼                                          ▼
┌──────────────────┐                    ┌──────────────────────┐
│  convert.py      │                    │  tcamviewer (PyPI)   │
│  Image/Compressed│  ── RGB24 numpy ──▶│  TerminalRenderer    │
│  → RGB24 (H,W,3) │                    │  render_rgb()        │
└──────────────────┘                    └──────────────────────┘
   numpy + opencv만 사용. cv_bridge 사용 금지.
```

### 모듈 계약 (변경 금지 원칙)

| 모듈 | 책임 | 금지 사항 |
| --- | --- | --- |
| `main.py` | wpycli 커맨드 정의, ctx → 파라미터 변환 | ROS/rclpy 직접 임포트 금지, 렌더 로직 금지 |
| `config_io.py` | config.toml 읽기/쓰기·TOML 리터럴 파싱 헬퍼 | 순수 함수 유지, rclpy 임포트 금지 |
| `ros_env.py` | rclpy 가용성 확인, sys.path 주입, 환경변수 구성 후 `os.execve` 재실행 | rclpy를 모듈 레벨에서 import 금지(항상 함수 내 지연 임포트) |
| `node.py` | rclpy 노드/구독/스핀 루프, 프레임 슬롯·레이트리미터 | 픽셀 변환 로직 금지(convert에 위임), 렌더러 생성만 |
| `convert.py` | 메시지 → RGB24 numpy. 순수 함수. rclpy 무의존 (테스트 가능) | rclpy/노드 상태 금지. cv2 임포트는 함수 내부 지연. 채널 재배치는 cv2.cvtColor 사용 |
| `tests/` | 단위 테스트는 rclpy 없이 실행 가능해야 함 | ROS 미설치 환경에서 fail 금지 → `skipif` 사용 |

### 데이터 규약

- **내부 프레임 표준**: `numpy.ndarray`, `dtype=uint8`, `shape=(H, W, 3)`, **RGB24**, C-contiguous.
  - 렌더러가 BGR을 원하면 `render_bgr`을 쓰지 말고 convert에서 RGB로 통일한다.
- `convert.image_to_rgb(data, encoding, width, height, step)`는 순수 함수 — 부작용 없음.
- 지원 encoding: `rgb8`, `bgr8`, `rgba8`, `bgra8`, `mono8`, `8UC1/3/4`. 추가 시
  `_SUPPORTED_ENCODINGS` 테이블 + 테스트를 **함께** 추가한다 (TDD).
- 지원하지 않는 encoding은 `UnsupportedEncodingError`, 데이터 손상은 `FrameDecodeError`.

### rclpy 다루기 (중요)

- **rclpy는 pip 설치 불가** — 시스템 ROS 2(`/opt/ros/<distro>`)에만 존재.
- 규칙:
  1. rclpy import는 **함수 내부 지연 임포트**만 허용 (`ros_env.ensure_rclpy()` 이후).
  2. CLI 런 핸들러 첫 줄에서 `ensure_rclpy()` 호출. 미설치 환경에서는
     명확한 `_HELP_MESSAGE`와 함께 `RuntimeError`.
  3. `ensure_rclpy()`는 find_spec 기반 확인 → sys.path 주입 → 실패 시 환경변수 구성 후
     **re-exec**(`os.execve`, 마커 `ROS_TVIEWER_REEXEC`로 무한루프 방지) 순서를 유지.
  4. ruff/pyright: `import rclpy` 라인에는 `# type: ignore[import-not-found]` 허용.

## 3. TDD 규칙 (Red → Green → Refactor)

1. **새 기능 = 실패하는 테스트부터**. 구현 전 테스트가 반드시 `pytest`에서 fail/red를
   확인한 뒤 구현한다.
2. 테스트 분류:
   - `tests/test_convert.py` — 변환 순수함수. rclpy 불필요, 항상 실행.
   - `tests/test_main.py` — CLI 커맨드/플래그 구조. rclpy 불필요, 항상 실행.
   - `tests/test_ros_env.py` — 부트스트랩. `os.execve`는 **반드시 monkeypatch**로 가로챔
     (테스트 프로세스 교체 방지).
   - `tests/test_ros2_e2e.py` — 실제 rclpy 구독/렌더. `pytest.mark.skipif`:
     rclpy 미탑재 환경에서는 skip. 서브프로세스로 `source /opt/ros/*/setup.bash` 후 실행.
3. Fake 메시지: `sensor_msgs`를 임포트하지 말고 `types.SimpleNamespace`로
   `data/encoding/width/height/step` 필드를 만든다 (`tests/fakes.py` 헬퍼 재사용).
4. 커버리지 목표: convert 100%, ros_env 분기 커버, main 플래그 파싱 스냅샷.
5. 커밋 단위: Red(테스트 추가) → Green(최소 구현) → Refactor → `uv run ruff check .` → 반복.

## 4. 명령어

```bash
uv sync                       # 의존성 설치 (tcamviewer는 sdist → 시스템에 cmake+FFmpeg dev 필요)
uv run pytest                 # 단위 테스트
uv run pytest tests/test_ros2_e2e.py -v   # ROS E2E (source 없이도 skip만 됨)
uv run ruff check . && uv run ruff format --check .   # 린트/포맷
bash tests/e2e.sh             # ROS 환경 E2E (더미 퍼블리셔 → play 60프레임)
uv run ros-tviewer play /camera/image_raw   # 실행
```

## 5. 설정 참조 (wpyconf)

로딩 후보와 우선순위(나중에 로드된 파일이 이긴다):

1. **defaults** (`main.py` `_CONFIG_DEFAULTS`)
2. 플랫폼 사용자 경로 `config.toml` — `wconfig.user_config_dir(APP_NAME)`
   (Linux: `$XDG_CONFIG_HOME/ros-tviewer/`, macOS: `~/Library/Application Support/ros-tviewer/`,
   Windows: `%APPDATA%/ros-tviewer/`) — uvx 등 임의 cwd에서도 유지되는 영구 설정
3. cwd `config.toml` — 프로젝트 로컬 오버라이드
4. `.env` (cwd) — `ROS_TVIEWER_` 프리픽스
5. 환경변수 — `ROS_TVIEWER_CAMERA__TOPIC` 형식
6. CLI 플래그 / `--config/-c` 플래그로 지정한 파일 (최우선)

`config` 서브커맨드: `show`(병합 결과 JSON), `path`(후보/로드 경로),
`init`(사용자 경로 생성, `--force`), `set <key> <value>`(저장 대상:
`--config` 플래그 경로 또는 사용자 경로). TOML 쓰기는 `config_io.py`가 담당한다.

| 키 (config) | env | CLI 플래그 | 기본값 |
| --- | --- | --- | --- |
| `camera.topic` | `ROS_TVIEWER_CAMERA__TOPIC` | (위치인자 `[topic]`) | `/camera/image_raw` |
| `camera.fps` | `ROS_TVIEWER_CAMERA__FPS` | `--fps/-f` | 30 |
| `camera.rotate` | `ROS_TVIEWER_CAMERA__ROTATE` | `--rotate/-r` | 0 |
| `camera.stretch` | `ROS_TVIEWER_CAMERA__STRETCH` | `--stretch/-s` | false |
| `camera.compressed` | `ROS_TVIEWER_CAMERA__COMPRESSED` | `--compressed/-z` | false(→None, 자동감지) |
| `camera.timeout` | `ROS_TVIEWER_CAMERA__TIMEOUT` | `--timeout/-t` | 5.0 |
| `camera.frames` | `ROS_TVIEWER_CAMERA__FRAMES` | `--frames/-n` | 0(무제한) |
| `logging.level` | `ROS_TVIEWER_LOGGING__LEVEL` | `--log-level` | WARNING |

- `compressed`는 트라이스테이트다: 플래그/설정 true → 강제, 미지정 → **None(자동 감지)**.
  bool로 강제하면 CompressedImage 토픽에 Image로 구독하는 미스매치로 무한 대기한다 (E2E 회귀 1회).
- 로그는 터미널 렌더를 오염시키므로 **기본 WARNING 이상** 유지. 렌더 루프 안에서 로그 금지.
- 새 플래그 추가 시: main.py 플래그 + defaults + config.toml + .env.example + AGENTS.md 표 — 5곳 동시 갱신.

## 6. 실행 모델 & 성능

- 구독 QoS: `qos_profile_sensor_data` (best effort, depth 1) — 프레임 밀림 방지.
- 콜백은 **변환 없이 원본 메시지만** `FrameSlot`에 저장(drop)한다. 픽셀 변환은 렌더 직전에만
  수행 — 수신률이 렌더율보다 높으면 수신 프레임 상당수가 렌더 없이 버려지므로, 변환 비용을
  렌더량에 비례시킨다.
- 손상 프레임(`FrameDecodeError`/`UnsupportedEncodingError`)은 렌더 루프에서 스킵하고
  종료 시 `bad_frames` 카운트만 로그에 남긴다.
- FPS 스로틀은 `RateLimiter`(모노토닉 클럭)로 구현 — `time.sleep` 사용 금지.
- 변환 성능(1080p, ms/frame): rgb8 0.2 / bgr8 0.3 / rgba·bgra 0.8 / mono 0.25 /
  CompressedImage(jpeg) ~20(디코딩 자체가 지배). 채널 재배치에 numpy 음수 스트라이드 복사
  (예: `[..., ::-1]`)을 쓰지 않는다 — `cv2.cvtColor`(SIMD)가 수십 배 빠르다.
- 터미널 리사이즈: 매 프레임 `get_terminal_size()` 비교, 변경 시 `renderer.resize()`.
- 렌더러는 `use_diff=True, alt_screen=True, hide_cursor=True` 고정.
  종료 시(Signal 포함) `renderer.close()` 보장 — 터미널 복구 필수.

## 7. 자주 하는 실수 (Do NOT)

- ❌ 모듈 레벨 `import rclpy` → ROS 미설치 머신의 단위 테스트 전부 붕괴.
- ❌ `cv_bridge` 사용 → ROS 전용 의존성, uvx 실행이 깨짐. convert.py (numpy/cv2)만 사용.
- ❌ BGR 프레임을 `render_rgb`로 전달 → 색 반전. RGB24로 정규화 후 전달.
- ❌ 렌더 콜백 안에서 `print`/`logging.info` → 화면 깨짐.
- ❌ `except Exception: pass` 같은 무시 처리 → 에러는 명시적 예외 타입 + 안내 메시지.
- ❌ `time.sleep` 기반 프레임 페이싱 → 지연 누적. 모노토닉 기반 RateLimiter 사용.

## 8. 배포

- `uv build` → `uv publish` (PyPI, 패키지명 `ros_tviewer` / 실행명 `ros-tviewer`).
- 배포 전 체크리스트: `uv run pytest`, `uv run ruff check .`, `bash tests/e2e.sh`, README 실행 예시 최신화.
- tcamviewer 하위호환: 구버전(≤0.2.2) 휠의 `.so` 이중 중첩 버그가 있으므로 하한 `>=0.2.3` 고정.
