import base64
import json
import os
from typing import Any, Dict, List

from google.adk.tools.tool_context import ToolContext
from google.genai import types
from openai import OpenAI

from .utils import (
    build_artifact_filename,
    build_composed_artifact_filename,
    build_image_prompt,
    build_final_storybook_summary,
    build_storybook_html,
    build_storybook_markdown,
    compose_full_storybook_preview_image,
    compose_storybook_page_image,
    story_output_to_dict,
)


IMAGE_MODEL = os.getenv("STORYBOOK_IMAGE_MODEL", "gpt-image-1.5")
IMAGE_QUALITY = os.getenv("STORYBOOK_IMAGE_QUALITY", "high")
IMAGE_SIZE = os.getenv("STORYBOOK_IMAGE_SIZE", "1024x1536")

STORYBOOK_MARKDOWN_ARTIFACT = "storybook.md"
STORYBOOK_HTML_ARTIFACT = "storybook.html"
STORYBOOK_MANIFEST_ARTIFACT = "storybook_manifest.json"
FULL_STORYBOOK_PREVIEW_ARTIFACT = "storybook_full_preview.jpeg"


def build_tool_display(
    title: str,
    description: str,
    state_name: str,
    next_step: str = "",
) -> Dict[str, str]:
    display = {
        "title": title,
        "description": description,
        "state": state_name,
    }
    if next_step:
        display["next_step"] = next_step
    return display


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


async def compose_page_artifacts(
    tool_context: ToolContext,
    pages: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    composed_images = []

    for page in pages:
        page_number = int(page.get("page_number", len(composed_images) + 1))
        source_filename = page.get("image_artifact") or build_artifact_filename(page_number)
        composed_filename = build_composed_artifact_filename(page_number)
        source_bytes = await load_artifact_bytes(tool_context, source_filename)

        if not source_bytes:
            continue

        composed_bytes = compose_storybook_page_image(
            image_bytes=source_bytes,
            page_number=page_number,
            text=page.get("text", ""),
        )

        await save_image_artifact(
            tool_context=tool_context,
            filename=composed_filename,
            image_bytes=composed_bytes,
        )

        page["source_image_artifact"] = source_filename
        page["composed_image_artifact"] = composed_filename

        composed_images.append(
            {
                "page_number": page_number,
                "filename": composed_filename,
                "source_filename": source_filename,
            }
        )

    return composed_images


def get_parallel_image_results(tool_context: ToolContext) -> Dict[str, Dict[str, Any]]:
    results = {}
    for page_number in range(1, 6):
        result = tool_context.state.get(f"page_image_result_{page_number}")
        if isinstance(result, dict) and result.get("filename"):
            results[str(page_number)] = result
    return results


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
    prompt_filename = f"storybook_page_{page_number}_prompt.md"

    page["prompt_artifact"] = prompt_filename

    await save_text_artifact(
        tool_context=tool_context,
        filename=prompt_filename,
        content="# 이미지 생성 프롬프트\n\n" + prompt.strip() + "\n",
        mime_type="text/markdown",
    )

    existing_artifacts = await tool_context.list_artifacts()

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

        await save_image_artifact(
            tool_context=tool_context,
            filename=filename,
            image_bytes=image_bytes,
        )

    return {
        "status": "complete",
        "page_number": page_number,
        "filename": filename,
        "message": f"{page_number}번째 삽화가 완성됐어요.",
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

    for page in pages:
        page_number = int(page.get("page_number", len(generated_images) + 1))
        filename = build_artifact_filename(page_number)

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

    # 개별 "글 붙인 페이지 이미지" artifact는 만들지 않는다.
    # 원본 이미지는 그대로 저장/표시하고,
    # 글이 붙은 페이지는 최종 전체 미리보기 안에서만 임시로 합성한다.
    composed_images = []
    story_output["composed_image_artifacts"] = composed_images

    full_preview_page_bytes = []

    for page in pages:
        page_number = int(page.get("page_number", len(full_preview_page_bytes) + 1))
        raw_filename = page.get("image_artifact", "")

        if not raw_filename:
            continue

        raw_image_bytes = await load_artifact_bytes(tool_context, raw_filename)
        if not raw_image_bytes:
            continue

        page_preview_bytes = compose_storybook_page_image(
            image_bytes=raw_image_bytes,
            page_number=page_number,
            text=page.get("text", ""),
        )
        full_preview_page_bytes.append(page_preview_bytes)

    if full_preview_page_bytes:
        full_preview_bytes = compose_full_storybook_preview_image(
            story_output=story_output,
            page_images=full_preview_page_bytes,
            target_width=450,
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
        "composed_image_artifacts": composed_images,
        "storybook_artifact": STORYBOOK_MARKDOWN_ARTIFACT,
        "storybook_html_artifact": STORYBOOK_HTML_ARTIFACT,
        "manifest_artifact": STORYBOOK_MANIFEST_ARTIFACT,
        "full_preview_artifact": FULL_STORYBOOK_PREVIEW_ARTIFACT,
    }

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

    full_preview_artifact = await tool_context.load_artifact(
        filename=FULL_STORYBOOK_PREVIEW_ARTIFACT
    )

    screen_parts_payload = []

    if full_preview_artifact and full_preview_artifact.inline_data:
        full_preview_b64 = base64.b64encode(
            full_preview_artifact.inline_data.data
        ).decode("ascii")
        screen_parts_payload.append(
            {
                "type": "image",
                "mime_type": full_preview_artifact.inline_data.mime_type or "image/jpeg",
                "data": full_preview_b64,
            }
        )
    else:
        screen_parts_payload.append(
            {
                "type": "text",
                "text": final_summary,
            }
        )

    story_output["storybook_artifact"] = STORYBOOK_MARKDOWN_ARTIFACT
    story_output["storybook_html_artifact"] = STORYBOOK_HTML_ARTIFACT
    story_output["manifest_artifact"] = STORYBOOK_MANIFEST_ARTIFACT
    story_output["full_preview_artifact"] = FULL_STORYBOOK_PREVIEW_ARTIFACT

    tool_context.state["story_writer_output"] = story_output
    tool_context.state["storybook_html_for_screen"] = storybook_html
    tool_context.state["storybook_screen_output"] = final_summary
    tool_context.state["storybook_screen_parts"] = screen_parts_payload
    tool_context.state["illustrator_output"] = {
        "status": "complete",
        "total_images": len(generated_images),
        "generated_images": generated_images,
        "composed_images": composed_images,
        "storybook_artifact": STORYBOOK_MARKDOWN_ARTIFACT,
        "storybook_html_artifact": STORYBOOK_HTML_ARTIFACT,
        "manifest_artifact": STORYBOOK_MANIFEST_ARTIFACT,
        "full_preview_artifact": FULL_STORYBOOK_PREVIEW_ARTIFACT,
        "display_output": final_summary,
    }

    return {
        "status": "complete",
        "message": "동화책 조립이 완료됐어요.",
        "storybook_artifact": STORYBOOK_MARKDOWN_ARTIFACT,
        "storybook_html_artifact": STORYBOOK_HTML_ARTIFACT,
        "manifest_artifact": STORYBOOK_MANIFEST_ARTIFACT,
        "full_preview_artifact": FULL_STORYBOOK_PREVIEW_ARTIFACT,
    }
