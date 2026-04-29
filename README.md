# Story Teller

Google ADK example for a two-agent children's storybook workflow using OpenAI.

## Agents

- `StoryWriterAgent`: receives a theme and writes a structured 5-page children's story.
- `IllustratorAgent`: reads `story_writer_output` from agent state, generates one image artifact per page, and saves a combined storybook artifact.

The root ADK app is a `SequentialAgent`, so the story is written first and the illustrations are generated second.

## State Shape

`StoryWriterAgent` stores this under `tool_context.state["story_writer_output"]`:

```json
{
  "theme": "작은 토끼의 우주 여행",
  "title": "베니의 반짝이는 여행",
  "pages": [
    {
      "page_number": 1,
      "text": "옛날 옛적에, 베니라는 작은 토끼가 살았습니다.",
      "visual": "버섯 집 앞에 서 있는 작은 흰 토끼"
    }
  ]
}
```

`IllustratorAgent` updates each page with `image_artifact`, and saves JPEG artifacts named:

```text
storybook_page_1.jpeg
storybook_page_2.jpeg
storybook_page_3.jpeg
storybook_page_4.jpeg
storybook_page_5.jpeg
```

It also saves combined book artifacts:

```text
storybook.md
storybook_manifest.json
```

`storybook.md` is the readable storybook draft with all page texts, visual descriptions, and image artifact filenames. `storybook_manifest.json` is structured metadata that can be used later to build a PDF, web viewer, or printed book layout.

## Run

Set your OpenAI API key:

```bash
export OPENAI_API_KEY="your-key"
```

Optional image quality settings:

```bash
export STORYBOOK_IMAGE_MODEL="gpt-image-1.5"
export STORYBOOK_IMAGE_QUALITY="high"
export STORYBOOK_IMAGE_SIZE="1024x1536"
```

The defaults already use those values. Lower `STORYBOOK_IMAGE_QUALITY` to `medium` or `low` if you want cheaper/faster test runs.

Install dependencies if needed:

```bash
uv sync
```

Start ADK Web UI from this folder:

```bash
adk web
```

Then choose the `story_teller` app and try a prompt such as:

```text
작은 토끼가 보라색 하늘 아래에서 친구를 찾는 이야기
```

## Test

The unit tests avoid live OpenAI API calls:

```bash
python -m unittest discover -p "test_*.py"
```
