# 보안 정책 (Security Policy)

## 지원 버전

| 버전 | 지원 여부 |
| --- | --- |
| 0.1.x | 지원 |

## 취약점 보고

- **공개 이슈(GitHub Issues)로 보고하지 마세요.** 공개 토론은 악용 위험을 키웁니다.
- GitHub의 [비공개 보안 보고(Security Advisories → Report a vulnerability)](../../security/advisories/new) 기능을 사용해 비공개로 보고해 주세요.
- 보고 내용에는 영향받는 버전(`ros-tviewer version` 출력), 재현 절차, 예상되는 영향을 포함해 주세요.

## 대응 목표

- 접수 확인: 7일 이내
- 심각도 평가 및 수정 계획: 30일 이내
- 수정 배포 후 사전 합의된 시점에 보고자에게 공개 크레딧 제공 (원하지 않는 경우 생략)

## 보안 관련 참고 사항

- 이 도구는 로컬 ROS 2 네트워크의 카메라 토픽을 구독하는 읽기 전용 CLI입니다.
- `rclpy`는 시스템 ROS 설치에서 로드되며, 필요 시 환경변수를 구성한 뒤 동일 argv로
  프로세스를 재실행(re-exec)합니다 (`src/ros_tviewer/ros_env.py` 참고).
