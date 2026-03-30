# 플로팅 챗봇 군집형 에이전트 목표 반복 관리 도입

- **ID**: 009
- **날짜**: 2026-03-23
- **유형**: 기능 추가

## 작업 요약
플로팅 챗봇 백엔드 에이전트를 단순 도구 호출형에서, 목표에 도달할 때까지 상태를 재평가하는 군집형 에이전트 방식으로 확장했다.
planner/retriever/analyst/synthesizer/navigator 역할 군집을 오케스트레이터 계획과 시스템 프롬프트에 반영하고, 반복 루프마다 남은 목표 항목을 점검해 부족한 경우 재계획을 수행하도록 구성했다.

## 변경 파일 목록
- `src/model/struct/agent.py`
  - goal, agent cluster, goal-state helper 추가
  - 반복 실행 루프에 목표 점검 및 재계획 로직 추가
  - 목표가 완전히 충족되지 않으면 추가 도구 선택을 유도하도록 강화
- `src/app/component.chat.floating/view.ts`
  - executionPlan에 goal / goalStatus / goalSummary / agentClusters 반영
  - `답변 생성 과정`에 목표 상태와 군집형 역할 분담이 자연스럽게 포함되도록 보강
- `src/app/component.chat.floating/view.pug`
  - 빈 상태 안내 문구를 군집형 에이전트 반복 관리 방식에 맞게 조정

## 검증
- `cd /opt/app/project/main && wiz project build --project=main`
