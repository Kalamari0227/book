import base64
from typing import Any, List, Mapping, Optional

try:
    from google.adk.agents.callback_context import CallbackContext
except ImportError:
    from google.adk.agents import CallbackContext

from google.genai import types


def get_storybook_callback_text(state: Mapping[str, Any]) -> Optional[str]:
    storybook_screen_output = state.get("storybook_screen_output")
    if isinstance(storybook_screen_output, str) and storybook_screen_output.strip():
        return storybook_screen_output

    illustrator_output = state.get("illustrator_output")
    if isinstance(illustrator_output, dict):
        display_output = illustrator_output.get("display_output")
        if isinstance(display_output, str) and display_output.strip():
            return display_output

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

    fallback_text = get_storybook_callback_text(state)
    if fallback_text:
        return [types.Part.from_text(text=fallback_text)]

    return []


def before_agent_callback(
    callback_context: CallbackContext,
) -> Optional[types.Content]:
    # State 업데이트를 하지 않는다.
    # ADK Events 화면에 State: progress... 칩이 남는 것을 막기 위함.
    return None


def after_agent_callback(
    callback_context: CallbackContext,
) -> Optional[types.Content]:
    # 중간 에이전트 완료 시에는 별도 state/message를 만들지 않는다.
    # 진행 메시지는 progress_agents가 채팅에 직접 출력한다.
    if callback_context.agent_name != "BookAssemblerAgent":
        return None

    storybook_callback_parts = build_storybook_callback_parts(callback_context.state)
    if storybook_callback_parts:
        return types.Content(
            role="model",
            parts=storybook_callback_parts,
        )

    return types.Content(
        role="model",
        parts=[types.Part.from_text(text="🎉 동화책이 완성됐어요.")],
    )
