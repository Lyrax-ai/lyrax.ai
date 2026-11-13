from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload

from agents.models import Agent, AgentProfile
from database import get_db
from schemas.agent import AgentCreate, AgentResponse, AgentUpdate

router = APIRouter(prefix="/agents", tags=["Agents"])


@router.post("/", response_model=AgentResponse, status_code=status.HTTP_201_CREATED)
def register_agent(payload: AgentCreate, db: Session = Depends(get_db)):
    data = payload.model_dump()
    profile_data = data.pop("profile")

    agent = Agent(**data)
    agent.profile = AgentProfile(**profile_data)

    db.add(agent)
    db.commit()
    db.refresh(agent)
    return agent


@router.get("/", response_model=list[AgentResponse])
def list_agents(db: Session = Depends(get_db)):
    return (
        db.query(Agent)
        .options(joinedload(Agent.profile))
        .order_by(Agent.id)
        .all()
    )


@router.get("/{agent_id}", response_model=AgentResponse)
def get_agent(agent_id: int, db: Session = Depends(get_db)):
    agent = (
        db.query(Agent)
        .options(joinedload(Agent.profile))
        .filter(Agent.id == agent_id)
        .first()
    )
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent


@router.put("/{agent_id}", response_model=AgentResponse)
def update_agent(
    agent_id: int,
    payload: AgentUpdate,
    db: Session = Depends(get_db)
):
    agent = (
        db.query(Agent)
        .options(joinedload(Agent.profile))
        .filter(Agent.id == agent_id)
        .first()
    )
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")

    data = payload.model_dump(exclude_unset=True)
    profile_data = data.pop("profile", None)

    for key, value in data.items():
        setattr(agent, key, value)

    if profile_data is not None:
        if agent.profile is None:
            agent.profile = AgentProfile(**profile_data)
        else:
            for key, value in profile_data.items():
                setattr(agent.profile, key, value)

    db.commit()
    db.refresh(agent)
    return agent


@router.delete("/{agent_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_agent(agent_id: int, db: Session = Depends(get_db)):
    agent = db.query(Agent).filter(Agent.id == agent_id).first()
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")

    db.delete(agent)
    db.commit()
