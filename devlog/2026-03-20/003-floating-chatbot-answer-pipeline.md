# 플로팅 챗봇 5요소 답변 파이프라인 적용

- **ID**: 003
- **날짜**: 2026-03-20
- **유형**: 기능 추가

## 작업 요약
플로팅 챗봇의 최종 답변 과정이 프롬프트, 오케스트레이터, 도구, 메모리, 스트리밍 UI의 5요소를 명시적으로 거치도록 구조를 보강했다.
에이전트 백엔드에서 각 구성 요소의 실행 상태를 SSE 이벤트로 내보내고, 프론트엔드에서는 이를 별도 파이프라인 카드로 시각화해 답변이 어떤 과정을 거쳐 생성되는지 실시간으로 확인할 수 있도록 했다.
변경 후 Angular 빌드를 다시 수행하고 서버 재시작 없이 bundle 정적 파일만 교체해 반영했다.

## 변경 파일 목록
- `src/model/struct/agent.py`
  - 세션 메모리 컨텍스트, 오케스트레이터 계획, 5요소 파이프라인 SSE 이벤트 추가
- `src/app/component.chat.floating/view.ts`
  - 프롬프트/오케스트레이터/도구/메모리/스트리밍 UI 상태 모델과 이벤트 반영 로직 추가
- `src/app/component.chat.floating/view.pug`
  - 5요소 답변 파이프라인 카드 UI 추가
- `build/src/app/component.chat.floating/component.chat.floating.component.ts`
  - build용 챗봇 컴포넌트에 동일 로직 동기화
- `build/src/app/component.chat.floating/view.pug`
  - build용 템플릿에 파이프라인 카드 UI 동기화
- `build/tsconfig.json`
  - build 전용 strict 완화 재적용
- `build/angular.json`
  - assets 복사 및 budget 설정 보정
- `build/src/libs/portal/season/service.ts`
  - build 호환성용 서비스 타입 완화 재적용
- `build/src/wiz.ts`
  - build 호환성용 Promise 반환 타입 보정 재적용
- `build/src/app/app-routing.module.ts`
  - build 전용 타입 검사 완화 재적용
- `build/src/styles/portal/dizest/workflow.scss`
  - 누락된 SCSS import 스텁 생성
- `build/src/styles/portal/dizest/markdown.scss`
  - 누락된 SCSS import 스텁 생성
- `bundle/www/`
  - 무중단 배포 반영
