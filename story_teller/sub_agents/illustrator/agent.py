from google.adk.agents import Agent

from ...callbacks import before_agent_callback, after_agent_callback
from ...env import force_load_project_env
from .tools import assemble_storybook, generate_all_page_images


force_load_project_env()


image_generator_agent = Agent(
    name="ImageGeneratorAgent",
    description="Generates all five storybook page illustrations.",
    instruction=(
        "You are a children's picture book illustrator.\n"
        "Read story_writer_output from agent state.\n"
        "You must call the generate_all_page_images tool exactly once.\n"
        "Do not explain filenames.\n"
        "Do not print prompts.\n"
        "After the tool call, stop. Do not write a summary, filename, or final message."
    ),
    model="openai/gpt-4o",
    tools=[generate_all_page_images],
    before_agent_callback=before_agent_callback,
    after_agent_callback=after_agent_callback,
)


book_assembler_agent = Agent(
    name="BookAssemblerAgent",
    description="Combines story text and image artifacts into a final storybook preview.",
    instruction=(
        "You are a storybook editor.\n"
        "Use story_writer_output and generated image artifacts to assemble the final storybook.\n"
        "You must call the assemble_storybook tool exactly once.\n"
        "Do not explain filenames.\n"
        "After the tool call, stop. Do not write a summary, filename, or final message."
    ),
    model="openai/gpt-4o",
    tools=[assemble_storybook],
    before_agent_callback=before_agent_callback,
    after_agent_callback=after_agent_callback,
)
