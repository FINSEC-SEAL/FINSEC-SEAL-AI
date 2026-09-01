# A Role Implementation — AI Repository Boundary

## 결론

이 레포에 A(Platform / Data / Evidence)가 구현할 실행 코드는 없습니다.
AI engine의 attack generation/mutation, vulnerability/root-cause analysis, policy patch recommendation은
A가 아닌 실행·분석 담당의 소유입니다.

A가 이 레포에 남긴 변경은 연동 경계 문서뿐입니다. 이는 미구현이 아니라 의도적인 역할 분리입니다.

## A Backend와의 연동 계약

AI worker를 구현할 담당자는 다음 원칙을 지킵니다.

1. A Backend이 발급한 `releaseId`, `testRunId`, `testCaseRunId`, `traceId`를 그대로 사용합니다.
2. 실행 이벤트는 Run별 단조 sequence와 `prevEventHash`/`eventHash`를 사용하여 A의
   append API로 전달합니다.
3. payload는 A의 redaction/tokenization 계약을 통과한 값만 저장하며 plaintext prompt,
   실제 고객·금융·신용정보, credential을 증거로 보내지 않습니다.
4. `agentArtifactFingerprint`, `releaseFingerprint`, model/config hash, fixture version/digest를
   실행 시점에 snapshot하고 종료 후 재작성하지 않습니다.
5. AI worker는 A의 PostgreSQL table을 직접 수정하지 않고 공식 HTTP 계약을 사용합니다.
6. 네트워크 timeout/retry 시 동일 mutation에는 동일 `Idempotency-Key`를 재사용합니다.

## 상태 전이 경계

- AI worker는 A가 생성한 `QUEUED/PREPARING/RUNNING/CANCELLING` Run을 소비할 수 있습니다.
- terminal Run/CaseRun에는 이벤트나 결과를 더 추가하지 않습니다.
- Run completion 순서는 `RUN_COMPLETED event commit → Run terminal transition`입니다.
- Oracle/Finding/Metric/Gate/Decision 계산은 해당 담당의 소유이며 A는 결과를 저장·봉인만 합니다.

## A 담당자가 할 일

- 이 레포의 runtime 알고리즘을 수정하지 않습니다.
- 연동 담당이 준비되면 BE의 TestRun/Event/Evidence DTO와 이 문서를 기준으로
  contract test를 추가합니다.
- 현재 레포는 README 외 코드가 없으므로 A 입장의 build/test 대상도 없습니다.

