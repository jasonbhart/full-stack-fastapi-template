"""Evaluation metrics loaded from markdown prompts."""

import os

metrics: list[dict[str, str]] = []

PROMPTS_DIR = os.path.join(os.path.dirname(__file__), "prompts")

# Auto-discover and load all metric prompts
if os.path.exists(PROMPTS_DIR):
    for file in os.listdir(PROMPTS_DIR):
        if file.endswith(".md"):
            with open(os.path.join(PROMPTS_DIR, file)) as f:
                metrics.append({"name": file.replace(".md", ""), "prompt": f.read()})
