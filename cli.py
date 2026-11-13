import argparse
import sys
from pathlib import Path

import yaml
from pydantic import ValidationError

from agents.models import Agent, AgentProfile
from database import SessionLocal
from schemas.agent import AgentCreate


def register_agent(config_path: str):
    path = Path(config_path)

    if not path.is_file():
        raise FileNotFoundError(f"Configuration file not found: {path}")

    with path.open("r", encoding="utf-8") as file:
        data = yaml.safe_load(file)

    if not isinstance(data, dict):
        raise ValueError("Agent configuration must be a YAML mapping.")

    payload = AgentCreate.model_validate(data)

    agent_data = payload.model_dump()
    profile_data = agent_data.pop("profile")

    db = SessionLocal()

    try:
        agent = Agent(**agent_data)
        agent.profile = AgentProfile(**profile_data)

        db.add(agent)
        db.commit()
        db.refresh(agent)

        print(f"Agent registered successfully.")
        print(f"ID: {agent.id}")
        print(f"Name: {agent.name}")
        print(f"Provider: {agent.provider}")

    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser(prog="lyrax")
    subparsers = parser.add_subparsers(dest="command", required=True)

    register_parser = subparsers.add_parser(
        "register",
        help="Register an agent from a YAML configuration file."
    )
    register_parser.add_argument("config")

    args = parser.parse_args()

    try:
        if args.command == "register":
            register_agent(args.config)
    except (FileNotFoundError, ValueError, ValidationError) as error:
        print(f"Registration failed: {error}", file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
