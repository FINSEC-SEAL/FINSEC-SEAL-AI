from __future__ import annotations

from typing import Annotated, Literal, Union
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AgentModelContext(StrictModel):
    provider: str = Field(min_length=1, max_length=80)
    name: str = Field(min_length=1, max_length=120)
    parameters: dict


class AgentBusinessPurposeContext(StrictModel):
    code: str = Field(min_length=1, max_length=120)
    description: str = Field(min_length=1, max_length=2_048)


class AgentToolContext(StrictModel):
    name: str = Field(min_length=1, max_length=80)
    description: str = Field(min_length=1, max_length=2_048)
    inputSchema: dict


class AgentRuntimeContext(StrictModel):
    caseKey: str = Field(min_length=1, max_length=80)
    currentApplicantId: str = Field(min_length=1, max_length=80)
    status: str = Field(min_length=1, max_length=80)
    context: dict
    allowedDocumentIds: list[str]

    @field_validator("allowedDocumentIds")
    @classmethod
    def validate_unique_allowed_document_ids(cls, document_ids):
        if len(document_ids) != len(set(document_ids)):
            raise ValueError(
                "agentContext.runtime.allowedDocumentIds must contain unique document ids"
            )
        return document_ids


class AgentDocumentContext(StrictModel):
    documentId: str = Field(min_length=1, max_length=120)
    documentType: str = Field(min_length=1, max_length=120)
    content: str = Field(min_length=1)
    contentDigest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    trustLevel: str = Field(min_length=1, max_length=80)
    classification: dict


class AgentContext(StrictModel):
    model: AgentModelContext
    systemPrompt: str = Field(min_length=1)
    businessPurpose: AgentBusinessPurposeContext
    workflow: dict
    tools: list[AgentToolContext] = Field(min_length=1)
    runtime: AgentRuntimeContext
    documents: list[AgentDocumentContext]

    @field_validator("tools")
    @classmethod
    def validate_unique_tool_names(cls, tools):
        names = [tool.name for tool in tools]
        if len(names) != len(set(names)):
            raise ValueError("agentContext.tools must contain unique tool names")
        return tools

    @model_validator(mode="after")
    def validate_document_scope(self):
        allowed_ids = set(self.runtime.allowedDocumentIds)
        document_id_list = [document.documentId for document in self.documents]

        if len(document_id_list) != len(set(document_id_list)):
            raise ValueError(
                "agentContext.documents must contain unique document ids"
            )

        document_ids = set(document_id_list)

        if allowed_ids != document_ids:
            raise ValueError(
                "agentContext.documents must exactly match runtime.allowedDocumentIds"
            )
        return self


class AttackVariantPayload(StrictModel):
    category: str = Field(min_length=1, max_length=40)
    severity: str = Field(min_length=1, max_length=20)
    targetTool: str = Field(min_length=1, max_length=80)
    invariantId: str = Field(min_length=1, max_length=80)
    oracleType: str = Field(min_length=1, max_length=80)
    toolArguments: dict
    variantHash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")


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
    agentContext: AgentContext
    attackVariant: AttackVariantPayload
    previousToolResult: PreviousToolResult | None = None

    @model_validator(mode="after")
    def validate_runtime_identity(self):
        if self.agentContext.runtime.caseKey != self.caseKey:
            raise ValueError("agentContext.runtime.caseKey must match caseKey")
        if self.agentContext.runtime.currentApplicantId != self.currentApplicantId:
            raise ValueError(
                "agentContext.runtime.currentApplicantId must match currentApplicantId"
            )
        return self


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
