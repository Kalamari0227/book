# Story Teller

Google ADK example for a workflow-agent children's storybook maker using OpenAI.

## Agents

- `StoryWriterAgent`: receives a theme and writes a structured 5-page children's story into agent state.
- `ParallelIllustratorAgent`: runs five page illustrator agents at the same time.
- `PageIllustratorAgent1` through `PageIllustratorAgent5`: each reads one story page and saves one image artifact.
- `StorybookAssemblerAgent`: merges the five image artifacts with the story text and saves the final storybook artifacts.

The root ADK app is a `SequentialAgent`, so the workflow is controlled in this order:

```text
StoryWriterAgent
ParallelIllustratorAgent
StorybookAssemblerAgent
```

The illustration phase uses a `ParallelAgent`:

```text
PageIllustratorAgent1 -> storybook_page_1.jpeg
PageIllustratorAgent2 -> storybook_page_2.jpeg
PageIllustratorAgent3 -> storybook_page_3.jpeg
PageIllustratorAgent4 -> storybook_page_4.jpeg
PageIllustratorAgent5 -> storybook_page_5.jpeg
```

Callbacks update progress state and artifacts with messages such as `스토리 작성 중...`, `이미지 1/5 생성 중...`, and `완성된 동화책 조립 중...`.

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

Each page illustrator stores its own result under `page_image_result_1` through `page_image_result_5`. `StorybookAssemblerAgent` merges those results into `story_writer_output["pages"]` with `image_artifact`, and saves JPEG artifacts named:

```text
storybook_page_1.jpeg
storybook_page_2.jpeg
storybook_page_3.jpeg
storybook_page_4.jpeg
storybook_page_5.jpeg
```

It also saves combined book artifacts:

```text
generation_progress.md
generation_progress.json
storybook_page_1_prompt.md
storybook_page_2_prompt.md
storybook_page_3_prompt.md
storybook_page_4_prompt.md
storybook_page_5_prompt.md
storybook.html
storybook.md
storybook_manifest.json
workflow_progress.md
workflow_progress.json
```

`generation_progress.md` and `generation_progress.json` track image generation status. `workflow_progress.md` and `workflow_progress.json` are written by callbacks and show the workflow-level progress messages. `storybook.html` is the complete viewable storybook with each generated image and its page text combined into a page layout. `storybook.md` is the readable draft with page metadata. `storybook_manifest.json` is structured metadata that can be used later to build a PDF, web viewer, or printed book layout.

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

Demo prompts for the assignment:

```text
용감한 아기 고양이 이야기
```

```text
달빛 정원에서 길을 찾는 작은 로봇 이야기
```

## Test

The unit tests avoid live OpenAI API calls:

```bash
python -m unittest discover -p "test_*.py"
```
