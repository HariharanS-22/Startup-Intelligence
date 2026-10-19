
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

import requests
from dotenv import load_dotenv
from PIL import Image

PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env", override=True)


class ImageGenerationAgent:
    def __init__(self, output_dir="outputs/images"):
        self.api_key = os.getenv("POLLINATIONS_API_KEY")

        if not self.api_key:
            raise ValueError(
                "POLLINATIONS_API_KEY is missing from .env"
            )

        self.model = os.getenv("IMAGE_MODEL", "flux").strip()
        self.output_dir = PROJECT_ROOT / output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {self.api_key}"
        })

        print(f"Image generation model: {self.model}")
        print(f"Output directory: {self.output_dir}")

    @staticmethod
    def safe_filename(name):
        name = re.sub(r"[^A-Za-z0-9_-]+", "_", name)
        return name.strip("_")[:60] or "team_logo"

    @staticmethod
    def build_prompt(team_name, concept, colors, style):
        return f"""
Create a professional logo for a student startup intelligence
agent system.

Team name: {team_name}
Concept: {concept}
Colors: {colors}
Style: {style}

Requirements:
- Square composition.
- Clean background and memorable geometric emblem.
- Represent AI agents, startup discovery, data analysis and ranking.
- Modern, futuristic, professional technology aesthetic.
- High contrast and crisp edges.
- Suitable for a presentation, website and report.
- No watermark, mockup or extra slogans.
- Avoid imitating existing company logos.
"""

    def generate_logo(
        self,
        team_name,
        concept="AI agents discovering promising startups",
        colors="navy blue, electric cyan, and white",
        style="minimal, futuristic, geometric"
    ):
        if not team_name or not team_name.strip():
            raise ValueError("A team name is required.")

        team_name = team_name.strip()
        prompt = self.build_prompt(
            team_name, concept, colors, style
        )

        print("Generating logo. Please wait...")

        url = (
            "https://gen.pollinations.ai/image/"
            + quote(prompt, safe="")
        )

        response = self.session.get(
            url,
            params={
                "model": self.model,
                "width": 1024,
                "height": 1024,
                "seed": 42,
            },
            timeout=300,
        )

        if not response.ok:
            message = response.text[:1500]
            raise RuntimeError(
                f"Pollinations API error ({response.status_code}): "
                f"{message}"
            )

        content_type = response.headers.get(
            "Content-Type", ""
        ).lower()

        if not content_type.startswith("image/"):
            raise RuntimeError(
                "The API did not return an image. "
                f"Content-Type: {content_type}. "
                f"Response: {response.text[:500]}"
            )

        image_bytes = response.content
        filename = self.safe_filename(team_name) + "_logo.png"
        image_path = self.output_dir / filename

        # Validate the response before saving it as PNG.
        try:
            from io import BytesIO

            with Image.open(BytesIO(image_bytes)) as image:
                image.load()
                width, height = image.size
                converted = image.convert("RGBA")
                converted.save(image_path, format="PNG")

        except Exception as exc:
            raise RuntimeError(
                "The API response was not a valid image."
            ) from exc

        report = {
            "status": "success",
            "agent": "ImageGenerationAgent",
            "team_name": team_name,
            "provider": "Pollinations.ai",
            "model": self.model,
            "concept": concept,
            "colors": colors,
            "style": style,
            "image_path": str(image_path.resolve()),
            "image_format": "PNG",
            "width": width,
            "height": height,
            "generated_at": datetime.now(
                timezone.utc
            ).isoformat(),
            "prompt": prompt,
        }

        report_path = self.output_dir / (
            self.safe_filename(team_name) + "_report.json"
        )

        report_path.write_text(
            json.dumps(report, indent=4),
            encoding="utf-8",
        )

        print(f"Logo saved: {image_path}")
        print(f"Report saved: {report_path}")

        return report


if __name__ == "__main__":
    agent = ImageGenerationAgent()

    result = agent.generate_logo(
        team_name="Startup Intelligence",
        concept="Connected AI agents finding and ranking startups",
        colors="navy blue, electric cyan, and white",
        style="minimal, futuristic, geometric",
    )

    print(json.dumps(result, indent=4))
