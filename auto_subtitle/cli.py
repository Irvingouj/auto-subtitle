import argparse
import os
import re
import subprocess
import tempfile
import warnings
from typing import Any, Callable, Dict, List

import whisper

from .utils import filename, str2bool, write_srt


def run_ffmpeg_with_progress(cmd_args: List[str], description: str) -> None:
    print(f"{description}")

    process = subprocess.Popen(
        cmd_args,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        bufsize=1,
    )

    duration = None
    stderr_output = []

    if process.stderr:
        for line in process.stderr:
            line = line.strip()
            stderr_output.append(line)

            if "Duration:" in line:
                duration_match = re.search(r"Duration: (\d+):(\d+):(\d+\.\d+)", line)
                if duration_match:
                    h, m, s = duration_match.groups()
                    duration = int(h) * 3600 + int(m) * 60 + float(s)

            elif "time=" in line and duration:
                time_match = re.search(r"time=(\d+):(\d+):(\d+\.\d+)", line)
                if time_match:
                    h, m, s = time_match.groups()
                    current_time = int(h) * 3600 + int(m) * 60 + float(s)
                    progress = min(current_time / duration * 100, 100)

                    print(f"\rProgress: {progress:.1f}%", end="", flush=True)

    process.wait()
    if process.returncode != 0:
        print(f"\nFFmpeg error (exit code {process.returncode}):")
        for line in stderr_output[-10:]:  # Show last 10 lines of error output
            print(line)
        raise subprocess.CalledProcessError(process.returncode, cmd_args, "\n".join(stderr_output))

    print("\rProgress: 100.0% - Complete!                ")


def main() -> None:
    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument(
        "video", nargs="+", type=str, help="paths to video files to transcribe"
    )
    parser.add_argument(
        "--model",
        default="small",
        choices=whisper.available_models(),
        help="name of the Whisper model to use",
    )
    parser.add_argument(
        "--output_dir",
        "-o",
        type=str,
        default=".",
        help="directory to save the outputs",
    )
    parser.add_argument(
        "--output_srt",
        type=str2bool,
        default=False,
        help="whether to output the .srt file along with the video files",
    )
    parser.add_argument(
        "--srt_only",
        type=str2bool,
        default=False,
        help="only generate the .srt file and not create overlayed video",
    )
    parser.add_argument(
        "--verbose",
        type=str2bool,
        default=False,
        help="whether to print out the progress and debug messages",
    )

    parser.add_argument(
        "--task",
        type=str,
        default="transcribe",
        choices=["transcribe", "translate"],
        help="whether to perform X->X speech recognition ('transcribe') or X->English translation ('translate')",
    )
    parser.add_argument(
        "--language",
        type=str,
        default="auto",
        choices=[
            "auto",
            "af",
            "am",
            "ar",
            "as",
            "az",
            "ba",
            "be",
            "bg",
            "bn",
            "bo",
            "br",
            "bs",
            "ca",
            "cs",
            "cy",
            "da",
            "de",
            "el",
            "en",
            "es",
            "et",
            "eu",
            "fa",
            "fi",
            "fo",
            "fr",
            "gl",
            "gu",
            "ha",
            "haw",
            "he",
            "hi",
            "hr",
            "ht",
            "hu",
            "hy",
            "id",
            "is",
            "it",
            "ja",
            "jw",
            "ka",
            "kk",
            "km",
            "kn",
            "ko",
            "la",
            "lb",
            "ln",
            "lo",
            "lt",
            "lv",
            "mg",
            "mi",
            "mk",
            "ml",
            "mn",
            "mr",
            "ms",
            "mt",
            "my",
            "ne",
            "nl",
            "nn",
            "no",
            "oc",
            "pa",
            "pl",
            "ps",
            "pt",
            "ro",
            "ru",
            "sa",
            "sd",
            "si",
            "sk",
            "sl",
            "sn",
            "so",
            "sq",
            "sr",
            "su",
            "sv",
            "sw",
            "ta",
            "te",
            "tg",
            "th",
            "tk",
            "tl",
            "tr",
            "tt",
            "uk",
            "ur",
            "uz",
            "vi",
            "yi",
            "yo",
            "zh",
        ],
        help="What is the origin language of the video? If unset, it is detected automatically.",
    )

    args = parser.parse_args().__dict__
    model_name: str = args.pop("model")
    output_dir: str = args.pop("output_dir")
    output_srt: bool = args.pop("output_srt")
    srt_only: bool = args.pop("srt_only")
    language: str = args.pop("language")

    # Normalize video paths to handle ~ and relative paths
    video_paths = args.pop("video")
    args["video"] = [os.path.abspath(os.path.expanduser(path)) for path in video_paths]

    os.makedirs(output_dir, exist_ok=True)

    if model_name.endswith(".en"):
        warnings.warn(
            f"{model_name} is an English-only model, forcing English detection.",
            stacklevel=2
        )
        args["language"] = "en"
    # if translate task used and language argument is set, then use it
    elif language != "auto":
        args["language"] = language

    model = whisper.load_model(model_name)
    audios = get_audio(args.pop("video"))
    subtitles = get_subtitles(
        audios,
        output_srt or srt_only,
        output_dir,
        lambda audio_path: model.transcribe(audio_path, **args),
    )

    if srt_only:
        return

    for path, srt_path in subtitles.items():
        out_path = os.path.join(output_dir, f"{filename(path)}.mp4")

        cmd_args = [
            "ffmpeg",
            "-y",
            "-i",
            path,
            "-vf",
            f"subtitles='{srt_path}':force_style='OutlineColour=&H40000000,BorderStyle=3'",
            "-c:a",
            "copy",
            out_path,
        ]

        run_ffmpeg_with_progress(cmd_args, f"Adding subtitles to {filename(path)}...")

        print(f"Saved subtitled video to {os.path.abspath(out_path)}.")


def get_audio(paths: List[str]) -> Dict[str, str]:
    temp_dir = tempfile.gettempdir()

    audio_paths = {}

    for path in paths:
        output_path = os.path.join(temp_dir, f"{filename(path)}.wav")

        cmd_args = [
            "ffmpeg",
            "-y",
            "-i",
            path,
            "-acodec",
            "pcm_s16le",
            "-ac",
            "1",
            "-ar",
            "16k",
            output_path,
        ]

        run_ffmpeg_with_progress(cmd_args, f"Extracting audio from {filename(path)}...")

        audio_paths[path] = output_path

    return audio_paths


def get_subtitles(
    audio_paths: Dict[str, str],
    output_srt: bool,
    output_dir: str,
    transcribe: Callable[[str], Dict[str, Any]],
) -> Dict[str, str]:
    subtitles_path = {}

    for path, audio_path in audio_paths.items():
        srt_path = output_dir if output_srt else tempfile.gettempdir()
        srt_path = os.path.join(srt_path, f"{filename(path)}.srt")

        print(f"Generating subtitles for {filename(path)}... This might take a while.")

        warnings.filterwarnings("ignore")
        result = transcribe(audio_path)
        warnings.filterwarnings("default")

        with open(srt_path, "w", encoding="utf-8") as srt:
            write_srt(result["segments"], file=srt)

        subtitles_path[path] = srt_path

    return subtitles_path


if __name__ == "__main__":
    main()
