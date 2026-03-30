# Research 페이지 PDF 원문 연결 기능

- **ID**: 002
- **날짜**: 2026-03-25
- **유형**: 기능 추가

## 작업 요약
/research 페이지의 모든 탭(주제 탐색, Research Gap, 가설 생성, 논문 추천, 제안서 생성, 특허 검색)에서 문서 파일명을 클릭하면 PDF 원본 파일을 브라우저 내장 뷰어로 열도록 구현. `#page=N` 프래그먼트를 사용하여 근거 텍스트가 위치한 해당 페이지로 바로 이동.

## 변경 파일 목록

### 백엔드 — PDF 저장 및 서빙

**page.embedding/api.py**
- 임베딩 업로드 시 PDF 원본을 `/opt/app/data/pdfs/{collection}/{doc_id}.pdf`에 영구 저장
- `shutil.copy2(tmp_path, pdf_dest)` — 임시파일 삭제 전 영구 사본 생성

**page.research/api.py**
- `PDF_DIR` 상수 추가
- `serve_pdf()` 함수 추가 — `doc_id`+`collection`으로 PDF 파일 조회 후 `flask.send_file`로 서빙
- `_build_evidence_item()`에 `page_num` 필드 추가
- **14개 `output_fields` 일괄 업데이트** — 모든 Milvus 검색 쿼리에 `"page_num"` 추가
  - discover: overview, keyword search
  - run_recommend_data: direct_results, cross_results, gap_results, gap_search, exp_results
  - find_related: search_results
  - keyword_density: results
  - hypothesis: main results, hyp_results
  - recommend_papers: results
  - proposal: references results
  - search_patents: results
  - gap analysis: combo_results
- `recommend_papers` inline dict에 `doc_id`, `page_num` 필드 추가
- `search_patents` inline dict에 `doc_id`, `page_num` 필드 추가

### 프론트엔드 — PDF 클릭 열기

**page.research/view.ts**
- `openPdf(docId, pageNum)` 메서드 추가 — 새 탭에서 PDF 열기, `#page=N` 지원

**page.research/view.pug** (6개 탭에 클릭 핸들러 추가)
- Discover: 파일명 배지 클릭, 청크 카드 클릭 (해당 페이지), 추천 근거 배지, 관련 문서 행
- Gap: 관련 문서 카드 클릭
- Hypothesis: 근거 문헌 배지 클릭
- Recommend: 파일명 링크 스타일(파란색 + 밑줄 hover)
- Proposal: 근거 청크 배지 클릭
- Patent: 파일명 링크 스타일
