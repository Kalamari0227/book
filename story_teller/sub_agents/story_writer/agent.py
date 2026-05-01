from typing import List

from google.adk.agents import Agent
from pydantic import BaseModel, Field

from ...callbacks import before_agent_callback, after_agent_callback
from ...env import force_load_project_env
from .prompt import STORY_WRITER_DESCRIPTION, STORY_WRITER_PROMPT


force_load_project_env()


class StoryPage(BaseModel):
    page_number: int = Field(description="Page number from 1 to 5")
    text: str = Field(description="Child-friendly story text for this page")
    visual: str = Field(description="Detailed visual description for illustration")


class StoryWriterOutput(BaseModel):
    theme: str = Field(description="The story theme provided by the user")
    title: str = Field(description="Short children's storybook title")
    pages: List[StoryPage] = Field(
        description="Exactly five story pages with text and visual descriptions",
        min_length=5,
        max_length=5,
    )


story_writer_agent = Agent(
    name="StoryWriterAgent",
    description=STORY_WRITER_DESCRIPTION,
    instruction=STORY_WRITER_PROMPT,
    model="openai/gpt-4o",
    output_schema=StoryWriterOutput,
    output_key="story_writer_output",
    before_agent_callback=before_agent_callback,
    after_agent_callback=after_agent_callback,
)
