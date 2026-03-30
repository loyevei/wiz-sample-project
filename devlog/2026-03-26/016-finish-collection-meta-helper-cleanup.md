# collection_meta helper 리팩토링 잔여 구간 마무리

- **ID**: 016
- **날짜**: 2026-03-26
- **유형**: 리팩토링

## 작업 요약
이전 `collection_meta` 공통화 작업 이후에도 `page.collaboration`과 `page.experiment.dataset` API는 여전히 개별 JSON 로딩 로직으로 컬렉션 메타를 읽고 있었다.
이번 작업에서는 두 API를 `src/model/collectionmeta.py` helper로 전환해 문자열 기반 메타 엔트리도 동일하게 정규화되도록 맞추고, 최근 클린업 흐름을 일관되게 마무리했다.

## 변경 파일 목록
- `src/app/page.collaboration/api.py`
  - `list_collections()`가 공통 `collectionmeta` helper를 사용하도록 전환
- `src/app/page.experiment.dataset/api.py`
  - `list_collections()`가 공통 `collectionmeta` helper를 사용하도록 전환
- `devlog.md`
  - 작업 요약 행 추가

## 검증
- `python3 -m py_compile /opt/app/project/main/src/model/collectionmeta.py /opt/app/project/main/src/app/page.collaboration/api.py /opt/app/project/main/src/app/page.experiment.dataset/api.py`
- `cd /opt/app/project/main && wiz project build --project=main`

## 변경 패턴
- Before
  - 일부 페이지 API가 `collection_meta.json`을 직접 읽고 dict라고 가정해 `info.get(...)`을 호출함
- After
  - 모든 대상 API가 `collectionmeta` helper를 통해 문자열/객체 메타를 동일하게 정규화해 사용함