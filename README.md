# Product Demo Video

将可运行的产品 Demo、原型或设计状态，制作成逐幕确认的 PRD 演示短片或完整产品视频。支持中文或英文说明文字与 TTS、封面先行、点击动效，以及最终视频的底部分幕进度条。

A Codex skill for turning product prototypes into scene-by-scene walkthroughs, with Chinese or English copy and narration, cover-first review, click indicators, and a segmented progress bar.

## 安装

将本仓库链接交给 Codex，并说：

> 请使用 skill-installer 安装这个仓库中 skills/product-demo-video 的 Skill。

也可以下载仓库 ZIP，把 `skills/product-demo-video` 整个文件夹复制到 `~/.codex/skills/product-demo-video`；设置了 `CODEX_HOME` 时放入对应目录的 `skills/` 下。安装后可在下一轮对话使用。安装目录应直接包含 `SKILL.md`、`scripts/`、`references/` 和 `agents/`。

## 开始使用

在 Codex 中提供 Demo 入口、本地项目、原型链接或设计状态：

> 用 $product-demo-video 为这个原型制作演示视频。屏幕说明和旁白都用中文，先和我确认章节，再做封面，然后逐幕制作。

英文版本也可以在中文对话中制作：

> 用 $product-demo-video 做英文版。屏幕说明和 TTS 都用 English，逐幕给我确认。

屏幕文字和旁白可以分别选择语种。默认只生成所选版本，需要中英文两版时明确说明。产品原始 UI 保留其语言；视频的封面、说明和标记使用所选语言。

## 制作流程

1. 检查原型，确认目标、受众、场次顺序、语种和配音方式。
2. 先确认封面文案与视觉静帧，再制作所需动效和配音。
3. 每幕分别确认屏幕文案、TTS 原句与画面安排，通过后制作该幕。
4. 审看片段，修改相关素材，再进入下一幕；已确认音轨可以复用。
5. 按需要交付 PRD 单幕短片，或合成整片并检查节奏、音轨和可见分幕进度条。

完整视频的封面不计正文幕数；进度条从正文开始，每幕一段，按实际时长分配。只有设计状态、没有连线时，可在确认行为后制作带「原型演示」标记的状态演示。

## 运行依赖

- Python 3.9+、Pillow 9.1+。
- FFmpeg 和 ffprobe，需在 PATH 中；FFmpeg 需要 libx264 与 AAC 编码能力。
- 需要豆包旁白时使用 Node.js 20+ 和自己的豆包 TTS API Key。
- 与语言匹配的本地字体。字体未自动找到时，在场景 JSON 的 `font` 中指定字体文件。
- 操作原型所需的浏览器、录制或设计工具，由当前 Codex 环境提供。

可先检查依赖，再按当前环境补齐：

```sh
python3 -c 'import PIL; print(PIL.__version__)'
ffmpeg -version
ffprobe -version
node --version
```

渲染器已在 macOS 实际验证。Linux / Windows 需按本机环境配置依赖和字体；豆包凭据使用下述环境变量方式。

## TTS API 配置

旁白可选豆包、用户录音或已有音轨。豆包配置和短句试听流程见 [豆包旁白指南](skills/product-demo-video/references/doubao.md)。

macOS 可把自己的 API Key 保存在登录钥匙串，项目名称为 `Product Demo Doubao API`，账户名称为 `product-demo-video`。从 Skill 目录检查绑定：

```sh
node scripts/tts-doubao.mjs check
```

使用安全环境变量管理器将 `DOUBAO_TTS_API_KEY` 注入进程的环境，也可以显式使用 `check --from-env` 和 `synthesize --from-env`。Key 由各使用者自行管理。

`dry-run` 可离线检查已确认文案的请求参数，不读取密钥、不调用合成。真实 `synthesize` 使用调用者的 API 额度；费用以服务商账户和计费规则为准。

## 文件结构

```text
README.md
skills/product-demo-video/
  SKILL.md
  agents/openai.yaml
  references/
  scripts/video.py
  scripts/tts-doubao.mjs
```

具体场景输入与命令见 [渲染和导出](skills/product-demo-video/references/render.md)。仓库用于分发 Skill，项目录屏、配音、导出视频和本地配置保存在各自任务目录。
