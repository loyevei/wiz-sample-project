# 군집형 에이전트 cluster-specific prompt 도입

- **ID**: 010
- **날짜**: 2026-03-23
- **유형**: 기능 추가

## 작업 요약
군집형 에이전트 구조를 한 단계 더 확장해 planner/retriever/analyst/synthesizer/navigator별 전용 프롬프트를 도입했다.
이제 goal-loop의 각 반복에서 현재 목표 상태와 남은 항목에 따라 active cluster를 결정하고, 해당 cluster 지시문을 system prompt에 주입해 다음 행동을 더 일관되게 선택하도록 구성했다.

## 변경 파일 목록
- `src/model/struct/agent.py`
  - `active_cluster`, `goal_progress`를 포함하는 system prompt 구조로 확장
  - `_determine_active_cluster`, `_build_cluster_prompt` helper 추가
  - loop iteration마다 active cluster에 맞춰 system prompt를 재구성하도록 변경
  - 재계획 시 임시 system 메시지 누적 대신 goal-state 기반 반복으로 정리
- `src/app/component.chat.floating/view.ts`
  - executionPlan에 `currentCluster` 반영
  - `답변 생성 과정`에서 현재 주도 군집이 보이도록 보강

## 검증
- `cd /opt/app/project/main && wiz project build --project=main`
