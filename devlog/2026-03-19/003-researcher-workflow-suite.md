# 연구자 워크플로우 확장: 근거 추적·실험 데이터셋·연구 노트 자동화·프로젝트 컬렉션·보고서 생성

- **ID**: 003
- **날짜**: 2026-03-19
- **유형**: 기능 추가

## 작업 요약
연구 탐색 결과를 저장 가능한 근거 추적으로 확장하고, 실험 조건·결과를 구조화하는 전용 데이터셋 페이지를 추가했다.
또한 DOE/레시피 기반 연구 노트 초안 자동화, 협업 프로젝트별 컬렉션 연결, 프로젝트 보고서 및 발표자료 초안 생성을 한 흐름으로 통합했다.
서버 재시작 없이 `build` 산출물을 `bundle/www`에 반영하는 방식으로 배포를 마무리했다.

## 변경 파일 목록
- **Research 근거 추적**
  - `src/app/page.research/api.py`: 근거 trace 저장/조회 API, 근거 청크 메타데이터, 조건 추출 로직 추가
  - `src/app/page.research/view.ts`: trace 로딩/저장 메서드 및 상태 추가
  - `src/app/page.research/view.pug`: 최근 trace 패널, 근거 저장 버튼, 조건 배지, proposal 근거 청크 UI 추가
- **Experiment 데이터 구조화/노트 자동화**
  - `src/app/page.experiment/api.py`: 자동 노트 초안 생성 API 및 노트 메타데이터 확장
  - `src/app/page.experiment/view.ts`: `generateNoteDraft`, `openDatasetPage` 추가
  - `src/app/page.experiment/view.pug`: 데이터셋 이동 버튼, AI 노트 초안 버튼 추가
  - `src/app/page.experiment.dataset/app.json`: 신규 페이지 메타데이터 정의
  - `src/app/page.experiment.dataset/api.py`: 데이터셋 CRUD, 프로젝트/컬렉션 목록 API 추가
  - `src/app/page.experiment.dataset/view.ts`: 검색/필터/폼/저장 로직 구현
  - `src/app/page.experiment.dataset/view.pug`: 데이터셋 목록/필터/폼 UI 구현
  - `src/app/page.experiment.dataset/view.scss`: 페이지 스타일 파일 생성
- **Collaboration 프로젝트 컬렉션/보고서**
  - `src/app/page.collaboration/api.py`: 프로젝트 컬렉션/목표/태그 저장, 컬렉션 조회, 보고서 생성/목록 API 추가
  - `src/app/page.collaboration/view.ts`: 컬렉션/보고서 상태, 보고서 생성 및 미리보기 제어 추가
  - `src/app/page.collaboration/view.pug`: 컬렉션 배지, 보고서 생성 버튼, 보고서 미리보기 모달 추가
- **Navigation / Build 반영**
  - `src/app/component.nav.sidebar/view.pug`: `실험 데이터셋` 메뉴 추가
  - `build/src/app/page.research/page.research.component.ts`: build-side wrapper 반영
  - `build/src/app/page.experiment.dataset/*`: 신규 페이지 build 입력 파일 반영
  - `bundle/www/main.js`: 무중단 배포용 번들 갱신

## 변경 패턴
- **Before**: 추천/가설/제안서 결과가 일회성 UI 출력에 머물러 후속 실험·협업 흐름으로 이어지지 않음
- **After**: 근거 저장 → 데이터셋 구조화 → 노트 자동화 → 프로젝트 컬렉션 연결 → 보고서 초안 생성으로 이어지는 연구자 중심 플로우를 구성
