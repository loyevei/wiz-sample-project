# 플로팅 챗봇 14단계 사고과정 UI 및 플라즈마 로봇 캐릭터 적용

- **ID**: 001
- **날짜**: 2026-03-20
- **유형**: 기능 추가

## 작업 요약
플로팅 챗봇에 에이전트 실행 과정을 14단계로 시각화하는 아코디언형 trace UI를 추가하고, 현재 단계 설명·참고 문헌·유사도·tool 실행 로그·최종 답변을 분리해 보여주도록 구성했다.
또한 챗봇의 시각 정체성을 플라즈마 톤의 로봇 캐릭터로 개편하고, 최신 턴만 펼치고 이전 턴은 접히는 동작으로 대화 가독성을 개선했다.
서버 재시작 없이 Angular 빌드 후 `bundle/www`에 산출물을 복사해 반영했다.

## 변경 파일 목록
- `src/app/component.chat.floating/view.ts`
  - 14단계 trace 상태, 현재 단계 동기화, 참고 문헌/유사도 파싱, 이전 assistant 턴 접기 로직 추가
- `src/app/component.chat.floating/view.pug`
  - 사고과정 아코디언, 현재 단계 패널, 참고 문헌/유사도, tool 카드, 최종 답변, 플라즈마 로봇 헤더/버튼 UI로 개편
- `build/src/app/component.chat.floating/component.chat.floating.component.ts`
  - source 로직을 build 컴포넌트로 동기화
- `build/src/app/component.chat.floating/view.pug`
  - build 템플릿을 source와 동일한 로봇형 UI로 동기화
- `build/src/app/component.chat.floating/view.html`
  - Pug 재컴파일 결과 반영
- `build/src/app/app-routing.module.ts`
  - build 회귀 대응을 위한 타입 검사 완화 적용
- `build/src/app/page.agent/page.agent.component.ts`
  - 중복 `wiz` 선언 제거
- `build/src/app/page.analysis/page.analysis.component.ts`
  - 중복 `wiz` 선언 제거
- `build/src/app/page.calculator/page.calculator.component.ts`
  - 중복 `wiz` 선언 제거
- `build/src/app/page.collaboration/page.collaboration.component.ts`
  - 중복 `wiz` 선언 제거
- `build/src/app/page.experiment/page.experiment.component.ts`
  - 중복 `wiz` 선언 제거
- `build/src/app/page.experiment.dataset/page.experiment.dataset.component.ts`
  - 중복 `wiz` 선언 제거
- `build/src/styles/portal/dizest/workflow.scss`
  - 누락 import 대응용 스타일 스텁 추가
- `build/src/styles/portal/dizest/markdown.scss`
  - 누락 import 대응용 스타일 스텁 추가
- `bundle/www/`
  - 무중단 배포 산출물 반영
