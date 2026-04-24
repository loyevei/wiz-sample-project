# AI 에이전트 챗봇 — 사이드바 패널 전환 + Claude×Copilot 하이브리드

- **ID**: 002
- **날짜**: 2026-04-08
- **유형**: 기능 추가 + 리팩토링

## 작업 요약
플로팅 챗봇(component.chat.floating)을 레이아웃 통합형 사이드바 패널(component.chat.sidebar)로 전환했다. 420px 우측 패널이 토글 가능하며, Claude와 VS Code Copilot의 에이전트 상호작용 패턴을 혼합한 UI/UX를 구현했다. 백엔드 에이전트 아키텍처(5 sub-agents + 21 tools)는 그대로 유지하고 SSE 엔드포인트를 공유한다.

## 핵심 변경 사항

### 1. 새 컴포넌트: component.chat.sidebar
- `view.ts` (~700줄): 기존 1997줄에서 60% 이상 코드 감소
  - 카드 reveal 시퀀스, journey 시스템, 복잡한 trace 상태 관리 제거
  - SSE 이벤트 핸들러 간소화 (switch/case 기반 깔끔한 분기)
  - 동일한 백엔드 SSE 엔드포인트 사용 (/wiz/api/page.agent.v2/agent_chat)
- `view.pug` (~160줄): 사이드바 네이티브 UI
  - Copilot 스타일 Thinking 섹션 (스피너/체크마크 + 접기/펼치기)
  - 인라인 도구 칩, 컴팩트 네비게이션/결과 카드
  - Claude 스타일 마크다운 답변 (코드 블록, 테이블 등 GFM 지원)
  - 근거 문헌 아코디언, 답변 복사
- `view.scss` (~200줄): 마크다운 렌더링 스타일 (Catppuccin 코드 블록 테마)
- `api.py`: 컬렉션 조회 (기존 floating과 동일)

### 2. 레이아웃 변경: layout.sidebar
- `view.pug`: flex 기반 레이아웃으로 재구성
  - `overflow-auto` 단일 컨테이너 → `flex overflow-hidden` + 내부 스크롤
  - 우측 420px 사이드바 패널 (`*ngIf="service.status.chat"`)
  - 우측 엣지에 토글 버튼 (사이드바 닫혀있을 때, 데스크탑 전용)
  - `wiz-component-chat-floating` 제거
- `view.ts`: `toggleChat()` 메서드 추가, localStorage 기반 상태 유지

### 3. 네비게이션 변경: component.nav.sidebar
- `view.pug`: AI 섹션에 "AI Chat" 토글 버튼 추가 (ON 뱃지 표시)
- `view.ts`: `toggleChatSidebar()` 메서드 추가

### 4. 보존된 기능
- 페이지 이동 (navigate_to_page) + 파라미터 전달
- 인자값 입력 후 결과 표시 (read_page_results)
- SSE 스트리밍 + 타이핑 애니메이션
- 마크다운 렌더링 (코드 블록, 테이블, 인용문)
- 근거 문헌 아코디언
- 답변 복사
- 컬렉션 선택/변경
- 백엔드 에이전트: KeywordAgent → RouterAgent → PatentAgent → CollectorAgent → SynthesizerAgent

## 변경 파일 목록

### 신규 생성
| 파일 | 역할 |
|------|------|
| `src/app/component.chat.sidebar/app.json` | 컴포넌트 메타데이터 |
| `src/app/component.chat.sidebar/api.py` | Milvus 컬렉션 조회 API |
| `src/app/component.chat.sidebar/view.ts` | 사이드바 챗봇 로직 (~700줄) |
| `src/app/component.chat.sidebar/view.pug` | 사이드바 챗봇 UI (~160줄) |
| `src/app/component.chat.sidebar/view.scss` | 마크다운 + 스크롤바 스타일 |

### 수정
| 파일 | 변경 내용 |
|------|----------|
| `src/app/layout.sidebar/view.pug` | flex 기반 재구성, 우측 패널 추가, 플로팅 챗 제거 |
| `src/app/layout.sidebar/view.ts` | toggleChat() + localStorage 초기화 |
| `src/app/component.nav.sidebar/view.pug` | AI Chat 토글 버튼 추가 |
| `src/app/component.nav.sidebar/view.ts` | toggleChatSidebar() 추가 |
