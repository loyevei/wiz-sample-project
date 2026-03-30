# 최종답변 한국어 정규화 및 페이지 이동 CTA 제거

- **ID**: 022
- **날짜**: 2026-03-23
- **유형**: 기능 추가

## 작업 요약
플로팅 챗봇 최종답변에서 영문 설명 문장이 남는 경우를 후처리 단계에서 한국어로 정규화하도록 보강했다.
또한 sandbox 링크, 주제 발굴 페이지 이동 권유, 페이지 탐색 유도 문구 등 최종답변 본문에 섞이는 CTA 문장을 제거해 사용자는 실제 결과 요약만 보게 했다.

## 변경 파일 목록
- `src/model/struct/agent.py`
  - `_needs_korean_answer_cleanup()` 추가
  - `_strip_navigation_cta()` 추가
  - `_normalize_final_answer_korean()` 추가
  - `_refine_final_answer()`의 refinement/fallback 반환 직전에 한국어 정규화와 CTA 제거 후처리를 적용
