import unittest
from importlib import util
from pathlib import Path

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

build_artifact_filename = illustrator_utils.build_artifact_filename
build_image_prompt = illustrator_utils.build_image_prompt
build_storybook_markdown = illustrator_utils.build_storybook_markdown
story_output_to_dict = illustrator_utils.story_output_to_dict


class IllustratorToolHelpersTest(unittest.TestCase):
    def test_build_artifact_filename_uses_page_number(self):
        self.assertEqual(build_artifact_filename(3), "storybook_page_3.jpeg")

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
        self.assertIn("Theme: 친구 찾기", markdown)
        self.assertIn("## Page 1", markdown)
        self.assertIn("Text: 베니는 보라색 하늘을 보았어요.", markdown)
        self.assertIn("Image Artifact: storybook_page_1.jpeg", markdown)


if __name__ == "__main__":
    unittest.main()
