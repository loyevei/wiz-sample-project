# 임베딩 chunk_type_stats 배치 페이지네이션 적용

- **ID**: 004
- **날짜**: 2026-02-27
- **유형**: 기능 추가

## 작업 요약
`chunk_type_stats()` API에 BATCH_SIZE=16000 기반 배치 페이지네이션을 적용하여 Milvus Lite의 query limit(16384) 제한을 초과하는 대용량 컬렉션에서도 정확한 청크 타입 통계를 반환하도록 개선.

## 변경 파일 목록

### api.py (src/app/page.embedding/api.py)
- `chunk_type_stats()` 함수: 기존 단일 `limit=16384` 쿼리 → `while` 루프 + `offset` 기반 배치 페이지네이션
- `BATCH_SIZE = 16000`: Milvus Lite limit 16384 이내로 설정
- 배치가 BATCH_SIZE 미만이면 마지막 배치로 판단하여 루프 종료

### 변경 패턴
```python
# Before: 단일 쿼리 (16384 초과 시 불완전)
results = client.query(..., limit=16384)
for r in results:
    type_counts[ct] = type_counts.get(ct, 0) + 1

# After: 배치 페이지네이션
BATCH_SIZE = 16000
offset = 0
while True:
    results = client.query(..., limit=BATCH_SIZE, offset=offset)
    for r in results:
        type_counts[ct] = type_counts.get(ct, 0) + 1
    if len(results) < BATCH_SIZE:
        break
    offset += len(results)
```

### 테스트 결과
- test_papers (schema 방식): 883 text + 129 figure + 83 formula + 8 table = 1103 총 청크 ✅
- plasma_papers (content_analysis 방식): 273 text ✅
