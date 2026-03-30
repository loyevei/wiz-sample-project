# PDF 원본 보존 및 검색 결과 원문 페이지 연결 복구

- **ID**: 013
- **날짜**: 2026-03-26
- **유형**: 버그 수정

## 작업 요약
PDF 원본 보존 및 원문 페이지 연결 기능은 소스 수준에서는 구현돼 있었지만, 실제 런타임에서는 두 문제가 겹쳐 end-to-end 동작이 깨져 있었다.
첫째, `page.embedding/api.py`의 원본 저장 단계에서 `DATA_DIR` 상수가 누락되어 업로드 응답은 성공하더라도 PDF 파일이 디스크에 남지 않았다. 둘째, 서버 재시작 없이 기존 캐시된 `page.embedding`/`page.research` API를 계속 타면서 최신 추천/서빙 로직이 반영되지 않았다.
이를 해결하기 위해 원본 저장 버그를 수정하고, 최신 소스를 매 요청 hot-load하는 `page.embedding.v2`, `page.research.v2` 프록시 앱을 추가한 뒤 실제 프런트 호출 경로를 v2로 전환했다.

## 변경 파일 목록
- `src/app/page.embedding/api.py`
  - 원본 PDF 저장 경로 계산에 필요한 `DATA_DIR = "/opt/app/data"` 상수를 추가
- `src/app/page.embedding.v2/app.json`
- `src/app/page.embedding.v2/api.py`
- `src/app/page.embedding.v2/view.ts`
- `src/app/page.embedding.v2/view.pug`
- `src/app/page.embedding.v2/view.html`
- `src/app/page.embedding.v2/view.scss`
  - 최신 `page.embedding/api.py`를 hot-load해 `upload()`를 실행하는 무중단 프록시 앱 추가
- `src/app/page.research.v2/app.json`
- `src/app/page.research.v2/api.py`
- `src/app/page.research.v2/view.ts`
- `src/app/page.research.v2/view.pug`
- `src/app/page.research.v2/view.html`
- `src/app/page.research.v2/view.scss`
  - 최신 `page.research/api.py`를 hot-load해 `recommend_papers()`와 `serve_pdf()`를 실행하는 무중단 프록시 앱 추가
- `src/app/page.embedding/view.ts`
  - 업로드 호출을 `/wiz/api/page.embedding.v2/upload`로 전환
- `src/app/page.research/view.ts`
  - 논문 추천 호출을 `/wiz/api/page.research.v2/recommend_papers`로 전환
  - PDF 열기 URL을 `/wiz/api/page.research.v2/serve_pdf?doc_id=...&collection=...#page=N`으로 전환

## 검증
- `cd /opt/app/project/main && wiz project build --project=main`
- 샘플 PDF 업로드 검증
  - `POST /wiz/api/page.embedding.v2/upload`
  - 결과: `doc_id=2b8bcff9`, 저장 경로 `/opt/app/data/pdfs/fn0003_pdf_validation_v2/2b8bcff9.pdf`, 파일 존재 및 크기 확인
- 논문 추천 검증
  - `POST /wiz/api/page.research.v2/recommend_papers`
  - 결과: 응답 항목에 `doc_id=2b8bcff9`, `page_num=1` 포함 확인
- 원문 PDF 서빙 검증
  - `GET /wiz/api/page.research.v2/serve_pdf?doc_id=2b8bcff9&collection=fn0003_pdf_validation_v2`
  - 결과: `Content-Type: application/pdf`, magic bytes `%PDF-` 확인