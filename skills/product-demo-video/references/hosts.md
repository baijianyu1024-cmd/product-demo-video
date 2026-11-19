# 在不同 Agent 中使用

本 Skill 的核心是 SKILL.md、参考资料和独立 Python/Node 脚本。宿主加载当前目录后，使用同一套封面先行、逐幕确认、中英文选择和合成流程。相对路径从实际 Skill 目录解析。`agents/openai.yaml` 是 OpenAI 宿主的可选配置，其他宿主不必识别其中的展示或调用设置。

## 先确定本次能做什么

| 能力 | 对制作的影响 | 缺少时的处理 |
| --- | --- | --- |
| 读取 Skill 目录及原型素材、写入任务目录 | 找到 scripts/references，保存可复用素材和导出文件 | 使用宿主授权的项目目录或上传完整文件夹；不要只加载孤立的 SKILL.md |
| 执行 Python、Pillow、FFmpeg/ffprobe；需要豆包时执行 Node.js | 运行本 Skill 的渲染、合成、音轨检查与 TTS 适配器 | 先完成文案和素材方案，说明尚需执行环境；不把脚本计划当成已导出的 MP4 |
| 浏览器、桌面或设计工具 | 走真实交互、录屏或导出设计状态 | 使用用户提供的录屏/状态图，按已确认行为制作标记清楚的原型演示 |
| 音视频/图片预览与文件交付 | 审核开始、动作、结果及旁白，交付可播放文件 | 用宿主能展示的预览或实际文件下载；未能播放检查的部分如实说明 |

先辨认命令在用户电脑、本地沙箱还是云端容器执行。操作范围、依赖、文件路径和 API 配置都以实际执行环境为准；用户电脑装有 FFmpeg 或已有登录，不代表容器自动可用。使用当前宿主提供的工具和权限流程，不照搬别的 Agent 的工具名或配置文件。

## 各类宿主的接入差别

- **Codex / Claude Code / Cursor / VS Code Copilot**：按各宿主支持的技能目录安装完整文件夹。激活语法不同；Codex 可用 `$product-demo-video`，Claude Code 可用 `/product-demo-video`，Cursor / VS Code 可在 `/` 菜单选择。激活后仍需核对可执行工具及素材访问。
- **WorkBuddy**：官方自定义技能入口为「专家·技能·连接器 → 技能 → 添加技能 → 上传技能」。对话中查找安装对应其技能市场，不把任意 GitHub URL 当作必定可安装。代码项目也可使用 `.codebuddy/skills/product-demo-video/`。安装成功后选择该技能或按名称提出制作需求。
- **豆包工作**：官方支持从「技能・连接器・伙伴」管理、自建及导入本地技能文件，并可在对话中指定技能。独立 PC 客户端、豆包内入口、飞书内入口的能力可能不同；按实际入口确认脚本、依赖、预览和文件导出能力。不要把工作伙伴后台的点击路径或开放平台上架限额直接套到个人客户端。
- **其他可读取文件的 Agent**：可以显式读取完整 Skill 文件夹，先执行本节的能力核对。手动读取流程不等于宿主已完成原生技能安装。

## TTS 绑定随执行环境选择

本适配器使用调用者配置的火山豆包 TTS API。它不会自动使用宿主内置语音服务或宿主登录。macOS 本机执行可按豆包指南使用钥匙串；云端、Linux、Windows 或明确选择环境变量时，使用已安全注入的 `DOUBAO_TTS_API_KEY` 并加 `--from-env`。复用已有音轨优先。更换成宿主内置语音、音色或服务商时，沿用主流程中的用户确认。

## 接入后的首次验证

沿用首幕样片审看，确认实际宿主能读取引用文件、运行所需命令、展示样片并交付输出；首个有声片段检查 TTS 配置及试听。记录宿主、系统、入口、执行位置和成功完成的部分，继续逐幕制作。

当前制作流程与渲染已在 Codex/macOS 实际使用。其他宿主的安装或导入入口已按下述官方文档核对，本 Skill 在这些客户端的完整视频制作仍待端到端实测。

## 官方依据

核对日期：2026-11-18。

- [Agent Skills 规范](https://agentskills.io/specification)
- [Claude Code Skills](https://code.claude.com/docs/en/skills)
- [Cursor Skills](https://cursor.com/docs/skills)
- [VS Code Agent Skills](https://code.visualstudio.com/docs/agent-customization/agent-skills)
- [OpenAI 技能配置](https://learn.chatgpt.com/docs/build-skills)
- [WorkBuddy 技能](https://www.codebuddy.cn/docs/workbuddy/From-Beginner-to-Expert-Guide/Function-Description/Skills-Market)与[项目级配置](https://www.codebuddy.cn/docs/workbuddy/From-Beginner-to-Expert-Guide/Function-Description/Project)
- [豆包工作官方介绍，第 13 节及三种入口](https://www.feishu.cn/content/article/7677519271848610746)
