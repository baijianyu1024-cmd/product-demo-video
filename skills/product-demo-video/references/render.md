# Render and export

Use `scripts/video.py` with Python 3, Pillow, FFmpeg with libx264 and AAC, and ffprobe. Check the available Python for Pillow before suggesting installation.

## One scene from a recording

Keep JSON and raw media in the current task's working area. Media paths are relative to the scene JSON. This existing input format remains supported.

```json
{
  "capture": "captures/citations.mp4",
  "start": 1.2,
  "duration": 8.0,
  "product": "Example product",
  "label": "查看引用",
  "headline": "点开回答里的引用，查看这次回答用到的两篇笔记。",
  "narration": "audio/citations.mp3",
  "narration_at": 0.25,
  "clicks": [{"at": 3.1, "x": 0.68, "y": 0.32}]
}
```

```bash
python3 /path/to/product-demo-video/scripts/video.py render work/citations.json outputs/01-citations.mp4
```

- `capture` supplies one raw video. `start` defaults to zero. `duration` is the exported scene length, including the result hold. The last picture holds when the capture ends early. Without `duration`, the helper uses the longer of the remaining recording and narration plus a short tail. Frame duration rounds up to 30 fps.
- `headline`, `product` and `label` hold the approved on-screen copy. Headline line breaks are preserved and long lines wrap. `font` can name a local font file. An installed CJK font is selected by default.
- `narration` supplies approved audio. `narration_at` defaults to 0.18 seconds. Reuse the audio for visual edits. Prepare local audio cuts separately when changing the narration timeline. The scene must include the entire narration. The helper centers and levels narration in a 48 kHz stereo track, with silence for an unvoiced scene.
- `clicks` add a soft marker only when the original capture needs one. Times are relative to the exported scene. Normalized x and y describe the full visible capture stage, from zero to one.
- `quality` can be `standard` (default, H.264 CRF 18) or `high` (CRF 14). Both retain 1920×1080, 30 fps and 192 kbps AAC. Source resolution still determines available detail.

## Layout and shared project style

Use the approved cover typography, palette and spacing. Confirm product framing and the planned bottom footer space on the first body scene preview, then use them consistently afterward. Keep the original states in full; an approved push-in or pan can be prepared as a single-view frame sequence.

| `layout` | Composition |
| --- | --- |
| `top` | Default. Product and label above the sentence, full capture beneath it. |
| `split` | Product, full sentence and label on the left, full portrait capture on the right. Landscape captures also fit within this display area. |
| `full` | Fits the supplied picture or title artwork to the entire frame, with letterboxing when needed. Set `headline`, `product` and `label` empty because the artwork contains its own text. |

A scene can specify `style: "project-style.json"`. The style JSON supports only `layout`, `font`, `product`, `label` and `quality`. Scene values override those defaults, including empty strings. The style font path is relative to the style JSON. Other scene media paths stay relative to the scene JSON.

The helper draws the supplied text; it does not translate it. Put approved Chinese or English wording directly into `headline`, `product` and `label`, and translate text baked into cover or annotation artwork before rendering. Use a font with the required glyphs and inspect wrapping at normal player size. Keep language choices in the project checkpoint or descriptive `metadata`, not as unsupported style fields. The assembler derives chapter titles from input filenames, so use readable scene file stems in the selected on-screen language. When two versions are requested, use separate language-specific manifests and outputs; set each scene's duration from its own approved narration and recalculate final progress by assembling that version's scenes.

```json
{
  "layout": "split",
  "product": "Example product",
  "label": "原型演示",
  "quality": "high"
}
```

## One scene from approved images or frame sequences

For an approved reconstruction, render its prepared states directly. Supply exactly one of `capture` or `shots`. This keeps edits to the current timeline from silently reusing a stale prebuilt video.

```json
{
  "style": "project-style.json",
  "duration": 8.5,
  "headline": "展开知识条目后，可以放大图片并继续阅读下方的说明。",
  "shots": [
    {"source": "states/collapsed.png", "at": 0},
    {"source": "states/expand-frames", "at": 1.5},
    {"source": "states/detail.png", "at": 2.2},
    {"source": "states/scroll-frames", "at": 5.1},
    {"source": "states/scrolled.png", "at": 6.3}
  ],
  "clicks": [{"at": 1.35, "x": 0.6, "y": 0.18}],
  "swipes": [
    {"at": 5.1, "duration": 1.2, "from": [0.7, 0.8], "to": [0.7, 0.6]}
  ],
  "metadata": {
    "source": "Approved prototype reconstruction from supplied design states"
  }
}
```

Image timelines require explicit `duration`, a first shot at zero, strictly increasing start times at least a frame apart, and a zero or omitted `start`. A shot accepts one PNG/JPEG or a directory of PNG frames sorted by filename. Images hold until the next shot. Directory frames play once from first to last across that shot's interval. Zero-pad sequential frame names. Use a following still shot to hold the transition's final state.

The first image sets the stage aspect ratio. Subsequent images are fitted in full within that fixed stage, with letterboxing if their aspect differs. Prepare related states on the same canvas so normalized click and gesture positions remain consistent.

`swipes` show a touch moving between normalized `from` and `to` positions during the given output-relative `at` and `duration`. They annotate the prepared motion. Scrolling behavior, state contents, form data and transitions must already exist in the source pictures or capture. Keep project-specific composition code with that task.

The direct CLI checks supported rendering fields. Put design node IDs, approved narration wording, source references and other descriptive fields in `metadata`. The legacy `narration_text` field remains accepted as descriptive text. Existing Python wrappers calling `render(scene_path, output)` retain their behavior with custom metadata and a prebuilt capture. When a legacy wrapper supplies both capture and project-specific shots, the helper announces that it is using the prebuilt capture. Migrate new work to one source form.

## Review and complete video

Use a distinct output path for a revision. View the approval composition, then inspect the actual starting screen, action, and readable result at normal player size. Reuse approved narration and source media for corrections.

Confirm the cover still before making the first body scene. A cover can use approved full-frame artwork with `layout: "full"`, empty `headline`, `product` and `label`, and one still in `shots`. Add its approved narration only when requested, holding the cover for the entire line. Keep it separate from the ordered body scenes.

```bash
python3 /path/to/product-demo-video/scripts/video.py assemble outputs/demo.mp4 \
  --opening outputs/cover.mp4 outputs/01-citations.mp4 outputs/02-save.mp4
python3 /path/to/product-demo-video/scripts/video.py verify outputs/demo.mp4
```

Assembly draws a visible segmented progress bar into the MP4 by default. Pass only body scenes as positional inputs. `--opening` prepends the unnumbered cover, without a progress bar, and excludes it from the body segment and chapter count. Omit this option when the requested video has no opening. Do not pass the cover both ways.

Each body scene has one segment. Segment widths follow the final exported frame counts after normalization, with gaps separating scenes. Completed portions stay filled; the current segment fills from left to right; future portions remain muted. The last body frame shows complete progress. Body pictures fit proportionally above a 36-pixel footer, so the bar does not cover buttons, text or results. The opening retains its full frame. Inspect the exported file at normal player size to confirm that the number of segments is visible, boundaries match scene cuts, and the footer remains clear. Recalculate progress when any scene is trimmed, reordered or replaced.

The progress bar requires picture re-encoding. Original approved scene files remain reusable. For an explicitly requested version without the bar, use `--no-progress`; compatible picture frames can then be copied and other formats are normalized using the high quality encoder:

```bash
python3 /path/to/product-demo-video/scripts/video.py assemble outputs/demo-clean.mp4 \
  --no-progress --opening outputs/cover.mp4 outputs/01-citations.mp4 outputs/02-save.mp4
```

Assembly aligns each scene's audio to its exact frame duration, adds silence where required, and encodes one joined audio track. Chapter titles include only body scenes. MP4 chapter readers may extend the first body chapter back to time zero over the opening; the visible progress bar uses the actual output frames and starts after the cover. Check its timing in the exported picture. Whole-file decoding and frame/sample checks run before replacing the output atomically. An output that overlaps any input is rejected.

Review the joined preview for scene order, pauses, results, chapter cuts and the visible progress bar before delivery. The helper handles media composition and encoding. The skill's approval and capture guidance determines which product behavior and source images are appropriate for the video.
