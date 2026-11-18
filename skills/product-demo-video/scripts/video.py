#!/usr/bin/env python3
"""Render a product demo scene from JSON and assemble scenes into an MP4."""

import argparse
from contextlib import closing
from fractions import Fraction
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory

from PIL import Image, ImageDraw, ImageFont, ImageOps

WIDTH, HEIGHT, FPS = 1920, 1080, 30
SAMPLE_RATE = 48_000
SAMPLES_PER_FRAME = SAMPLE_RATE // FPS
TRACK_TIMESCALE = 15_360
BACKGROUND = "#f3f5f0"
INK = "#28332d"
MUTED = "#53615a"
VIDEO_ENCODING = [
    "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-g", "60",
    "-profile:v", "high", "-level:v", "4.1", "-pix_fmt", "yuv420p",
    "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709",
    "-color_range", "tv", "-video_track_timescale", str(TRACK_TIMESCALE),
]
AUDIO_ENCODING = ["-c:a", "aac", "-b:a", "192k", "-ar", str(SAMPLE_RATE), "-ac", "2"]
MP4_FLAGS = ["-movie_timescale", str(SAMPLE_RATE), "-movflags", "+faststart"]
STYLE_FIELDS = {"layout", "font", "product", "label", "quality"}
SCENE_FIELDS = {
    "capture", "shots", "start", "duration", "headline", "product", "label", "font",
    "layout", "style", "quality", "narration", "narration_at", "narration_text",
    "clicks", "swipes", "metadata",
}


def ffmpeg(*args):
    return ["ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-y", *map(str, args)]


def probe(path):
    output = subprocess.check_output([
        "ffprobe", "-v", "error", "-show_streams", "-show_format",
        "-show_data_hash", "sha256", "-of", "json", str(path),
    ])
    data = json.loads(output)
    stream = next((s for s in data["streams"]
                   if s["codec_type"] == "video" and not s.get("disposition", {}).get("attached_pic")), None)
    audio = next((s for s in data["streams"] if s["codec_type"] == "audio"), None)
    return stream, audio, data.get("format", {})


def stream_duration(stream, format_info):
    if stream.get("duration_ts") is not None and stream.get("time_base"):
        return float(int(stream["duration_ts"]) * Fraction(stream["time_base"]))
    try:
        return float(stream.get("duration", format_info.get("duration", "nan")))
    except ValueError:
        return math.nan


def stream_start(stream):
    if stream.get("start_pts") is not None and stream.get("time_base"):
        return float(int(stream["start_pts"]) * Fraction(stream["time_base"]))
    try:
        return float(stream.get("start_time", 0.0))
    except ValueError:
        return 0.0


def number(value, field, minimum=0.0, maximum=math.inf):
    if (not isinstance(value, (float, int)) or isinstance(value, bool)
            or not math.isfinite(value) or not minimum <= value <= maximum):
        raise ValueError(f"{field} must be a finite number between {minimum} and {maximum}")
    return float(value)


def text_field(manifest, name):
    value = manifest.get(name, "")
    if not isinstance(value, str):
        raise ValueError(f"{name} must be a string")
    return value.strip()


def input_path(path):
    source = Path(path).expanduser().resolve()
    if not source.is_file():
        raise ValueError(f"Input file does not exist: {source}")
    return source


def manifest_path(directory, value, field):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a file path")
    return input_path(directory / Path(value).expanduser())


def load_manifest(scene, strict):
    manifest = json.loads(scene.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict):
        raise ValueError("Scene JSON must contain one scene object")
    if strict and set(manifest) - SCENE_FIELDS:
        names = ", ".join(sorted(set(manifest) - SCENE_FIELDS))
        raise ValueError(f"Unsupported scene fields: {names}. Put descriptive data in metadata")
    if "metadata" in manifest and not isinstance(manifest["metadata"], dict):
        raise ValueError("metadata must be an object")
    sources = [scene]
    if "style" in manifest:
        source = manifest_path(scene.parent, manifest["style"], "style")
        defaults = json.loads(source.read_text(encoding="utf-8"))
        if not isinstance(defaults, dict) or set(defaults) - STYLE_FIELDS:
            raise ValueError("Style JSON supports layout, font, product, label and quality")
        if "font" in defaults:
            defaults["font"] = str(manifest_path(source.parent, defaults["font"], "style.font"))
        manifest = {**defaults, **manifest}
        sources.append(source)
    if manifest.get("layout", "top") not in ("top", "split", "full"):
        raise ValueError("layout must be top, split or full")
    if manifest.get("quality", "standard") not in ("standard", "high"):
        raise ValueError("quality must be standard or high")
    return manifest, sources


def video_encoding(quality="standard"):
    options = VIDEO_ENCODING.copy()
    if quality == "high":
        options[options.index("-crf") + 1] = "14"
    return options


def output_path(path, sources):
    output = Path(path).expanduser().absolute()
    if output.suffix.lower() != ".mp4":
        raise ValueError("Output must have an .mp4 extension")
    for source in sources:
        if output.resolve() == source.resolve() or (output.exists() and output.samefile(source)):
            raise ValueError(f"Output overlaps an input: {source}")
    output.parent.mkdir(parents=True, exist_ok=True)
    return output


def font_path():
    candidates = [
        "/System/Library/Fonts/Hiragino Sans GB.ttc",
        "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
        "C:/Windows/Fonts/msyh.ttc",
    ]
    for candidate in candidates:
        if Path(candidate).is_file():
            return candidate
    if shutil.which("fc-match"):
        result = subprocess.run(
            ["fc-match", "-f", "%{file}", "sans-serif:lang=zh-cn"],
            check=False, capture_output=True, text=True,
        )
        if result.returncode == 0 and Path(result.stdout).is_file():
            return result.stdout
    raise ValueError("Set font in the scene JSON to an installed TrueType or OpenType font")


def wrapped_lines(caption, draw, font, width):
    lines = []
    for paragraph in caption.splitlines():
        line = ""
        tokens = re.findall(r"\s+|[A-Za-z0-9_][A-Za-z0-9_.'’/@\-]*|[^\s]", paragraph)
        for token in tokens:
            if draw.textlength(token, font=font) > width:
                line = line.rstrip()
                if line:
                    lines.append(line)
                fit = ""
                for character in token:
                    if draw.textlength(fit + character, font=font) > width:
                        lines.append(fit)
                        fit = ""
                    fit += character
                line = fit
            elif line and draw.textlength(line + token, font=font) > width:
                lines.append(line.rstrip())
                line = token.lstrip()
            else:
                line = (line + token).lstrip()
        lines.append(line.rstrip())
    return lines


def display_ratio(video):
    sar = video.get("sample_aspect_ratio")
    ratio = Fraction(video["width"], video["height"])
    if sar and sar not in {"0:1", "N/A"}:
        ratio *= Fraction(sar.replace(":", "/"))
    rotation = next((item["rotation"] for item in video.get("side_data_list", []) if "rotation" in item), 0)
    return float(1 / ratio if abs(rotation) % 180 == 90 else ratio)


def fit_size(ratio, max_width, max_height):
    width = min(max_width, max_height * ratio)
    height = min(max_height, width / ratio)
    return max(2, int(width) // 2 * 2), max(2, int(height) // 2 * 2)


def scene_background(manifest, font_file, video):
    image = Image.new("RGB", (WIDTH, HEIGHT), BACKGROUND)
    draw = ImageDraw.Draw(image)
    product, label, headline = (text_field(manifest, key) for key in ("product", "label", "headline"))
    layout = manifest.get("layout", "top")
    if layout == "full":
        if product or label or headline:
            raise ValueError("full layout uses the supplied title/card image. Leave overlay text empty")
        width, height = fit_size(display_ratio(video), WIDTH, HEIGHT)
        return image, Image.new("L", (width, height), 255), ((WIDTH - width) // 2, (HEIGHT - height) // 2)
    if layout == "split":
        brand_font = ImageFont.truetype(font_file, 29)
        small_font = ImageFont.truetype(font_file, 26)
        if draw.textlength(product, font=brand_font) > 760 or draw.textlength(label, font=small_font) > 716:
            raise ValueError("The product or label text does not fit the split layout")
        draw.text((172, 279), product, font=brand_font, fill=MUTED, anchor="lm")
        if headline:
            for size in (48, 44, 40, 36, 32):
                body_font = ImageFont.truetype(font_file, size)
                lines = wrapped_lines(headline, draw, body_font, 760)
                if len(lines) <= 4:
                    break
            else:
                raise ValueError("The headline needs over four lines in the split layout")
            for index, line in enumerate(lines):
                draw.text((172, 426 + index * (size + 27)), line, font=body_font, fill=INK, anchor="lm")
        if label:
            width = round(draw.textlength(label, font=small_font)) + 44
            draw.rounded_rectangle((172, 773, 172 + width, 823), 14, fill="#e2ece5")
            draw.text((194, 798), label, font=small_font, fill=MUTED, anchor="lm")
        width, height = fit_size(display_ratio(video), 624, 982)
        x, y = 1080 + (624 - width) // 2, 49 + (982 - height) // 2
        draw.rounded_rectangle((x - 1, y - 1, x + width, y + height), 18, fill="#d8dfd7")
        mask = Image.new("L", (width, height))
        ImageDraw.Draw(mask).rounded_rectangle((0, 0, width - 1, height - 1), 17, fill=255)
        return image, mask, (x, y)
    margin = 120
    header = 70 if product or label else 52
    if product or label:
        font = ImageFont.truetype(font_file, 26)
        if draw.textlength(product, font=font) + draw.textlength(label, font=font) > WIDTH - 2 * margin - 44:
            raise ValueError("The product and label text do not fit in the scene header")
        draw.text((margin, 46), product, font=font, fill=INK, anchor="lm")
        draw.text((WIDTH - margin, 46), label, font=font, fill=MUTED, anchor="rm")

    if headline:
        for size in (50, 46, 42, 38, 34):
            font = ImageFont.truetype(font_file, size)
            lines = wrapped_lines(headline, draw, font, WIDTH - 2 * margin)
            if len(lines) <= 3:
                break
        else:
            raise ValueError("The headline needs over three lines. Shorten it or split the scene")
        line_height = size + 12
        first = header + line_height // 2
        for index, line in enumerate(lines):
            draw.text((WIDTH // 2, first + line_height * index), line, font=font, fill=INK, anchor="mm")
        header += line_height * len(lines) + 28

    bottom = HEIGHT - 58
    stage_width, stage_height = fit_size(display_ratio(video), WIDTH - 2 * margin, bottom - header)
    x = (WIDTH - stage_width) // 2
    y = header + (bottom - header - stage_height) // 2
    draw.rounded_rectangle((x - 1, y - 1, x + stage_width, y + stage_height), 13, fill="#d8dfd7")
    mask = Image.new("L", (stage_width, stage_height))
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, stage_width - 1, stage_height - 1), 12, fill=255)
    return image, mask, (x, y)


def parse_clicks(manifest, duration):
    raw = manifest.get("clicks", [])
    if not isinstance(raw, list):
        raise ValueError("clicks must be an array of {at, x, y} objects")
    clicks = []
    for item in raw:
        if not isinstance(item, dict):
            raise ValueError("Each click must contain at, x and y")
        at = number(item.get("at"), "click.at", maximum=duration)
        if at >= duration:
            raise ValueError("click.at must be before the end of the scene")
        x = number(item.get("x"), "click.x", maximum=1.0)
        y = number(item.get("y"), "click.y", maximum=1.0)
        clicks.append((at, x, y))
    return sorted(clicks)


def click_ring(frame, click, cursor):
    phase, rel_x, rel_y = click
    x, y, stage_width, stage_height = cursor
    px, py = x + rel_x * (stage_width - 1), y + rel_y * (stage_height - 1)
    radius = 14 + 26 * phase
    draw = ImageDraw.Draw(frame, "RGBA")
    alpha = round(185 * (1 - phase))
    bounds = (px - radius, py - radius, px + radius, py + radius)
    draw.ellipse(bounds, fill=(65, 133, 96, alpha // 7), outline=(55, 110, 83, alpha), width=3)


def parse_swipes(manifest, duration):
    rows = manifest.get("swipes", [])
    if not isinstance(rows, list):
        raise ValueError("swipes must be an array of {at, duration, from, to} objects")
    swipes = []
    for row in rows:
        if not isinstance(row, dict) or set(row) != {"at", "duration", "from", "to"}:
            raise ValueError("Each swipe needs at, duration, from and to")
        start = number(row["at"], "swipe.at", maximum=duration)
        length = number(row["duration"], "swipe.duration", minimum=1 / FPS)
        if start + length > duration + 1e-8:
            raise ValueError("The swipe ends after the scene")
        points = []
        for key in ("from", "to"):
            point = row[key]
            if not isinstance(point, list) or len(point) != 2:
                raise ValueError(f"swipe.{key} must contain normalized x and y")
            points.append(tuple(number(value, f"swipe.{key}", maximum=1) for value in point))
        swipes.append((start, length, *points))
    return swipes


def swipe_marker(frame, progress, first, last, stage):
    x, y, width, height = stage
    px = x + (first[0] + (last[0] - first[0]) * progress) * (width - 1)
    py = y + (first[1] + (last[1] - first[1]) * progress) * (height - 1)
    alpha = round(220 * min(1, progress * 8, (1 - progress) * 8))
    ImageDraw.Draw(frame, "RGBA").ellipse(
        (px - 10, py - 10, px + 10, py + 10),
        fill=(232, 250, 241, alpha), outline=(55, 110, 83, alpha), width=3,
    )


def parse_shots(manifest, directory, duration):
    rows = manifest.get("shots")
    if not isinstance(rows, list) or not rows:
        raise ValueError("shots must be a nonempty array of {source, at} objects")
    shots, sources = [], []
    previous = -1
    first_size = None
    for row in rows:
        if not isinstance(row, dict) or set(row) != {"source", "at"}:
            raise ValueError("Each shot needs only source and at")
        at = number(row["at"], "shot.at", maximum=duration)
        frame = round(at * FPS)
        if (not shots and at != 0) or frame <= previous or frame >= math.ceil(duration * FPS - 1e-8):
            raise ValueError("Shots must start at zero and increase by at least one frame before the scene ends")
        name = row["source"]
        if not isinstance(name, str) or not name.strip():
            raise ValueError("shot.source must be an image path or a directory of PNG frames")
        source = (directory / Path(name).expanduser()).resolve()
        files = sorted(source.glob("*.png")) if source.is_dir() else [input_path(source)]
        if not files:
            raise ValueError(f"No PNG frames in {source}")
        for path in files:
            if path.suffix.lower() not in {".png", ".jpg", ".jpeg"}:
                raise ValueError("Shot images must be PNG or JPEG")
            with Image.open(path) as image:
                image.verify()
            if first_size is None:
                with Image.open(path) as image:
                    first_size = ImageOps.exif_transpose(image).size
        shots.append((frame, files))
        sources.extend(files)
        previous = frame
    return shots, sources, {"width": first_size[0], "height": first_size[1]}


def image_frames(shots, frames, size):
    current = None
    rendered = None
    for index, (start, paths) in enumerate(shots):
        end = shots[index + 1][0] if index + 1 < len(shots) else frames
        count = end - start
        for offset in range(count):
            selected = round(offset * (len(paths) - 1) / max(1, count - 1))
            path = paths[selected]
            if path != current:
                with Image.open(path) as image:
                    fitted = ImageOps.contain(ImageOps.exif_transpose(image).convert("RGB"), size,
                                             Image.Resampling.LANCZOS)
                rendered = Image.new("RGB", size, BACKGROUND)
                rendered.paste(fitted, ((size[0] - fitted.width) // 2, (size[1] - fitted.height) // 2))
                current = path
            yield rendered


def capture_frames(video, capture, start, frames, size):
    width, height = size
    command = ffmpeg(
        "-ss", f"{start:.9f}", "-i", capture, "-map", f"0:{video['index']}",
        "-vf", f"fps={FPS},scale={width}:{height}:flags=lanczos,setsar=1",
        "-frames:v", frames, "-an", "-f", "rawvideo", "-pix_fmt", "rgb24", "-threads", 1, "pipe:1",
    )
    reader = subprocess.Popen(command, stdout=subprocess.PIPE)
    try:
        previous = None
        for _ in range(frames):
            raw = reader.stdout.read(width * height * 3)
            if raw:
                if len(raw) != width * height * 3:
                    raise ValueError("The capture produced an incomplete video frame")
                previous = Image.frombytes("RGB", size, raw)
            elif reader.wait():
                raise ValueError("Could not decode the capture")
            if previous is None:
                raise ValueError("No capture frames at the requested start time")
            yield previous
        if reader.wait():
            raise ValueError("Could not decode the capture")
    finally:
        if reader.poll() is None:
            reader.terminate()
            reader.wait()
        reader.stdout.close()


def exact_audio_frames(frames):
    samples = frames * SAMPLES_PER_FRAME
    return f"apad=whole_len={samples},atrim=end_sample={samples},asetpts=N/SR/TB"


def write_scene(manifest, video, capture, narration, audio, start, frames, at, clicks, font_file, output,
                shots=None, swipes=()):
    backdrop, mask, origin = scene_background(manifest, font_file, video)
    width, height = mask.size
    encode = ffmpeg("-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{WIDTH}x{HEIGHT}",
                    "-r", FPS, "-i", "pipe:0")
    if narration:
        encode += ["-i", str(narration)]
        audio_map = f"[1:{audio['index']}]"
        filters = (
            "asetpts=PTS-STARTPTS,aformat=channel_layouts=mono,highpass=f=55,"
            "loudnorm=I=-18:TP=-2:LRA=7:dual_mono=true,aresample=48000,"
            "pan=stereo|c0=c0|c1=c0,"
            f"adelay={round(at * SAMPLE_RATE)}S:all=1,{exact_audio_frames(frames)}"
        )
    else:
        encode += ["-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo"]
        audio_map = "[1:a:0]"
        filters = exact_audio_frames(frames)
    encode += [
        "-filter_complex", f"{audio_map}{filters}[sound]", "-map", "0:v:0", "-map", "[sound]",
        "-vf", "scale=out_color_matrix=bt709:out_range=tv,format=yuv420p",
        *video_encoding(manifest.get("quality", "standard")), *AUDIO_ENCODING, *MP4_FLAGS, str(output),
    ]
    pictures = (image_frames(shots, frames, mask.size) if shots is not None
                else capture_frames(video, capture, start, frames, mask.size))
    writer = subprocess.Popen(encode, stdin=subprocess.PIPE)
    try:
        with closing(pictures):
            for index, picture in enumerate(pictures):
                frame = backdrop.copy()
                frame.paste(picture, origin, mask)
                seconds = index / FPS
                for at_time, x, y in clicks:
                    elapsed = seconds - at_time
                    if 0 <= elapsed < .36:
                        click_ring(frame, (elapsed / .36, x, y), (*origin, width, height))
                for begin, length, first, last in swipes:
                    if begin <= seconds < begin + length:
                        swipe_marker(frame, (seconds - begin) / length, first, last, (*origin, width, height))
                writer.stdin.write(frame.tobytes())
        writer.stdin.close()
        if writer.wait():
            raise ValueError("Could not encode the scene")
    finally:
        if writer.poll() is None:
            writer.terminate()
            writer.wait()
        if not writer.stdin.closed:
            try:
                writer.stdin.close()
            except BrokenPipeError:
                pass


def render(scene_file, target, *, strict=False):
    scene = input_path(scene_file)
    manifest, sources = load_manifest(scene, strict)
    has_capture, has_shots = "capture" in manifest, "shots" in manifest
    if has_capture and has_shots and not strict:
        # Existing project wrappers prepare their own capture from a legacy shots schema.
        print("Using prebuilt capture for this legacy Python render() manifest; shots remain project data", file=sys.stderr)
        has_shots = False
    if has_capture == has_shots:
        raise ValueError("Supply exactly one of capture or shots. Move historical shot data to metadata")
    start = number(manifest.get("start", 0), "start")
    capture, shots = None, None
    if has_shots:
        if start != 0 or "duration" not in manifest:
            raise ValueError("shots require an explicit duration and a zero start")
        capture_duration = number(manifest["duration"], "duration", minimum=1e-6)
        shots, images, video = parse_shots(manifest, scene.parent, capture_duration)
        sources.extend(images)
    else:
        capture = manifest_path(scene.parent, manifest.get("capture"), "capture")
        sources.append(capture)
        video, _, capture_format = probe(capture)
        if not video:
            raise ValueError("The capture does not contain a video stream")
        capture_duration = stream_duration(video, capture_format)
        if math.isfinite(capture_duration) and start >= capture_duration:
            raise ValueError("start is at or beyond the end of the capture")
    narration = manifest_path(scene.parent, manifest["narration"], "narration") if manifest.get("narration") else None
    font_file = (manifest_path(scene.parent, manifest["font"], "font") if manifest.get("font")
                 else input_path(font_path()))
    sources.extend(path for path in (narration, font_file) if path is not None)
    output = output_path(target, sources)
    at = number(manifest.get("narration_at", .18), "narration_at")
    audio = None
    voice_end = 0.0
    if narration:
        _, audio, audio_format = probe(narration)
        if not audio:
            raise ValueError("The narration does not contain an audio stream")
        length = stream_duration(audio, audio_format)
        if not math.isfinite(length) or length <= 0:
            raise ValueError("Cannot determine the narration duration")
        voice_end = at + length
    default_duration = max(capture_duration - start, voice_end + .20 if narration else 0.0)
    duration = number(manifest.get("duration", default_duration), "duration", minimum=1e-6)
    frames = math.ceil(duration * FPS - 1e-8)
    if voice_end > frames / FPS + 1e-6:
        raise ValueError("The narration runs past the scene. Increase duration or start it earlier")
    clicks = parse_clicks(manifest, frames / FPS)
    swipes = parse_swipes(manifest, frames / FPS)
    with TemporaryDirectory(prefix=".scene-", dir=output.parent) as working:
        staging = Path(working) / "scene.mp4"
        write_scene(manifest, video, capture, narration, audio, start, frames, at, clicks, font_file, staging,
                    shots=shots, swipes=swipes)
        verify_file(staging, frames)
        os.replace(staging, output)
    print(output)


def picture_key(video):
    keys = ("codec_name", "profile", "level", "width", "height", "pix_fmt", "sample_aspect_ratio",
            "avg_frame_rate", "r_frame_rate", "time_base", "color_space", "color_transfer",
            "color_primaries", "color_range", "extradata_hash")
    return tuple(video.get(key) for key in keys)


def canonical_frames(source, video):
    if (video.get("codec_name") != "h264" or video.get("width") != WIDTH or video.get("height") != HEIGHT
            or video.get("pix_fmt") != "yuv420p" or video.get("sample_aspect_ratio") not in {"1:1", None}
            or video.get("avg_frame_rate") != f"{FPS}/1" or video.get("time_base") != f"1/{TRACK_TIMESCALE}"
            or video.get("start_pts") != 0 or not video.get("extradata_hash")
            or any(item.get("rotation") for item in video.get("side_data_list", []))):
        return None
    raw = subprocess.check_output([
        "ffprobe", "-v", "error", "-select_streams", str(video["index"]),
        "-show_packets", "-show_entries", "packet=pts,dts,flags", "-of", "json", str(source),
    ])
    packets = json.loads(raw).get("packets", [])
    if not packets or "K" not in packets[0].get("flags", ""):
        return None
    try:
        pts = sorted(int(packet["pts"]) for packet in packets)
        dts = [int(packet["dts"]) for packet in packets]
    except (KeyError, TypeError, ValueError):
        return None
    ticks = TRACK_TIMESCALE // FPS
    if any(pts[index] != index * ticks or dts[index] != dts[0] + index * ticks for index in range(len(packets))):
        return None
    if video.get("duration_ts") != len(packets) * ticks:
        return None
    return len(packets), dts[0]


def normalize_picture(source, video, target):
    width, height = fit_size(display_ratio(video), WIDTH, HEIGHT)
    filters = (
        f"setpts=PTS-STARTPTS,fps={FPS}:start_time=0,"
        f"scale={width}:{height}:flags=lanczos:out_color_matrix=bt709:out_range=tv,"
        f"setsar=1,pad={WIDTH}:{HEIGHT}:(ow-iw)/2:(oh-ih)/2:color=0xf3f5f0"
    )
    subprocess.run(ffmpeg(
        "-i", source, "-map", f"0:{video['index']}", "-an", "-vf", filters,
        *video_encoding("high"), target,
    ), check=True)
    normalized, _, _ = probe(target)
    result = normalized and canonical_frames(target, normalized)
    if not result:
        raise ValueError(f"Could not normalize the video from {source}")
    return result[0]


def chapter_title(path):
    return re.sub(r"([=;#\\])", r"\\\1", " ".join(path.stem.splitlines()))


def progress_filters(frames, opening_frames):
    """Reserve a footer and animate a small strip using output-frame counts."""
    margin, gap, width, height = 96, 6, WIDTH - 192, 6
    if len(frames) > width:
        raise ValueError("Too many scenes for a visible progress segment. Use --no-progress")
    if len(frames) > 1:
        gap = min(gap, (width - len(frames)) // (len(frames) - 1))
    total = sum(frames)
    # Each scene gets one pixel, including one-frame scenes, and shares the rest
    # in proportion to its final output-frame duration.
    available = width - gap * (len(frames) - 1) - len(frames)
    segments, filled = [], []
    elapsed = 0
    for index, length in enumerate(frames):
        left = index * (gap + 1) + round(available * elapsed / total)
        right = index * (gap + 1) + 1 + round(available * (elapsed + length) / total)
        segment = f"gte(X,{left})*lt(X,{right})"
        fill = f"floor({right - left}*clip((N+1-{elapsed})/{length},0,1))"
        segments.append(f"({segment})")
        filled.append(f"({segment}*lt(X,{left}+{fill}))")
        elapsed += length
    active = "+".join(filled)
    visible = "+".join(segments)
    filters = []
    if opening_frames:
        filters.extend([
            "[0:v:0]split[coverinput][bodyinput]",
            f"[coverinput]trim=end_frame={opening_frames},setpts=PTS-STARTPTS[cover]",
            f"[bodyinput]trim=start_frame={opening_frames},setpts=PTS-STARTPTS,"
            f"scale=1856:1044:flags=lanczos,pad={WIDTH}:{HEIGHT}:32:0:color=0xf3f5f0[body]",
            "[cover][body]concat=n=2:v=1:a=0[canvas]",
        ])
    else:
        filters.append(
            f"[0:v:0]scale=1856:1044:flags=lanczos,"
            f"pad={WIDTH}:{HEIGHT}:32:0:color=0xf3f5f0[canvas]"
        )
    filters.extend([
        f"color=c=black:s={width}x{height}:r={FPS},format=rgba,trim=end_frame={total},"
        f"geq=r='if({active},57,216)':g='if({active},115,223)':"
        f"b='if({active},92,215)':a='if({visible},255,0)',"
        f"setpts=PTS+{opening_frames}/{FPS}/TB[progress]",
        f"[canvas][progress]overlay=x={margin}:y=1056:eof_action=pass:repeatlast=0:"
        f"enable='gte(n,{opening_frames})':format=auto,setsar=1,"
        "scale=out_color_matrix=bt709:out_range=tv,format=yuv420p[picture]",
    ])
    return filters


def assemble(target, scene_paths, *, opening=None, progress=True):
    scenes = [input_path(path) for path in scene_paths]
    if not scenes:
        raise ValueError("Assembly requires at least one body scene")
    sources = ([input_path(opening)] if opening is not None else []) + scenes
    output = output_path(target, sources)
    streams = [probe(path) for path in sources]
    videos = [video for video, _, _ in streams]
    if any(video is None for video in videos):
        raise ValueError("Every input scene must have a video stream")
    frame_info = [canonical_frames(path, video) for path, video in zip(sources, videos)]
    copy_picture = (
        all(entry is not None for entry in frame_info)
        and len({picture_key(video) for video in videos}) == 1
        and len({entry[1] for entry in frame_info}) == 1
    )
    with TemporaryDirectory(prefix=".assemble-", dir=output.parent) as working:
        scratch = Path(working)
        frames = []
        listing = ["ffconcat version 1.0"]
        for index, (source, video) in enumerate(zip(sources, videos)):
            local = scratch / f"scene-{index:03d}.mp4"
            if copy_picture:
                # The concat demuxer can otherwise offset the picture by AAC priming.
                subprocess.run(ffmpeg(
                    "-i", source, "-map", f"0:{video['index']}", "-c:v", "copy",
                    "-map_metadata", "-1", "-map_chapters", "-1",
                    "-video_track_timescale", TRACK_TIMESCALE, local,
                ), check=True)
                length = frame_info[index][0]
            else:
                length = normalize_picture(source, video, local)
            frames.append(length)
            listing.extend([f"file {local.name}", f"duration {length / FPS:.9f}"])
        concat = scratch / "scenes.ffconcat"
        concat.write_text("\n".join(listing) + "\n", encoding="utf-8")

        meta = [";FFMETADATA1"]
        filters = []
        if progress:
            filters.extend(progress_filters(frames[1:] if opening is not None else frames,
                                            frames[0] if opening is not None else 0))
        offset = 0
        for index, (path, length, (video, audio, _)) in enumerate(zip(sources, frames, streams)):
            if opening is None or index > 0:
                meta.extend(["[CHAPTER]", f"TIMEBASE=1/{FPS}", f"START={offset}", f"END={offset + length}",
                             f"title={chapter_title(path)}"])
            offset += length
            clip = f"a{index}"
            if audio:
                source_filter = (
                    f"[{index + 1}:{audio['index']}]asetpts=PTS-STARTPTS,"
                    "aresample=48000,aformat=channel_layouts=stereo"
                )
                shift = round((stream_start(audio) - stream_start(video)) * SAMPLE_RATE)
                if shift > 0:
                    source_filter += f",adelay={shift}S:all=1"
                elif shift < 0:
                    source_filter += f",atrim=start_sample={-shift},asetpts=PTS-STARTPTS"
            else:
                source_filter = "anullsrc=r=48000:cl=stereo"
            filters.append(f"{source_filter},{exact_audio_frames(length)}[{clip}]")
        metadata = scratch / "chapters.ffmeta"
        metadata.write_text("\n".join(meta) + "\n", encoding="utf-8")
        links = "".join(f"[a{index}]" for index in range(len(sources)))
        filters.append(f"{links}concat=n={len(sources)}:v=0:a=1[joined]")
        filters.append(f"[joined]aresample={SAMPLE_RATE},{exact_audio_frames(sum(frames))}[sound]")
        arguments = [argument for path in sources for argument in ("-i", path)]
        staging = scratch / "master.mp4"
        subprocess.run(ffmpeg(
            "-f", "concat", "-i", concat, *arguments, "-i", metadata,
            "-filter_complex", ";".join(filters), "-map", "[picture]" if progress else "0:v:0",
            "-map", "[sound]", "-map_metadata", str(len(sources) + 1),
            "-map_chapters", str(len(sources) + 1),
            *(video_encoding("high") if progress else ["-c:v", "copy"]),
            *AUDIO_ENCODING, *MP4_FLAGS, staging,
        ), check=True)
        verify_file(staging, sum(frames))
        os.replace(staging, output)
    picture_status = "progress rendered" if progress else "video copied" if copy_picture else "video normalized"
    print(f"{output} ({picture_status}, {sum(frames) / FPS:.3f}s)")


def verify_file(path, expected_frames=None):
    video, audio, media = probe(path)
    if not video:
        raise ValueError("File contains no video")
    if expected_frames is not None:
        result = canonical_frames(path, video)
        if result is None or result[0] != expected_frames:
            raise ValueError(f"Expected {expected_frames} continuous 1080p30 video frames")
        if (not audio or audio.get("codec_name") != "aac" or audio.get("sample_rate") != str(SAMPLE_RATE)
                or audio.get("channel_layout") != "stereo"):
            raise ValueError("Output requires 48 kHz stereo AAC audio")
        length = stream_duration(audio, media)
        if (audio.get("start_pts") != 0 or not math.isfinite(length)
                or abs(length - expected_frames / FPS) > 1 / SAMPLE_RATE):
            raise ValueError("Audio and picture end at different times")
    streams = ["-map", f"0:{video['index']}"]
    if audio:
        streams += ["-map", f"0:{audio['index']}"]
    subprocess.run(ffmpeg("-xerror", "-i", path, *streams, "-f", "null", "-"), check=True)
    return video, audio, media


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    make = commands.add_parser("render", help="Render one scene from a JSON manifest")
    make.add_argument("scene")
    make.add_argument("output")
    combine = commands.add_parser("assemble", help="Join ordered scenes into one MP4")
    combine.add_argument("output")
    combine.add_argument("scenes", nargs="+")
    combine.add_argument("--opening", help="Prepend a cover clip outside the body progress segments")
    combine.add_argument("--no-progress", action="store_true", help="Join compatible picture frames without an overlay")
    validate = commands.add_parser("verify", help="Decode and inspect a video")
    validate.add_argument("file")
    args = parser.parse_args()
    try:
        if args.command == "render":
            render(args.scene, args.output, strict=True)
        elif args.command == "assemble":
            assemble(args.output, args.scenes, opening=args.opening, progress=not args.no_progress)
        else:
            path = input_path(args.file)
            video, audio, media = verify_file(path)
            duration = stream_duration(video, media)
            print(json.dumps({
                "file": str(path), "width": video["width"], "height": video["height"],
                "frame_rate": video.get("avg_frame_rate"), "duration": duration if math.isfinite(duration) else None,
                "video_codec": video.get("codec_name"), "audio_codec": audio and audio.get("codec_name"),
            }, indent=2, ensure_ascii=False))
    except (OSError, ValueError, KeyError, subprocess.CalledProcessError) as error:
        parser.exit(1, f"video.py: {error}\n")


if __name__ == "__main__":
    main()
