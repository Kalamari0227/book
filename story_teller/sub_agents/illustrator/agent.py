from google.adk.agents import Agent

from ...callbacks import before_agent_callback, after_agent_callback
from ...env import force_load_project_env
from .tools import assemble_storybook, generate_page_image


force_load_project_env()


def create_page_image_agent(page_number: int) -> Agent:
    return Agent(
        name=f"Page{page_number}ImageAgent",
        description=f"Generates page {page_number} illustration only.",
        instruction=(
            "You are a silent image generation step.\n"
            "Call the generate_page_image tool exactly once.\n"
            f"Pass page_number={page_number}.\n"
            "Do not explain the result.\n"
            "Do not mention filenames.\n"
            "After the tool call, stop."
        ),
        model="openai/gpt-4o-mini",
        tools=[generate_page_image],
        before_agent_callback=before_agent_callback,
        after_agent_callback=after_agent_callback,
    )


page_1_image_agent = create_page_image_agent(1)
page_2_image_agent = create_page_image_agent(2)
page_3_image_agent = create_page_image_agent(3)
page_4_image_agent = create_page_image_agent(4)
page_5_image_agent = create_page_image_agent(5)


book_assembler_agent = Agent(
    name="BookAssemblerAgent",
    description="Combines story text and image artifacts into a final storybook preview.",
    instruction=(
        "You are a silent storybook assembly step.\n"
        "Call the assemble_storybook tool exactly once.\n"
        "Do not explain the result.\n"
        "Do not mention filenames.\n"
        "After the tool call, stop."
    ),
    model="openai/gpt-4o-mini",
    tools=[assemble_storybook],
    before_agent_callback=before_agent_callback,
    after_agent_callback=after_agent_callback,
)
