# 플로팅 챗봇 근거 조합형 답변 품질 고도화

- **ID**: 006
- **날짜**: 2026-03-20
- **유형**: 기능 추가

## 작업 요약
플로팅 챗봇이 Milvus 검색 결과를 그대로 나열하지 않고, 수집한 근거를 조합·구조화·검증한 뒤 더 품질 높은 최종 답변으로 재작성하도록 에이전트 로직을 보강했다.
백엔드에서는 검색 근거 bank, 답변 재구성, 검증 요약 이벤트를 추가했고, 프론트엔드에서는 근거 조합 요약·검증 체크·주요 소스를 보여주는 품질 보강 패널을 렌더링하도록 확장했다.
변경 후 build 워크스페이스 호환성 패치를 재적용하고 Angular 빌드 및 bundle 교체를 수행해 서버 재시작 없이 반영했다.

## 변경 파일 목록
- `src/model/struct/agent.py`
  - Milvus 검색 결과를 evidence bank로 수집
  - 최종 답변 재구성용 품질 정제 pass 추가
  - quality SSE 이벤트와 검증 요약 추가
- `src/app/component.chat.floating/view.ts`
  - answerQuality 상태 모델과 quality 이벤트 처리 추가
  - trace 12/13 단계에 근거 조합/검증 상태 반영
- `src/app/component.chat.floating/view.pug`
  - 답변 품질 보강 패널 추가
- `build/src/app/component.chat.floating/component.chat.floating.component.ts`
  - build용 플로팅 챗봇에 동일 로직 동기화
- `build/src/app/component.chat.floating/view.pug`
  - build용 품질 보강 패널 동기화
- `build/tsconfig.json`
  - build 전용 strict 완화 재적용
- `build/angular.json`
  - assets 복사 및 budget 설정 복원
- `build/src/libs/portal/season/service.ts`
  - build 호환성용 타입 완화 재적용
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
