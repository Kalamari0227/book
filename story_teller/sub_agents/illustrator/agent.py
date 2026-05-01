from google.adk.agents import Agent

from ...callbacks import before_agent_callback, after_agent_callback
from ...env import force_load_project_env
from .tools import assemble_storybook, generate_page_image


force_load_project_env()


def create_page_illustrator_agent(page_number: int) -> Agent:
    return Agent(
        name=f"Page{page_number}IllustratorAgent",
        description=f"Generates the illustration artifact for page {page_number}.",
        instruction=(
            "You are a children's picture book illustrator.\n"
            "Read story_writer_output from agent state.\n"
            f"Generate only the illustration for page {page_number}.\n"
            "You must call the generate_page_image tool.\n"
            f"Pass page_number={page_number}."
        ),
        model="openai/gpt-4o",
        tools=[generate_page_image],
        before_agent_callback=before_agent_callback,
        after_agent_callback=after_agent_callback,
    )


page_1_illustrator_agent = create_page_illustrator_agent(1)
page_2_illustrator_agent = create_page_illustrator_agent(2)
page_3_illustrator_agent = create_page_illustrator_agent(3)
page_4_illustrator_agent = create_page_illustrator_agent(4)
page_5_illustrator_agent = create_page_illustrator_agent(5)


book_assembler_agent = Agent(
    name="BookAssemblerAgent",
    description="Combines story text and image artifacts into final storybook artifacts.",
    instruction=(
        "You are a storybook editor.\n"
        "Use story_writer_output and generated image artifacts to assemble the final storybook.\n"
        "You must call the assemble_storybook tool.\n"
        "After the tool returns, briefly say that storybook.html, storybook.md, "
        "and storybook_manifest.json were saved. The after-agent callback will display "
        "the finished storybook preview on screen."
    ),
    model="openai/gpt-4o",
    tools=[assemble_storybook],
    output_key="assembler_output",
    before_agent_callback=before_agent_callback,
    after_agent_callback=after_agent_callback,
)
