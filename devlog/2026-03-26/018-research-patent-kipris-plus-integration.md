# Research 특허 검색 KIPRIS Plus 연동

- **ID**: 018
- **날짜**: 2026-03-26
- **유형**: 기능 추가

## 작업 요약
`/research` 페이지의 특허 검색 탭을 내부 논문 벡터 검색 대신 KIPRIS Plus 외부 API를 호출하는 구조로 전환했다.
프로젝트 설정 파일에서 endpoint/API key/파라미터명을 관리하도록 구성해 KIPRIS 운영 키를 연결하면 서버 재시작 없이 build만으로 실제 특허 검색 결과를 조회할 수 있게 했다.

## 변경 파일 목록
- `config/research.py`
  - KIPRIS Plus endpoint/API key/파라미터/timeout 설정 추가
- `src/app/page.research/api.py`
  - KIPRIS Plus API 호출 helper, XML/JSON 파서, 특허 결과 정규화 로직 추가
  - `search_patents()`를 외부 API 기반으로 교체
- `src/app/page.research/view.ts`
  - 특허 검색 source/error 상태 처리 추가
- `src/app/page.research/view.pug`
  - KIPRIS Plus 안내 문구, 오류 표시, 특허 번호 정보 표시 추가

## 검증
- `python3 -m py_compile /opt/app/project/main/config/research.py /opt/app/project/main/src/app/page.research/api.py`
- `cd /opt/app/project/main && wiz project build --project=main`

## 변경 패턴
- Before
  - 특허 검색 탭이 로컬 Milvus 논문 문헌을 특허 유사 문헌처럼 보여줌
- After
  - 특허 검색 탭이 KIPRIS Plus API를 직접 호출해 실제 특허 메타데이터를 정규화해 반환함