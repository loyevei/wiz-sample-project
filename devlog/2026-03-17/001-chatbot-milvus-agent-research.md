# 플로팅 챗봇 에이전트 구조 강화 + Milvus DB 선택 + Research 기능 구현

- **ID**: 001
- **날짜**: 2026-03-17
- **유형**: 기능 추가

## 작업 요약
플로팅 AI 챗봇에 Milvus 컬렉션 선택 화면을 추가하고, 선택된 컬렉션을 에이전트 Tool Context로 전달하여 모든 도구가 올바른 DB를 사용하도록 구조를 강화했다. Research 페이지의 논문 추천/제안서 생성/특허 검색 3개 탭의 queryParams 자동 실행을 연동하여 에이전트 네비게이션으로 실질적인 기능 수행이 가능해졌다.

## 변경 파일 목록

### 플로팅 챗봇 UI (컬렉션 선택)
- `src/app/component.chat.floating/view.ts` — collections/selectedCollection 상태 추가, loadCollections/selectCollection/changeCollection 메서드, sendChat에 collection 파라미터
- `src/app/component.chat.floating/view.pug` — 컬렉션 선택 카드 화면, 헤더 컬렉션 뱃지, collectionSelected 조건부 렌더링
- `src/app/component.chat.floating/api.py` — 신규 생성 (Milvus 컬렉션 목록 API)

### 에이전트 구조 (collection 전달)
- `src/model/struct.py` — agent(collection="") 파라미터 추가
- `src/model/struct/agent.py` — collection을 tool context에 포함, system prompt에 컬렉션 정보 자동 삽입
- `src/app/page.agent/api.py` — collection 파라미터 추출 및 agent에 전달

### 도구 16개 (컬렉션 기본값)
- `src/model/struct/agent/tools/*.py` — `self.ctx.get("collection", "") or "plasma_papers"` 패턴으로 통일
- `src/model/struct/agent/tools/navigate_to_page.py` — research 탭에 recommend/proposal/patent 추가, ctx collection URL 전달

### Research 페이지
- `src/app/page.research/view.ts` — handleQueryParams에 recommend/proposal/patent 자동 실행 추가
