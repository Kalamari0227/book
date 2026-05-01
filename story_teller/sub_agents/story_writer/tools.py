import json
from typing import Any, Dict, List

from google.adk.tools.tool_context import ToolContext
from openai import OpenAI


STORY_WRITER_SYSTEM_PROMPT = """
You are a professional children's storybook planner.

Create a five-page children's storybook from the user's theme.

Requirements:
- Write in Korean unless the user explicitly asks for another language.
- Create exactly 5 pages.
- Keep the story gentle, imaginative, and age-appropriate.
- Maintain the same main character and visual style across all pages.
- Do not include scary, violent, or unsafe content.
- Each page must have:
  - page_number: 1 through 5
  - text: one or two short, warm Korean sentences suitable for young children
  - visual: detailed English image-generation description for the page
- Return JSON only.

JSON shape:
{
  "theme": "...",
  "title": "...",
  "main_character": "...",
  "art_direction": "...",
  "story_summary": "...",
  "pages": [
    {
      "page_number": 1,
      "text": "...",
      "visual": "..."
    }
  ]
}
"""


def normalize_story_output(raw: Dict[str, Any], theme: str) -> Dict[str, Any]:
    pages = raw.get("pages", [])
    if not isinstance(pages, list):
        pages = []

    normalized_pages: List[Dict[str, Any]] = []
    main_character = str(raw.get("main_character", "")).strip()
    art_direction = str(raw.get("art_direction", "")).strip()

    for index, page in enumerate(pages[:5], start=1):
        if not isinstance(page, dict):
            page = {}

        normalized_pages.append(
            {
                "page_number": int(page.get("page_number") or index),
                "text": str(page.get("text", "")).strip(),
                "visual": str(page.get("visual", "")).strip(),
                "main_character": main_character,
                "art_direction": art_direction,
            }
        )

    while len(normalized_pages) < 5:
        page_number = len(normalized_pages) + 1
        normalized_pages.append(
            {
                "page_number": page_number,
                "text": f"{page_number}번째 장의 이야기가 이어졌어요.",
                "visual": "A warm children's book illustration scene.",
                "main_character": main_character,
                "art_direction": art_direction,
            }
        )

    return {
        "theme": str(raw.get("theme") or theme).strip(),
        "title": str(raw.get("title") or "작은 모험 이야기").strip(),
        "main_character": main_character,
        "art_direction": art_direction,
        "story_summary": str(raw.get("story_summary", "")).strip(),
        "pages": normalized_pages,
    }


async def write_storybook_plan(
    theme: str,
    tool_context: ToolContext,
) -> Dict[str, Any]:
    client = OpenAI()

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": STORY_WRITER_SYSTEM_PROMPT},
            {"role": "user", "content": theme},
        ],
        response_format={"type": "json_object"},
        temperature=0.8,
    )

    content = response.choices[0].message.content or "{}"

    try:
        raw_story = json.loads(content)
    except json.JSONDecodeError:
        raw_story = {
            "theme": theme,
            "title": "작은 모험 이야기",
            "main_character": "",
            "art_direction": "",
            "story_summary": "",
            "pages": [],
        }

    story_output = normalize_story_output(raw_story, theme)
    tool_context.state["story_writer_output"] = story_output

    return {
        "status": "complete",
        "message": "동화 기획 데이터가 준비됐어요.",
        "title": story_output.get("title", ""),
        "total_pages": len(story_output.get("pages", [])),
    }
