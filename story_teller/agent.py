from google.adk.agents import SequentialAgent

from .env import force_load_project_env
from .progress_agents import (
    book_start_message_agent,
    illustration_done_message_agent,
    illustration_start_message_agent,
    story_done_message_agent,
    story_start_message_agent,
)


force_load_project_env()

from .sub_agents.illustrator.agent import (
    book_assembler_agent,
    image_generator_agent,
)
from .sub_agents.story_writer.agent import story_writer_agent


root_agent = SequentialAgent(
    name="StoryBookCreator",
    description=(
        "Creates a five-page children's storybook from a theme. "
        "The workflow writes the story, generates all illustrations, "
        "then assembles the final storybook preview."
    ),
    sub_agents=[
        story_start_message_agent,
        story_writer_agent,
        story_done_message_agent,
        illustration_start_message_agent,
        image_generator_agent,
        illustration_done_message_agent,
        book_start_message_agent,
        book_assembler_agent,
    ],
)
