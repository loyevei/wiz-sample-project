# E2E 검증 및 버그 수정

- **ID**: 006
- **날짜**: 2026-04-24
- **유형**: 버그 수정

## 작업 요약
API 레벨 E2E 테스트 수행. `pages_data` 미정의 버그(`upload()` 내 provenance 맵에서 `extract_result["pages"]` 대신 `pages_data` 참조) 발견·수정. Native/Nougat Hybrid 두 모드 모두 200 성공 확인.

## 변경 파일 목록
### api.py (src/app/page.embedding/api.py)
- `upload()` 내 provenance 맵: `pages_data` → `extract_result["pages"]`로 수정
