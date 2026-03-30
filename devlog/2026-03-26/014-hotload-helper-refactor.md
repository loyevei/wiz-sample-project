# 공통 hot-load helper로 무중단 프록시 로더 정리

- **ID**: 014
- **날짜**: 2026-03-26
- **유형**: 리팩토링

## 작업 요약
최근 추가된 `page.agent`, `page.agent.v2`, `page.embedding.v2`, `page.research.v2`는 모두 bundle/build/src 우선순위로 최신 Python 소스를 다시 읽고 `exec`하는 동일한 hot-load 패턴을 각 파일에 중복으로 가지고 있었다.
이번 작업에서는 이 중복 로직을 `src/model/hotload.py`로 추출해 공통 helper로 통합하고, 각 API는 어떤 파일과 symbol을 읽을지만 지정하도록 단순화했다. 이를 통해 향후 무중단 프록시 앱을 추가할 때 중복 복사 없이 같은 로더를 재사용할 수 있게 정리했다.

## 변경 파일 목록
- `src/model/hotload.py`
  - bundle/build/src 우선순위 경로 해석
  - `exec` 기반 module scope 로드 helper 추가
  - symbol 추출용 `load_symbol()` 추가
- `src/app/page.agent/api.py`
  - `Agent` hot-load 중복 코드를 제거하고 공통 helper 사용으로 정리
- `src/app/page.agent.v2/api.py`
  - `Agent` hot-load 중복 코드를 제거하고 공통 helper 사용으로 정리
- `src/app/page.embedding.v2/api.py`
  - `page.embedding/api.py` scope 로드 로직을 공통 helper로 대체
- `src/app/page.research.v2/api.py`
  - `page.research/api.py` scope 로드 로직을 공통 helper로 대체

## 검증
- `python3 -m py_compile /opt/app/project/main/src/model/hotload.py /opt/app/project/main/src/app/page.agent/api.py /opt/app/project/main/src/app/page.agent.v2/api.py /opt/app/project/main/src/app/page.embedding.v2/api.py /opt/app/project/main/src/app/page.research.v2/api.py`
- `cd /opt/app/project/main && wiz project build --project=main`

## 변경 패턴
- Before
  - 각 API가 개별적으로 project root 계산, 후보 경로 구성, 파일 읽기, `exec`, symbol 추출을 반복 구현
- After
  - 공통 helper가 hot-load 책임을 전담하고, 각 API는 대상 경로와 symbol만 지정