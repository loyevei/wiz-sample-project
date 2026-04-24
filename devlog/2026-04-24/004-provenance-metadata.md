# Provenance 메타데이터 저장 구조

- **ID**: 004
- **날짜**: 2026-04-24
- **유형**: 기능 추가

## 작업 요약
Milvus `structured_content` 필드에 `_provenance` JSON 블록을 추가하여 각 청크의 텍스트 소스(nougat/native/surya), 레이아웃 소스, 추출 모드, rescue 적용 여부를 기록.

## 변경 파일 목록
### api.py (src/app/page.embedding/api.py)
- `upload()` 내 record 생성부: `extract_result["pages"]`에서 페이지별 provenance 맵 구축
- `structured_content`에 `{"_provenance": {...}}` JSON을 append
