# Embedding 프론트엔드 — 청킹 전략 선택 + 미리보기 + 청크 타입 통계

- **ID**: 003
- **날짜**: 2026-02-27
- **유형**: 기능 추가 + 버그 수정

## 작업 요약
FN-0009/0010(Diagnosis Multimodal)은 이미 완전 구현 확인. FN-0025~0032(Embedding 청킹/OCR/수식/표) 백엔드는 완전 구현되어 있었으나 프론트엔드에 청킹 전략 선택 UI, 미리보기 패널, 청크 타입 통계가 누락되어 있어 구현 완료. api.py의 중복 함수 버그도 수정.

## 변경 파일 목록

### view.ts (전면 재작성)
- `chunkStrategies`, `selectedStrategy`, `similarityThreshold` 변수 추가
- `chunkTypeStats`, `chunkTypeEntries`, `chunkTypeStatsLoading` 변수 추가
- `previewData`, `previewLoading` 변수 추가
- `loadChunkStrategies()` — chunk_strategies API 호출
- `onStrategyChange()` — 전략 변경 시 파라미터 초기화
- `getStrategyParams()`, `getSelectedStrategyInfo()` — 전략별 파라미터 조회
- `loadChunkTypeStats()` — chunk_type_stats API 호출 + 시각화 데이터 변환
- `buildChunkTypeEntries()` — 타입별 색상/라벨/퍼센트 계산
- `previewExtract()` — PDF 미리보기 (임베딩 없이 추출+청킹만)
- `getPreviewChunkTypeDist()` — 미리보기 청크 타입 분포 배열 변환
- `getChunkTypeColor()`, `getChunkTypeLabel()` — UI 헬퍼
- `upload()` — chunk_strategy, similarity_threshold 파라미터 전달 추가
- `onCollectionChange()` — loadChunkTypeStats 호출 추가

### view.pug (3개 영역 수정)
1. **고급 옵션 섹션**: 청킹 전략 드롭다운 + 전략 설명 + 전략별 동적 파라미터
2. **업로드 버튼 영역**: 미리보기 버튼 추가 (검색 아이콘 + 로딩 스피너)
3. **미리보기 결과 패널**: 요약 통계(5칸), 청크 타입 분포, 섹션 구조, 샘플 청크

### api.py (3개 수정)
1. `chunk_type_stats()` 중복 정의 제거
2. `_get_collection_fields()` 헬퍼 함수 추가
3. Milvus query limit 50000→16384 수정
4. Pug `#{{}}` 보간 충돌 수정
