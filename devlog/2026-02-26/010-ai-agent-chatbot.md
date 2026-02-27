# AI Agent 챗봇 구현 — 플라즈마 연구 특화 대화형 에이전트

- **ID**: 010
- **날짜**: 2026-02-26
- **유형**: 기능 추가

## 작업 요약
09-ai-agent.md 설계 문서를 기반으로 Tool-Use 기반 AI Agent 챗봇을 구현했다.
Anthropic Claude API + SSE 스트리밍 + Tool Auto-Discovery 아키텍처로 플라즈마 연구 전문 어시스턴트를 구축했다.

## 변경 파일 목록

### Config 추가
- `config/season.py` (신규) — Anthropic API 키 및 모델 설정

### Agent Struct (핵심 엔진)
- `src/model/struct/agent.py` (신규) — Agent Run Loop, Tool Auto-Discovery, System Prompt, SDK 직렬화
- `src/model/struct.py` (수정) — Agent 클래스 로드 및 `agent()` 팩토리 메서드 추가

### Tool 시스템
- `src/model/struct/agent/tools/base_tool.py` (신규) — BaseTool 추상 클래스
- `src/model/struct/agent/tools/search_papers.py` (신규) — Milvus 벡터 검색 도구
- `src/model/struct/agent/tools/get_collections.py` (신규) — 컬렉션 목록 조회 도구
- `src/model/struct/agent/tools/search_equations.py` (신규) — 수식 검색 도구
- `src/model/struct/agent/tools/analyze_keywords.py` (신규) — 키워드 분석 도구

### Page UI
- `src/app/page.agent/app.json` (신규) — viewuri=/agent, layout=layout.sidebar
- `src/app/page.agent/api.py` (신규) — SSE 스트리밍 agent_chat, agent_tools API
- `src/app/page.agent/view.ts` (신규) — 채팅 UI 로직 (SSE, Turn 관리, Markdown 렌더링)
- `src/app/page.agent/view.pug` (신규) — 채팅 UI (메시지, Tool 카드, 입력창)
- `src/app/page.agent/view.scss` (신규) — 채팅 스타일

### 사이드바
- `src/app/component.nav.sidebar/view.pug` (수정) — AI 어시스턴트 메뉴 항목 추가

### 패키지 설치
- anthropic 0.84.0 pip 설치
