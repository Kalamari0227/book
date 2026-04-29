from typing import Any, Dict, List


def story_output_to_dict(story_output: Any) -> Dict[str, Any]:
    if story_output is None:
        return {}
    if isinstance(story_output, dict):
        return story_output
    if hasattr(story_output, "model_dump"):
        return story_output.model_dump()
    if hasattr(story_output, "dict"):
        return story_output.dict()
    return {}


def build_artifact_filename(page_number: int) -> str:
    return f"storybook_page_{page_number}.jpeg"


def build_image_prompt(title: str, page: Dict[str, Any]) -> str:
    text = page.get("text", "")
    visual = page.get("visual", "")
    return (
        "Create a warm children's picture book illustration. "
        "Use a premium children's book style with soft watercolor texture, "
        "gentle cinematic lighting, rich but calm colors, rounded shapes, "
        "expressive friendly characters, clear page composition, and no readable text in the image. "
        "Make it suitable for a portrait storybook page. "
        f"Story title: {title}. "
        f"Page text for context: {text}. "
        f"Illustration scene: {visual}."
    )


def build_storybook_markdown(story_output: Dict[str, Any]) -> str:
    title = story_output.get("title", "Children's Storybook")
    theme = story_output.get("theme", "")
    pages: List[Dict[str, Any]] = story_output.get("pages", [])

    lines = [f"# {title}", ""]
    if theme:
        lines.extend([f"Theme: {theme}", ""])

    for page in pages:
        page_number = page.get("page_number", "")
        text = page.get("text", "")
        visual = page.get("visual", "")
        image_artifact = page.get("image_artifact", "")

        lines.extend(
            [
                f"## Page {page_number}",
                "",
                f"Text: {text}",
                "",
                f"Visual: {visual}",
                "",
            ]
        )
        if image_artifact:
            lines.extend([f"Image Artifact: {image_artifact}", ""])

    return "\n".join(lines).strip() + "\n"
