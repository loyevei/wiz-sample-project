# 최신 논문 추천에 채택연도와 접수연도 노출 추가

- **ID**: 007
- **날짜**: 2026-03-26
- **유형**: 기능 추가

## 작업 요약
추천 논문 결과에 이미 추출되던 `accepted_year`, `received_year`를 page result와 UI 카드까지 전파했다.
플로팅 챗봇의 `read_page_results(research/recommend)` 응답에도 두 필드를 포함시켰고, Research 추천 카드에서는 출판연도/온라인 공개연도와 함께 채택연도/접수연도를 조건부로 표시하도록 정리했다. 에이전트의 recommend 요약 로직도 해당 연도 필드가 존재하면 자연스럽게 근거 문구에 포함할 수 있도록 보강했다.

## 변경 파일 목록
- `src/model/struct/agent/tools/read_page_results.py`
  - `accepted_year`, `received_year`를 recommend page result papers 항목에 포함
- `src/model/struct/agent.py`
  - recommend 하이라이트/근거 문구가 채택연도/접수연도도 읽을 수 있게 보강
- `src/app/page.research/view.pug`
  - 추천 카드 메타행에 `채택 {accepted_year}`, `접수 {received_year}` 조건부 표시 추가

## 검증
- `python3 -m py_compile` 문법 확인
- `wiz project build --project=main` 성공
- `page.agent.v2` SSE 검증
  - papers 항목에 `accepted_year`, `received_year` 필드 포함 유지 확인
  - 최종 verification 답변 정상 출력 확인
