# 복구 전략 기반 다음 도구 우선순위 반영

- **ID**: 014
- **날짜**: 2026-03-23
- **유형**: 기능 추가

## 작업 요약
군집형 에이전트의 recovery strategy가 단순 상태 표시를 넘어서 다음 iteration의 실제 도구 선택 순서까지 바꾸도록 확장했다.
planner는 self-correction 이후 전략별로 재정렬된 recommended tools를 우선 사용하며, 플로팅 챗봇 UI에도 변경된 우선 도구 순서가 그대로 반영된다.

## 변경 파일 목록
- `src/model/struct/agent.py`
  - goal state에 `recommended_tools`를 유지하도록 확장
  - recovery strategy별 preferred tools를 계산하는 우선순위 로직을 planner prompt 및 planner allowed tools 순서에 반영
  - self-correction 시 선택된 strategy에 따라 다음 iteration용 `recommended_tools`를 재계산하도록 수정
- `src/app/component.chat.floating/view.ts`
  - `goal_manager` 이벤트에서 갱신된 `recommended_tools`를 executionPlan에 반영
  - 실행 계획 상세에 `우선 도구`를 표시하도록 확장
