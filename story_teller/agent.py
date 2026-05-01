from google.adk.agents import ParallelAgent, SequentialAgent

from .callbacks import before_agent_callback, after_agent_callback
from .env import force_load_project_env


force_load_project_env()

from .sub_agents.illustrator.agent import (
    book_assembler_agent,
    page_1_illustrator_agent,
    page_2_illustrator_agent,
    page_3_illustrator_agent,
    page_4_illustrator_agent,
    page_5_illustrator_agent,
)
from .sub_agents.story_writer.agent import story_writer_agent


parallel_illustrator_agent = ParallelAgent(
    name="ParallelIllustratorAgent",
    description="Generates five page illustrations in parallel.",
    sub_agents=[
        page_1_illustrator_agent,
        page_2_illustrator_agent,
        page_3_illustrator_agent,
        page_4_illustrator_agent,
        page_5_illustrator_agent,
    ],
    before_agent_callback=before_agent_callback,
    after_agent_callback=after_agent_callback,
)


root_agent = SequentialAgent(
    name="StoryBookCreator",
    description=(
        "Creates a five-page children's storybook from a theme. "
        "The workflow writes the story first, generates five illustrations in parallel, "
        "then assembles the final storybook artifacts."
    ),
    sub_agents=[
        story_writer_agent,
        parallel_illustrator_agent,
        book_assembler_agent,
    ],
)
