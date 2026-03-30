# 최신 논문 날짜 파서를 본문/초록까지 확장

- **ID**: 005
- **날짜**: 2026-03-26
- **유형**: 기능 추가

## 작업 요약
최신 논문 추천의 신뢰도를 높이기 위해, 파일명 기반 연도 추출만 사용하던 로직을 본문/초록 텍스트까지 읽도록 확장했다.
`Available online 15 November 2024`, `Applied Surface Science 508 (2020)` 같은 문구 패턴에서 연도를 추출하도록 보강했고, 파일명 연도가 있으면 우선 사용하되 없을 때는 텍스트에서 가장 신뢰할 수 있는 최신 연도를 채택하도록 정리했다.

## 변경 파일 목록
- `src/app/page.research/api.py`
  - `_extract_year_candidates_from_text()` 추가
  - `_extract_best_paper_year()` 추가
  - 추천 결과 생성 시 `filename + text/abstract`를 함께 사용해 `year` 결정

## 검증
- `python3 -m py_compile src/app/page.research/api.py`
- `wiz project build --project=main`
- `page.agent.v2` SSE 검증
  - `research/recommend` 결과의 상위 연도: `2025`, `2015`
  - 최종 verification 답변에 최신 연도 문구 유지 확인
