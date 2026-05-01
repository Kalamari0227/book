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
  - text: exactly one short Korean sentence for a picture book caption
  - visual: detailed English image-generation description for the page
- The page text must be warm, simple, and lyrical.
- The page text must fit inside a small caption panel.
- Keep each page text under 34 Korean characters when possible.
- Do not use long clauses, parentheses, bullet points, or multiple sentences in page text.
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


def compact_page_text(value: Any, max_chars: int = 34) -> str:
    text = str(value or "").strip()
    if not text:
        return ""

    # 줄바꿈/중복 공백 제거
    text = " ".join(text.split())

    # 여러 문장이 오면 첫 문장 중심으로 사용
    sentence_endings = ["。", ".", "!", "?", "！", "？"]
    first_cut = len(text)

    for mark in sentence_endings:
        index = text.find(mark)
        if index != -1:
            first_cut = min(first_cut, index + 1)

    text = text[:first_cut].strip()

    # 한국어 종결이 없으면 부드럽게 마무리
    if text and text[-1] not in "요다죠네까.!?。！？":
        text = text.rstrip(",，、") + "요."

    # 너무 길면 자연스럽게 자르고 말줄임 대신 온점으로 마무리
    if len(text) > max_chars:
        text = text[:max_chars].rstrip(" ,，、")
        if text and text[-1] not in ".!?。！？":
            text += "."

    return text


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
                "text": compact_page_text(page.get("text", "")),
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
                "text": compact_page_text("작은 이야기가 조용히 이어졌어요."),
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
        "title": story_output.get("title", ""),
        "total_pages": len(story_output.get("pages", [])),
    }
