from google.adk.agents import Agent

from .env import force_load_project_env


force_load_project_env()


def create_message_agent(name: str, message: str) -> Agent:
    return Agent(
        name=name,
        description=f"Shows workflow message: {message}",
        instruction=(
            "You are a workflow progress notifier.\n"
            "Return exactly this message and nothing else:\n\n"
            f"{message}"
        ),
        model="openai/gpt-4o",
    )


story_start_message_agent = create_message_agent(
    "StoryStartMessageAgent",
    "✍️ 동화의 글과 그림을 고민하고 있어요.",
)

story_done_message_agent = create_message_agent(
    "StoryDoneMessageAgent",
    "✅ 동화 기획이 완료됐어요!",
)

illustration_start_message_agent = create_message_agent(
    "IllustrationStartMessageAgent",
    "🎨 다섯 장의 그림을 함께 그리고 있어요. 시간을 조금만 주세요!",
)

illustration_done_message_agent = create_message_agent(
    "IllustrationDoneMessageAgent",
    "✅ 그림이 모두 완성됐어요.",
)

book_start_message_agent = create_message_agent(
    "BookStartMessageAgent",
    "📚 그림과 글을 모아 동화책으로 엮고 있어요.",
)

book_done_message_agent = create_message_agent(
    "BookDoneMessageAgent",
    "🎉 동화책이 완성됐어요.",
)
