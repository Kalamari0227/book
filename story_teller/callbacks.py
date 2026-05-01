from typing import Optional

try:
    from google.adk.agents.callback_context import CallbackContext
except ImportError:
    from google.adk.agents import CallbackContext

from google.genai import types


def before_agent_callback(
    callback_context: CallbackContext,
) -> Optional[types.Content]:
    return None


def after_agent_callback(
    callback_context: CallbackContext,
) -> Optional[types.Content]:
    # 최종 동화책 미리보기는 assemble_storybook tool이 저장하는
    # storybook_full_preview.jpeg artifact 이벤트에서만 보여준다.
    # callback에서 다시 출력하면 동화책이 두 번 나온다.
    return None
