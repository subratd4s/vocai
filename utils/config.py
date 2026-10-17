"""Load local configuration without overriding the process environment."""

from pathlib import Path

from dotenv import load_dotenv


def load_environment() -> None:
    load_dotenv(Path(__file__).resolve().parents[1] / ".env", override=False)
