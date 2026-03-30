# 최신 논문 추천의 출판연도와 온라인 공개연도 분리

- **ID**: 006
- **날짜**: 2026-03-26
- **유형**: 기능 추가

## 작업 요약
최신 논문 추천 결과에서 연도 정보를 단일 `year`로만 다루던 구조를 확장해, `publication_year`와 `online_year`를 분리해 저장하고 응답에 포함하도록 변경했다.
본문/초록의 `available online`, `published`, `accepted`, `received` 패턴을 구분해 추출하며, 기존 `year`는 하위 호환을 위해 대표 연도로 유지한다. 에이전트 최종답변과 Research 추천 카드에서도 출판연도/온라인 공개연도를 구분해 표시하도록 정리했다.

## 변경 파일 목록
- `src/app/page.research/api.py`
  - `_extract_temporal_signals()` 추가
  - `publication_year`, `online_year`, `accepted_year`, `received_year` 추출
  - 추천 결과에 새 날짜 필드 포함, `year`는 대표값으로 유지
- `src/model/struct/agent/tools/read_page_results.py`
  - recommend 결과의 `publication_year`, `online_year` 전달
- `src/model/struct/agent.py`
  - recommend 하이라이트/근거 문구에서 출판연도/온라인 공개연도를 분리해 요약
- `src/app/page.research/view.pug`
  - 추천 카드에 `출판 {publication_year}`, `온라인 {online_year}` 표시

## 검증
- `python3 -m py_compile` 문법 확인
- `wiz project build --project=main` 성공
- `page.agent.v2` SSE 검증
  - `read_page_results` 상위 결과에 `publication_year`/`online_year` 포함
  - verification 최종답변에 `추천 후보의 출판연도는 2025, 2015` 문구 반영
