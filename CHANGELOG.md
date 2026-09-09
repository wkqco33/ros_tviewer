# Changelog

이 프로젝트의 모든 주목할 만한 변경 사항이 이 파일에 기록됩니다.

형식은 [Keep a Changelog](https://keepachangelog.com/ko/1.1.0/)을 따르며,
버전 관리는 [Semantic Versioning](https://semver.org/lang/ko/)을 따릅니다.

## [Unreleased]

### Added

- `play` 커맨드: ROS 2 카메라 토픽(Image/CompressedImage)을 tcamviewer
  Half-Block TrueColor 렌더러로 터미널에 실시간 재생 — `--fps`, `--rotate`,
  `--stretch`, `--compressed`, `--timeout`, `--frames` 플래그
- `topics` 커맨드: 광고 중인 sensor_msgs 카메라 토픽 나열
- `config` / `version` 커맨드
- 플랫폼별 사용자 설정 경로 로드 (XDG_CONFIG_HOME / APPDATA / Library),
  cwd `config.toml`이 사용자 설정을 오버라이드
- `config` 서브커맨드: `init`(사용자 설정 파일 생성, `--force`),
  `set <key> <value>`(TOML 리터럴 타입 해석 저장), `show`, `path`
- 설정 기본값에서 어디서도 읽지 않는 `app.*` 키 제거
- 최신 프레임 우선(drop) 구독 + 모노토닉 FPS 스로틀, 렌더 직전 변환
- 시스템 ROS 2 자동 부트스트랩 (sys.path 주입 → re-exec)
- 단위 테스트(ROS 불필요), ROS E2E 테스트, CI (ruff lint/format + pytest)

## [0.1.0] - 2025-09-09

### Added

- 최초 릴리스 (위 Unreleased 항목 포함)

[Unreleased]: https://github.com/wkqco33/ros_tviewer/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/wkqco33/ros_tviewer/releases/tag/v0.1.0
