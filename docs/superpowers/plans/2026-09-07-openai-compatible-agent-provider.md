# OpenAI-compatible Agent Provider Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 기존 `AgentProvider` 경계에 `httpx` 기반 OpenAI-compatible Chat Completions 구현체를 추가하고 환경변수로 선택 가능하게 만든다.

**Architecture:** `StatelessAgentService`는 계속 `AgentProvider`만 호출한다. `OpenAICompatibleAgentProvider`가 `AgentStepRequest`를 Chat Completions payload로 변환하고, 외부 응답을 `TOOL_PROPOSAL` 또는 `FINAL_RESPONSE`로 파싱한다. Tool 실행·권한·retry·Run 상태는 Spring 소유를 유지한다.

**Tech Stack:** Python 3.11+, FastAPI, Pydantic v2, httpx, pytest

**Spec:** `docs/superpowers/specs/2026-09-07-openai-compatible-agent-provider-design.md`

## Global Constraints

- OpenAI SDK를 추가하지 않고 기존 `httpx>=0.28,<1`만 사용한다.
- 외부 호출은 `POST {OPENAI_BASE_URL}/chat/completions`를 사용한다.
- Python은 Tool을 실행하지 않는다.
- Python은 자동 retry하지 않는다.
- 기본 `AGENT_PROVIDER`는 `deterministic`이다.
- `OPENAI_API_KEY`는 openai-compatible 선택 시에만 필수다.
- API key와 외부 응답 본문은 FastAPI 오류 응답에 노출하지 않는다.
- 한 step에서 Tool proposal은 최대 1개만 허용한다.
- `parallel_tool_calls=false`, `tool_choice=auto`, `stream=false`를 Provider가 소유한다.
- `model`, `messages`, `tools`, `tool_choice`, `stream`, `parallel_tool_calls`는 model parameters가 덮어쓸 수 없다.
- 현재 계약의 camelCase 모델 파라미터 중 `maxTokens -> max_tokens`, `topP -> top_p`를 정규화한다.

---

### Task 1: OpenAI-compatible HTTP Provider와 응답 파싱

**Files:**
- Create: `app/provider/provider_errors.py`
- Create: `app/provider/openai_compatible_agent_provider.py`
- Create: `tests/test_openai_compatible_agent_provider.py`

**Interfaces:**
- Consumes: `AgentProvider.execute(request: AgentStepRequest) -> AgentStepResponse`
- Produces: `OpenAICompatibleAgentProvider.execute(request: AgentStepRequest) -> AgentStepResponse`
- Produces: `ProviderTimeoutError`, `ProviderUnavailableError`, `ProviderProtocolError`

- [ ] **Step 1: Provider 예외와 payload 매핑 실패 테스트 작성**

`tests/test_openai_compatible_agent_provider.py`에 실제 `AgentStepRequest` fixture와 `httpx.MockTransport` handler를 만들고 다음을 검증한다.

```python
def test_openai_provider_maps_request_to_chat_completions():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["authorization"] = request.headers["authorization"]
        captured["payload"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "model": "configured-model-id",
                "choices": [{
                    "finish_reason": "stop",
                    "message": {"role": "assistant", "content": "review complete"},
                }],
            },
        )

    provider = OpenAICompatibleAgentProvider(
        api_key="test-secret",
        base_url="https://llm.example/v1",
        transport=httpx.MockTransport(handler),
    )

    result = provider.execute(agent_step_request())

    payload = captured["payload"]
    assert captured["authorization"] == "Bearer test-secret"
    assert payload["model"] == "configured-model-id"
    assert payload["messages"][0] == {
        "role": "system",
        "content": "Review using trusted context.",
    }
    assert payload["tools"][0]["function"]["name"] == "CUSTOMER_DATA_READ"
    assert payload["tools"][0]["function"]["parameters"]["type"] == "object"
    assert payload["tool_choice"] == "auto"
    assert payload["stream"] is False
    assert payload["parallel_tool_calls"] is False
    assert payload["temperature"] == 0
    assert payload["max_tokens"] == 2048
    assert "maxTokens" not in payload
    assert result.action.type == "FINAL_RESPONSE"
    assert result.action.content == "review complete"
```

- [ ] **Step 2: 테스트를 실행해 RED 확인**

Run:

```bash
python -m pytest -q tests/test_openai_compatible_agent_provider.py
```

Expected: `ModuleNotFoundError` 또는 `OpenAICompatibleAgentProvider` 미정의로 FAIL.

- [ ] **Step 3: 최소 Provider 구현**

`app/provider/provider_errors.py`:

```python
class AgentProviderError(Exception):
    pass


class ProviderTimeoutError(AgentProviderError):
    pass


class ProviderUnavailableError(AgentProviderError):
    pass


class ProviderProtocolError(AgentProviderError):
    pass
```

`app/provider/openai_compatible_agent_provider.py`는 다음 책임만 가진다.

```python
class OpenAICompatibleAgentProvider:
    provider = "openai-compatible"

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.openai.com/v1",
        timeout_seconds: float = 30.0,
        transport: httpx.BaseTransport | None = None,
    ):
        ...

    def execute(self, request: AgentStepRequest) -> AgentStepResponse:
        ...
```

구현 규칙:

```python
PARAMETER_ALIASES = {
    "maxTokens": "max_tokens",
    "topP": "top_p",
}

RESERVED_PARAMETERS = {
    "model",
    "messages",
    "tools",
    "tool_choice",
    "stream",
    "parallel_tool_calls",
}
```

- `request.agentContext.model.parameters`를 복사한다.
- alias를 정규화한다.
- reserved key는 제거한 뒤 Provider가 최종값을 쓴다.
- user message는 `businessPurpose`, `workflow`, `runtime`, `documents`, `attackVariant`, `previousToolResult`를 `model_dump(mode="json")`한 뒤 `json.dumps(..., ensure_ascii=False, sort_keys=True)`로 직렬화한다.
- Tool은 `{"type":"function","function":{"name", "description", "parameters"}}` 형태로 변환한다.
- `POST {base_url.rstrip("/")}/chat/completions`.
- Authorization은 `Bearer {api_key}`.
- `time.perf_counter()`로 latencyMs를 계산한다.
- `httpx.TimeoutException`은 `ProviderTimeoutError`.
- 그 외 `httpx.HTTPError`와 non-2xx는 `ProviderUnavailableError`.
- 응답 JSON 구조 오류는 `ProviderProtocolError`.

- [ ] **Step 4: payload/FINAL_RESPONSE 테스트 GREEN 확인**

Run:

```bash
python -m pytest -q tests/test_openai_compatible_agent_provider.py::test_openai_provider_maps_request_to_chat_completions
```

Expected: PASS.

- [ ] **Step 5: Tool call 파싱 실패 테스트 작성**

```python
def test_openai_provider_maps_single_known_tool_call():
    response_json = {
        "model": "configured-model-id",
        "choices": [{
            "finish_reason": "tool_calls",
            "message": {
                "role": "assistant",
                "content": None,
                "tool_calls": [{
                    "id": "call_1",
                    "type": "function",
                    "function": {
                        "name": "CUSTOMER_DATA_READ",
                        "arguments": "{\"customerIds\":[\"CUST-1001\"]}",
                    },
                }],
            },
        }],
    }

    result = provider_with_response(response_json).execute(agent_step_request())

    assert result.finishReason == "tool_call"
    assert result.action.type == "TOOL_PROPOSAL"
    assert result.action.toolName == "CUSTOMER_DATA_READ"
    assert result.action.arguments == {"customerIds": ["CUST-1001"]}
```

같은 파일에 다음 protocol error case를 parameterize한다.

```python
@pytest.mark.parametrize("response_json", [
    multiple_tool_calls_response(),
    unknown_tool_response(),
    invalid_arguments_json_response(),
    arguments_array_response(),
    empty_choices_response(),
    empty_content_response(),
])
def test_openai_provider_rejects_invalid_provider_response(response_json):
    with pytest.raises(ProviderProtocolError):
        provider_with_response(response_json).execute(agent_step_request())
```

- [ ] **Step 6: RED 확인**

Run:

```bash
python -m pytest -q tests/test_openai_compatible_agent_provider.py
```

Expected: 새 tool/protocol case가 FAIL.

- [ ] **Step 7: Tool/Protocol 파싱 최소 구현**

파싱 규칙:

```python
choices = payload.get("choices")
if not isinstance(choices, list) or not choices:
    raise ProviderProtocolError()

message = choices[0].get("message")
tool_calls = message.get("tool_calls") or []

if tool_calls:
    if len(tool_calls) != 1:
        raise ProviderProtocolError()
    # type=function, known tool name, arguments string JSON object 검증
    return AgentStepResponse(... finishReason="tool_call", action=ToolProposalAction(...))

content = message.get("content")
if not isinstance(content, str) or not content.strip():
    raise ProviderProtocolError()

return AgentStepResponse(... finishReason="stop", action=FinalResponseAction(...))
```

응답의 provider는 항상 `"openai-compatible"`, model은 가능하면 응답의 `model` 문자열을 사용하고 없으면 요청의 `agentContext.model.name`을 사용한다.

- [ ] **Step 8: Provider 단위 테스트 전체 GREEN**

Run:

```bash
python -m pytest -q tests/test_openai_compatible_agent_provider.py
```

Expected: PASS.

- [ ] **Step 9: Task 1 커밋**

```bash
git add app/provider/provider_errors.py app/provider/openai_compatible_agent_provider.py tests/test_openai_compatible_agent_provider.py
git commit -m "feat: add openai compatible agent provider"
```

---

### Task 2: Provider Factory와 환경변수 Wiring

**Files:**
- Create: `app/provider/provider_factory.py`
- Modify: `app/service/agent_service.py`
- Create: `tests/test_provider_factory.py`
- Modify: `tests/test_agent_provider_boundary.py`

**Interfaces:**
- Produces: `build_agent_provider(environ: Mapping[str, str] | None = None) -> AgentProvider`
- Consumes: `DeterministicAgentProvider`, `OpenAICompatibleAgentProvider`

- [ ] **Step 1: Factory RED 테스트 작성**

```python
def test_factory_defaults_to_deterministic_provider():
    provider = build_agent_provider({})
    assert isinstance(provider, DeterministicAgentProvider)


def test_factory_builds_openai_compatible_provider():
    provider = build_agent_provider({
        "AGENT_PROVIDER": "openai-compatible",
        "OPENAI_API_KEY": "test-key",
        "OPENAI_BASE_URL": "https://llm.example/v1",
        "OPENAI_TIMEOUT_SECONDS": "12.5",
    })
    assert isinstance(provider, OpenAICompatibleAgentProvider)


def test_factory_requires_api_key_for_openai_compatible():
    with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
        build_agent_provider({"AGENT_PROVIDER": "openai-compatible"})


def test_factory_rejects_unknown_provider():
    with pytest.raises(RuntimeError, match="AGENT_PROVIDER"):
        build_agent_provider({"AGENT_PROVIDER": "unknown"})
```

- [ ] **Step 2: RED 확인**

Run:

```bash
python -m pytest -q tests/test_provider_factory.py
```

Expected: `provider_factory`가 없어 FAIL.

- [ ] **Step 3: Factory 최소 구현**

```python
def build_agent_provider(
    environ: Mapping[str, str] | None = None,
) -> AgentProvider:
    env = os.environ if environ is None else environ
    provider_name = env.get("AGENT_PROVIDER", "deterministic")

    if provider_name == "deterministic":
        return DeterministicAgentProvider()

    if provider_name == "openai-compatible":
        api_key = env.get("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError(
                "OPENAI_API_KEY is required when AGENT_PROVIDER=openai-compatible"
            )
        timeout_seconds = float(env.get("OPENAI_TIMEOUT_SECONDS", "30"))
        return OpenAICompatibleAgentProvider(
            api_key=api_key,
            base_url=env.get("OPENAI_BASE_URL", "https://api.openai.com/v1"),
            timeout_seconds=timeout_seconds,
        )

    raise RuntimeError(f"Unsupported AGENT_PROVIDER: {provider_name}")
```

`app/service/agent_service.py`의 기본 wiring:

```python
_service = StatelessAgentService(build_agent_provider())
```

- [ ] **Step 4: Factory + 기존 boundary 테스트 GREEN**

Run:

```bash
python -m pytest -q tests/test_provider_factory.py tests/test_agent_provider_boundary.py
```

Expected: PASS. 기본 환경에서는 기존 deterministic wiring 유지.

- [ ] **Step 5: Task 2 커밋**

```bash
git add app/provider/provider_factory.py app/service/agent_service.py tests/test_provider_factory.py tests/test_agent_provider_boundary.py
git commit -m "feat: configure agent provider factory"
```

---

### Task 3: FastAPI Provider 오류 변환

**Files:**
- Modify: `app/main.py`
- Create: `tests/test_provider_error_handlers.py`

**Interfaces:**
- Consumes: `ProviderTimeoutError`, `ProviderUnavailableError`, `ProviderProtocolError`
- Produces: 정적 504/502 JSON 오류 응답

- [ ] **Step 1: API 오류 RED 테스트 작성**

FastAPI dependency override로 오류를 발생시키는 fake service를 주입한다.

```python
@pytest.mark.parametrize(
    ("error", "status_code", "detail"),
    [
        (ProviderTimeoutError(), 504, "Agent provider timed out."),
        (ProviderUnavailableError(), 502, "Agent provider unavailable."),
        (ProviderProtocolError(), 502, "Agent provider returned an invalid response."),
    ],
)
def test_provider_errors_return_static_safe_responses(error, status_code, detail):
    app.dependency_overrides[get_agent_service] = lambda: RaisingService(error)
    try:
        response = client.post("/v1/agent/steps", json=step_request())
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == status_code
    assert response.json() == {"detail": detail}
    assert "secret" not in response.text
```

`RaisingService.execute_step()`는 전달받은 예외를 그대로 raise한다.

- [ ] **Step 2: RED 확인**

Run:

```bash
python -m pytest -q tests/test_provider_error_handlers.py
```

Expected: 예외가 처리되지 않아 FAIL.

- [ ] **Step 3: 정적 Exception Handler 구현**

`app/main.py`에 세 handler를 추가한다.

```python
@app.exception_handler(ProviderTimeoutError)
async def provider_timeout_handler(_: Request, __: ProviderTimeoutError) -> JSONResponse:
    return JSONResponse(status_code=504, content={"detail": "Agent provider timed out."})


@app.exception_handler(ProviderUnavailableError)
async def provider_unavailable_handler(
    _: Request, __: ProviderUnavailableError
) -> JSONResponse:
    return JSONResponse(
        status_code=502,
        content={"detail": "Agent provider unavailable."},
    )


@app.exception_handler(ProviderProtocolError)
async def provider_protocol_handler(
    _: Request, __: ProviderProtocolError
) -> JSONResponse:
    return JSONResponse(
        status_code=502,
        content={"detail": "Agent provider returned an invalid response."},
    )
```

원본 예외 문자열, HTTP response body, API key는 절대 response에 넣지 않는다.

- [ ] **Step 4: API 오류 테스트 GREEN**

Run:

```bash
python -m pytest -q tests/test_provider_error_handlers.py
```

Expected: PASS.

- [ ] **Step 5: Task 3 커밋**

```bash
git add app/main.py tests/test_provider_error_handlers.py
git commit -m "feat: map agent provider failures to api errors"
```

---

### Task 4: 회귀 검증과 문서 정리

**Files:**
- Modify: `docs/B_STATELESS_AGENT_RUNTIME.md`
- Test: 전체 `tests/`

**Interfaces:**
- Produces: 운영자가 설정할 수 있는 provider 환경변수 문서
- Verifies: deterministic 기본 동작과 기존 Spring ↔ Python 계약 유지

- [ ] **Step 1: 런타임 문서 갱신**

`docs/B_STATELESS_AGENT_RUNTIME.md`의 deterministic-only 설명을 다음 운영 선택 구조로 바꾼다.

```markdown
## Agent provider

Default:

`AGENT_PROVIDER=deterministic`

OpenAI-compatible Chat Completions:

- `AGENT_PROVIDER=openai-compatible`
- `OPENAI_API_KEY=<secret>`
- `OPENAI_BASE_URL=https://api.openai.com/v1`
- `OPENAI_TIMEOUT_SECONDS=30`

Python still executes one stateless Agent step only. Tool execution,
authorization, retry, Run state, and evidence persistence remain Spring-owned.
```

- [ ] **Step 2: 관련 테스트 실행**

Run:

```bash
python -m pytest -q \
  tests/test_openai_compatible_agent_provider.py \
  tests/test_provider_factory.py \
  tests/test_provider_error_handlers.py \
  tests/test_agent_provider_boundary.py \
  tests/test_agent_steps.py \
  tests/test_agent_context_contract.py
```

Expected: PASS.

- [ ] **Step 3: 전체 회귀 테스트와 diff 형식 검증**

Run:

```bash
python -m pytest -q
git diff --check
```

Expected: 전체 PASS, `git diff --check` 출력 없음.

- [ ] **Step 4: 실제 네트워크 호출이 테스트에 없는지 확인**

Run:

```bash
grep -R "api.openai.com" -n tests app | cat
```

Expected: 실제 네트워크 통합 테스트 없음. URL 기본값 문자열만 구현/테스트에 존재할 수 있다.

- [ ] **Step 5: Task 4 커밋**

```bash
git add docs/B_STATELESS_AGENT_RUNTIME.md
git commit -m "docs: document agent provider configuration"
```

- [ ] **Step 6: 최종 상태 확인**

Run:

```bash
git status --short
git log --oneline -5
```

Expected: 작업 트리 clean, 이번 브랜치에 설계 + 구현 관련 커밋만 존재.
