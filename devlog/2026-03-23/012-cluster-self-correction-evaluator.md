# 군집형 에이전트 self-correction 평가기 도입

- **ID**: 012
- **날짜**: 2026-03-23
- **유형**: 기능 추가

## 작업 요약
군집형 에이전트에 cluster별 성공/실패 평가기를 추가해, 수집·분석·이동·최종답변 결과가 충분하지 않을 때 planner로 되돌아가 다른 전략을 선택하는 self-correction 루프를 도입했다.
또한 플로팅 챗봇의 `답변 생성 과정`에 현재 평가 결과가 노출되도록 연결해, 목표 반복 관리와 재계획 판단이 더 명확하게 보이도록 정리했다.

## 변경 파일 목록
- `src/model/struct/agent.py`
  - `_evaluate_cluster_outcome`, `_mark_self_correction` helper 추가
  - retriever/analyst/navigator/synthesizer 단계별 결과 품질 평가 로직 구현
  - 결과가 약할 때 planner fallback과 self-correction 이벤트 발생
- `src/app/component.chat.floating/view.ts`
  - executionPlan에 `evaluationStatus`, `evaluationSummary` 반영
  - `답변 생성 과정`과 실행 계획 요약에 결과 평가 표시 추가

## 검증
- `cd /opt/app/project/main && wiz project build --project=main`
