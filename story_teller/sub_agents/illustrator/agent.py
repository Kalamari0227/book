from google.adk.agents import Agent
from google.adk.models.lite_llm import LiteLlm

from .prompt import ILLUSTRATOR_DESCRIPTION, ILLUSTRATOR_PROMPT
from .tools import generate_storybook_images


MODEL = LiteLlm(model="openai/gpt-4o")

illustrator_agent = Agent(
    name="IllustratorAgent",
    description=ILLUSTRATOR_DESCRIPTION,
    instruction=ILLUSTRATOR_PROMPT,
    model=MODEL,
    output_key="illustrator_output",
    tools=[
        generate_storybook_images,
    ],
)
