# 최신 논문 추천 라우팅 및 최신성 정렬 보강

- **ID**: 004
- **날짜**: 2026-03-26
- **유형**: 기능 추가

## 작업 요약
플로팅 챗봇에서 "최신 논문 찾아줘" 요청이 주제 탐색(discover)로 흐르던 문제를 수정했다.
에이전트 오케스트레이터가 논문/최신 의도를 `research/recommend`로 분류하도록 보강했고, `read_page_results`와 `navigate_to_page` 실행 시에도 plan의 page/tab을 우선 적용해 계획과 실제 실행이 어긋나지 않게 맞췄다.
또한 Research 논문 추천 API에 파일명 기반 연도 추출과 최신성 정렬을 추가해, `latest/recent/최신/최근` 의도가 있을 때 연도 내림차순 + 유사도 기준으로 추천 결과를 정렬하도록 개선했다.

## 변경 파일 목록
- `src/model/struct/agent.py`
  - 논문 추천 intent 휴리스틱 추가
  - `read_page_results` / `navigate_to_page` 입력 보정 로직 추가
  - recommend 결과 요약 시 `papers[].year` 기반 최신 연도 문구 반영
- `src/model/struct/agent/tools/read_page_results.py`
  - `research/recommend`가 UI의 논문 추천 로직과 동일한 helper를 사용하도록 변경
  - `papers` 구조에 `year`, `relevance`, `snippets` 반영
- `src/app/page.research/api.py`
  - `_extract_year_from_filename`, `_is_latest_intent`, `_strip_latest_terms`, `_recommend_papers_data` helper 추가
  - `recommend_papers()`가 최신성 의도를 반영한 공용 helper를 사용하도록 정리

## 검증
- `python3 -m py_compile`로 수정 파일 문법 확인
- `wiz project build --project=main` 빌드 성공
- `page.agent.v2` SSE 호출로 다음 항목 확인
  - `research/recommend` 탭으로 handoff
  - `read_page_results` 결과에 `year` 포함
  - 최종 verification 답변에 최신 연도(예: 2025) 반영
