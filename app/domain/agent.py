from __future__ import annotations

from typing import Annotated, Literal, Union
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AttackVariantPayload(StrictModel):
    category: str = Field(min_length=1, max_length=40)
    severity: str = Field(min_length=1, max_length=20)
    targetTool: str = Field(min_length=1, max_length=80)
    invariantId: str = Field(min_length=1, max_length=80)
    oracleType: str = Field(min_length=1, max_length=80)
    toolArguments: dict
    variantHash: str = Field(min_length=1, max_length=100)


class PreviousToolResult(StrictModel):
    toolName: str = Field(min_length=1, max_length=80)
    output: dict
    sourceEventId: UUID
    sourceSequence: int = Field(ge=1)


class AgentStepRequest(StrictModel):
    releaseId: UUID
    testRunId: UUID
    testCaseRunId: UUID
    traceId: UUID
    caseKey: str = Field(min_length=1, max_length=80)
    currentApplicantId: str = Field(min_length=1, max_length=80)
    attackVariant: AttackVariantPayload
    previousToolResult: PreviousToolResult | None = None


class ToolProposalAction(StrictModel):
    type: Literal["TOOL_PROPOSAL"]
    toolName: str = Field(min_length=1, max_length=80)
    arguments: dict


class FinalResponseAction(StrictModel):
    type: Literal["FINAL_RESPONSE"]
    content: str = Field(min_length=1, max_length=8_192)


AgentAction = Annotated[
    Union[ToolProposalAction, FinalResponseAction],
    Field(discriminator="type"),
]


class AgentStepResponse(StrictModel):
    provider: str = Field(min_length=1, max_length=80)
    model: str = Field(min_length=1, max_length=120)
    finishReason: Literal["tool_call", "stop"]
    action: AgentAction
    latencyMs: int = Field(ge=0)
