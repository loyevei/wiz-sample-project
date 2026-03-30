# 영어 근거 기반이어도 최종답변/preview를 한국어로 강제

- **ID**: 019
- **날짜**: 2026-03-23
- **유형**: 기능 추가

## 작업 요약
플로팅 챗봇이 영어 근거나 영어 초안을 사용하더라도, 사용자가 보게 되는 preview와 최종답변은 모두 한국어로 나오도록 강제했다.
영어 raw 초안이 preview로 직접 노출되는 경로를 제거했고, refinement 결과가 한국어가 아니면 한국어 fallback으로 다시 덮어쓰도록 보강했다.

## 변경 파일 목록
- `src/model/struct/agent.py`
  - `_has_korean()` helper 추가
  - `_needs_refinement()`가 비한글 답변을 반드시 후처리 대상으로 보도록 강화
  - `_build_fast_final_answer()`가 영어 draft를 그대로 노출하지 않고 한국어 구조화 fallback을 우선 사용하도록 수정
  - refinement 결과가 한국어가 아니면 한국어 fallback으로 강제 교체
  - tool-call 전 preview에서 raw `msg.content`를 직접 보내지 않고 `_build_quick_preview_answer()` 기반 한국어 preview만 전송하도록 수정
