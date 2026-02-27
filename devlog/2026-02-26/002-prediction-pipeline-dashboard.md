# Prediction 페이지 — 공정 예측 모델링 파이프라인 구축

- **ID**: 002
- **날짜**: 2026-02-26
- **유형**: 기능 추가

## 작업 요약
page.prediction에 4개 핵심 기능(Parameter Extraction Pipeline, Inverse Condition Finder, Uncertainty Estimator, Hybrid Modeling)을 구현하고, 5탭 대시보드 UI로 통합.

## 변경 파일 목록

### 백엔드 (api.py)
- `page.prediction/api.py`: 전면 재작성
  - **PARAM_PATTERNS**: 12종 공정 파라미터 regex 패턴 (pressure, rf_power, gas_flow, temperature, frequency, bias_voltage, electrode_gap, etch_rate, deposition_rate, uniformity, selectivity + gas_species)
  - **UNIT_CONVERSIONS**: 14종 단위 변환 (Torr→mTorr, kW→W, slm→sccm, K→°C, Å/min→nm/min 등)
  - **_extract_parameters_from_text()**: 텍스트에서 파라미터 자동 추출 + 단위 정규화 + 중복 제거
  - **_calc_condition_similarity()**: 입력 조건과 문서 조건 간 유사도 (상대 차이 기반 0~1)
  - **_build_feature_matrix()**: 파라미터 DB → sklearn 회귀용 특징 행렬 (NaN imputation 포함)
  - **extract_params()**: 전체 청크 조회 → regex 추출 → 문서별 그룹핑 → JSON 캐시 저장
  - **param_database()**: 캐시된 파라미터 DB 필터/정렬 조회
  - **inverse_search()**: 목표 결과 텍스트 → 벡터 검색 → 조건 범위 가중 통계 + 신뢰도
  - **estimate_uncertainty()**: 조건 유사도 기반 문서 그룹핑 → 결과 분산/CI/신뢰도
  - **surrogate_predict()**: Ridge regression + LOO-CV → 수치 예측 + RMSE/R² + feature importance

### 프론트엔드 (view.ts)
- 5탭 관리 (predict, paramdb, inverse, uncertainty, analysis)
- 각 탭별 상태/메서드 분리
- Surrogate 예측 서브섹션 (조건 예측 탭 내)
- objectKeys() 헬퍼, confidenceColor/Label/reliabilityColor 등 UI 헬퍼

### 프론트엔드 (view.pug)
- 상단: 3열 통계 카드 (학습 데이터, 예측 방식, 파라미터 DB 상태)
- 탭 네비게이션 바 (SVG 아이콘 포함)
- Tab 1: 공정 조건 입력 + 유사도 검색 결과 + Surrogate Model 예측 패널
- Tab 2: 파라미터 추출/재추출 + 조건/결과 통계 테이블 + 가스 분포 + 문서별 상세 (확장형)
- Tab 3: 제안 쿼리 태그 + 역설계 입력 + 조건 범위 카드 + 가스 추천 + 근거 문서
- Tab 4: 6종 조건 입력 + 결과별 불확실성 카드 (가중 평균/CI/std/신뢰도) + 유사 문서 목록
- Tab 5: 파라미터 심층 분석 (기존 기능 유지)
