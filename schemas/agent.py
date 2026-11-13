from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class AgentProfileCreate(BaseModel):
    claimed_capabilities: list[str] = Field(default_factory=list)
    protocols: list[str] = Field(default_factory=list)
    input_types: list[str] = Field(default_factory=list)
    output_types: list[str] = Field(default_factory=list)


class AgentCreate(BaseModel):
    name: str = Field(min_length=2, max_length=150)
    provider: str = Field(min_length=1, max_length=150)
    marketplace: str | None = None
    endpoint: str | None = None
    version: str | None = None
    auth_type: str = "none"
    profile: AgentProfileCreate = Field(default_factory=AgentProfileCreate)


class AgentUpdate(BaseModel):
    name: str | None = None
    provider: str | None = None
    marketplace: str | None = None
    endpoint: str | None = None
    version: str | None = None
    auth_type: str | None = None
    profile: AgentProfileCreate | None = None


class AgentProfileResponse(AgentProfileCreate):
    model_config = ConfigDict(from_attributes=True)


class AgentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    provider: str
    marketplace: str | None
    endpoint: str | None
    version: str | None
    auth_type: str
    created_at: datetime
    updated_at: datetime
    profile: AgentProfileResponse | None
