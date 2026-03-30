# 페이지 인자 결과를 LLM이 한국어로 최종 정리하도록 복원

- **ID**: 021
- **날짜**: 2026-03-23
- **유형**: 기능 추가

## 작업 요약
기존에는 `read_page_results` 결과가 존재하면 빠른 fallback 답변으로 즉시 종료되어, 인자값이 반영된 페이지 결과를 LLM이 한국어로 정리하는 과정이 약해질 수 있었다.
이를 수정해 페이지 결과가 있더라도 LLM refinement가 실행되도록 복원하고, query/params로 실행된 실제 페이지 결과를 한국어 최종답변에서 직접 해석하도록 지시문을 강화했다.

## 변경 파일 목록
- `src/model/struct/agent.py`
  - `_refine_final_answer()`에서 page_results fast return 제거
  - refinement system/user prompt에 “인자값이 반영된 페이지 결과를 한국어로 설명” 규칙 추가
  - 품질 보고 detail을 페이지 결과 기반 한국어 재구성에 맞게 조정
