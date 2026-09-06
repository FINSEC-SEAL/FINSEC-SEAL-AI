# OpenAI-compatible Agent Provider 설계

## 목표

기존 `AgentProvider` 경계에 실제 LLM 호출 구현체를 추가한다.

`POST /v1/agent/steps`
→ `StatelessAgentService`
→ `AgentProvider`
→ `OpenAICompatibleAgentProvider`
→ `POST /v1/chat/completions`

Spring은 Tool 실행/권한 검증/Run 상태/재시도/증적 저장을 계속 소유하고, Python은 한 번의 stateless Agent step만 처리한다.

## 선택

OpenAI SDK 대신 기존 의존성인 `httpx`로 Chat Completions REST API를 직접 호출한다.

- OpenAI와 OpenAI-compatible 서버 모두 연결하기 쉽다.
- 새 런타임 의존성이 없다.
- `httpx.MockTransport`로 네트워크 없는 단위 테스트가 가능하다.
- Responses API보다 범용 호환성이 높다.

## 구성

### `app/provider/openai_compatible_agent_provider.py`

`AgentStepRequest`를 Chat Completions payload로 변환하고 응답을 `AgentStepResponse`로 변환한다. 실제 Tool은 실행하지 않는다.

### `app/provider/provider_factory.py`

환경변수로 구현체를 선택한다.

- `AGENT_PROVIDER=deterministic` 기본값
- `AGENT_PROVIDER=openai-compatible`
- `OPENAI_API_KEY` openai-compatible 선택 시 필수
- `OPENAI_BASE_URL=https://api.openai.com/v1`
- `OPENAI_TIMEOUT_SECONDS=30`

기본값은 deterministic으로 유지하여 API key가 없는 개발/테스트 환경을 깨지 않는다.

## 요청 매핑

- model: `agentContext.model.name`
- system message: `agentContext.systemPrompt`
- user message: `businessPurpose`, `workflow`, `runtime`, `documents`, `attackVariant`, `previousToolResult`를 JSON 직렬화
- tools: `agentContext.tools`를 function tool의 name/description/parameters로 변환
- `tool_choice=auto`
- `stream=false`

`agentContext.model.parameters`도 payload에 반영하되 `model`, `messages`, `tools`, `tool_choice`, `stream`은 Provider가 최종 소유하여 덮어쓰기를 막는다.

`previousToolResult`는 native tool message로 만들지 않는다. 현재 FINSEC SEAL 계약에는 이전 provider의 `tool_call_id`가 없으므로 trusted step context에 포함한다.

`strict:true`는 강제하지 않는다. 전달되는 임의 `inputSchema`가 OpenAI strict mode 제약을 모두 만족한다는 보장이 없기 때문이다.

## 응답 매핑

`choices[0].message.tool_calls`가 있으면 정확히 한 개의 function call만 허용한다. Tool 이름이 `agentContext.tools`에 존재하는지 검증하고 arguments를 JSON object로 파싱해 `TOOL_PROPOSAL`을 반환한다.

Tool 호출이 없고 assistant content가 비어 있지 않으면 `FINAL_RESPONSE`를 반환한다.

여러 Tool 호출, 알 수 없는 Tool, 잘못된 arguments, 빈 choices/content는 provider protocol error다.

## 오류 처리

Python은 자동 retry하지 않는다. Spring이 retry와 step orchestration의 소유자다.

- timeout → provider timeout
- 연결/HTTP 오류 → provider unavailable
- 잘못된 LLM 응답 → provider protocol error

FastAPI는 비밀값이나 외부 응답 본문을 노출하지 않는 정적 502/504 오류로 변환한다. API key는 환경변수에서만 읽는다.

## 테스트

외부 네트워크 없이 다음을 검증한다.

1. payload/model/system/context/tools 매핑
2. tool call → `TOOL_PROPOSAL`
3. content → `FINAL_RESPONSE`
4. multiple/unknown tool 및 invalid arguments 거부
5. timeout/HTTP 오류 변환
6. factory의 deterministic/openai-compatible 선택
7. API key 누락 실패
8. 기존 전체 테스트 회귀 없음

## 이번 PR 제외

Python Tool 실행, Run 상태 저장, 자동 retry, streaming, Responses API, OpenAI SDK, 다중 Tool 동시 처리, provider-native conversation state 저장.
