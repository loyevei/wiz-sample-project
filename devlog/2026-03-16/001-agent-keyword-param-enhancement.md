# AI Agent 키워드 분류 → 페이지 파라미터 자동 실행 기능 강화

- **ID**: 001
- **날짜**: 2026-03-16
- **유형**: 기능 추가

## 작업 요약
AI Agent가 사용자 입력 키워드를 분석하여 8개 카테고리로 분류한 뒤, 키워드를 파라미터로 해당 페이지에 전달하여 자동 실행하도록 기능을 강화했다. navigate_to_page 도구의 탭 ID를 실제 페이지와 동기화하고, 4개 신규 페이지(calculator, experiment, analysis, collaboration)에 ActivatedRoute + 쿼리 파라미터 수신 + 자동 실행 로직을 추가했다.

## 변경 파일 목록

### navigate_to_page 도구 동기화
- `src/model/struct/agent/tools/navigate_to_page.py` — 탭 ID 수정 (calculator: debye→plasma, experiment: list→doe, collaboration: messages→discussions 등), params description에 정확한 키 이름 반영

### Agent 시스템 프롬프트 갱신
- `src/model/struct/agent.py` — 8대 기능 영역의 정확한 탭 ID, params 키-값 매핑 예시 추가 (Te, ne, gas, pressure, process_type, chart_type, fitting_model 등)

### Calculator 페이지 쿼리 파라미터 연동
- `src/app/page.calculator/view.ts` — ActivatedRoute import, handleQueryParams() 추가. tab/Te/ne/gas/pressure/B 파라미터 수신 → 자동 calculatePlasma/calculatePaschen 실행

### Experiment 페이지 쿼리 파라미터 연동
- `src/app/page.experiment/view.ts` — ActivatedRoute import, handleQueryParams() 추가. tab/q/gas/pressure/power/temperature/time 파라미터 수신 → 탭 전환 + 검색어/레시피 파라미터 설정

### Analysis 페이지 쿼리 파라미터 연동
- `src/app/page.analysis/view.ts` — ActivatedRoute import, handleQueryParams() 추가. tab/chart_type/csv_data/fitting_model/q 파라미터 수신 → 자동 parsePlotData/calculateStatistics/performFitting 실행

### Collaboration 페이지 쿼리 파라미터 연동
- `src/app/page.collaboration/view.ts` — ActivatedRoute import, handleQueryParams() 추가. tab/q 파라미터 수신 → 탭 전환 + 검색어 설정
