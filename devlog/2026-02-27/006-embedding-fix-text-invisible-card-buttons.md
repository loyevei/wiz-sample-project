# Embedding 페이지 글자 안 보이는 오류 수정 + 청킹 전략 카드형 UI 개선

- **ID**: 006
- **날짜**: 2026-02-27
- **유형**: 버그 수정 + UI 개선

## 작업 요약
1. Embedding 페이지 view.ts에서 청킹 전략, 미리보기, 청크 타입 통계 관련 변수·메서드가 전부 누락되어 컴포넌트 초기화 시 런타임 에러 발생 → 페이지 렌더링 실패(글자 안 보임) 문제 수정 (FN-0007)
2. 청킹 전략 선택 버튼을 단순 pill 버튼에서 카드형(아이콘+라벨+설명+체크마크) 디자인으로 개선 (FN-0008)

## 변경 파일 목록

### FN-0007: view.ts 누락 코드 복원

**src/app/page.embedding/view.ts**
- 누락된 변수 추가: `chunkStrategies`, `selectedStrategy`, `similarityThreshold`, `previewData`, `previewLoading`, `chunkTypeStats`, `chunkTypeEntries`, `chunkTypeStatsLoading`
- `ngOnInit`에 `loadChunkStrategies()` 호출 추가
- `onCollectionChange`에 `loadChunkTypeStats()` 호출 추가
- `upload()` FormData에 `chunk_strategy`, `similarity_threshold` 파라미터 추가
- 누락된 메서드 전부 복원: `loadChunkStrategies`, `onStrategyChange`, `getStrategyParams`, `getSelectedStrategyInfo`, `getStrategyIcon`, `previewExtract`, `getPreviewChunkTypeDist`, `loadChunkTypeStats`, `buildChunkTypeEntries`, `getChunkTypeColor`, `getChunkTypeLabel`

### FN-0008: 청킹 전략 카드형 버튼

**src/app/page.embedding/view.pug**
- 단순 pill 버튼(`flex flex-wrap gap-2`) → 카드형 그리드(`grid grid-cols-2 lg:grid-cols-3`)
- 각 카드: 전략 아이콘(이모지) + 라벨 + 짧은 설명(2줄 clamp)
- 선택 상태: `bg-indigo-50 border-indigo-500 shadow-sm` + 체크마크 SVG
- 비선택 상태: `bg-white border-gray-200` + hover 시 `border-indigo-300 shadow-sm`
- 파라미터 라벨 색상 `text-gray-600` → `text-gray-700`으로 강화
