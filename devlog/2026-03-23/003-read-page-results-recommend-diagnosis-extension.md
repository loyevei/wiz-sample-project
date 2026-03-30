# `read_page_results` Research 추천·Diagnosis 확장

- **ID**: 003
- **날짜**: 2026-03-23
- **유형**: 기능 추가

## 작업 요약
플로팅 챗봇의 페이지 기반 최종답변 범위를 확장하기 위해 `read_page_results`가 `research/recommend`와 `diagnosis` 주요 탭 결과를 직접 읽도록 확장했다.
페이지 프론트엔드가 실제로 호출하는 서버 로직을 공용 함수로 분리해, 에이전트가 동일한 결과 JSON을 받아 OpenAI로 한글 답변을 재구성하도록 연결했다.

## 변경 파일 목록
- `src/app/page.research/api.py`
  - `run_recommend_data()`를 추가해 추천 결과를 공용 로직으로 분리
  - 기존 `recommend()`가 공용 함수를 재사용하도록 정리
- `src/app/page.diagnosis/api.py`
  - `run_search_diagnostic_data()` 추가
  - `run_compare_diagnostics_data()` 추가
  - `run_diagnosis_detection_data()` 추가
- `src/model/struct/agent/tools/read_page_results.py`
  - `research/recommend` 지원 추가
  - `diagnosis/search`, `diagnosis/compare`, `diagnosis/detection` 지원 추가
- `src/model/struct/agent.py`
  - 진단 분석 워크플로우에 `read_page_results` 우선 사용 가이드 반영

## 변경 패턴
- Before
  - 에이전트가 일부 페이지 결과만 직접 읽을 수 있었고, 추천/진단 결과는 페이지 이동 후 별도 확인이 필요했다.
- After
  - 에이전트가 추천/진단 탭의 실제 결과 JSON을 직접 읽고, 그 내용을 바탕으로 한글 최종답변을 재구성할 수 있다.
