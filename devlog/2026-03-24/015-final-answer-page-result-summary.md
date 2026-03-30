# 최종 답변 페이지 결과 요약 포함

- **ID**: 015
- **날짜**: 2026-03-24
- **유형**: 기능 추가

## 작업 요약
플로팅 챗봇의 최종 답변에 질문과 직접 연결된 페이지 결과 요약이 항상 함께 보이도록 보강했다.
백엔드 최종답변 조합부에는 `페이지 결과 요약:` bullet을 강제하는 규칙을 추가했고, 서버 재시작 전에도 사용자 화면에서 같은 정보가 빠지지 않도록 프론트 최종 표시 단계에서도 page result card를 이용해 동일한 요약 문구를 주입하도록 했다.

## 변경 파일 목록
- `src/model/struct/agent.py`
  - 페이지 결과 기반 fallback 답변에 `페이지 결과 요약:` bullet 추가
  - 한국어/영어 최종답변 정규화 프롬프트에 페이지 결과 요약 유지 규칙 추가
  - 최종답변 반환 직전에 페이지 결과 요약 bullet을 강제로 보정하는 후처리 helper 추가
- `src/app/component.chat.floating/view.ts`
  - verification 단계 최종 텍스트를 화면에 표시하기 전 `pageResultCard.summary`를 근거 첫 줄로 삽입하는 보강 추가
- `devlog.md`
  - 2026-03-24 작업 인덱스 015 추가

## 검증
- `src/model/struct/agent.py` 정적 오류 없음
- `wiz project build --project=main` 성공
- `src/app/component.chat.floating/view.ts`의 IDE 타입 오류는 로컬 Angular 타입 해석 부재에 따른 기존 환경 이슈이며, 실제 WIZ 빌드는 성공
