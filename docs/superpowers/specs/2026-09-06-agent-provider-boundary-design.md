# Agent Provider 경계 설계

## 목표

현재 `StatelessAgentService` 안에 들어있는 deterministic Agent 실행 로직을
별도의 Provider로 분리한다.

이번 작업에서는 실제 OpenAI API를 호출하지 않는다.

## 현재 구조

POST /v1/agent/steps
→ StatelessAgentService
→ deterministic 응답 직접 생성

## 변경 구조

POST /v1/agent/steps
→ StatelessAgentService
→ AgentProvider
→ DeterministicAgentProvider

향후에는 아래 Provider를 추가할 수 있도록 한다.

→ OpenAICompatibleAgentProvider

## 역할

### AgentProvider

Agent 실행 구현체가 따라야 하는 공통 인터페이스다.

입력:
- AgentStepRequest

출력:
- AgentStepResponse

### DeterministicAgentProvider

현재 `StatelessAgentService`에 들어있는 기존 로직을 그대로 이동한다.

- 첫 요청이면 TOOL_PROPOSAL 반환
- Tool 결과가 들어오면 FINAL_RESPONSE 반환
- 기존 provider/model 값 유지
- Tool 결과 원문은 최종 응답에 그대로 노출하지 않음

### StatelessAgentService

Agent 로직을 직접 수행하지 않고 Provider에게 요청을 전달하는 역할만 한다.

## 유지해야 하는 원칙

Spring이 계속 담당한다.

- Tool 실제 실행
- Tool 권한 검증
- Run 상태 저장
- 실행 증적 저장
- trusted agentContext 생성

Python은 한 번의 Agent Step만 처리하는 stateless 구조를 유지한다.

## 이번 작업에서 하지 않는 것

- OpenAI SDK 추가
- OpenAI API 호출
- API Key 설정
- 네트워크 통신
- timeout/retry
- LLM 응답 파싱

이 기능들은 다음 작업에서 추가한다.

## 테스트 순서

1. StatelessAgentService가 주입된 Provider를 호출하는지 테스트
2. AgentProvider 인터페이스 추가
3. 기존 deterministic 로직을 DeterministicAgentProvider로 이동
4. 기존 Agent API 테스트가 그대로 통과하는지 확인
5. 전체 테스트 실행
