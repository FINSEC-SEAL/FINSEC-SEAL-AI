# FINSEC SEAL AI

Stateless AI execution service for FINSEC SEAL.

## Architectural boundary

Spring Boot owns:

- TestRun / TestCaseRun state
- step orchestration
- retry and timeout
- Tool validation / policy / execution
- ExecutionEvent / Evidence / Finding persistence
- recovery and idempotency

Python owns only one stateless Agent step:

1. receive the complete current context from Spring,
2. invoke/prepare the model step,
3. return either `TOOL_PROPOSAL` or `FINAL_RESPONSE`.

Python never executes FINSEC SEAL Tools and does not persist Run state.

## API

### `POST /v1/agent/steps`

The request carries Spring-owned identity directly: `releaseId`, `testRunId`,
`testCaseRunId`, and `traceId`.

The required `agentContext` is Spring-owned trusted execution context and contains:

- `agentContext.model`
- `agentContext.systemPrompt`
- `agentContext.businessPurpose`
- `agentContext.workflow`
- `agentContext.tools`
- `agentContext.runtime`
- `agentContext.documents`

Python validates this context for the current stateless step only. It does not store
`agentContext` as canonical state and does not resolve it from FINSEC SEAL databases
or the Sandbox.

Initial Agent step:

- `previousToolResult = null`
- returns `TOOL_PROPOSAL`

Step after Spring executes a Tool:

- Spring calls the same endpoint again with `previousToolResult`
- returns the next `TOOL_PROPOSAL` or `FINAL_RESPONSE`

The default provider remains deterministic so local tests and contract validation
do not require external network access. Production can opt into the
OpenAI-compatible provider through environment configuration.

## Agent provider configuration

Supported provider modes:

- `AGENT_PROVIDER=deterministic`
  - default when `AGENT_PROVIDER` is unset,
  - uses the local deterministic contract provider,
  - does not require an API key.
- `AGENT_PROVIDER=openai-compatible`
  - calls an OpenAI-compatible Chat Completions endpoint,
  - requires `OPENAI_API_KEY`.

OpenAI-compatible settings:

- `OPENAI_API_KEY`
  - required when `AGENT_PROVIDER=openai-compatible`.
- `OPENAI_BASE_URL`
  - optional,
  - defaults to `https://api.openai.com/v1`.
- `OPENAI_TIMEOUT_SECONDS`
  - optional,
  - defaults to `30`.

The provider sends one stateless request to `/chat/completions`. Python does not
execute returned Tools. A single valid function call is converted into
`TOOL_PROPOSAL`; a non-empty assistant response is converted into
`FINAL_RESPONSE`.

Provider failures are normalized at the API boundary:

- provider timeout → HTTP `504` with `Agent provider timed out.`
- connection or upstream HTTP failure → HTTP `502` with
  `Agent provider unavailable.`
- malformed provider response → HTTP `502` with
  `Agent provider returned an invalid response.`

Provider exception details and upstream response bodies are not returned to API
clients.

### `GET /health`

Returns `{"status":"ok"}`.

## Local run

Python 3.11+:

```bash
python -m venv .venv
```

Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m pytest -q
python -m uvicorn app.main:app --reload --port 8001
```

macOS/Linux:

```bash
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m pytest -q
python -m uvicorn app.main:app --reload --port 8001
```
