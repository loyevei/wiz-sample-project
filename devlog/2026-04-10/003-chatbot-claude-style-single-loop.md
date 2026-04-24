# 챗봇 백엔드를 Claude 분석서형 단일 Tool-Use 루프로 재구성

- **ID**: 003
- **날짜**: 2026-04-10
- **유형**: 리팩토링

## 작업 요약
기존 계층형 오케스트레이터 중심 구조를 단순화해, `.github/09-ai-agent.md`의 Claude 분석서와 같은 형태의 `Agent.run()` 단일 Generator loop로 재구성했다. `KeywordAgent`와 `RouterAgent`는 사전 계획 보조로만 사용하고, 실제 실행은 `text / tool_use / tool_result / done` 중심의 단일 Tool-Use 반복으로 전환했다. 페이지 이동, 인자값 삽입, 페이지 결과 출력은 유지했다.

## 변경 파일 목록
- **`/opt/app/.github/task/todo.md`**
  - `FN-20260410-0002` 작업 항목 추가
- **`project/main/src/model/struct/agent.py`**
  - `OrchestratorAgent` 위임 구조 제거
  - `Agent.run()`을 Claude 스타일 단일 loop로 재작성
  - `KeywordAgent`, `RouterAgent`만 동적 로드해 사전 계획 생성
  - `read_page_results` 선실행으로 페이지 결과 카드 유지
  - `navigate_to_page` 최종 handoff 보장 로직 유지
  - history / tool_call / tool_result 메시지 관리 로직을 `agent.py` 내부로 통합

## 검증
- 일반 빌드 성공: `EsBuild complete in 237ms`
- SSE 흐름 확인: `orchestration → tool_use(read_page_results) → tool_result → text → tool_use(navigate_to_page) → tool_result → text → done`
- 서버 재시작 없이 `wiz project build main`만으로 반영 완료
