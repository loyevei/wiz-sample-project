# Research 토픽맵 연구자 맞춤 확장

- **ID**: 017
- **날짜**: 2026-03-26
- **유형**: 기능 추가

## 작업 요약
`/research`의 토픽맵을 단순 군집 시각화에서 연구자용 탐색/분석 워크벤치로 확장했다.
토픽 클릭 시 해당 문서 집합만 `discover` 탭으로 넘길 수 있게 하고, 토픽별 최신·핵심·브릿지 논문, 연도/조건/장비·가스·소재 분포, 조건은 비슷하지만 목적이 다른 토픽 쌍, 사용자 키워드/열람 이력/프로젝트 컬렉션 기반 개인화 가이드를 함께 제공하도록 정리했다.

## 변경 파일 목록
- `src/app/page.research/api.py`
  - 토픽맵 응답 데이터 확장: 토픽별 문서 카드, 연도/조건/엔터티 분포, objective 태그, contrast pair, personalization 계산 추가
- `src/app/page.research/view.ts`
  - 개인화 키워드/열람 이력 localStorage 관리, topic_map 요청 파라미터 확장, 토픽→discover 전환 동작 추가
- `src/app/page.research/view.pug`
  - 개인화 입력 UI, 토픽별 최신/핵심/브릿지 논문 카드, 분석 패널, 개인화 패널 추가

## 검증
- `python3 -m py_compile /opt/app/project/main/src/app/page.research/api.py`
- `cd /opt/app/project/main && wiz project build --project=main`

## 변경 패턴
- Before
  - 토픽맵은 클러스터/관계/브릿지 문서 중심의 요약 시각화에 머무름
- After
  - 토픽별 탐색 액션, 문서 큐레이션, 분포 분석, 조건 대비 해석, 개인화 추천까지 포함한 연구자용 토픽 워크벤치로 확장