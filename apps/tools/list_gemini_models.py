"""List Gemini models and highlight those that support generateContent."""
from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

try:
    import google.generativeai as genai
except ModuleNotFoundError as exc:  # pragma: no cover - optional helper
    raise RuntimeError(
        "google-generativeai is required. Install via pip install -r requirements.txt"
    ) from exc

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DOTENV_PATH = PROJECT_ROOT / ".env"


def load_env() -> None:
    load_dotenv(dotenv_path=DOTENV_PATH)


def list_models() -> None:
    load_env()
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not set in .env")

    genai.configure(api_key=api_key)
    models = list(genai.list_models())
    if not models:
        print("No models returned by Gemini API")
        return

    suggested = None
    print("Available Gemini models:")
    for model in models:
        name = getattr(model, "name", "<unknown>")
        methods = getattr(model, "generation_methods", []) or []
        supports = "generateContent" in methods
        flag = "(supports generateContent)" if supports else ""
        print(f"- {name} {flag}")
        if supports and suggested is None:
            suggested = name

    if suggested:
        print(f"\nSuggested default model: {suggested}")
        print("Set GEMINI_MODEL in .env to override the default.")
    else:
        print("\nNo model supporting generateContent was found."
              " Please request access or check your account.")


if __name__ == "__main__":
    try:
        list_models()
    except Exception as exc:  # pragma: no cover - helper output
        print(f"Failed to list models: {exc}")
        sys.exit(1)
