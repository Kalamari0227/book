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
    compose_storybook_page_image,
    resize_storybook_image_bytes,
    story_output_to_dict,
)


IMAGE_MODEL = os.getenv("STORYBOOK_IMAGE_MODEL", "gpt-image-1.5")
IMAGE_QUALITY = os.getenv("STORYBOOK_IMAGE_QUALITY", "high")
IMAGE_SIZE = os.getenv("STORYBOOK_IMAGE_SIZE", "1024x1536")
STORYBOOK_MARKDOWN_ARTIFACT = "storybook.md"
STORYBOOK_HTML_ARTIFACT = "storybook.html"
STORYBOOK_MANIFEST_ARTIFACT = "storybook_manifest.json"


def build_tool_display(
    title: str,
    description: str,
    state_name: str,
    next_step: str = "",
) -> Dict[str, str]:
    display = {
        "🛠️ 함수 응답": title,
        "📌 설명": description,
        "🔖 state": state_name,
    }
    if next_step:
        display["➡️ 다음 단계"] = next_step
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


async def load_image_data_uris(
    tool_context: ToolContext,
    pages: List[Dict[str, Any]],
    scale: float = 1,
) -> Dict[str, str]:
    image_data_uris = {}

    for page in pages:
        filename = page.get("image_artifact")
        if not filename:
            continue

        image_artifact = await tool_context.load_artifact(filename=filename)
        if not image_artifact or not image_artifact.inline_data:
            continue

        mime_type = image_artifact.inline_data.mime_type or "image/jpeg"
        image_bytes = image_artifact.inline_data.data
        if scale != 1:
            image_bytes = resize_storybook_image_bytes(image_bytes, scale)
            mime_type = "image/jpeg"

        image_b64 = base64.b64encode(image_bytes).decode("ascii")
        image_data_uris[filename] = f"data:{mime_type};base64,{image_b64}"

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
        source_artifact = await tool_context.load_artifact(filename=source_filename)

        if not source_artifact or not source_artifact.inline_data:
            continue

        composed_bytes = compose_storybook_page_image(
            image_bytes=source_artifact.inline_data.data,
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


def build_screen_output(
    story_output: Dict[str, Any],
    generated_images: List[Dict[str, Any]],
) -> str:
    title = story_output.get("title", "완성된 동화책")
    storybook_html_artifact = story_output.get(
        "storybook_html_artifact",
        STORYBOOK_HTML_ARTIFACT,
    )
    storybook_artifact = story_output.get("storybook_artifact", STORYBOOK_MARKDOWN_ARTIFACT)
    manifest_artifact = story_output.get("manifest_artifact", STORYBOOK_MANIFEST_ARTIFACT)
    image_by_page = {
        int(image.get("page_number")): image.get("filename")
        for image in generated_images
        if image.get("page_number") is not None
    }

    lines = [
        "# 완성된 동화책",
        "",
        f"## {title}",
        "",
        "저장된 파일",
        f"- 웹에서 볼 수 있는 동화책: `{storybook_html_artifact}`",
        f"- 글 원고: `{storybook_artifact}`",
        f"- 동화책 정보: `{manifest_artifact}`",
        "",
    ]

    for page in story_output.get("pages", []):
        page_number = int(page.get("page_number", len(lines)))
        image_artifact = (
            image_by_page.get(page_number)
            or page.get("composed_image_artifact")
            or page.get("image_artifact", "")
        )
        lines.extend(
            [
                f"## {page_number}번째 장",
                "",
                f"![Page {page_number}]({image_artifact})",
                "",
                page.get("text", ""),
                "",
                f"삽화 파일: `{image_artifact}`",
                "",
            ]
        )

    return "\n".join(lines).strip()


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
            "display": build_tool_display(
                title="삽화 생성 중단",
                description="동화 글이 5장으로 준비되지 않아 삽화를 만들 수 없어요.",
                state_name="story_writer_output",
                next_step="먼저 동화 글 5장을 완성해야 해요.",
            ),
        }

    page = next(
        (item for item in pages if int(item.get("page_number", 0)) == int(page_number)),
        None,
    )

    if page is None:
        return {
            "status": "error",
            "message": f"{page_number}번째 장을 찾을 수 없어요.",
            "display": build_tool_display(
                title="페이지 확인 실패",
                description=f"{page_number}번째 장의 글과 그림 설명을 찾지 못했어요.",
                state_name="story_writer_output",
                next_step="페이지 번호와 story_writer_output 상태를 확인해 주세요.",
            ),
        }

    filename = build_artifact_filename(page_number)
    prompt = build_image_prompt(title, page)

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

        artifact = types.Part(
            inline_data=types.Blob(
                mime_type="image/jpeg",
                data=image_bytes,
            )
        )

        await tool_context.save_artifact(filename=filename, artifact=artifact)

    page_result = {
        "🖼️ state 업데이트": f"{page_number}번째 삽화 결과",
        "📌 설명": f"{page_number}번째 장의 원본 삽화가 저장됐어요.",
        "🔖 state": f"page_image_result_{page_number}",
        "page_number": page_number,
        "filename": filename,
        "visual": page.get("visual", ""),
    }
    tool_context.state[f"page_image_result_{page_number}"] = page_result

    return {
        "status": "complete",
        "page_number": page_number,
        "filename": filename,
        "message": f"{page_number}번째 삽화가 완성됐어요. ({page_number}/5)",
        "display": build_tool_display(
            title="삽화 생성 완료",
            description=f"{page_number}번째 장면 그림을 만들고 `{filename}` 파일로 저장했어요.",
            state_name=f"page_image_result_{page_number}",
            next_step="다른 페이지 삽화를 계속 만들거나, 모두 끝나면 동화책으로 엮어요.",
        ),
    }


async def assemble_storybook(
    tool_context: ToolContext,
) -> Dict[str, Any]:
    story_output = story_output_to_dict(tool_context.state.get("story_writer_output"))
    pages: List[Dict[str, Any]] = story_output.get("pages", [])
    illustration_outputs = get_parallel_image_results(tool_context)

    if len(pages) != 5:
        return {
            "status": "error",
            "message": "동화책으로 엮으려면 5장 분량의 동화 글이 필요해요.",
            "display": build_tool_display(
                title="동화책 조립 중단",
                description="5장 분량의 동화 글이 준비되지 않아 최종 동화책을 만들 수 없어요.",
                state_name="story_writer_output",
                next_step="StoryWriterAgent가 5장짜리 글을 먼저 만들어야 해요.",
            ),
        }

    generated_images = []

    for page in pages:
        page_number = int(page.get("page_number", len(generated_images) + 1))
        filename = build_artifact_filename(page_number)

        if str(page_number) in illustration_outputs:
            filename = illustration_outputs[str(page_number)].get("filename", filename)

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

    composed_images = await compose_page_artifacts(tool_context, pages)
    if composed_images:
        story_output["composed_image_artifacts"] = composed_images

    storybook_markdown = build_storybook_markdown(story_output)
    image_data_uris = await load_image_data_uris(tool_context, pages)
    storybook_html = build_storybook_html(story_output, image_data_uris)
    final_summary = build_final_storybook_summary(story_output)
    screen_pages = []
    for page in pages:
        screen_page = dict(page)
        screen_page["image_artifact"] = (
            page.get("composed_image_artifact") or page.get("image_artifact", "")
        )
        screen_pages.append(screen_page)

    screen_story_output = {**story_output, "pages": screen_pages}
    screen_image_data_uris = await load_image_data_uris(
        tool_context,
        screen_pages,
        scale=0.4,
    )
    screen_parts_payload = build_screen_parts_payload(
        screen_story_output,
        screen_image_data_uris,
        include_page_text=True,
    )

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

    story_output["storybook_artifact"] = STORYBOOK_MARKDOWN_ARTIFACT
    story_output["storybook_html_artifact"] = STORYBOOK_HTML_ARTIFACT
    story_output["manifest_artifact"] = STORYBOOK_MANIFEST_ARTIFACT
    display_output = final_summary

    tool_context.state["story_writer_output"] = story_output
    tool_context.state["storybook_html_for_screen"] = storybook_html
    tool_context.state["storybook_screen_output"] = display_output
    tool_context.state["storybook_screen_parts"] = screen_parts_payload
    tool_context.state["illustrator_output"] = {
        "🛠️ 함수 응답": "동화책 조립 완료",
        "📌 설명": "각 삽화 아래에 여백을 만들고 페이지 글을 넣어 완성 페이지 5장을 만들었어요.",
        "🔖 state": "illustrator_output",
        "📚 최종 결과": "완성된 그림동화책 페이지를 1번째 장부터 5번째 장까지 차례로 보여줘요.",
        "status": "complete",
        "total_images": len(generated_images),
        "generated_images": generated_images,
        "composed_images": composed_images,
        "storybook_artifact": STORYBOOK_MARKDOWN_ARTIFACT,
        "storybook_html_artifact": STORYBOOK_HTML_ARTIFACT,
        "manifest_artifact": STORYBOOK_MANIFEST_ARTIFACT,
        "display_output": display_output,
        "display_mode": "markdown_callback",
        "final_output": {
            "title": story_output.get("title"),
            "pages": [
                {
                    "page_number": page.get("page_number"),
                    "text": page.get("text"),
                    "image_artifact": page.get("image_artifact"),
                    "composed_image_artifact": page.get("composed_image_artifact"),
                }
                for page in pages
            ],
        },
        "display": build_tool_display(
            title="동화책 조립 완료",
            description="원본 삽화와 페이지 글을 합쳐 완성된 그림동화책 페이지를 만들었어요.",
            state_name="illustrator_output",
            next_step="최종 화면에서 1번째 장부터 5번째 장까지 순서대로 확인하면 돼요.",
        ),
    }

    return tool_context.state["illustrator_output"]
