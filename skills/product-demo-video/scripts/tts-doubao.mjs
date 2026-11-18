import { spawnSync } from "node:child_process";
import { createHash, randomUUID } from "node:crypto";
import { link, mkdir, mkdtemp, readFile, rm, unlink, writeFile } from "node:fs/promises";
import { dirname, extname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { parseArgs } from "node:util";

const endpoint = "https://openspeech.bytedance.com/api/v3/tts/unidirectional";
const resourceId = "seed-tts-2.0";
const keychains = [
  { service: "Product Demo Doubao API", account: "product-demo-video" },
];
const envName = "DOUBAO_TTS_API_KEY";
const help = `Usage:
  node scripts/tts-doubao.mjs check [--from-env]
  node scripts/tts-doubao.mjs dry-run --text-file FILE [voice options]
  node scripts/tts-doubao.mjs synthesize --text-file FILE --output FILE.mp3 [voice options] [--from-env]

Voice options: --voice ID (default Vivi 2.0), --rate -50..100 (default 0),
               --language zh-cn|en (default zh-cn), --direction TEXT.
The adapter writes the MP3 and a sibling .doubao.json with timings.
`;

const sha256 = (data) => createHash("sha256").update(data).digest("hex");

export function buildRequest(text, options = {}) {
  const voice = options.voice ?? "zh_female_vv_uranus_bigtts";
  const rate = Number(options.rate ?? 0);
  const language = options.language ?? "zh-cn";
  const direction = options.direction?.trim();
  if (!text.trim()) throw new Error("旁白文案为空。");
  if (!/^[a-zA-Z0-9_.-]+$/u.test(voice)) throw new Error("请传入有效的豆包音色 ID。");
  if (options.rate === "" || !Number.isInteger(rate) || rate < -50 || rate > 100) {
    throw new Error("语速必须是 −50 到 100 之间的整数。");
  }
  if (!["zh-cn", "en"].includes(language)) throw new Error("语种必须为 zh-cn 或 en。");
  return {
    req_params: {
      text,
      speaker: voice,
      audio_params: {
        format: "mp3", sample_rate: 24000, bit_rate: 160000, speech_rate: rate, enable_subtitle: true,
      },
      additions: JSON.stringify({
        explicit_language: language,
        aigc_metadata: { enable: true },
        ...(direction ? { context_texts: [direction] } : {}),
      }),
    },
  };
}

export function collectAudio(body, redact = (value) => value) {
  let messages;
  try {
    messages = body.split(/\r?\n/u).filter((line) => line.trim()).map((line) => JSON.parse(line));
  } catch {
    throw new Error("豆包语音返回了无法读取的音频记录。");
  }
  const chunks = [];
  const sentences = [];
  let completed = false;
  let billedCharacters;
  for (const message of messages) {
    if (!message || ![0, 20000000].includes(message.code)) {
      const code = Number.isSafeInteger(message?.code) ? `（${message.code}）` : "";
      throw new Error("豆包语音返回错误" + code + "。");
    }
    if (message.code === 20000000) completed = true;
    if (Number.isSafeInteger(message.usage?.text_words)) billedCharacters = message.usage.text_words;
    if (typeof message.data === "string" && message.data.length) {
      const chunk = Buffer.from(message.data, "base64");
      if (chunk.toString("base64").replace(/=+$/u, "") !== message.data.replace(/=+$/u, "")) {
        throw new Error("豆包语音返回了无效的 Base64 音频。");
      }
      if (chunk.length) chunks.push(chunk);
    }
    const sentence = message.sentence;
    if (Array.isArray(sentence?.words) && sentence.words.length) {
      sentences.push({
        text: typeof sentence.text === "string" ? redact(sentence.text) : "",
        words: sentence.words.flatMap(({ word, startTime, endTime, confidence }) => (
          typeof word === "string" && Number.isFinite(startTime) && Number.isFinite(endTime)
            ? [{ word: redact(word), startTime, endTime, confidence: Number.isFinite(confidence) ? confidence : undefined }]
            : []
        )),
      });
    }
  }
  if (!completed) throw new Error("豆包语音流提前结束，未收到完成状态。");
  if (!chunks.length) throw new Error("豆包语音未返回音频。");
  return { bytes: Buffer.concat(chunks), billedCharacters, sentences };
}

function keychainCommand({ service, account }, password = false) {
  return spawnSync("/usr/bin/security", [
    "find-generic-password", "-s", service, "-a", account, ...(password ? ["-w"] : []),
  ], {
    encoding: "utf8",
    stdio: ["ignore", password ? "pipe" : "ignore", "ignore"],
    timeout: password ? 60_000 : 5000,
  });
}

function credentialSource(fromEnv) {
  if (fromEnv) {
    if (!process.env[envName]?.trim()) throw new Error("当前进程未配置 " + envName + "。");
    return { name: envName, read: () => process.env[envName].trim() };
  }
  if (process.platform !== "darwin") throw new Error("请使用 --from-env 指定已安全配置的环境变量。");
  for (const item of keychains) {
    const result = keychainCommand(item);
    if (result.status === 0) {
      return {
        name: item.service,
        read: () => {
          const lookup = keychainCommand(item, true);
          if (lookup.status !== 0) throw new Error("无法从钥匙串读取 " + item.service + "。请检查解锁与访问授权。");
          return lookup.stdout.trim();
        },
      };
    }
    // security exits with the low byte of errSecItemNotFound (-25300).
    if (result.status !== 44) throw new Error("无法检查登录钥匙串，请确认它已解锁。");
  }
  throw new Error("未找到豆包 API 钥匙串项目，请参照 references/doubao.md 配置。");
}

async function readIfPresent(path) {
  try {
    return await readFile(path);
  } catch (error) {
    if (error.code === "ENOENT") return undefined;
    throw error;
  }
}

async function reusable(output, metadataPath, requestSha256) {
  const [audio, metadataBytes] = await Promise.all([readIfPresent(output), readIfPresent(metadataPath)]);
  if (!audio && !metadataBytes) return false;
  let metadata;
  try {
    if (metadataBytes) metadata = JSON.parse(metadataBytes.toString("utf8"));
  } catch {
    // A damaged or unrelated sidecar must not authorize a replacement.
  }
  if (audio && metadata?.requestSha256 === requestSha256 && metadata?.audioSha256 === sha256(audio)) return true;
  throw new Error("目标 MP3 或时间戳已存在，且无法确认与本次参数一致。请使用新的输出路径。");
}

async function writeResults(output, metadataPath, bytes, metadata) {
  const directory = dirname(output);
  await mkdir(directory, { recursive: true });
  const staging = await mkdtemp(join(directory, ".doubao-"));
  const audioTemp = join(staging, "audio.mp3");
  const metadataTemp = join(staging, "timings.json");
  try {
    await Promise.all([
      writeFile(audioTemp, bytes, { mode: 0o600 }),
      writeFile(metadataTemp, JSON.stringify(metadata, null, 2) + "\n", { mode: 0o600 }),
    ]);
    await link(metadataTemp, metadataPath);
    try {
      await link(audioTemp, output);
    } catch (error) {
      await unlink(metadataPath);
      throw error;
    }
  } finally {
    await rm(staging, { recursive: true, force: true });
  }
}

async function invoke(body, apiKey) {
  let response;
  let responseText;
  try {
    response = await fetch(endpoint, {
      method: "POST",
      redirect: "error",
      signal: AbortSignal.timeout(60_000),
      headers: {
        "Content-Type": "application/json",
        "X-Api-Key": apiKey,
        "X-Api-Resource-Id": resourceId,
        "X-Api-Request-Id": randomUUID(),
        "X-Control-Require-Usage-Tokens-Return": "*",
      },
      body,
    });
    if (response.ok) responseText = await response.text();
  } catch {
    throw new Error("豆包语音未完成请求，请检查网络后再决定是否重试。");
  }
  const logId = response.headers.get("X-Tt-Logid");
  const trace = logId && /^[a-zA-Z0-9_.-]{6,128}$/u.test(logId) && !logId.includes(apiKey)
    ? ` 日志 ID ${logId}` : "";
  try {
    if (!response.ok) throw new Error(`豆包语音 HTTP ${response.status}。`);
    return collectAudio(responseText, (value) => value.replaceAll(apiKey, "[redacted]"));
  } catch (error) {
    throw new Error(error.message.replaceAll(apiKey, "[redacted]") + trace);
  }
}

async function main(args) {
  const [command, ...rest] = args;
  if (!command || command === "--help" || command === "-h") {
    console.log(help);
    return;
  }
  if (!["check", "dry-run", "synthesize"].includes(command)) throw new Error("请选择 check、dry-run 或 synthesize。");
  const { values } = parseArgs({
    args: rest,
    options: command === "check" ? { "from-env": { type: "boolean" } } : {
      "text-file": { type: "string" },
      voice: { type: "string" },
      rate: { type: "string" },
      language: { type: "string" },
      direction: { type: "string" },
      ...(command === "synthesize" ? { output: { type: "string" }, "from-env": { type: "boolean" } } : {}),
    },
  });
  if (command === "check") {
    const source = credentialSource(values["from-env"]);
    console.log(JSON.stringify({ credential: "present", source: source.name }));
    return;
  }
  if (!values["text-file"]) throw new Error("请用 --text-file 指定 UTF-8 旁白文案。");
  const text = new TextDecoder("utf-8", { fatal: true }).decode(await readFile(values["text-file"])).trim();
  const request = buildRequest(text, values);
  const body = JSON.stringify(request);
  const requestSha256 = sha256(JSON.stringify({ endpoint, resourceId, body }));
  if (command === "dry-run") {
    const { audio_params, speaker } = request.req_params;
    console.log(JSON.stringify({
      resourceId, speaker, audio: audio_params, language: values.language ?? "zh-cn",
      hasDirection: Boolean(values.direction?.trim()), characters: [...text].length, requestSha256,
    }, null, 2));
    return;
  }
  if (!values.output || extname(values.output).toLowerCase() !== ".mp3") {
    throw new Error("请用 --output 指定 MP3 文件路径。");
  }
  const output = resolve(values.output);
  const metadataPath = output + ".doubao.json";
  if (await reusable(output, metadataPath, requestSha256)) {
    console.log(JSON.stringify({ reused: true, output, metadata: metadataPath }));
    return;
  }
  const apiKey = credentialSource(values["from-env"]).read();
  if (!apiKey || /\s/u.test(apiKey)) throw new Error("豆包 API Key 格式无效。");
  const { bytes, billedCharacters, sentences } = await invoke(body, apiKey);
  const { speaker, audio_params: audio } = request.req_params;
  const additions = JSON.parse(request.req_params.additions);
  const metadata = {
    resourceId,
    speaker,
    speechRate: audio.speech_rate,
    language: additions.explicit_language,
    direction: (additions.context_texts?.[0] ?? "").replaceAll(apiKey, "[redacted]"),
    audio: {
      format: audio.format,
      sampleRate: audio.sample_rate,
      bitRate: audio.bit_rate,
      enableSubtitle: audio.enable_subtitle,
    },
    requestSha256,
    audioSha256: sha256(bytes),
    billedCharacters,
    sentences,
  };
  await writeResults(output, metadataPath, bytes, metadata);
  console.log(JSON.stringify({ reused: false, output, metadata: metadataPath, bytes: bytes.length, billedCharacters }));
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  try {
    await main(process.argv.slice(2));
  } catch (error) {
    console.error(error.message);
    process.exitCode = 1;
  }
}
