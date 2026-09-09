# 기여 가이드 (Contributing)

ros-tviewer에 관심을 가져주셔서 감사합니다. 아래 규칙을 따라주시면 리뷰가 빨라집니다.

## 개발 환경

- Python 3.12, [uv](https://docs.astral.sh/uv/), ROS 2 (Jazzy/Humble, 테스트 실행 시)
- 빌드 도구: `cmake`, FFmpeg dev 라이브러리 (`libavcodec-dev` 등) — tcamviewer sdist 빌드용

```bash
uv sync                        # 의존성 설치
uv run pytest                  # 단위 테스트 (ROS 미설치 환경에서도 실행 가능)
uv run ruff check .            # 린트
uv run ruff format --check .   # 포맷 검사
uvx pyright --project .        # 타입 체크
bash tests/e2e.sh              # ROS 환경 E2E (더미 퍼블리셔 → play 60프레임)
```

## 규칙

- **[AGENTS.md](AGENTS.md)를 먼저 읽어주세요** — 아키텍처·모듈 계약·TDD 규칙이 정리되어 있습니다.
- 새 기능은 **실패하는 테스트부터** 추가합니다 (Red → Green → Refactor).
- 단위 테스트는 rclpy/sensor_msgs 없이 실행 가능해야 합니다 (`tests/fakes.py` 헬퍼 사용).
  rclpy가 필요한 경로는 `pytest.mark.skipif` 또는 서브프로세스 E2E로 검증합니다.
- 모듈 레벨 `import rclpy` 금지 (함수 내부 지연 임포트만 허용).
- 렌더 루프 안에서 `print`/로깅 금지 (터미널 오염).
- 커밋 전에 린트·포맷·테스트를 모두 통과해야 합니다.

## PR 프로세스

1. 이슈를 먼저 생성해 방향을 맞추는 것을 권장합니다.
2. 작은 단위의 PR을 선호합니다 (한 PR = 한 목적).
3. PR 설명에 변경 요약과 검증 방법(`pytest`, E2E 등)을 적어주세요.
