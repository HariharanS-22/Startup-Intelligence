
import json
import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv
from magic_hour import Client


PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")


class VideoAgent:
    """Generate a Startup Intelligence explainer using Magic Hour."""

    def __init__(self):
        self.api_key = os.getenv("MAGIC_HOUR_API_KEY", "").strip()
        self.model = os.getenv("VIDEO_MODEL", "ltx-2.5").strip()
        self.duration = int(
            os.getenv("VIDEO_DURATION_SECONDS", "5")
        )
        self.resolution = os.getenv(
            "VIDEO_RESOLUTION", "480p"
        ).strip()

        self.output_dir = PROJECT_ROOT / "outputs" / "videos"
        self.output_dir.mkdir(parents=True, exist_ok=True)

        if not self.api_key or self.api_key == "your_actual_magic_hour_api_key":
            raise ValueError(
                "Set your actual MAGIC_HOUR_API_KEY in the project .env file."
            )

        if self.duration < 1:
            raise ValueError("Video duration must be positive.")

        self.client = Client(token=self.api_key)

    def generate_explainer(self, project_name="Startup Intelligence"):
        prompt = f"""
Create a polished technology explainer video for {project_name},
a multi-agent AI system that researches and ranks startups.

Show a cohesive sequence of visual stages:
1. Intro title: Startup Intelligence.
2. User enters a startup category such as FinTech or HealthTech.
3. Research Agent gathers startup data from web sources.
4. Local Coding Agent, powered by an open-source language model,
   supports automated coding and analysis.
5. Ranking Agent evaluates funding, financial performance,
   customer traction, recent developments, and market position.
6. Display a dashboard with the top 10 ranked startups.
7. Show an AI Logo Generation Agent creating the project logo.
8. End with a professional report and the words
   "Research. Evaluate. Rank. Report."

Visual style: modern AI technology, dark navy background,
cyan and white accents, glowing data connections, clean dashboard,
smooth camera motion, cinematic lighting, professional university
project presentation.

Use coherent imagery and smooth transitions. Keep the scene
uncluttered. Avoid misspelled text and unrelated imagery.
Make the visual story understandable even without narration.
""".strip()

        output_path = self.output_dir / "startup_workflow_explainer.mp4"

        print("\nStarting Magic Hour video generation...")
        print(f"Model: {self.model}")
        print(f"Duration: {self.duration} seconds")
        print(f"Resolution: {self.resolution}")
        print(f"Output directory: {self.output_dir}")
        print("Generation may take several minutes.")

        start_time = time.time()

        result = self.client.v1.text_to_video.generate(
            name="Startup Intelligence Explainer",
            end_seconds=self.duration,
            aspect_ratio="16:9",
            style={"prompt": prompt},
            model=self.model,
            resolution=self.resolution,
            wait_for_completion=True,
            download_outputs=True,
            download_directory=str(self.output_dir),
        )

        elapsed = round(time.time() - start_time, 2)

        status = getattr(result, "status", "unknown")
        downloaded_paths = getattr(result, "downloaded_paths", None)
        credits_charged = getattr(result, "credits_charged", None)
        error = getattr(result, "error", None)

        if status != "complete":
            error_message = (
                getattr(error, "message", str(error))
                if error else "No additional error details returned."
            )
            raise RuntimeError(
                f"Magic Hour job status: {status}. {error_message}"
            )

        # The SDK downloads the generated file to output_dir.
        downloaded_files = []

        if downloaded_paths:
            if isinstance(downloaded_paths, (str, Path)):
                downloaded_paths = [downloaded_paths]

            for item in downloaded_paths:
                path = Path(str(item))
                if not path.is_absolute():
                    path = self.output_dir / path

                if path.exists() and path.is_file():
                    downloaded_files.append(path)

        # If the SDK used a different filename, rename the first
        # downloaded video to the expected project filename.
        if not downloaded_files:
            candidates = [
                path for path in self.output_dir.glob("*")
                if path.is_file()
                and path.suffix.lower() in {".mp4", ".mov", ".webm"}
                and path.name != output_path.name
            ]

            if candidates:
                downloaded_files = [
                    max(candidates, key=lambda p: p.stat().st_mtime)
                ]

        if not downloaded_files:
            raise RuntimeError(
                "The job completed, but no downloaded video was found. "
                f"Check the SDK result: {result}"
            )

        source_path = downloaded_files[0]

        if source_path.resolve() != output_path.resolve():
            if output_path.exists():
                output_path.unlink()
            source_path.replace(output_path)

        report = {
            "project": project_name,
            "agent": "VideoAgent",
            "provider": "Magic Hour",
            "status": status,
            "model": self.model,
            "requested_duration_seconds": self.duration,
            "resolution": self.resolution,
            "aspect_ratio": "16:9",
            "video_path": str(output_path),
            "video_size_bytes": output_path.stat().st_size,
            "credits_charged": credits_charged,
            "generation_time_seconds": elapsed,
        }

        report_path = self.output_dir / "video_report.json"
        with report_path.open("w", encoding="utf-8") as file:
            json.dump(report, file, indent=4, ensure_ascii=False)

        print("\nVideo generation completed.")
        print(f"Video: {output_path}")
        print(f"Report: {report_path}")
        print(f"Size: {output_path.stat().st_size / (1024 * 1024):.2f} MB")
        print(f"Time: {elapsed} seconds")
        print(f"Credits charged: {credits_charged}")

        return report


def main():
    try:
        agent = VideoAgent()
        report = agent.generate_explainer()
        print("\n" + json.dumps(report, indent=4))

    except KeyboardInterrupt:
        print("\nGeneration cancelled.")
        sys.exit(130)

    except Exception as exc:
        print(f"\nVIDEO GENERATION FAILED: {exc}")
        print(
            "Check your API key, available credits, model settings, "
            "and the error message returned by Magic Hour."
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
