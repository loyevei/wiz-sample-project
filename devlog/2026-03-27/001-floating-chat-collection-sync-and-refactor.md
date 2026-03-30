# 플로팅 챗봇 컬렉션 동기화 수정 및 구조 리팩토링

- **ID**: 001
- **날짜**: 2026-03-27
- **유형**: 버그 수정

## 작업 요약
플로팅 챗봇에서 컬렉션 변경 후 질문을 이어갈 때 페이지 handoff에 최신 컬렉션이 반영되지 않던 문제를 수정했다.
동시에 플로팅 챗봇 프론트엔드의 상태 관리/네비게이션 로직 중복을 줄이고, 에이전트 오케스트레이터가 최신 컬렉션 상태를 사용하도록 정리했다.

## 변경 파일 목록

### 프론트엔드
- `src/app/component.chat.floating/view.ts`
  - `selectedCollection` 동기화를 `syncSelectedCollection()`로 일원화
  - 대화/타이핑/네비게이션 초기화를 `resetConversationState()`로 통합
  - `buildNavigationQueryParams()`를 추가해 즉시 이동/자동 이동의 query param 생성 중복 제거
  - 질문 전송과 handoff 시점 모두 `getActiveCollection()` 기준으로 최신 컬렉션 사용
- `src/app/page.agent.v2/view.ts`
  - quality 이벤트를 수신해 `llmUsed` 등 품질 메타를 표시하도록 확장
- `src/app/page.agent.v2/view.pug`
  - 답변 품질 분석 카드와 `LLM 해석` 배지 표시 추가

### 백엔드
- `src/model/struct/agent/agents/orchestrator_agent.py`
  - 초기 스냅샷에 묶여 있던 컬렉션 참조를 `_current_collection()` 기반으로 변경
  - CollectorAgent 이후 최신 컬렉션 상태를 품질/메모리 이벤트에 반영

## 구조 분석 및 우선순위 정리
1. **우선순위 높음 — 컬렉션 상태 소스 분산**
   - `selectedCollection`, `localStorage`, `pendingNavigation.collection`이 각각 따로 사용되며 동기화 경로가 중복되어 있었음
   - 공통 helper로 정리해 최신 컬렉션을 단일 흐름으로 사용하도록 수정
2. **우선순위 높음 — 네비게이션 파라미터 생성 중복**
   - 자동 이동과 수동 이동이 각각 query param을 구성해 collection 누락/불일치 가능성이 있었음
   - 공통 `buildNavigationQueryParams()`로 통합
3. **우선순위 중간 — 에이전트 오케스트레이터의 초기 상태 고정**
   - 실행 초기에 읽은 collection 값을 이후 품질/메모리 단계에서도 재사용해 최신 상태 반영이 약했음
   - 런타임 조회 helper로 교체

## 검증
- `python3 -m py_compile src/model/struct/agent/agents/orchestrator_agent.py`
- `wiz project build --project=main`
- SSE 호출로 `navigate_to_page` 결과의 `collection`이 최신 값으로 포함되는지 확인
