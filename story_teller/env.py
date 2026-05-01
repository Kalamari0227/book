from pathlib import Path

from dotenv import load_dotenv


def force_load_project_env() -> None:
    """Load the project .env and override placeholder shell values."""
    project_root = Path(__file__).resolve().parents[1]
    load_dotenv(project_root / ".env", override=True)
