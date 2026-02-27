# 플라즈마 이론 연구 지원 페이지 전체 구현

- **ID**: 005
- **날짜**: 2026-02-26
- **유형**: 기능 추가

## 작업 요약
새로운 `/theory` 페이지를 생성하여 3개 탭(수식 검색, 가정 검증, 이론 그래프) 기능을 전체 구현했다. 플라즈마 도메인 수식 사전(12개), 가정 사전(15개), 개념 사전(40+개)을 기반으로 문서 분석 기능을 제공한다.

## 변경 파일 목록

### 신규 생성
- `src/app/page.theory/app.json`: 페이지 설정 (viewuri: /theory, layout: layout.sidebar)
- `src/app/page.theory/api.py` (~600줄): 전체 백엔드 API
  - Equation-aware Retrieval: `extract_equations()`, `search_equations()`, `equation_stats()`
  - Assumption Consistency Checker: `extract_assumptions()`, `check_consistency()`, `assumption_stats()`
  - Theory Knowledge Graph: `build_theory_graph()`, `get_theory_graph()`, `trace_impact()`, `search_graph()`
  - 플라즈마 도메인 사전: PLASMA_EQUATIONS(12개), ASSUMPTION_DICT(15개), PLASMA_CONCEPTS(40+개)
- `src/app/page.theory/view.ts` (~350줄): 3탭 프론트엔드 로직
  - 컬렉션 관리, 탭 전환, 자동 로드
  - 수식 탭: 추출/검색/필터링/통계
  - 가정 탭: 추출/문서 선택/상충 검사
  - 그래프 탭: Canvas 렌더링, 노드 클릭/검색/영향 추적
- `src/app/page.theory/view.pug` (~290줄): 전체 UI (class="" 속성 방식)
  - 수식 탭: 통계 카드, 분류 분포, 검색, 결과, 카테고리 필터
  - 가정 탭: 통계, 빈도 차트, 문서별 가정, 상충 경고, 호환성 매트릭스
  - 그래프 탭: Canvas 그래프, 범례, 검색 패널, 노드 상세, 영향 추적
- `src/app/page.theory/view.scss`: 컨테이너 스타일

### 수정
- `src/app/component.nav.sidebar/view.pug`: 사이드바에 "이론 연구" 메뉴 항목 추가 (/theory)

### Pug 구문 주의사항
- Tailwind 임의값 클래스(`text-[13px]`, `max-w-[200px]`)와 소수점 클래스(`py-0.5`, `mt-1.5`)는 Pug 도트 표기법에서 파싱 오류 발생
- 모든 클래스를 `class=""` 속성 방식으로 통일하여 해결
