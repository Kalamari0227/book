import base64
import json
import os
from typing import Any, Dict, List

from google.adk.tools.tool_context import ToolContext
from google.genai import types
from openai import OpenAI

from .utils import (
    build_artifact_filename,
    build_image_prompt,
    build_storybook_markdown,
    story_output_to_dict,
)


IMAGE_MODEL = os.getenv("STORYBOOK_IMAGE_MODEL", "gpt-image-1.5")
IMAGE_QUALITY = os.getenv("STORYBOOK_IMAGE_QUALITY", "high")
IMAGE_SIZE = os.getenv("STORYBOOK_IMAGE_SIZE", "1024x1536")


async def save_text_artifact(
    tool_context: ToolContext,
    filename: str,
    content: str,
    mime_type: str,
) -> None:
    artifact = types.Part(
        inline_data=types.Blob(
            mime_type=mime_type,
            data=content.encode("utf-8"),
        )
    )
    await tool_context.save_artifact(filename=filename, artifact=artifact)


async def generate_storybook_images(tool_context: ToolContext) -> Dict[str, Any]:
    client = OpenAI()
    story_output = story_output_to_dict(tool_context.state.get("story_writer_output"))
    pages: List[Dict[str, Any]] = story_output.get("pages", [])
    title = story_output.get("title", "Children's Storybook")

    if len(pages) != 5:
        return {
            "status": "error",
            "message": "story_writer_output must contain exactly 5 pages before illustrating.",
        }

    existing_artifacts = await tool_context.list_artifacts()
    generated_images = []

    for page in pages:
        page_number = int(page.get("page_number", len(generated_images) + 1))
        filename = build_artifact_filename(page_number)
        prompt = build_image_prompt(title, page)

        if filename not in existing_artifacts:
            image = client.images.generate(
                model=IMAGE_MODEL,
                prompt=prompt,
                n=1,
                quality=IMAGE_QUALITY,
                moderation="low",
                output_format="jpeg",
                background="opaque",
                size=IMAGE_SIZE,
            )

            image_bytes = base64.b64decode(image.data[0].b64_json)
            artifact = types.Part(
                inline_data=types.Blob(
                    mime_type="image/jpeg",
                    data=image_bytes,
                )
            )
            await tool_context.save_artifact(filename=filename, artifact=artifact)

        page["image_artifact"] = filename
        generated_images.append(
            {
                "page_number": page_number,
                "filename": filename,
                "visual": page.get("visual", ""),
            }
        )

    story_output["pages"] = pages
    story_output["image_artifacts"] = generated_images
    storybook_markdown = build_storybook_markdown(story_output)
    storybook_manifest = {
        "title": story_output.get("title"),
        "theme": story_output.get("theme"),
        "pages": pages,
        "image_artifacts": generated_images,
        "storybook_artifact": "storybook.md",
        "manifest_artifact": "storybook_manifest.json",
    }

    await save_text_artifact(
        tool_context=tool_context,
        filename="storybook.md",
        content=storybook_markdown,
        mime_type="text/markdown",
    )
    await save_text_artifact(
        tool_context=tool_context,
        filename="storybook_manifest.json",
        content=json.dumps(storybook_manifest, ensure_ascii=False, indent=2),
        mime_type="application/json",
    )

    story_output["storybook_artifact"] = "storybook.md"
    story_output["manifest_artifact"] = "storybook_manifest.json"
    tool_context.state["story_writer_output"] = story_output
    tool_context.state["illustrator_output"] = {
        "status": "complete",
        "total_images": len(generated_images),
        "generated_images": generated_images,
        "storybook_artifact": "storybook.md",
        "manifest_artifact": "storybook_manifest.json",
    }

    return tool_context.state["illustrator_output"]
