# 豆包旁白

这个适配器接入火山引擎的豆包语音合成模型 2.0，需要 Node.js 20+。在封面制作前确定本项目采用豆包、已有音轨或用户录音，同时分别明确屏幕文案和旁白采用中文还是英文。采用豆包后，在第一次配音前检查本地配置，沿用本项目已确认的音色、语速和语气。需要比较音色或验证首次配置时，可以用一小段已确认文案试听。

CLI 默认使用 Vivi 2.0（`zh_female_vv_uranus_bigtts`）、语速 0、`zh-cn`，语气指令默认为空。下面的中文示例使用 Vivi 2.0、语速 8 和作者口吻，实际参数以项目试听确认为准。后续章节继续传入项目确认的参数，项目进度中保留这套设置。已确认的方法和参数可随当前场景的文案审批一起沿用。

## 在 macOS 配置一次钥匙串

1. 在豆包语音控制台确认对应项目已开通「豆包语音合成模型 2.0」，并在该项目的「API Key 管理」准备密钥。
2. 用 Spotlight 打开系统的「钥匙串访问」，选中登录钥匙串。在「文件」菜单中新建密码项目。项目名称填 `Product Demo Doubao API`，账户名称填 `product-demo-video`，把密钥直接粘贴到密码栏并保存。
3. 从 Skill 目录运行下面的本地检查。它只查看项目是否存在，不读取密码或验证云端权限。分享版使用上述通用钥匙串项目；每位使用者配置自己的 API Key。

```sh
node scripts/tts-doubao.mjs check
```

合成时系统可能显示钥匙串访问提示。核对项目名称，再点「允许」。密钥留在系统钥匙串和合成进程内存里。通过安全环境变量管理器已注入 `DOUBAO_TTS_API_KEY` 的环境，也可以对 `check` 和 `synthesize` 显式加 `--from-env`。密钥字段不要写入命令、文案、项目文件或对话。

## 本地预检与合成

`--text-file` 指向用户已确认的 UTF-8 旁白文本。中文为主、夹读英文时用 `zh-cn`，英文旁白用 `--language en` 并选择适合英语的音色。`--rate` 接受 −50 到 100 的整数。负值用 `--rate=-8` 形式传入。`--voice` 和 `--direction` 可选。

项目选中文旁白时显式传 `--language zh-cn`，英文旁白时传 `--language en`。该参数控制合成请求，不会翻译文本，也不会自动更换音色。先按目标语种写好并确认口播。沿用已在该语种试听通过的音色；没有对应试听记录时，用一小段含产品名的目标语种句子确认读法和节奏。不要猜测英文音色 ID，也不要把中文语速数值当作英文成片时长的保证。

切换语言时复用本地 API 绑定，并为新语种单独保留音轨和元数据；例如 `narration.zh.mp3`、`narration.en.mp3`。合成前可用相同 CLI 的 `dry-run` 检查 `language`、`speaker` 和请求校验值，不读取密钥也不产生 TTS 费用。画面可复用已有录屏和状态，时间点按该语种实际旁白重新对齐。

```sh
node scripts/tts-doubao.mjs dry-run --text-file /path/to/approved-narration.txt \
  --voice zh_female_vv_uranus_bigtts --rate 8 \
  --direction '像向朋友介绍自己做的工具，按语义自然停顿，英文品牌名称按英语读。'
```

`dry-run` 不打开钥匙串、不联网、不写文件。用户确认采用豆包后，执行明确的 `synthesize` 请求。

```sh
node scripts/tts-doubao.mjs synthesize --text-file /path/to/approved-narration.txt \
  --output /path/to/work/narration.mp3 --voice zh_female_vv_uranus_bigtts --rate 8 \
  --direction '像向朋友介绍自己做的工具，按语义自然停顿，英文品牌名称按英语读。'
```

输出为 `narration.mp3` 和同目录的 `narration.mp3.doubao.json`。JSON 记录实际使用的 `speaker`、`speechRate`、`language` 和 `direction`，以及 `audio` 下的格式、采样率、比特率和字幕开关。请求和音频校验值用于复用检查，`billedCharacters` 和 `sentences` 保存服务返回的计费字符数和字级时间戳。

修改画面和时间点时继续使用已确认的音频。同一路径的音频和本次请求校验一致时，脚本直接复用音轨，随后可继续制作。旧版 JSON 即使缺少新增设置字段，也按原有校验值复用。文案、音色、语速或语气发生变化时，使用新的输出文件名。

对照原文和画面试听成品，重点检查中英文混读、产品名和实际操作时点。首次包含品牌词的短句可作为发音试听，沿用已确认的音色和节奏。需要调整读法时，在项目里分别保存展示名称、实际 TTS 输入及已确认的发音写法；画面继续使用正式名称。发音写法改变实际合成输入，不改用户已确认的介绍含义。检查成片中该词的全部出现位置，仅重做仍不清楚的音轨。

## 发音或漏字排查

先对比原始音频与成片对应的短片段，区分原音发音、剪切和合成问题，再决定是否重新生成。低置信度的字级时间戳可能不准确，某个词时间很短不能证明漏读。ASR 转写只能辅助定位，不能证明读音符合用户偏好；保留试听判断及必要的用户确认。

复用本地已有的音频检查工具，以文件路径和简短结果记录证据。避免把完整音频的 Base64 输出到对话，也不为同一发音问题临时搭建多套识别流程。确需比较时，使用少量短句候选；选定后复用该音轨。时间戳可用于初步对齐字幕。音频未返回或流未结束时，脚本会报错，避免把半段旁白当成可用音轨。

[火山引擎单向流式语音合成接口](https://docs.volcengine.com/docs/doubao-voice/unidirectional-streaming-text-to-speech-http?lang=zh) · [控制台指引](https://docs.volcengine.com/docs/doubao-voice/console-guidance?lang=zh)
