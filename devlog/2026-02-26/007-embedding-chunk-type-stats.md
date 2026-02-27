# Embedding 페이지 청크 타입 분류 통계 기능 추가

- **ID**: 007
- **날짜**: 2026-02-26
- **유형**: 기능 추가

## 작업 요약
Embedding 페이지에 각 컬렉션의 청크 타입별 분류 통계(text, table, figure, formula) 표시 기능을 추가했다. 구 스키마(chunk_type 필드 없음) 컬렉션은 텍스트 마커 기반 content_analysis 방식으로, 신 스키마는 chunk_type 필드를 직접 조회하여 통계를 산출한다.

## 변경 파일 목록

### Backend (api.py)
- `src/app/page.embedding/api.py`: `chunk_type_stats()` 함수 추가
  - `_get_collection_fields()`로 스키마 확인 → `chunk_type` 필드 유무에 따라 분기
  - 구 스키마: text 내용에서 `[FIGURE:]`, `[EQUATION:]`, `[TABLE:]` 마커로 분류 (`_detect_chunk_type()` 활용)
  - 신 스키마: `chunk_type` 필드 직접 조회
  - Milvus Lite limit 16384 제한 대응을 위한 배치 페이지네이션 (BATCH_SIZE=16000)

### Frontend (view.ts)
- `src/app/page.embedding/view.ts`: 청크 타입 통계 관련 상태/메서드 추가
  - 상태: `chunkTypeStats`, `chunkTypeStatsLoading`, `chunkTypeEntries`
  - 메서드: `loadChunkTypeStats()`, `_computeChunkTypeEntries()`, `getChunkTypeBarColor()`
  - 타입 순서: text → figure → formula → table → mixed
  - `ngOnInit()`, `onCollectionChange()`, 업로드 완료 시 자동 로드

### Frontend (view.pug)
- `src/app/page.embedding/view.pug`: 통계 패널에 청크 타입 분포 UI 추가
  - 색상별 분포 바 (stacked progress bar)
  - 타입별 상세 카드 (아이콘 + 라벨 + 개수 + 퍼센트)
  - 로딩 스피너
