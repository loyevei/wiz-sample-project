# 군집형 에이전트 cluster별 허용 tool 정책 분리

- **ID**: 011
- **날짜**: 2026-03-23
- **유형**: 기능 추가

## 작업 요약
군집형 에이전트의 각 cluster가 사용할 수 있는 tool 범위를 분리해, 반복 루프마다 active cluster에 맞는 tool schema만 OpenAI 호출에 전달하도록 강화했다.
planner는 추천 도구 범위를 조정하고, retriever는 수집 계열, analyst는 분석 계열, navigator는 handoff 계열만 사용하도록 제한해 cluster 역할 경계가 더 분명해졌다.

## 변경 파일 목록
- `src/model/struct/agent.py`
  - `_get_cluster_allowed_tools`, `_get_openai_tools_for_cluster` helper 추가
  - goal-state에 `allowed_tools` 반영
  - active cluster마다 다른 tool schema를 사용하도록 run loop 강화
- `src/app/component.chat.floating/view.ts`
  - `executionPlan.allowedTools` 반영
  - `답변 생성 과정`과 실행 계획 요약에 현재 군집 허용 도구 표시 추가

## 검증
- `cd /opt/app/project/main && wiz project build --project=main`
