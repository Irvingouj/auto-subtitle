# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Python package that automatically generates and overlays subtitles on videos using OpenAI's Whisper and ffmpeg. The project creates a command-line tool that can transcribe speech to text and embed subtitles directly into video files.

## Installation and Setup

The package is installed via pip:
```bash
pip install git+https://github.com/m1guelpf/auto-subtitle.git
```

External dependency required:
- `ffmpeg` must be installed on the system

## Architecture

The codebase is structured as a simple Python package:

- `auto_subtitle/cli.py`: Main entry point with argument parsing and orchestration logic
- `auto_subtitle/utils.py`: Utility functions for timestamp formatting, SRT file writing, and helper functions
- `setup.py`: Package configuration with console script entry point

### Core Workflow

1. **Audio Extraction**: Videos are processed with ffmpeg to extract 16kHz mono WAV audio
2. **Transcription**: Whisper models transcribe audio to text with timestamps
3. **SRT Generation**: Transcription results are formatted into SRT subtitle files
4. **Video Processing**: ffmpeg overlays subtitles onto the original video

### Key Components

- **CLI Interface**: Supports multiple Whisper models (tiny to large), language selection, and output options
- **Audio Processing**: Temporary audio files are created in system temp directory
- **Subtitle Formatting**: Custom SRT timestamp formatting with millisecond precision
- **Video Output**: Configurable output directory with subtitle styling options

## Development Commands

This project uses uv for dependency management. Common development tasks:

```bash
# Install dependencies and create virtual environment
uv sync

# Run the tool
uv run auto_subtitle /path/to/video.mp4

# Add new dependencies
uv add package_name

# Add development dependencies
uv add --dev package_name

# Install in editable mode for development
uv pip install -e .
```

# Code quality tools
uv run ruff check .    # Lint code
uv run ruff format .   # Format code
uv run mypy auto_subtitle/  # Type check

No test framework or build scripts are currently configured in this project.

## Language and Model Support

The tool supports:
- Multiple Whisper model sizes (tiny, small, medium, large with .en variants)
- 99 language codes for transcription
- Translation mode (X->English)
- Automatic language detection