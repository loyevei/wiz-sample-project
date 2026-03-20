# 플로팅 챗봇 색상 테마 및 로봇 아이콘 교체

- **ID**: 002
- **날짜**: 2026-03-20
- **유형**: 기능 추가

## 작업 요약
플로팅 챗봇의 전체 색상 톤을 기존 시안/하늘색 중심에서 보라/핑크 기반 플라즈마 테마로 변경했다.
또한 플로팅 버튼, 헤더, 빈 상태, 입력 영역의 아이콘을 공통 SVG 로봇 이미지로 교체해 시각 정체성을 강화했다.
빌드 후 서버 재시작 없이 번들을 갱신하고, 로봇 SVG를 런타임 자산 경로에 복사해 즉시 반영되도록 처리했다.

## 변경 파일 목록
- `src/app/component.chat.floating/view.pug`
  - 플로팅 버튼, 헤더, 빈 상태, 입력부 색상을 보라/핑크 계열로 변경하고 로봇 이미지 삽입
- `src/app/component.chat.floating/view.scss`
  - 스크롤바와 이미지 상호작용 스타일 보정
- `src/assets/brand/plasma-robot.svg`
  - 새 플라즈마 로봇 SVG 아이콘 추가
- `build/src/app/component.chat.floating/view.pug`
  - build 템플릿에 동일한 테마/이미지 반영
- `build/src/app/component.chat.floating/view.scss`
  - build 스타일 동기화
- `build/angular.json`
  - build 자산 복사 설정 보완
- `bundle/www/assets/brand/plasma-robot.svg`
  - 런타임 자산 경로에 로봇 이미지 배포
