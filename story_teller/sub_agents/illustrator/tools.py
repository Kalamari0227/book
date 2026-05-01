import base64
import json
import os
from typing import Any, Dict, List

from google.adk.tools.tool_context import ToolContext
from google.genai import types
from openai import OpenAI

from .utils import (
    build_artifact_filename,
    build_final_storybook_summary,
    build_image_prompt,
    build_storybook_html,
    build_storybook_markdown,
    compose_full_storybook_preview_image,
    compose_storybook_page_image,
    resize_storybook_image_bytes,
    resize_storybook_image_to_width,
    story_output_to_dict,
)


IMAGE_MODEL = os.getenv("STORYBOOK_IMAGE_MODEL", "gpt-image-1.5")
IMAGE_QUALITY = os.getenv("STORYBOOK_IMAGE_QUALITY", "high")
IMAGE_SIZE = os.getenv("STORYBOOK_IMAGE_SIZE", "1024x1536")

STORYBOOK_MARKDOWN_ARTIFACT = "storybook.md"
STORYBOOK_HTML_ARTIFACT = "storybook.html"
STORYBOOK_MANIFEST_ARTIFACT = "storybook_manifest.json"
FULL_STORYBOOK_PREVIEW_ARTIFACT = "storybook_full_preview.jpeg"
SAVE_EXTRA_STORYBOOK_ARTIFACTS = os.getenv("STORYBOOK_SAVE_EXTRA_ARTIFACTS", "false").lower() == "true"


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


async def save_image_artifact(
    tool_context: ToolContext,
    filename: str,
    image_bytes: bytes,
    mime_type: str = "image/jpeg",
) -> None:
    artifact = types.Part(
        inline_data=types.Blob(
            mime_type=mime_type,
            data=image_bytes,
        )
    )
    await tool_context.save_artifact(filename=filename, artifact=artifact)


async def load_artifact_bytes(
    tool_context: ToolContext,
    filename: str,
) -> bytes | None:
    artifact = await tool_context.load_artifact(filename=filename)
    if not artifact or not artifact.inline_data:
        return None
    return artifact.inline_data.data


def image_bytes_to_screen_part(
    image_bytes: bytes,
    scale: float = 0.5,
) -> Dict[str, str]:
    display_bytes = resize_storybook_image_bytes(image_bytes, scale=scale)
    image_b64 = base64.b64encode(display_bytes).decode("ascii")
    return {
        "type": "image",
        "mime_type": "image/jpeg",
        "data": image_b64,
    }


async def load_image_data_uris(
    tool_context: ToolContext,
    pages: List[Dict[str, Any]],
) -> Dict[str, str]:
    image_data_uris = {}

    for page in pages:
        filename = page.get("image_artifact")
        if not filename:
            continue

        image_bytes = await load_artifact_bytes(tool_context, filename)
        if not image_bytes:
            continue

        image_b64 = base64.b64encode(image_bytes).decode("ascii")
        image_data_uris[filename] = f"data:image/jpeg;base64,{image_b64}"

    return image_data_uris


async def generate_all_page_images(
    tool_context: ToolContext,
) -> Dict[str, Any]:
    client = OpenAI()

    story_output = story_output_to_dict(tool_context.state.get("story_writer_output"))
    pages: List[Dict[str, Any]] = story_output.get("pages", [])
    title = story_output.get("title", "Children's Storybook")

    if len(pages) != 5:
        return {
            "status": "error",
            "message": "삽화를 만들기 전에 5장 분량의 동화 글이 필요해요.",
        }

    existing_artifacts = await tool_context.list_artifacts()
    generated_images: List[Dict[str, Any]] = []

    for page in pages:
        page_number = int(page.get("page_number", len(generated_images) + 1))
        filename = build_artifact_filename(page_number)
        prompt = build_image_prompt(title, page)

        if filename in existing_artifacts:
            image_bytes = await load_artifact_bytes(tool_context, filename)
        else:
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
            await save_image_artifact(
                tool_context=tool_context,
                filename=filename,
                image_bytes=image_bytes,
            )

        # The saved artifact event shows each generated image in ADK Dev UI.
        # Do not collect images for callback output to avoid duplicate display.

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

    tool_context.state["story_writer_output"] = story_output
    tool_context.state["image_generation_output"] = {
        "status": "complete",
        "total_images": len(generated_images),
        "generated_images": generated_images,
    }

    return {
        "status": "complete",
        "total_images": len(generated_images),
    }


async def generate_page_image(
    page_number: int,
    tool_context: ToolContext,
) -> Dict[str, Any]:
    client = OpenAI()

    story_output = story_output_to_dict(tool_context.state.get("story_writer_output"))
    pages: List[Dict[str, Any]] = story_output.get("pages", [])
    title = story_output.get("title", "Children's Storybook")

    if len(pages) != 5:
        return {
            "status": "error",
            "message": "삽화를 만들기 전에 5장 분량의 동화 글이 필요해요.",
        }

    page = next(
        (item for item in pages if int(item.get("page_number", 0)) == int(page_number)),
        None,
    )

    if page is None:
        return {
            "status": "error",
            "message": f"{page_number}번째 장을 찾을 수 없어요.",
        }

    filename = build_artifact_filename(page_number)
    prompt = build_image_prompt(title, page)

    existing_artifacts = await tool_context.list_artifacts()

    if filename in existing_artifacts:
        image_bytes = await load_artifact_bytes(tool_context, filename)
    else:
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

        display_image_bytes = resize_storybook_image_to_width(
            image_bytes,
            target_width=300,
        )

        await save_image_artifact(
            tool_context=tool_context,
            filename=filename,
            image_bytes=display_image_bytes,
        )
        image_bytes = display_image_bytes

    page["image_artifact"] = filename
    story_output["pages"] = pages
    tool_context.state["story_writer_output"] = story_output

    return {
        "status": "complete",
        "page_number": page_number,
        "filename": filename,
    }


async def assemble_storybook(
    tool_context: ToolContext,
) -> Dict[str, Any]:
    story_output = story_output_to_dict(tool_context.state.get("story_writer_output"))
    pages: List[Dict[str, Any]] = story_output.get("pages", [])

    if len(pages) != 5:
        return {
            "status": "error",
            "message": "동화책으로 엮으려면 5장 분량의 동화 글이 필요해요.",
        }

    generated_images = []
    full_preview_page_bytes: List[bytes] = []

    for page in pages:
        page_number = int(page.get("page_number", len(generated_images) + 1))
        filename = page.get("image_artifact") or build_artifact_filename(page_number)
        page["image_artifact"] = filename

        generated_images.append(
            {
                "page_number": page_number,
                "filename": filename,
                "visual": page.get("visual", ""),
            }
        )

        raw_image_bytes = await load_artifact_bytes(tool_context, filename)
        if raw_image_bytes:
            page_preview_bytes = compose_storybook_page_image(
                image_bytes=raw_image_bytes,
                page_number=page_number,
                text=page.get("text", ""),
            )
            full_preview_page_bytes.append(page_preview_bytes)

    story_output["pages"] = pages
    story_output["image_artifacts"] = generated_images
    story_output["composed_image_artifacts"] = []

    if full_preview_page_bytes:
        full_preview_bytes = compose_full_storybook_preview_image(
            story_output=story_output,
            page_images=full_preview_page_bytes,
            target_width=300,
        )
        await save_image_artifact(
            tool_context=tool_context,
            filename=FULL_STORYBOOK_PREVIEW_ARTIFACT,
            image_bytes=full_preview_bytes,
        )

    storybook_markdown = build_storybook_markdown(story_output)
    image_data_uris = await load_image_data_uris(tool_context, pages)
    storybook_html = build_storybook_html(story_output, image_data_uris)
    final_summary = build_final_storybook_summary(story_output)

    storybook_manifest = {
        "title": story_output.get("title"),
        "theme": story_output.get("theme"),
        "story_summary": story_output.get("story_summary"),
        "main_character": story_output.get("main_character"),
        "art_direction": story_output.get("art_direction"),
        "pages": pages,
        "image_artifacts": generated_images,
        "composed_image_artifacts": [],
        "storybook_artifact": STORYBOOK_MARKDOWN_ARTIFACT,
        "storybook_html_artifact": STORYBOOK_HTML_ARTIFACT,
        "manifest_artifact": STORYBOOK_MANIFEST_ARTIFACT,
        "full_preview_artifact": FULL_STORYBOOK_PREVIEW_ARTIFACT,
    }

    if SAVE_EXTRA_STORYBOOK_ARTIFACTS:
        await save_text_artifact(
            tool_context=tool_context,
            filename=STORYBOOK_MARKDOWN_ARTIFACT,
            content=storybook_markdown,
            mime_type="text/markdown",
        )

        await save_text_artifact(
            tool_context=tool_context,
            filename=STORYBOOK_HTML_ARTIFACT,
            content=storybook_html,
            mime_type="text/html",
        )

        await save_text_artifact(
            tool_context=tool_context,
            filename=STORYBOOK_MANIFEST_ARTIFACT,
            content=json.dumps(storybook_manifest, ensure_ascii=False, indent=2),
            mime_type="application/json",
        )

    full_preview_bytes = await load_artifact_bytes(
        tool_context,
        FULL_STORYBOOK_PREVIEW_ARTIFACT,
    )

    # 마지막 동화책 미리보기 전용 screen_parts.
    # 원본 그림 생성 단계의 screen_parts와는 별개다.
    screen_parts: List[Dict[str, str]] = []

    if full_preview_bytes:
        screen_parts.append(image_bytes_to_screen_part(full_preview_bytes, scale=1))

    story_output["storybook_artifact"] = STORYBOOK_MARKDOWN_ARTIFACT
    story_output["storybook_html_artifact"] = STORYBOOK_HTML_ARTIFACT
    story_output["manifest_artifact"] = STORYBOOK_MANIFEST_ARTIFACT
    story_output["full_preview_artifact"] = FULL_STORYBOOK_PREVIEW_ARTIFACT

    tool_context.state["story_writer_output"] = story_output
    tool_context.state["storybook_html_for_screen"] = storybook_html
    tool_context.state["storybook_screen_output"] = final_summary
    tool_context.state["storybook_screen_parts"] = screen_parts
    tool_context.state["illustrator_output"] = {
        "status": "complete",
        "total_images": len(generated_images),
        "generated_images": generated_images,
        "composed_images": [],
        "storybook_artifact": STORYBOOK_MARKDOWN_ARTIFACT,
        "storybook_html_artifact": STORYBOOK_HTML_ARTIFACT,
        "manifest_artifact": STORYBOOK_MANIFEST_ARTIFACT,
        "full_preview_artifact": FULL_STORYBOOK_PREVIEW_ARTIFACT,
        "display_output": final_summary,
    }

    return {
        "status": "complete",
        "full_preview_artifact": FULL_STORYBOOK_PREVIEW_ARTIFACT,
    }
