# Diagnosis 페이지 — 컬렉션 선택 연동 및 진단 비교 분석 텍스트 추가

- **ID**: 009
- **날짜**: 2026-02-26
- **유형**: 버그 수정 + 기능 추가

## 작업 요약
Diagnosis 페이지에서 컬렉션 드롭다운 변경 시 데이터가 갱신되지 않는 버그를 수정하고, 진단 비교 탭에서 두 방법의 차이점/공통점을 텍스트로 분석하여 보여주는 기능을 추가했다.

## 변경 파일 목록

### 수정: `src/app/page.diagnosis/view.ts`
- `onCollectionChange()` 메서드 추가: 컬렉션 변경 시 탭별 기존 결과 초기화 + `loadOverview()` 재호출 + 활성 탭 데이터 재로드

### 수정: `src/app/page.diagnosis/view.pug`
- select 요소에 `(ngModelChange)="onCollectionChange()"` 이벤트 바인딩 추가
- 진단 비교 결과 영역에 분석 UI 섹션 추가:
  - 비교 분석 요약 카드 (gradient 배경)
  - 방법 A/B 고유 키워드 태그 (blue/purple)
  - 공통 키워드 태그
  - 차이점/공통점 리스트 카드 (amber/green)

### 수정: `src/app/page.diagnosis/api.py`
- `compare_diagnostics()` 확장: 3개 쿼리 다각도 검색 + 텍스트 기반 비교 분석 생성
- `_build_comparison_analysis()` 신규 함수: TF 기반 키워드 추출, 고유/공통 키워드 분류, 차이점/공통점 텍스트 생성, 평균 유사도 비교

## 테스트 결과
- OES vs Langmuir probe 비교: 각 15건 검색, 6건 공통 문서
- OES 고유 키워드: fig, flexible, schematic, particle, density, emission
- Langmuir probe 고유 키워드: etching, modeling, introduction, gas, systems, anodic
- 공통 키워드: optical, qds, iii, high, signal
