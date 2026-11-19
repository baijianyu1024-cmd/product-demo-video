# Product Demo Video

将可运行的产品 Demo、原型或设计状态，制作成逐幕确认的 PRD 演示短片或完整产品视频。支持中文或英文说明文字与 TTS、封面先行、点击动效，以及最终视频的底部分幕进度条。

A portable Agent Skills workflow for scene-by-scene product walkthroughs, with Chinese or English copy and narration, cover-first review, click indicators, and a segmented progress bar.

## 适用 Agent 与安装

本项目按 [Agent Skills](https://agentskills.io/specification) 目录结构分发。核心流程共用，技能发现、安装入口、命令执行和媒体预览取决于宿主。请安装完整目录，保留 `scripts/` 和 `references/`。

| Agent | 安装与调用 | 当前验证范围 |
| --- | --- | --- |
| Codex | 使用 `skill-installer` 安装本仓库的 `skills/product-demo-video`；本次使用的本地目录为 `~/.codex/skills/product-demo-video/`，自定义 `CODEX_HOME` 时沿用对应目录。可用 `$product-demo-video` 调用。 | Codex/macOS 制作与渲染已实测 |
| Claude Code | 项目 `.claude/skills/product-demo-video/` 或个人 `~/.claude/skills/product-demo-video/`；使用 `/product-demo-video`。 | 原生技能入口有官方依据，本 Skill 待端到端实测 |
| Cursor | 项目 `.cursor/skills/product-demo-video/` 或个人 `~/.cursor/skills/product-demo-video/`；在 Agent 聊天的 `/` 菜单选择。 | 原生技能入口有官方依据，本 Skill 待端到端实测 |
| VS Code / GitHub Copilot | 项目 `.github/skills/product-demo-video/` 或个人 `~/.copilot/skills/product-demo-video/`；在 `/` 菜单选择。 | 原生技能入口有官方依据，本 Skill 待端到端实测 |
| WorkBuddy | 下载下方独立 ZIP，在「专家·技能·连接器 → 技能 → 添加技能 → 上传技能」导入。代码项目也支持 `.codebuddy/skills/product-demo-video/`。 | 本地技能包导入有官方依据，执行依赖和完整视频制作待实测 |
| 豆包工作 | 下载独立 ZIP，在「技能・连接器・伙伴」中使用本地技能导入入口；以当前客户端可接受的包格式为准。 | 官方支持自定义技能和本地导入；Python/Node/FFmpeg 及完整视频制作待实测 |

**本地包导入：** [下载独立 Skill ZIP](dist/product-demo-video.zip)。包内根目录直接包含 `SKILL.md`，适合上传型入口尝试导入。它与 GitHub 的「Download ZIP」整仓包不同；整仓包用于获取源码或手动复制 `skills/product-demo-video`。宿主导入成功后，再检查执行环境和首幕样片。

若 Agent 没有原生技能安装入口，但能读取文件并执行命令，也可提供完整 Skill 文件夹，让它先读取 `SKILL.md` 及引用资料。实际制作仍需要下方运行依赖与原型素材。

`agents/openai.yaml` 是 OpenAI 宿主的可选配置；其他 Agent 的接入不依赖它。安装能力和视频制作能力分别核对，详细差异、首次运行方法及官方资料见 [不同 Agent 的接入说明](skills/product-demo-video/references/hosts.md)。官方入口核对日期：2026-11-18。

## 开始使用

在所用 Agent 中提供 Demo 入口、本地项目、原型链接或设计状态：

> 使用 product-demo-video 技能，为这个原型制作演示视频。屏幕说明和旁白都用中文，先和我确认章节，再做封面，然后逐幕制作。

英文版本也可以在中文对话中制作：

> 使用 product-demo-video 技能做英文版。屏幕说明和 TTS 都用 English，逐幕给我确认。

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
- 操作原型所需的浏览器、录制或设计工具，由当前 Agent 环境提供。仅安装技能不会自动添加这些工具。

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
dist/product-demo-video.zip
tools/package_skill.py
skills/product-demo-video/
  SKILL.md
  agents/openai.yaml
  references/
  scripts/video.py
  scripts/tts-doubao.mjs
```

具体场景输入与命令见 [渲染和导出](skills/product-demo-video/references/render.md)。仓库用于分发 Skill，项目录屏、配音、导出视频和本地配置保存在各自任务目录。

维护者可在仓库根运行 `python3 tools/package_skill.py`，从同一份源码更新独立导入包。
