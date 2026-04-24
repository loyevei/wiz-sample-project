# Nougat OCR 래퍼 및 추출 모드 추가

- **ID**: 001
- **날짜**: 2026-04-24
- **유형**: 기능 추가

## 작업 요약

`src/model/nougat_ocr.py`를 추가해 Hugging Face Nougat 모델을 WIZ model 형태로 감쌌고, `page.embedding/api.py` 업로드 경로에 `use_nougat`, `gemma_rescue`, `extraction_mode` 옵션을 연결했다. 기존 PyMuPDF 기반 레이아웃/bbox 축은 유지하면서 Nougat를 페이지별 선호 텍스트 소스로만 얹는 방식으로, 서버 재시작 없이 normal build와 devmode 캐시 우회 검증까지 완료했다.

## 변경 파일 목록

### 백엔드
- `src/model/nougat_ocr.py`
  - `facebook/nougat-small` 기반 싱글톤 래퍼 추가
  - `available()`, `status()`, `load()`, `unload()`, `extract_document()` 제공
  - Transformers `NougatProcessor` + `VisionEncoderDecoderModel` 기반 문서 단위 추출 구현
- `src/app/page.embedding/api.py`
  - `native` / `surya` / `nougat_hybrid` 추출 모드 해석 헬퍼 추가
  - `_extract_text_from_pdf()`에 `use_nougat`, `gemma_rescue`, `extraction_mode` 인자 추가
  - Nougat 페이지 텍스트를 페이지별 선호 텍스트로 병합하되, bbox/레이아웃은 PyMuPDF 결과 유지
  - `nougat_status()` API 추가
  - 업로드 응답에 `nougat_available`, `nougat_pages_used`, `native_pages_used`, `failed_pages`, `extraction_mode` 등 통계 포함

## 검증

- `wiz project build --project=main` 성공 (서버 재실행 없음)
- `GET /wiz/api/page.embedding/nougat_status` + `season-wiz-devmode=true` 쿠키로 200 확인
- 응답 요약: `available=true`, `model=facebook/nougat-small`, `runtime=transformers`, `loaded=false`
- VS Code 오류 진단: `src/model/nougat_ocr.py`, `src/app/page.embedding/api.py` 모두 오류 없음

## 메모

- 현재 환경은 Nougat Python 의존성(`transformers`의 Nougat classes, `torch`, `PIL`)이 이미 있어 별도 패키지 설치는 하지 않았다.
- 실제 모델 가중치 다운로드/로드는 첫 추출 실행 시점에 발생한다.