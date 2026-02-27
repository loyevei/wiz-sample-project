# Research 토픽맵 결과 해석 기능 추가

- **ID**: 004
- **날짜**: 2026-02-26
- **유형**: 기능 추가

## 작업 요약
page.research의 토픽맵(Topic Map) 탭에 클러스터 간 관계 분석, 브릿지 문서 탐지, 대표 snippet 추출, 자연어 해석 요약 기능을 추가하여 연구 동향 해석을 자동화했다.

## 변경 파일 목록

### 백엔드 (api.py)
- `src/app/page.research/api.py`: `topic_map()` 함수 확장
  - 섹션 6: 클러스터 간 관계 분석 (코사인 유사도 기반 클러스터 중심 간 거리 계산, 관계 유형 분류)
  - 섹션 7: 브릿지 문서 탐지 (여러 클러스터에 걸친 문서 식별)
  - 섹션 8: 대표 snippet 추출 (클러스터별 대표 문장)
  - 섹션 9: 자연어 해석 요약 생성 (전체 맵 해석 텍스트)
  - 반환 데이터에 `interpretation` dict 추가 (summary, relationships, bridge_docs)

### 프론트엔드 (view.ts / view.pug)
- `src/app/page.research/view.ts`:
  - `topicInterpretation` 상태 변수 추가
  - `loadTopicMap()`에서 interpretation 데이터 저장
  - `renderTopicCanvas()`에 클러스터 간 관계선(relationship lines) 렌더링 추가
- `src/app/page.research/view.pug`:
  - 클러스터 상세 패널에 대표 snippet 표시
  - 해석 패널 추가: 전체 요약 카드, 클러스터 관계 그리드, 브릿지 문서 목록
