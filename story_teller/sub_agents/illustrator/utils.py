from io import BytesIO
import os
from typing import Any, Dict, List

from PIL import Image, ImageDraw, ImageFont


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


def build_composed_artifact_filename(page_number: int) -> str:
    return f"storybook_page_{page_number}_composed.jpeg"


def build_image_prompt(title: str, page: Dict[str, Any]) -> str:
    text = page.get("text", "")
    visual = page.get("visual", "")
    main_character = page.get("main_character", "")
    art_direction = page.get("art_direction", "")
    return (
        "Create a warm children's picture book illustration. "
        "Use a premium children's book style with soft watercolor texture, "
        "gentle cinematic lighting, rich but calm colors, rounded shapes, "
        "expressive friendly characters, clear page composition, and no readable text in the image. "
        "Make it suitable for a portrait storybook page. "
        f"Story title: {title}. "
        f"Main character: {main_character}. "
        f"Art direction: {art_direction}. "
        f"Page text for context: {text}. "
        f"Illustration scene: {visual}."
    )


def load_storybook_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    font_paths = [
        "/System/Library/Fonts/AppleSDGothicNeo.ttc",
        "/System/Library/Fonts/Supplemental/AppleGothic.ttf",
        "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for font_path in font_paths:
        if os.path.exists(font_path):
            return ImageFont.truetype(font_path, size=size)
    return ImageFont.load_default()


def measure_text_width(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
) -> int:
    if not text:
        return 0
    bbox = draw.textbbox((0, 0), text, font=font)
    return bbox[2] - bbox[0]


def wrap_story_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    max_width: int,
) -> List[str]:
    lines = []
    current = ""

    for token in text.split():
        candidate = token if not current else f"{current} {token}"
        if measure_text_width(draw, candidate, font) <= max_width:
            current = candidate
            continue

        if current:
            lines.append(current)
            current = ""

        token_line = ""
        for char in token:
            char_candidate = f"{token_line}{char}"
            if measure_text_width(draw, char_candidate, font) <= max_width:
                token_line = char_candidate
            else:
                if token_line:
                    lines.append(token_line)
                token_line = char
        current = token_line

    if current:
        lines.append(current)

    return lines or [text]


def compose_storybook_page_image(
    image_bytes: bytes,
    page_number: int,
    text: str,
) -> bytes:
    image = Image.open(BytesIO(image_bytes)).convert("RGB")
    width, height = image.size
    margin_height = max(int(height * 0.28), 280)
    canvas = Image.new("RGB", (width, height + margin_height), "#fbf7ef")
    canvas.paste(image, (0, 0))

    draw = ImageDraw.Draw(canvas)
    padding_x = max(int(width * 0.075), 48)
    padding_top = max(int(margin_height * 0.16), 36)
    title_font = load_storybook_font(max(int(width * 0.034), 28))
    body_font_size = max(int(width * 0.043), 34)
    body_font = load_storybook_font(body_font_size)
    title_color = "#8a7258"
    text_color = "#2d2926"

    y = height + padding_top
    draw.text((padding_x, y), f"{page_number}번째 장", fill=title_color, font=title_font)
    title_bbox = draw.textbbox((padding_x, y), f"{page_number}번째 장", font=title_font)
    y = title_bbox[3] + max(int(margin_height * 0.08), 22)

    max_text_width = width - (padding_x * 2)
    line_spacing = max(int(body_font_size * 0.45), 14)
    available_height = height + margin_height - y - padding_top

    lines = wrap_story_text(draw, text, body_font, max_text_width)
    while len(lines) * (body_font_size + line_spacing) > available_height and body_font_size > 24:
        body_font_size -= 2
        body_font = load_storybook_font(body_font_size)
        line_spacing = max(int(body_font_size * 0.45), 12)
        lines = wrap_story_text(draw, text, body_font, max_text_width)

    for line in lines:
        draw.text((padding_x, y), line, fill=text_color, font=body_font)
        line_bbox = draw.textbbox((padding_x, y), line, font=body_font)
        y = line_bbox[3] + line_spacing

    output = BytesIO()
    canvas.save(output, format="JPEG", quality=92, optimize=True)
    return output.getvalue()


def resize_storybook_image_bytes(image_bytes: bytes, scale: float) -> bytes:
    image = Image.open(BytesIO(image_bytes)).convert("RGB")
    if scale <= 0 or scale == 1:
        return image_bytes

    width, height = image.size
    resized_size = (max(int(width * scale), 1), max(int(height * scale), 1))
    resized = image.resize(resized_size, Image.Resampling.LANCZOS)

    output = BytesIO()
    resized.save(output, format="JPEG", quality=90, optimize=True)
    return output.getvalue()


def build_final_storybook_summary(story_output: Dict[str, Any]) -> str:
    title = story_output.get("title", "완성된 동화책")
    pages: List[Dict[str, Any]] = story_output.get("pages", [])

    lines = [
        f"📚 {title}",
        "",
        "동화책 페이지 조립이 완료됐어요.",
        "완성 페이지 이미지는 왼쪽 Artifacts 탭에서 확인할 수 있어요.",
        "",
    ]

    for page in pages:
        page_number = page.get("page_number", "")
        text = page.get("text", "")
        composed_artifact = page.get("composed_image_artifact") or page.get("image_artifact", "")
        lines.extend(
            [
                f"Page {page_number}",
                text,
                f"> {composed_artifact}",
                "",
            ]
        )

    lines.append("완성입니다.")
    return "\n".join(lines).strip()


def build_progress_payload(
    current_step: str,
    pages: List[Dict[str, Any]],
    generated_images: List[Dict[str, Any]],
) -> Dict[str, Any]:
    completed_pages = {image.get("page_number") for image in generated_images}
    page_statuses = []

    for page in pages:
        page_number = page.get("page_number")
        prompt_artifact = page.get("prompt_artifact")
        image_artifact = page.get("image_artifact")
        status = "complete" if page_number in completed_pages else "pending"
        if prompt_artifact and status == "pending":
            status = "prompt_ready"

        page_statuses.append(
            {
                "page_number": page_number,
                "status": status,
                "prompt_artifact": prompt_artifact,
                "image_artifact": image_artifact,
            }
        )

    return {
        "current_step": current_step,
        "total_pages": len(pages),
        "completed_pages": len(generated_images),
        "pages": page_statuses,
    }


def build_progress_markdown(progress: Dict[str, Any]) -> str:
    lines = [
        "# 동화책 생성 진행 상황",
        "",
        f"현재 단계: {progress.get('current_step', '')}",
        f"완성된 장면: {progress.get('completed_pages', 0)} / {progress.get('total_pages', 0)}",
        "",
    ]

    for page in progress.get("pages", []):
        status_label = {
            "complete": "완성",
            "pending": "대기 중",
            "prompt_ready": "그림 설명 준비 완료",
        }.get(page.get("status"), page.get("status"))
        lines.append(
            "- {page_number}번째 장: {status} | 그림 설명: {prompt_artifact} | 삽화: {image_artifact}".format(
                page_number=page.get("page_number"),
                status=status_label,
                prompt_artifact=page.get("prompt_artifact") or "-",
                image_artifact=page.get("image_artifact") or "-",
            )
        )

    return "\n".join(lines).strip() + "\n"


def build_storybook_markdown(story_output: Dict[str, Any]) -> str:
    title = story_output.get("title", "완성된 동화책")
    theme = story_output.get("theme", "")
    story_summary = story_output.get("story_summary", "")
    main_character = story_output.get("main_character", "")
    art_direction = story_output.get("art_direction", "")
    pages: List[Dict[str, Any]] = story_output.get("pages", [])

    lines = [f"# {title}", ""]
    if theme:
        lines.extend([f"주제: {theme}", ""])
    if story_summary:
        lines.extend([f"줄거리: {story_summary}", ""])
    if main_character:
        lines.extend([f"주인공: {main_character}", ""])
    if art_direction:
        lines.extend([f"그림 분위기: {art_direction}", ""])

    for page in pages:
        page_number = page.get("page_number", "")
        text = page.get("text", "")
        visual = page.get("visual", "")
        prompt_artifact = page.get("prompt_artifact", "")
        image_artifact = page.get("image_artifact", "")

        lines.extend(
            [
                f"## {page_number}번째 장",
                "",
                f"글: {text}",
                "",
                f"그림 설명: {visual}",
                "",
            ]
        )
        if prompt_artifact:
            lines.extend([f"그림 설명 파일: {prompt_artifact}", ""])
        if image_artifact:
            lines.extend([f"삽화 파일: {image_artifact}", ""])

    return "\n".join(lines).strip() + "\n"


def build_screen_parts_payload(
    story_output: Dict[str, Any],
    image_data_uris: Dict[str, str],
    include_page_text: bool = True,
) -> List[Dict[str, str]]:
    title = story_output.get("title", "완성된 동화책")
    theme = story_output.get("theme", "")
    story_summary = story_output.get("story_summary", "")
    main_character = story_output.get("main_character", "")
    art_direction = story_output.get("art_direction", "")
    pages: List[Dict[str, Any]] = story_output.get("pages", [])

    cover_lines = [
        "# 📚 완성된 동화책",
        "",
        f"# {title}",
    ]

    if theme:
        cover_lines.extend(["", f"**주제**: {theme}"])
    if story_summary:
        cover_lines.extend(["", f"**줄거리**: {story_summary}"])
    if main_character:
        cover_lines.extend(["", f"**주인공**: {main_character}"])
    if art_direction:
        cover_lines.extend(["", f"**그림 분위기**: {art_direction}"])

    cover_lines.extend(
        [
            "",
            "---",
            "",
            "이제 표지부터 마지막 장까지 순서대로 보여드릴게요.",
        ]
    )

    screen_parts = [
        {
            "type": "text",
            "text": "\n".join(cover_lines).strip(),
        }
    ]

    for page in pages:
        page_number = page.get("page_number", "")
        image_artifact = page.get("image_artifact", "")
        image_data_uri = image_data_uris.get(image_artifact, "")

        screen_parts.append(
            {
                "type": "text",
                "text": f"## {page_number}번째 장",
            }
        )

        if image_data_uri.startswith("data:") and ";base64," in image_data_uri:
            header, data_b64 = image_data_uri.split(";base64,", 1)
            screen_parts.append(
                {
                    "type": "image",
                    "mime_type": header.removeprefix("data:"),
                    "data": data_b64,
                }
            )
        else:
            screen_parts.append(
                {
                    "type": "text",
                    "text": f"삽화 파일 `{image_artifact}`를 화면에 불러오지 못했어요.",
                }
            )

        if include_page_text:
            screen_parts.append(
                {
                    "type": "text",
                    "text": page.get("text", "").strip(),
                }
            )

    screen_parts.append(
        {
            "type": "text",
            "text": (
                "---\n\n"
                "🎉 동화책 전체가 완성됐어요.\n\n"
                "원본 파일은 Artifacts에서 `storybook.html`, `storybook.md`, "
                "`storybook_manifest.json`으로도 확인할 수 있어요."
            ),
        }
    )

    return screen_parts


def build_storybook_html(
    story_output: Dict[str, Any],
    image_data_uris: Dict[str, str],
) -> str:
    title = story_output.get("title", "완성된 동화책")
    theme = story_output.get("theme", "")
    story_summary = story_output.get("story_summary", "")
    pages: List[Dict[str, Any]] = story_output.get("pages", [])

    page_sections = []
    for page in pages:
        page_number = page.get("page_number", "")
        text = page.get("text", "")
        visual = page.get("visual", "")
        image_artifact = page.get("image_artifact", "")
        image_src = image_data_uris.get(image_artifact, "")
        image_html = (
            f'<img src="{image_src}" alt="{visual}" />'
            if image_src
            else '<div class="missing-image">삽화 파일을 찾을 수 없어요.</div>'
        )

        page_sections.append(
            f"""
            <section class="book-page">
              <div class="page-number">{page_number}번째 장</div>
              <div class="illustration">{image_html}</div>
              <p class="story-text">{text}</p>
            </section>
            """
        )

    return f"""<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{title}</title>
  <style>
    :root {{
      color-scheme: light;
      font-family: -apple-system, BlinkMacSystemFont, "Apple SD Gothic Neo", "Noto Sans KR", sans-serif;
      background: #f7f1e8;
      color: #2d2926;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background: #f7f1e8;
    }}
    .book {{
      width: min(920px, 100%);
      margin: 0 auto;
      padding: 40px 20px 64px;
    }}
    .cover {{
      min-height: 72vh;
      display: grid;
      align-content: center;
      gap: 18px;
      text-align: center;
      padding: 48px 24px;
    }}
    h1 {{
      margin: 0;
      font-size: clamp(40px, 8vw, 78px);
      line-height: 1.05;
      letter-spacing: 0;
    }}
    .theme,
    .summary {{
      margin: 0 auto;
      max-width: 680px;
      font-size: 20px;
      line-height: 1.7;
    }}
    .book-page {{
      min-height: 100vh;
      display: grid;
      align-content: center;
      gap: 20px;
      padding: 44px 0;
      break-after: page;
    }}
    .page-number {{
      font-size: 15px;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0;
      color: #76695f;
    }}
    .illustration {{
      width: 100%;
      overflow: hidden;
      border-radius: 8px;
      background: #eadfce;
      box-shadow: 0 18px 48px rgba(51, 39, 28, 0.18);
    }}
    .illustration img {{
      display: block;
      width: 100%;
      aspect-ratio: 2 / 3;
      object-fit: cover;
    }}
    .missing-image {{
      min-height: 520px;
      display: grid;
      place-items: center;
      color: #76695f;
    }}
    .story-text {{
      margin: 0;
      padding: 0 8px;
      font-size: clamp(24px, 4vw, 36px);
      line-height: 1.55;
      font-weight: 700;
      word-break: keep-all;
    }}
    @media print {{
      body {{ background: white; }}
      .book {{ padding: 0; width: 100%; }}
      .cover, .book-page {{ min-height: 100vh; padding: 32px; }}
      .illustration {{ box-shadow: none; }}
    }}
  </style>
</head>
<body>
  <main class="book">
    <section class="cover">
      <h1>{title}</h1>
      <p class="theme">{theme}</p>
      <p class="summary">{story_summary}</p>
    </section>
    {"".join(page_sections)}
  </main>
</body>
</html>
"""


def compose_full_storybook_preview_image(
    story_output: Dict[str, Any],
    page_images: List[bytes],
    target_width: int = 900,
) -> bytes:
    title = story_output.get("title", "완성된 동화책")
    theme = story_output.get("theme", "")
    story_summary = story_output.get("story_summary", "")

    title_font = load_storybook_font(58)
    subtitle_font = load_storybook_font(30)
    body_font = load_storybook_font(28)

    cover_height = 900
    padding = 72
    gap = 42

    cover = Image.new("RGB", (target_width, cover_height), "#fbf7ef")
    draw = ImageDraw.Draw(cover)

    y = 140
    draw.text((padding, y), "완성된 동화책", fill="#8a7258", font=subtitle_font)
    y += 72

    title_lines = wrap_story_text(draw, title, title_font, target_width - padding * 2)
    for line in title_lines:
        draw.text((padding, y), line, fill="#2d2926", font=title_font)
        bbox = draw.textbbox((padding, y), line, font=title_font)
        y = bbox[3] + 20

    if theme:
        y += 40
        draw.text((padding, y), f"주제: {theme}", fill="#5f554d", font=body_font)
        y += 48

    if story_summary:
        y += 20
        summary_lines = wrap_story_text(
            draw,
            story_summary,
            body_font,
            target_width - padding * 2,
        )
        for line in summary_lines:
            draw.text((padding, y), line, fill="#5f554d", font=body_font)
            bbox = draw.textbbox((padding, y), line, font=body_font)
            y = bbox[3] + 14

    resized_pages: List[Image.Image] = [cover]

    for image_bytes in page_images:
        page_image = Image.open(BytesIO(image_bytes)).convert("RGB")
        width, height = page_image.size
        ratio = target_width / width
        resized_height = max(int(height * ratio), 1)
        page_image = page_image.resize(
            (target_width, resized_height),
            Image.Resampling.LANCZOS,
        )
        resized_pages.append(page_image)

    total_height = sum(image.height for image in resized_pages) + gap * (len(resized_pages) - 1)
    canvas = Image.new("RGB", (target_width, total_height), "#f7f1e8")

    y = 0
    for image in resized_pages:
        canvas.paste(image, (0, y))
        y += image.height + gap

    output = BytesIO()
    canvas.save(output, format="JPEG", quality=90, optimize=True)
    return output.getvalue()


def compose_full_storybook_preview_image(
    story_output: Dict[str, Any],
    page_images: List[bytes],
    target_width: int = 900,
) -> bytes:
    title = story_output.get("title", "완성된 동화책")
    theme = story_output.get("theme", "")
    story_summary = story_output.get("story_summary", "")

    title_font = load_storybook_font(58)
    subtitle_font = load_storybook_font(30)
    body_font = load_storybook_font(28)

    cover_height = 900
    padding = 72
    gap = 42

    cover = Image.new("RGB", (target_width, cover_height), "#fbf7ef")
    draw = ImageDraw.Draw(cover)

    y = 140
    draw.text((padding, y), "완성된 동화책", fill="#8a7258", font=subtitle_font)
    y += 72

    title_lines = wrap_story_text(draw, title, title_font, target_width - padding * 2)
    for line in title_lines:
        draw.text((padding, y), line, fill="#2d2926", font=title_font)
        bbox = draw.textbbox((padding, y), line, font=title_font)
        y = bbox[3] + 20

    if theme:
        y += 40
        draw.text((padding, y), f"주제: {theme}", fill="#5f554d", font=body_font)
        y += 48

    if story_summary:
        y += 20
        summary_lines = wrap_story_text(
            draw,
            story_summary,
            body_font,
            target_width - padding * 2,
        )
        for line in summary_lines:
            draw.text((padding, y), line, fill="#5f554d", font=body_font)
            bbox = draw.textbbox((padding, y), line, font=body_font)
            y = bbox[3] + 14

    resized_pages: List[Image.Image] = [cover]

    for image_bytes in page_images:
        page_image = Image.open(BytesIO(image_bytes)).convert("RGB")
        width, height = page_image.size
        ratio = target_width / width
        resized_height = max(int(height * ratio), 1)
        page_image = page_image.resize(
            (target_width, resized_height),
            Image.Resampling.LANCZOS,
        )
        resized_pages.append(page_image)

    total_height = sum(image.height for image in resized_pages) + gap * (len(resized_pages) - 1)
    canvas = Image.new("RGB", (target_width, total_height), "#f7f1e8")

    y = 0
    for image in resized_pages:
        canvas.paste(image, (0, y))
        y += image.height + gap

    output = BytesIO()
    canvas.save(output, format="JPEG", quality=90, optimize=True)
    return output.getvalue()
