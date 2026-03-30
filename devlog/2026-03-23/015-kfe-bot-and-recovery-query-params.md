# KFE bot 명칭 변경 및 복구 전략 입력 힌트 확장

- **ID**: 015
- **날짜**: 2026-03-23
- **유형**: 기능 추가

## 작업 요약
플로팅 챗봇의 노출 명칭을 `KFE bot`으로 변경했다.
또한 군집형 에이전트의 recovery strategy가 다음 iteration에서 사용할 query/params 힌트까지 생성해 goal state와 플로팅 UI에 표시되도록 확장했다.

## 변경 파일 목록
- `src/app/component.chat.floating/view.ts`
  - `robotProfile.name`을 `KFE bot`으로 변경
  - executionPlan에 `recoveryQuery`, `recoveryParams`를 추가하고 답변 생성 과정/실행 계획에 표시
- `src/app/component.chat.floating/view.pug`
  - 플로팅 버튼 하단 `PX14` 표기를 `KFE bot`으로 변경
  - 빈 상태 헤더가 `robotProfile.name`을 사용하도록 정리
- `src/model/struct/agent.py`
  - recovery strategy별 다음 시도용 `query/params`를 계산하는 helper 추가
  - self-correction 이벤트 meta에 `recovery_query`, `recovery_params`를 포함해 UI가 다음 입력 힌트를 표시할 수 있도록 연결
