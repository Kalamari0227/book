from google.adk.agents import Agent

from ...callbacks import before_agent_callback, after_agent_callback
from ...env import force_load_project_env
from .tools import write_storybook_plan


force_load_project_env()


story_writer_agent = Agent(
    name="StoryWriterAgent",
    description="Creates a structured five-page storybook plan and stores it in state.",
    instruction=(
        "You are the StoryWriterAgent.\n"
        "Call the write_storybook_plan tool exactly once using the user's theme.\n"
        "The tool stores story_writer_output in state for the next agents.\n"
        "Do not print JSON.\n"
        "After the tool call, say only: 동화 기획 데이터가 준비됐어요."
    ),
    model="openai/gpt-4o",
    tools=[write_storybook_plan],
    before_agent_callback=before_agent_callback,
    after_agent_callback=after_agent_callback,
)
