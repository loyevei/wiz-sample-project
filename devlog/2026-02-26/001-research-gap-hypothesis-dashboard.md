# Research Gap Detector + 가설 생성 + 대시보드 탭 통합

- **ID**: 001
- **날짜**: 2026-02-26
- **유형**: 기능 추가

## 작업 요약
연구 페이지(page.research)에 Research Gap Detector, 가설 자동 생성기를 추가하고, 전체 UI를 5개 탭 기반 대시보드로 재구성했다.

## 변경 파일 목록

### Backend (api.py)
- `src/app/page.research/api.py`
  - `gap_detector()`: 키워드별 KNN 밀도 분석 + 교차 키워드 조합 밀도 비교 + 연구 공백 탐지
  - `generate_hypothesis()`: 연구 조건 → 관련 논문 검색 → novel terms 추출 → 5가지 템플릿 기반 가설 생성

### Frontend State (view.ts)
- `src/app/page.research/view.ts`
  - 5개 탭 관리 (discover, topicmap, gap, hypothesis, keywords)
  - Gap Detector / Hypothesis Generator 상태 및 메서드 추가
  - `onCollectionChange()` 확장: 모든 탭 데이터 초기화

### Frontend UI (view.pug)
- `src/app/page.research/view.pug` — 5개 탭 기반 대시보드로 전면 재구성
  - 주제 탐색 / 토픽 맵 / Research Gap / 가설 생성 / 키워드 분석
