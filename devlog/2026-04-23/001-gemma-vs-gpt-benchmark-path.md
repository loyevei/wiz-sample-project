# Gemma 4와 GPT-4.1 A/B 벤치마크 경로 추가 및 실측 비교

- **ID**: 001
- **날짜**: 2026-04-23
- **유형**: 기능 추가

## 작업 요약
Gemma 4 로컬 모델과 GPT-4.1을 동일 프롬프트로 반복 비교할 수 있도록 에이전트에 provider 추상화를 추가하고, page.agent 및 page.agent.v2 API에 벤치마크 수집 경로를 구현했다.

WIZ의 API 캐시 특성 때문에 기존 page.agent 경로는 즉시 반영이 불안정했고, 무중단 적용이 가능한 page.agent.v2의 기존 agent_chat 경로에 benchmark_compare 모드를 실어 실제 5회 비교를 수행했다.

## 변경 파일 목록
- `src/model/struct/agent.py`
  - local / openai provider 전환 로직 추가
  - model_name, api_key, temperature, top_p, max_tokens 주입 지원
  - 동일 Agent 루프에서 로컬 Gemma와 GPT-4.1을 공정 비교할 수 있도록 정리
- `src/app/page.agent/api.py`
  - benchmark_compare 수집 로직 추가
  - trial별 total_ms, first_event_ms, first_text_ms, tool 호출 수, answer 길이 집계 추가
  - 기존 agent_chat 경로에서 mode=benchmark_compare 분기 지원 추가
- `src/app/page.agent.v2/api.py`
  - 무중단 반영이 가능한 벤치마크 경로 추가
  - agent_chat 경로에서 mode=benchmark_compare 분기 지원 추가
  - 실제 운영 검증 및 5회 A/B 비교 실행 경로로 사용

## 실측 결과 요약
- 프롬프트: 안녕하세요. 간단히 자기소개 해주세요.
- 반복 횟수: local 5회, openai 5회
- local 모델: google/gemma-4-26B-A4B-it
- openai 모델: gpt-4.1

### 평균 지표
- Local Gemma 4
  - 평균 전체 시간: 351531.82ms
  - 평균 첫 이벤트 시간: 2.17ms
  - 평균 첫 텍스트 시간: 351531.80ms
  - 평균 답변 길이: 1183.6자
- GPT-4.1
  - 평균 전체 시간: 8680.18ms
  - 평균 첫 이벤트 시간: 234.7ms
  - 평균 첫 텍스트 시간: 8680.16ms
  - 평균 답변 길이: 722.8자

### 해석
- 현재 로컬 Gemma 경로는 tool 실행 이후 최종 text가 나오기까지 지연이 매우 커서, 동일 프롬프트 기준 GPT-4.1보다 현저히 느렸다.
- 반면 로컬 응답은 평균적으로 더 길고 설명적인 편이었다.
- WIZ 서버 재시작 없이도 page.agent.v2 경로를 통해 반복 벤치마크를 수행할 수 있는 상태를 확보했다.

## 검증
- `wiz bundle --project=main` 정상 완료
- `/wiz/api/page.agent.v2/agent_chat` 에서 `mode=benchmark_compare` 1회 스모크 테스트 성공
- 동일 경로로 local 5회 + GPT-4.1 5회 실측 JSON 수신 및 비교 완료