import base64
from typing import Any, Dict, List, Mapping, Optional

try:
    from google.adk.agents.callback_context import CallbackContext
except ImportError:
    from google.adk.agents import CallbackContext

from google.genai import types


BEFORE_AGENT_MESSAGES = {
    "StoryWriterAgent": "동화 줄거리를 쓰고 있어요.",
    "ParallelIllustratorAgent": "다섯 장의 삽화를 준비하고 있어요.",
    "Page1IllustratorAgent": "1번째 장면을 그리고 있어요. (1/5)",
    "Page2IllustratorAgent": "2번째 장면을 그리고 있어요. (2/5)",
    "Page3IllustratorAgent": "3번째 장면을 그리고 있어요. (3/5)",
    "Page4IllustratorAgent": "4번째 장면을 그리고 있어요. (4/5)",
    "Page5IllustratorAgent": "5번째 장면을 그리고 있어요. (5/5)",
    "BookAssemblerAgent": "그림과 글을 모아 동화책으로 엮고 있어요.",
}


AFTER_AGENT_MESSAGES = {
    "StoryWriterAgent": "동화 글 작성이 끝났어요.",
    "ParallelIllustratorAgent": "다섯 장의 삽화가 모두 준비됐어요.",
    "Page1IllustratorAgent": "1번째 삽화가 완성됐어요. (1/5)",
    "Page2IllustratorAgent": "2번째 삽화가 완성됐어요. (2/5)",
    "Page3IllustratorAgent": "3번째 삽화가 완성됐어요. (3/5)",
    "Page4IllustratorAgent": "4번째 삽화가 완성됐어요. (4/5)",
    "Page5IllustratorAgent": "5번째 삽화가 완성됐어요. (5/5)",
    "BookAssemblerAgent": "동화책이 완성됐어요.",
}


def get_agent_progress_message(agent_name: str, phase: str) -> str:
    if phase == "before":
        return BEFORE_AGENT_MESSAGES.get(agent_name, f"{agent_name}을 실행하고 있어요.")
    return AFTER_AGENT_MESSAGES.get(agent_name, f"{agent_name} 실행이 끝났어요.")


def build_progress_state_message(agent_name: str, phase: str, message: str) -> str:
    phase_label = "시작" if phase == "before" else "완료"
    return "\n".join(
        [
            f"📌 설명: {message}",
            "🔖 state: progress",
            f"🤖 에이전트: {agent_name}",
            f"⏱️ 단계: {phase_label}",
        ]
    )


def build_progress_chat_message(agent_name: str, message: str) -> str:
    return "\n".join(
        [
            f'✅ progress_message: "{message}"',
            f"🤖 agent: {agent_name}",
        ]
    )


def build_progress_event(agent_name: str, phase: str, message: str) -> Dict[str, str]:
    return {
        "agent": agent_name,
        "phase": "started" if phase == "before" else "completed",
        "label": "진행 중" if phase == "before" else "완료",
        "message": message,
    }


def append_progress_event(
    state: Any,
    agent_name: str,
    phase: str,
    message: str,
) -> None:
    progress_events = state.get("progress_events")
    if not isinstance(progress_events, list):
        progress_events = []

    progress_events.append(build_progress_event(agent_name, phase, message))
    state["progress_events"] = progress_events


def get_storybook_callback_text(state: Mapping[str, Any]) -> Optional[str]:
    illustrator_output = state.get("illustrator_output")
    if isinstance(illustrator_output, dict):
        display_output = illustrator_output.get("display_output")
        if isinstance(display_output, str) and display_output.strip():
            return display_output

    storybook_screen_output = state.get("storybook_screen_output")
    if isinstance(storybook_screen_output, str) and storybook_screen_output.strip():
        return storybook_screen_output

    return None


def build_storybook_callback_parts(state: Mapping[str, Any]) -> List[types.Part]:
    screen_parts = state.get("storybook_screen_parts")
    if isinstance(screen_parts, list):
        parts = []
        for screen_part in screen_parts:
            if not isinstance(screen_part, dict):
                continue

            if screen_part.get("type") == "text":
                text = screen_part.get("text")
                if isinstance(text, str) and text.strip():
                    parts.append(types.Part.from_text(text=text))

            if screen_part.get("type") == "image":
                mime_type = screen_part.get("mime_type")
                data_b64 = screen_part.get("data")
                if isinstance(mime_type, str) and isinstance(data_b64, str):
                    parts.append(
                        types.Part(
                            inline_data=types.Blob(
                                mime_type=mime_type,
                                data=base64.b64decode(data_b64),
                            )
                        )
                    )

        if parts:
            return parts

    storybook_callback_text = get_storybook_callback_text(state)
    if storybook_callback_text:
        return [types.Part.from_text(text=storybook_callback_text)]

    return []


def before_agent_callback(
    callback_context: CallbackContext,
) -> Optional[types.Content]:
    agent_name = callback_context.agent_name
    message = get_agent_progress_message(agent_name, "before")
    progress_state_message = build_progress_state_message(agent_name, "before", message)

    callback_context.state["progress"] = progress_state_message
    callback_context.state["progress_message"] = message
    append_progress_event(callback_context.state, agent_name, "before", message)
    print(f"[PROGRESS] {message}")

    return None


def after_agent_callback(
    callback_context: CallbackContext,
) -> Optional[types.Content]:
    agent_name = callback_context.agent_name
    message = get_agent_progress_message(agent_name, "after")
    progress_state_message = build_progress_state_message(agent_name, "after", message)

    callback_context.state["progress"] = progress_state_message
    callback_context.state["progress_message"] = message
    append_progress_event(callback_context.state, agent_name, "after", message)
    print(f"[PROGRESS] {message}")

    if agent_name == "BookAssemblerAgent":
        storybook_callback_parts = build_storybook_callback_parts(callback_context.state)
        if storybook_callback_parts:
            storybook_callback_parts.insert(
                0,
                types.Part.from_text(
                    text=build_progress_chat_message(agent_name, message)
                ),
            )
            return types.Content(
                role="model",
                parts=storybook_callback_parts,
            )

    return types.Content(
        role="model",
        parts=[types.Part.from_text(text=build_progress_chat_message(agent_name, message))],
    )
