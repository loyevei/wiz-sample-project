# 추천 메타 추출을 헤더 청크 기반으로 보강하고 에이전트 최종 요약 반영

- **ID**: 011
- **날짜**: 2026-03-26
- **유형**: 버그 수정

## 작업 요약
논문 추천 경로에서 `accepted_year` / `received_year`가 비던 원인을 수정했다.
검색 hit가 항상 문서 첫 청크가 아니어서 초록/본문 일부만으로 연도 메타를 추출하던 문제가 있었고, 이를 문서의 `chunk_index == 0` 헤더 청크를 함께 읽는 방식으로 보강했다. 이후 에이전트 최종 답변 요약도 `papers` 배열을 직접 읽어 출판/온라인/채택/접수 연도를 함께 말하도록 정리했다.

## 변경 파일 목록
- `src/app/page.research/api.py`
  - `_load_doc_head_text()` 추가
  - `_recommend_papers_data()`가 문서 첫 청크 텍스트와 검색 hit 텍스트를 합쳐 연도 메타를 추출하도록 수정
- `src/model/struct/agent.py`
  - `research/recommend`용 page summary 조립을 `papers` 기반으로 강화
  - 최종 답변 정리 단계가 출판/온라인/채택/접수 연도를 함께 반영하도록 보강
- `devlog.md`
  - 작업 인덱스 추가

## 검증
- `python3 -m py_compile /opt/app/project/main/src/app/page.research/api.py /opt/app/project/main/src/model/struct/agent.py`
- `wiz project build --project=main`
- `read_page_results` 직접 검증
  - `doc_id=01408398` → `publication_year=2013`, `accepted_year=2012`, `received_year=2012`
- `page.agent.v2` SSE 검증
  - 최종 text에 `채택연도는 2012 입니다. 접수연도는 2012 입니다.` 포함 확인
