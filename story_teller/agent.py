from google.adk.agents import SequentialAgent

from .env import force_load_project_env
from .progress_agents import (
    book_start_message_agent,
    illustration_done_message_agent,
    illustration_start_message_agent,
    story_start_message_agent,
)


force_load_project_env()

from .sub_agents.illustrator.agent import (
    book_assembler_agent,
    page_1_image_agent,
    page_2_image_agent,
    page_3_image_agent,
    page_4_image_agent,
    page_5_image_agent,
)
from .sub_agents.story_writer.agent import story_writer_agent


root_agent = SequentialAgent(
    name="StoryBookCreator",
    description=(
        "Creates a five-page children's storybook from a theme. "
        "The workflow writes the story, generates illustrations one by one, "
        "then assembles the final storybook preview."
    ),
    sub_agents=[
        story_start_message_agent,
        story_writer_agent,
            illustration_start_message_agent,
        page_1_image_agent,
        page_2_image_agent,
        page_3_image_agent,
        page_4_image_agent,
        page_5_image_agent,
        illustration_done_message_agent,
        book_start_message_agent,
        book_assembler_agent,
    ],
)
