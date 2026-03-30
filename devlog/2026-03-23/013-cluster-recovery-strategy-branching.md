# 군집형 에이전트 실패 사유별 복구 전략 분기

- **ID**: 013
- **날짜**: 2026-03-23
- **유형**: 기능 추가

## 작업 요약
군집형 에이전트의 self-correction 루프를 일반적인 planner fallback에서 실패 사유별 recovery strategy 분기로 확장했다.
retriever/analyst/synthesizer/navigator 실패 유형에 따라 다른 복구 전략 라벨과 힌트를 goal state에 기록하고, 플로팅 챗봇 UI의 답변 생성 과정에 그대로 노출되도록 연결했다.

## 변경 파일 목록
- `src/model/struct/agent.py`
  - `_select_recovery_strategy()`를 추가해 실패 원인과 cluster 종류에 따라 복구 전략을 결정하도록 구현
  - `goal_manager` 이벤트 meta에 `recovery_strategy`, `recovery_hint`를 포함
  - cluster prompt가 현재 복구 전략 힌트를 반영하도록 확장
  - tool/synthesizer 평가 실패 시 선택된 복구 전략을 goal state에 기록하고 즉시 다음 iteration 재계획으로 전환
- `src/app/component.chat.floating/view.ts`
  - executionPlan에 `recoveryStrategy`, `recoveryHint`를 추가
  - `답변 생성 과정`에 `복구 전략` 항목을 표시하도록 확장
