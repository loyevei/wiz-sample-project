# 임베딩 파이프라인 temporal metadata 보존 강화

- **ID**: 008
- **날짜**: 2026-03-26
- **유형**: 기능 추가

## 작업 요약
PDF 임베딩 파이프라인에서 논문 첫머리의 출판 시계열 메타(available online, accepted, received)가 시맨틱 청킹 이후 추천 경로에서 더 자주 활용되도록 보존 로직을 추가했다.
또한 `Received 12 March 2024`처럼 연도 앞에 일/월이 포함된 형식도 인식하도록 Research/Embedding 양쪽의 연도 추출 정규식을 보강했다.

## 변경 파일 목록
- `src/app/page.embedding/api.py`
  - publication timeline 추출 헬퍼 추가 (`_extract_temporal_signals`, `_build_temporal_metadata_prefix`)
  - 초기 텍스트 청크에 메타 문구를 보강하는 `_enrich_chunks_with_temporal_metadata` 추가
  - `_chunk_text()`에서 공통적으로 메타 보강이 적용되도록 연결
  - available online / accepted / received 날짜 패턴을 `12 March 2024` 같은 형식까지 대응하도록 확장
- `src/app/page.research/api.py`
  - 추천 논문 연도 추출 정규식을 날짜 포함 형식까지 대응하도록 확장

## 검증
- `python3 -m py_compile /opt/app/project/main/src/app/page.embedding/api.py /opt/app/project/main/src/app/page.research/api.py`
- synthetic text로 helper 실행 확인
  - `Publication timeline: Available online 2025. Accepted 2025. Received 2024.`
- `wiz project build --project=main`

## 변경 패턴
- Before: `accepted[^\d]{0,40}((?:19|20)\d{2})`
- After: `accepted[\s\S]{0,80}?((?:19|20)\d{2})`
- Before: 검색에 걸린 청크가 본문 중심이면 접수/채택 메타가 누락되기 쉬움
- After: 문서 선두의 publication timeline을 초기 텍스트 청크에 함께 보강해 downstream 추천/요약에서 재사용 가능
