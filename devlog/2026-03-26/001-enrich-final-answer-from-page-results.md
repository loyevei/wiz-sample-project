# 페이지 결과 기반 최종답변 풍부화 (LLM 정제 강제)

- **ID**: 001
- **날짜**: 2026-03-26
- **유형**: 버그 수정

## 작업 요약
챗봇이 페이지 이동/검색까지는 정확히 수행했지만, 최종답변 생성 단계에서 `page_results`가 존재하면 조기 return으로 요약만 반환하여 `핵심 결론`이 1문장(대표 유사도 숫자 반복)으로 끝나는 문제가 있었다. 이를 해결하기 위해 `page_results`를 1차 근거로 LLM 정제 단계까지 반드시 연결하고, 페이지 결과에서 추출한 snippet/top_terms 시그널을 프롬프트에 주입해 결론 문단을 풍부화했다.

## 변경 파일 목록
- project/main/src/model/struct/agent.py
  - `page_results`가 있을 때 요약만 반환하던 조기 return 제거 → LLM 정제 단계로 연결
  - `_needs_refinement()`에 `page_results` 기반 휴리스틱 추가 (문단 수/길이/유사도 문장 단독 패턴 감지)
  - `_collect_text_snippets_from_page_results()`, `_extract_top_keywords()` 신규 추가
  - 정제 프롬프트에 Derived signals(top_terms/sample_snippets) 블록 추가

## 빌드
- `wiz project build --project=main` (서버 재시작 없이 반영)
