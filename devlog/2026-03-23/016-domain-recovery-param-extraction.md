# 도메인별 recovery query/params 추출 고도화

- **ID**: 016
- **날짜**: 2026-03-23
- **유형**: 기능 추가

## 작업 요약
군집형 에이전트의 recovery strategy가 다음 iteration에 사용할 query/params를 도메인별로 더 정교하게 뽑도록 확장했다.
계산기, 공정 예측, 진단 분석, 데이터 분석, 실험 관리, 이론 연구 각각에서 숫자 단위와 핵심 조건을 구조화해 플로팅 챗봇의 `다음 시도 입력` 정확도를 높였다.

## 변경 파일 목록
- `src/model/struct/agent.py`
  - recovery 입력 추출용 helper를 확장해 gas, pressure, power, temperature, time, B field, frequency, diagnostic methods, chart type, fitting model 등을 인식하도록 구현
  - prediction/calculator/diagnosis/analysis/experiment/theory 도메인별 params 매핑을 세분화
  - theory 키워드(Boltzmann, Drude, Paschen)와 target_property, substrate 같은 예측용 파라미터도 추가 추출
