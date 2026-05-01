import unittest
import base64
from io import BytesIO
from importlib import util
from pathlib import Path

from PIL import Image

UTILS_PATH = (
    Path(__file__).resolve().parent
    / "story_teller"
    / "sub_agents"
    / "illustrator"
    / "utils.py"
)
spec = util.spec_from_file_location("illustrator_utils", UTILS_PATH)
illustrator_utils = util.module_from_spec(spec)
spec.loader.exec_module(illustrator_utils)

CALLBACKS_PATH = Path(__file__).resolve().parent / "story_teller" / "callbacks.py"
callbacks_spec = util.spec_from_file_location("story_teller_callbacks", CALLBACKS_PATH)
story_teller_callbacks = util.module_from_spec(callbacks_spec)
callbacks_spec.loader.exec_module(story_teller_callbacks)

build_artifact_filename = illustrator_utils.build_artifact_filename
build_composed_artifact_filename = illustrator_utils.build_composed_artifact_filename
build_final_storybook_summary = illustrator_utils.build_final_storybook_summary
build_image_prompt = illustrator_utils.build_image_prompt
build_progress_markdown = illustrator_utils.build_progress_markdown
build_progress_payload = illustrator_utils.build_progress_payload
build_screen_parts_payload = illustrator_utils.build_screen_parts_payload
build_storybook_html = illustrator_utils.build_storybook_html
build_storybook_markdown = illustrator_utils.build_storybook_markdown
compose_storybook_page_image = illustrator_utils.compose_storybook_page_image
resize_storybook_image_bytes = illustrator_utils.resize_storybook_image_bytes
story_output_to_dict = illustrator_utils.story_output_to_dict
build_storybook_callback_parts = story_teller_callbacks.build_storybook_callback_parts
build_progress_chat_message = story_teller_callbacks.build_progress_chat_message
build_progress_event = story_teller_callbacks.build_progress_event
build_progress_state_message = story_teller_callbacks.build_progress_state_message
get_agent_progress_message = story_teller_callbacks.get_agent_progress_message
get_storybook_callback_text = story_teller_callbacks.get_storybook_callback_text


class IllustratorToolHelpersTest(unittest.TestCase):
    def test_build_artifact_filename_uses_page_number(self):
        self.assertEqual(build_artifact_filename(3), "storybook_page_3.jpeg")
        self.assertEqual(
            build_composed_artifact_filename(3),
            "storybook_page_3_composed.jpeg",
        )

    def test_story_output_to_dict_accepts_dict(self):
        story = {"title": "달빛 모험", "pages": []}
        self.assertEqual(story_output_to_dict(story), story)

    def test_build_image_prompt_includes_page_context(self):
        prompt = build_image_prompt(
            "숲속 친구",
            {
                "text": "루나는 반짝이는 씨앗을 찾았어요.",
                "visual": "작은 여우가 빛나는 씨앗을 바라보는 장면",
            },
        )

        self.assertIn("숲속 친구", prompt)
        self.assertIn("루나는 반짝이는 씨앗을 찾았어요.", prompt)
        self.assertIn("작은 여우가 빛나는 씨앗을 바라보는 장면", prompt)
        self.assertIn("no readable text", prompt)

    def test_build_storybook_markdown_combines_pages_and_images(self):
        markdown = build_storybook_markdown(
            {
                "theme": "친구 찾기",
                "title": "베니의 보라색 하늘",
                "pages": [
                    {
                        "page_number": 1,
                        "text": "베니는 보라색 하늘을 보았어요.",
                        "visual": "하늘을 올려다보는 작은 토끼",
                        "image_artifact": "storybook_page_1.jpeg",
                    }
                ],
            }
        )

        self.assertIn("# 베니의 보라색 하늘", markdown)
        self.assertIn("주제: 친구 찾기", markdown)
        self.assertIn("## 1번째 장", markdown)
        self.assertIn("글: 베니는 보라색 하늘을 보았어요.", markdown)
        self.assertIn("삽화 파일: storybook_page_1.jpeg", markdown)

    def test_build_progress_markdown_summarizes_page_statuses(self):
        progress = build_progress_payload(
            "2번째 삽화를 그리고 있어요.",
            [
                {"page_number": 1, "prompt_artifact": "storybook_page_1_prompt.md"},
                {"page_number": 2, "prompt_artifact": "storybook_page_2_prompt.md"},
            ],
            [
                {
                    "page_number": 1,
                    "filename": "storybook_page_1.jpeg",
                }
            ],
        )
        markdown = build_progress_markdown(progress)

        self.assertEqual(progress["completed_pages"], 1)
        self.assertIn("현재 단계: 2번째 삽화를 그리고 있어요.", markdown)
        self.assertIn("1번째 장: 완성", markdown)
        self.assertIn("2번째 장: 그림 설명 준비 완료", markdown)

    def test_build_storybook_html_embeds_images_with_text(self):
        html = build_storybook_html(
            {
                "theme": "친구 찾기",
                "title": "베니의 보라색 하늘",
                "story_summary": "베니가 친구를 찾아 떠나는 이야기",
                "pages": [
                    {
                        "page_number": 1,
                        "text": "베니는 보라색 하늘을 보았어요.",
                        "visual": "하늘을 올려다보는 작은 토끼",
                        "image_artifact": "storybook_page_1.jpeg",
                    }
                ],
            },
            {"storybook_page_1.jpeg": "data:image/jpeg;base64,abc123"},
        )

        self.assertIn("<!doctype html>", html)
        self.assertIn("베니의 보라색 하늘", html)
        self.assertIn("data:image/jpeg;base64,abc123", html)
        self.assertIn("1번째 장", html)
        self.assertIn("베니는 보라색 하늘을 보았어요.", html)

    def test_storybook_callback_prefers_display_output_over_html_source(self):
        callback_text = get_storybook_callback_text(
            {
                "storybook_html_for_screen": "<!doctype html><html></html>",
                "illustrator_output": {
                    "display_output": "# 완성된 동화책\n\n![Page 1](storybook_page_1.jpeg)"
                },
            }
        )

        self.assertIn("# 완성된 동화책", callback_text)
        self.assertIn("![Page 1](storybook_page_1.jpeg)", callback_text)
        self.assertNotIn("<!doctype html>", callback_text)

    def test_storybook_callback_returns_image_and_text_parts(self):
        image_bytes = b"fake image bytes"
        screen_parts = build_screen_parts_payload(
            {
                "title": "베니의 보라색 하늘",
                "pages": [
                    {
                        "page_number": 1,
                        "text": "베니는 보라색 하늘을 보았어요.",
                        "image_artifact": "storybook_page_1.jpeg",
                    }
                ],
            },
            {
                "storybook_page_1.jpeg": "data:image/jpeg;base64,"
                + base64.b64encode(image_bytes).decode("ascii")
            },
        )
        callback_parts = build_storybook_callback_parts(
            {"storybook_screen_parts": screen_parts}
        )

        self.assertEqual(callback_parts[1].inline_data.mime_type, "image/jpeg")
        self.assertEqual(callback_parts[1].inline_data.data, image_bytes)
        self.assertIn("1번째 장", callback_parts[2].text)
        self.assertIn("베니는 보라색 하늘을 보았어요.", callback_parts[2].text)

    def test_screen_parts_can_show_composed_pages_without_extra_text_parts(self):
        image_bytes = b"composed image bytes"
        screen_parts = build_screen_parts_payload(
            {
                "title": "베니의 보라색 하늘",
                "pages": [
                    {
                        "page_number": 1,
                        "text": "베니는 보라색 하늘을 보았어요.",
                        "image_artifact": "storybook_page_1_composed.jpeg",
                    }
                ],
            },
            {
                "storybook_page_1_composed.jpeg": "data:image/jpeg;base64,"
                + base64.b64encode(image_bytes).decode("ascii")
            },
            include_page_text=False,
        )

        self.assertEqual([part["type"] for part in screen_parts], ["text", "image"])

    def test_compose_storybook_page_image_adds_text_margin(self):
        source = Image.new("RGB", (320, 480), "#88aa77")
        source_buffer = BytesIO()
        source.save(source_buffer, format="JPEG")

        composed_bytes = compose_storybook_page_image(
            source_buffer.getvalue(),
            1,
            "베니는 보라색 하늘을 보았어요.",
        )
        composed = Image.open(BytesIO(composed_bytes))

        self.assertEqual(composed.width, 320)
        self.assertGreater(composed.height, 480)

    def test_resize_storybook_image_bytes_halves_dimensions(self):
        source = Image.new("RGB", (320, 480), "#88aa77")
        source_buffer = BytesIO()
        source.save(source_buffer, format="JPEG")

        resized_bytes = resize_storybook_image_bytes(source_buffer.getvalue(), 0.5)
        resized = Image.open(BytesIO(resized_bytes))

        self.assertEqual(resized.size, (160, 240))

    def test_build_final_storybook_summary_lists_composed_artifacts(self):
        summary = build_final_storybook_summary(
            {
                "title": "순이와 함께하는 산책",
                "pages": [
                    {
                        "page_number": 1,
                        "text": "순이는 강아지와 함께 산책을 나섰어요.",
                        "composed_image_artifact": "storybook_page_1_composed.jpeg",
                    }
                ],
            }
        )

        self.assertIn("📚 순이와 함께하는 산책", summary)
        self.assertIn("Artifacts 탭", summary)
        self.assertIn("Page 1", summary)
        self.assertIn("> storybook_page_1_composed.jpeg", summary)

    def test_agent_progress_messages_are_korean(self):
        self.assertEqual(
            get_agent_progress_message("StoryWriterAgent", "before"),
            "동화 줄거리를 쓰고 있어요.",
        )
        self.assertEqual(
            get_agent_progress_message("BookAssemblerAgent", "after"),
            "동화책이 완성됐어요.",
        )

    def test_progress_state_message_includes_description_and_state_name(self):
        message = build_progress_state_message(
            "StoryWriterAgent",
            "before",
            "동화 줄거리를 쓰고 있어요.",
        )

        self.assertIn("📌 설명: 동화 줄거리를 쓰고 있어요.", message)
        self.assertIn("🔖 state: progress", message)
        self.assertIn("🤖 에이전트: StoryWriterAgent", message)

    def test_progress_chat_message_matches_visible_chat_format(self):
        message = build_progress_chat_message(
            "StoryWriterAgent",
            "동화 글 작성이 끝났어요.",
        )

        self.assertIn('✅ progress_message: "동화 글 작성이 끝났어요."', message)
        self.assertIn("🤖 agent: StoryWriterAgent", message)

    def test_progress_event_uses_korean_label(self):
        event = build_progress_event(
            "StoryWriterAgent",
            "after",
            "동화 글 작성이 끝났어요.",
        )

        self.assertEqual(event["label"], "완료")
        self.assertEqual(event["message"], "동화 글 작성이 끝났어요.")


if __name__ == "__main__":
    unittest.main()
