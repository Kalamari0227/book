from io import BytesIO
import os
from typing import Any, Dict, List

from PIL import Image, ImageDraw, ImageFont, ImageStat


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

def strip_thumbnail_card_frame(image: Image.Image) -> Image.Image:
    """
    Generated page images are displayed as thumbnail cards during progress.
    For the final storybook, remove the warm outer card frame so the caption
    is composed directly on the illustration.
    """
    image = image.convert("RGB")
    width, height = image.size

    # Only small progress thumbnails should be cropped.
    # Raw generated images are much larger and should pass through unchanged.
    if width > 420:
        return image

    if width < 180 or height < 180:
        return image

    # Thumbnail card background is warm beige. If corners are not close to that,
    # assume this is not a thumbnail card.
    expected = (247, 241, 232)
    corner_points = [
        (2, 2),
        (max(width - 3, 0), 2),
        (2, max(height - 3, 0)),
        (max(width - 3, 0), max(height - 3, 0)),
    ]

    def color_distance(c1, c2):
        return sum(abs(int(c1[i]) - int(c2[i])) for i in range(3))

    corner_colors = [image.getpixel(point) for point in corner_points]
    avg_distance = sum(color_distance(color, expected) for color in corner_colors) / len(corner_colors)

    if avg_distance > 55:
        return image

    padding = max(int(width * 0.06), 14)
    shadow_offset = max(int(width * 0.012), 3)

    left = padding
    top = padding
    right = max(width - padding - shadow_offset, left + 1)
    bottom = max(height - padding - shadow_offset, top + 1)

    cropped = image.crop((left, top, right, bottom))
    return cropped


def compose_storybook_page_image(
    image_bytes: bytes,
    page_number: int,
    text: str,
) -> bytes:
    image = Image.open(BytesIO(image_bytes)).convert("RGB")
    image = strip_thumbnail_card_frame(image)
    width, height = image.size

    canvas = image.copy().convert("RGBA")

    # 이미지 하단 색감을 가져와 패널 색과 자연스럽게 섞는다.
    sample_height = max(int(height * 0.12), 24)
    bottom_strip = image.crop((0, height - sample_height, width, height))
    avg = ImageStat.Stat(bottom_strip).mean
    sampled_color = tuple(int(v) for v in avg[:3])

    paper_color = (250, 242, 225)
    ink_color = "#2d2926"

    def blend(c1, c2, ratio: float):
        return tuple(int(c1[i] * (1 - ratio) + c2[i] * ratio) for i in range(3))

    panel_base = blend(sampled_color, paper_color, 0.74)

    # 패널을 더 작게: 최종 300px 미리보기 기준 캡션 느낌.
    panel_width = int(width * 0.82)
    panel_height = max(int(height * 0.125), int(width * 0.22), 58)

    panel_x = (width - panel_width) // 2
    panel_y = height - panel_height - max(int(height * 0.050), 14)
    radius = max(int(width * 0.030), 8)

    overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    overlay_draw = ImageDraw.Draw(overlay)

    shadow_offset = max(int(width * 0.010), 2)
    overlay_draw.rounded_rectangle(
        (
            panel_x + shadow_offset,
            panel_y + shadow_offset,
            panel_x + panel_width + shadow_offset,
            panel_y + panel_height + shadow_offset,
        ),
        radius=radius,
        fill=(58, 44, 32, 26),
    )

    overlay_draw.rounded_rectangle(
        (panel_x, panel_y, panel_x + panel_width, panel_y + panel_height),
        radius=radius,
        fill=(*panel_base, 205),
        outline=(255, 250, 238, 120),
        width=max(int(width * 0.003), 1),
    )

    canvas = Image.alpha_composite(canvas, overlay).convert("RGB")
    draw = ImageDraw.Draw(canvas)

    padding_x = max(int(panel_width * 0.075), 14)
    padding_y = max(int(panel_height * 0.16), 9)

    body_font_size = max(int(width * 0.045), 13)
    body_font = load_storybook_font(body_font_size)

    max_text_width = panel_width - padding_x * 2
    line_spacing = max(int(body_font_size * 0.26), 3)

    lines = wrap_story_text(draw, text, body_font, max_text_width)

    def body_height() -> int:
        total = 0
        for line in lines:
            bbox = draw.textbbox((0, 0), line, font=body_font)
            total += bbox[3] - bbox[1]
        total += line_spacing * max(len(lines) - 1, 0)
        return total

    available_height = panel_height - padding_y * 2

    while body_height() > available_height and body_font_size > 9:
        body_font_size -= 1
        body_font = load_storybook_font(body_font_size)
        line_spacing = max(int(body_font_size * 0.24), 3)
        lines = wrap_story_text(draw, text, body_font, max_text_width)

    text_x = panel_x + padding_x
    text_y = panel_y + max(int((panel_height - body_height()) / 2), padding_y)

    for line in lines:
        draw.text((text_x, text_y), line, fill=ink_color, font=body_font)
        bbox = draw.textbbox((text_x, text_y), line, font=body_font)
        text_y += (bbox[3] - bbox[1]) + line_spacing

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

    padding = max(int(target_width * 0.085), 22)
    gap = max(int(target_width * 0.065), 16)

    title_font_size = max(int(target_width * 0.092), 22)
    subtitle_font_size = max(int(target_width * 0.046), 13)
    body_font_size = max(int(target_width * 0.044), 12)

    title_font = load_storybook_font(title_font_size)
    subtitle_font = load_storybook_font(subtitle_font_size)
    body_font = load_storybook_font(body_font_size)

    dummy = Image.new("RGB", (target_width, 1), "#fbf7ef")
    draw = ImageDraw.Draw(dummy)

    max_text_width = target_width - padding * 2

    title_lines = wrap_story_text(draw, title, title_font, max_text_width)
    theme_text = f"주제: {theme}" if theme else ""
    theme_lines = wrap_story_text(draw, theme_text, body_font, max_text_width) if theme_text else []
    summary_lines = wrap_story_text(draw, story_summary, body_font, max_text_width) if story_summary else []

    title_line_height = title_font_size + max(int(title_font_size * 0.24), 5)
    body_line_height = body_font_size + max(int(body_font_size * 0.38), 5)

    cover_height = max(
        int(target_width * 1.42),
        padding * 2
        + max(int(target_width * 0.16), 44)
        + len(title_lines) * title_line_height
        + max(int(target_width * 0.12), 28)
        + len(theme_lines) * body_line_height
        + max(int(target_width * 0.05), 12)
        + min(len(summary_lines), 3) * body_line_height
        + max(int(target_width * 0.12), 28),
    )

    cover = Image.new("RGB", (target_width, cover_height), "#f7f1e8")
    draw = ImageDraw.Draw(cover)

    # 종이 질감 느낌의 안쪽 카드
    inner_margin = max(int(target_width * 0.055), 14)
    card_box = (
        inner_margin,
        inner_margin,
        target_width - inner_margin,
        cover_height - inner_margin,
    )

    draw.rounded_rectangle(
        card_box,
        radius=max(int(target_width * 0.035), 10),
        fill="#fbf7ef",
        outline="#eadcc7",
        width=max(int(target_width * 0.006), 1),
    )

    # 상단 작은 장식
    deco_y = padding + max(int(target_width * 0.02), 6)
    line_x1 = padding
    line_x2 = target_width - padding
    draw.line(
        (line_x1, deco_y, line_x2, deco_y),
        fill="#d6c3aa",
        width=max(int(target_width * 0.004), 1),
    )

    dot_radius = max(int(target_width * 0.010), 3)
    dot_x = target_width // 2
    draw.ellipse(
        (
            dot_x - dot_radius,
            deco_y - dot_radius,
            dot_x + dot_radius,
            deco_y + dot_radius,
        ),
        fill="#c7a57f",
    )

    y = padding + max(int(target_width * 0.16), 44)

    # 작은 표지 라벨
    label = "A LITTLE STORYBOOK"
    label_bbox = draw.textbbox((0, 0), label, font=subtitle_font)
    label_width = label_bbox[2] - label_bbox[0]
    draw.text(
        ((target_width - label_width) // 2, y),
        label,
        fill="#9a7b5f",
        font=subtitle_font,
    )
    y += max(int(target_width * 0.095), 26)

    # 제목 중앙 정렬
    for line in title_lines:
        bbox = draw.textbbox((0, 0), line, font=title_font)
        line_width = bbox[2] - bbox[0]
        draw.text(
            ((target_width - line_width) // 2, y),
            line,
            fill="#2d2926",
            font=title_font,
        )
        y += title_line_height

    # 제목 아래 장식선
    y += max(int(target_width * 0.04), 10)
    short_line = max(int(target_width * 0.32), 72)
    draw.line(
        (
            (target_width - short_line) // 2,
            y,
            (target_width + short_line) // 2,
            y,
        ),
        fill="#d8c3a8",
        width=max(int(target_width * 0.005), 1),
    )
    y += max(int(target_width * 0.08), 20)

    # 주제와 요약은 작게, 너무 길면 3줄까지만
    info_lines = theme_lines + summary_lines[:3]
    for line in info_lines:
        bbox = draw.textbbox((0, 0), line, font=body_font)
        line_width = bbox[2] - bbox[0]
        draw.text(
            ((target_width - line_width) // 2, y),
            line,
            fill="#6f5f52",
            font=body_font,
        )
        y += body_line_height

    # 하단 장식
    footer = "made with story agents"
    footer_bbox = draw.textbbox((0, 0), footer, font=subtitle_font)
    footer_width = footer_bbox[2] - footer_bbox[0]
    draw.text(
        (
            (target_width - footer_width) // 2,
            cover_height - padding - subtitle_font_size,
        ),
        footer,
        fill="#b19a81",
        font=subtitle_font,
    )

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


def resize_storybook_image_to_width(image_bytes: bytes, target_width: int) -> bytes:
    image = Image.open(BytesIO(image_bytes)).convert("RGB")
    width, height = image.size

    if target_width <= 0 or width == target_width:
        return image_bytes

    ratio = target_width / width
    resized_height = max(int(height * ratio), 1)

    resized = image.resize(
        (target_width, resized_height),
        Image.Resampling.LANCZOS,
    )

    output = BytesIO()
    resized.save(output, format="JPEG", quality=90, optimize=True)
    return output.getvalue()


def create_storybook_thumbnail_card(
    image_bytes: bytes,
    target_width: int = 300,
) -> bytes:
    image = Image.open(BytesIO(image_bytes)).convert("RGB")

    inner_width = max(int(target_width * 0.88), 1)
    width, height = image.size
    ratio = inner_width / width
    inner_height = max(int(height * ratio), 1)

    resized = image.resize(
        (inner_width, inner_height),
        Image.Resampling.LANCZOS,
    )

    padding = max(int(target_width * 0.06), 14)
    shadow_offset = max(int(target_width * 0.012), 3)

    card_width = target_width
    card_height = inner_height + padding * 2

    canvas = Image.new(
        "RGB",
        (card_width + shadow_offset, card_height + shadow_offset),
        "#f7f1e8",
    )

    shadow = Image.new(
        "RGB",
        (inner_width, inner_height),
        "#d8c7b3",
    )

    image_x = padding
    image_y = padding

    canvas.paste(shadow, (image_x + shadow_offset, image_y + shadow_offset))
    canvas.paste(resized, (image_x, image_y))

    draw = ImageDraw.Draw(canvas)

    border_color = "#fff8ec"
    draw.rectangle(
        (
            image_x,
            image_y,
            image_x + inner_width - 1,
            image_y + inner_height - 1,
        ),
        outline=border_color,
        width=max(int(target_width * 0.006), 1),
    )

    output = BytesIO()
    canvas.save(output, format="JPEG", quality=90, optimize=True)
    return output.getvalue()
