from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, Integer, JSON, String
from sqlalchemy.orm import relationship

from database import Base


class Agent(Base):
    __tablename__ = "agents"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(150), nullable=False, index=True)
    provider = Column(String(150), nullable=False)
    marketplace = Column(String(150), nullable=True)
    endpoint = Column(String(1000), nullable=True)
    version = Column(String(100), nullable=True)
    auth_type = Column(String(100), nullable=False, default="none")

    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    profile = relationship(
        "AgentProfile",
        back_populates="agent",
        uselist=False,
        cascade="all, delete-orphan"
    )


class AgentProfile(Base):
    __tablename__ = "agent_profiles"

    id = Column(Integer, primary_key=True, index=True)
    agent_id = Column(
        Integer,
        ForeignKey("agents.id", ondelete="CASCADE"),
        unique=True,
        nullable=False
    )

    claimed_capabilities = Column(JSON, nullable=False, default=list)
    protocols = Column(JSON, nullable=False, default=list)
    input_types = Column(JSON, nullable=False, default=list)
    output_types = Column(JSON, nullable=False, default=list)

    agent = relationship("Agent", back_populates="profile")
