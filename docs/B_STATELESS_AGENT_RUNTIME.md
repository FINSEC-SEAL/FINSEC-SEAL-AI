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

The current contract-first implementation is deterministic. A real LLM provider
adapter is intentionally deferred until Spring ↔ Python contract and failure
semantics are proven.

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
