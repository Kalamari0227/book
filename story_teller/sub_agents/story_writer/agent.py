from typing import List

from google.adk.agents import Agent
from google.adk.models.lite_llm import LiteLlm
from pydantic import BaseModel, Field

from .prompt import STORY_WRITER_DESCRIPTION, STORY_WRITER_PROMPT


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


MODEL = LiteLlm(model="openai/gpt-4o")

story_writer_agent = Agent(
    name="StoryWriterAgent",
    description=STORY_WRITER_DESCRIPTION,
    instruction=STORY_WRITER_PROMPT,
    model=MODEL,
    output_schema=StoryWriterOutput,
    output_key="story_writer_output",
)
