# `navigate_to_page` 빈 인자 fallback 보강

- **ID**: 014
- **날짜**: 2026-03-24
- **유형**: 버그 수정

## 작업 요약
플로팅 챗봇 런타임 검증 중 첫 번째 `navigate_to_page` 호출이 빈 JSON 인자 `{}`로 생성되면서 `missing 1 required positional argument: 'page'` 오류가 발생했다.
서버 재시작 없이 바로 반영되도록, 동적으로 로드되는 `navigate_to_page` 도구 자체에 fallback 로직을 추가했고, 동시에 차기 로드 시에는 `Agent`가 orchestrator plan·recovery state·최근 page result를 합쳐 네비게이션 입력을 자동 보강하도록 `agent.py`도 함께 정리했다.

## 변경 파일 목록
- `src/model/struct/agent.py`
  - 현재 질문과 orchestrator plan을 인스턴스 상태로 보관하도록 확장
  - `navigate_to_page` 실행 전 `page/tab/query/params`를 최근 page result·recovery state·질문 키워드로 자동 보강하는 helper 추가
  - `read_page_results` 결과의 collection을 tool context에 다시 반영하도록 동기화
- `src/model/struct/agent/tools/navigate_to_page.py`
  - `page` 없는 호출도 처리할 수 있도록 함수 시그니처를 완화
  - 현재 HTTP 요청의 `message`를 읽어 page/tab/query를 추론하는 fallback 추가
  - 빈 인자 호출이어도 `/research?tab=discover` 등 유효한 handoff 결과를 반환하도록 수정
- `.github/task/todo.md`
  - 다음 작업 번호 템플릿으로 갱신
- `devlog.md`
  - 2026-03-24 작업 인덱스 014 추가

## 검증
- `src/model/struct/agent.py` 정적 오류 없음
- `src/model/struct/agent/tools/navigate_to_page.py` 정적 오류 없음
- `wiz project build --project=main` 성공
- 동일 SSE 요청에서 `Error executing navigate_to_page` 0건 확인
