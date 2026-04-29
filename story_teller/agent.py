from google.adk.agents import SequentialAgent

from .sub_agents.illustrator.agent import illustrator_agent
from .sub_agents.story_writer.agent import story_writer_agent


root_agent = SequentialAgent(
    name="StoryBookCreator",
    description=(
        "Creates a five-page children's storybook from a theme, then generates "
        "one image artifact per page using the story data stored in agent state."
    ),
    sub_agents=[
        story_writer_agent,
        illustrator_agent,
    ],
)
