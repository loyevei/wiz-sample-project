# 업로드 UI에 추출 파이프라인 설정 노출

- **ID**: 005
- **날짜**: 2026-04-24
- **유형**: 기능 추가

## 작업 요약
page.embedding 업로드 화면에 텍스트 추출 모드 선택(Native/Surya/Nougat Hybrid), Nougat 가용 상태 표시, Gemma rescue 토글을 추가. 업로드 결과 로그에 Nougat/Gemma 통계 표시.

## 변경 파일 목록
### view.ts (src/app/page.embedding/view.ts)
- `extractionMode`, `nougatAvailable`, `gemmaRescue` 상태 변수 추가
- `checkNougatStatus()` 메서드 추가
- FormData에 `extraction_mode`, `use_nougat`, `gemma_rescue` 전송
- 업로드 성공 로그에 Nougat/Gemma rescue 통계 포함

### view.pug (src/app/page.embedding/view.pug)
- 추출 모드 3버튼(Native/Surya/Nougat Hybrid) UI 추가
- Nougat 미사용 시 경고 메시지
- Gemma rescue ON/OFF 토글 (Nougat Hybrid + Vision 사용 가능 시만 표시)
