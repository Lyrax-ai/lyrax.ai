from pydantic import BaseModel, ConfigDict, Field


class A2AModel(BaseModel):
    model_config = ConfigDict(extra="allow")


class AgentInterface(A2AModel):
    url: str = Field(min_length=1)
    protocolBinding: str = Field(min_length=1)
    protocolVersion: str = Field(min_length=1)


class AgentCapabilities(A2AModel):
    streaming: bool | None = None
    pushNotifications: bool | None = None
    extendedAgentCard: bool | None = None


class AgentSkill(A2AModel):
    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    description: str = Field(min_length=1)
    tags: list[str] = Field(min_length=1)


class AgentProvider(A2AModel):
    url: str = Field(min_length=1)
    organization: str = Field(min_length=1)


class A2AAgentCard(A2AModel):
    name: str = Field(min_length=1)
    description: str = Field(min_length=1)
    supportedInterfaces: list[AgentInterface] = Field(min_length=1)
    version: str = Field(min_length=1)
    capabilities: AgentCapabilities
    defaultInputModes: list[str] = Field(min_length=1)
    defaultOutputModes: list[str] = Field(min_length=1)
    skills: list[AgentSkill] = Field(min_length=1)
    provider: AgentProvider | None = None
