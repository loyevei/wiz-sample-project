# 변경 컬렉션 기준 에이전트 파이프라인 재적용

- **ID**: 002
- **날짜**: 2026-03-27
- **유형**: 버그 수정

## 작업 요약
플로팅 챗봇에서 컬렉션이 변경된 뒤 이어지는 질문이 이전 컬렉션의 대화 이력이나 도구 실행 결과에 영향을 받지 않도록 흐름을 정리했다.
최신 컬렉션 기준으로 페이지 결과를 먼저 읽고, 이후 페이지 handoff까지 보장되도록 collector 파이프라인을 보강했다.

## 변경 파일 목록
- `src/app/component.chat.floating/view.ts`
  - 외부 컬렉션 변경 이벤트 수신 시 기존 대화 상태와 진행 중 SSE 요청을 정리하도록 수정
  - 신규 assistant 턴 생성 시 현재 활성 컬렉션을 executionPlan에 직접 반영
- `src/model/struct/agent/agents/orchestrator_agent.py`
  - keyword classification 및 router plan에 현재 collection을 명시적으로 주입
- `src/model/struct/agent/agents/collector_agent.py`
  - `read_page_results`를 최신 컬렉션 기준으로 선실행하는 synthetic tool 단계 추가
  - `navigate_to_page`가 누락되면 fallback으로 handoff를 보장하도록 보강
  - synthetic tool 결과를 messages/history에 반영해 이후 LLM 단계가 최신 컬렉션의 페이지 결과를 기반으로 동작하도록 수정
