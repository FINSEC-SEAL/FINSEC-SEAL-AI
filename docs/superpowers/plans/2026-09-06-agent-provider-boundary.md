# Agent Provider Boundary 구현 계획

- 목표: StatelessAgentService의 deterministic 로직을 Provider로 분리한다.
- 구조: API -> StatelessAgentService -> AgentProvider -> DeterministicAgentProvider
- 생성: app/provider/agent_provider.py
- 수정: app/service/agent_service.py
- 생성: tests/test_agent_provider_boundary.py
- TDD: 위임 테스트 RED -> 최소 구현 GREEN -> 기존 deterministic 로직 이동 -> 전체 테스트
- 이번 작업에서는 OpenAI API나 SDK를 추가하지 않는다.
