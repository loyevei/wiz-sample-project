# 추천 논문 연도 추출용 원문 범위 확장

- **ID**: 010
- **날짜**: 2026-03-26
- **유형**: 버그 수정

## 작업 요약
추천 논문 결과에서 `accepted_year`가 비어 있던 원인을 수정했다.
원인은 추천 경로가 연도 추출에도 화면용 `text_preview[:400]`를 재사용해, `Accepted 17 November 2012`의 연도 부분이 preview 끝에서 잘리던 것이었다. 연도 추출은 더 긴 원문(`[:2000]`)을 사용하고, 화면 표시용 preview는 기존 400자를 유지하도록 분리했다.

## 변경 파일 목록
- `src/app/page.research/api.py`
  - `raw_text`, `text_preview`, `year_source_text`를 분리
  - `_extract_best_paper_years()` 호출에 `year_source_text[:2000]` 사용
- `devlog.md`
  - 작업 인덱스 추가

## 검증
- `python3 -m py_compile /opt/app/project/main/src/app/page.research/api.py`
- 운영 문서 재검증
  - `doc_id=01408398`
  - 결과: `publication_year=2013`, `accepted_year=2012`, `received_year=2012`
- `wiz project build --project=main`
