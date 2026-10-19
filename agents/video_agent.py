
import json
import os
import sys
import time
from pathlib import Path
from urllib.parse import quote

import requests
from dotenv import load_dotenv


# Project root: H:\AI_agent
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Load .env from the project root
load_dotenv(PROJECT_ROOT / ".env")


class VideoAgent:
    """Generate one continuous explainer video using Pollinations AI."""

    def __init__(self):
        self.api_key = os.getenv("POLLINATIONS_API_KEY", "").strip()
        self.model = os.getenv(
            "VIDEO_MODEL", "google/veo-3.1-fast"
        ).strip()

        self.output_dir = PROJECT_ROOT / "outputs" / "videos"
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.video_endpoint = "https://gen.pollinations.ai/video"

        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {self.api_key}",
            "Accept": "video/mp4, application/json, */*",
            "User-Agent": "StartupIntelligenceAgent/1.0",
        })

    def _check_configuration(self):
        """Validate required configuration before making a request."""
        if not self.api_key:
            raise ValueError(
                "POLLINATIONS_API_KEY is missing from the project .env file."
            )

        if self.api_key in {
            "your_pollinations_key",
            "YOUR_POLLINATIONS_API_KEY",
        }:
            raise ValueError(
                "Replace the placeholder API key in .env with your real "
                "Pollinations API key."
            )

        if not self.model:
            raise ValueError("VIDEO_MODEL cannot be empty.")

    @staticmethod
    def _is_video_content(content_type):
        return content_type.lower().startswith("video/")

    def _download_video_url(self, video_url, output_path):
        """Download a generated video when the API returns a URL."""
        if not video_url.startswith("https://"):
            raise RuntimeError(
                "The API returned a video URL that is not HTTPS."
            )

        # Avoid forwarding the API key to a different host.
        response = requests.get(
            video_url,
            timeout=(20, 300),
            stream=True,
        )

        try:
            response.raise_for_status()

            content_type = response.headers.get(
                "Content-Type", ""
            )

            if not self._is_video_content(content_type):
                raise RuntimeError(
                    "The returned URL did not provide a video file. "
                    f"Content-Type: {content_type or 'unknown'}"
                )

            total_bytes = 0
            max_bytes = 20 * 1024 * 1024

            with output_path.open("wb") as video_file:
                for chunk in response.iter_content(chunk_size=1024 * 256):
                    if not chunk:
                        continue

                    total_bytes += len(chunk)

                    if total_bytes > max_bytes:
                        raise RuntimeError(
                            "The video exceeds the 20 MB download limit."
                        )

                    video_file.write(chunk)

            if total_bytes == 0:
                raise RuntimeError("The downloaded video is empty.")

        except Exception:
            output_path.unlink(missing_ok=True)
            raise
        finally:
            response.close()

        return total_bytes

    def generate_clip(
        self,
        prompt,
        filename="startup_workflow_explainer.mp4",
        duration=8,
        aspect_ratio="16:9",
    ):
        """Generate and save a single MP4 video."""
        self._check_configuration()

        if not prompt or not prompt.strip():
            raise ValueError("The video prompt cannot be empty.")

        if not isinstance(duration, int) or duration < 1:
            raise ValueError("Duration must be a positive integer.")

        output_path = self.output_dir / filename
        encoded_prompt = quote(prompt.strip(), safe="")
        url = f"{self.video_endpoint}/{encoded_prompt}"

        params = {
            "model": self.model,
            "duration": duration,
            "aspectRatio": aspect_ratio,
        }

        print("\nStarting video generation...")
        print(f"Model: {self.model}")
        print(f"Requested duration: {duration} seconds")
        print(f"Output: {output_path}")
        print("This request may take several minutes.")

        start_time = time.time()
        response = None

        try:
            response = self.session.get(
                url,
                params=params,
                timeout=(30, 300),
                stream=True,
            )

            if not response.ok:
                try:
                    error_details = response.text[:3000]
                except Exception:
                    error_details = "No error details returned."

                raise RuntimeError(
                    f"Pollinations API returned HTTP "
                    f"{response.status_code}.\n{error_details}"
                )

            content_type = response.headers.get(
                "Content-Type", ""
            )

            # Case 1: the API returns the MP4 bytes directly.
            if self._is_video_content(content_type):
                total_bytes = 0
                max_bytes = 20 * 1024 * 1024

                with output_path.open("wb") as video_file:
                    for chunk in response.iter_content(
                        chunk_size=1024 * 256
                    ):
                        if not chunk:
                            continue

                        total_bytes += len(chunk)

                        if total_bytes > max_bytes:
                            raise RuntimeError(
                                "The generated video exceeds the "
                                "20 MB response limit."
                            )

                        video_file.write(chunk)

                if total_bytes == 0:
                    raise RuntimeError(
                        "The API returned an empty video."
                    )

            # Case 2: the API returns JSON containing a video URL.
            elif "application/json" in content_type.lower():
                try:
                    payload = response.json()
                except ValueError as exc:
                    raise RuntimeError(
                        "The API returned invalid JSON."
                    ) from exc

                video_url = None

                if isinstance(payload, dict):
                    data = payload.get("data", [])

                    if isinstance(data, list) and data:
                        first_item = data[0]
                        if isinstance(first_item, dict):
                            video_url = first_item.get("url")

                    video_url = video_url or payload.get("url")

                if not video_url:
                    raise RuntimeError(
                        "The API response did not contain a video URL. "
                        f"Response: {json.dumps(payload)[:2000]}"
                    )

                total_bytes = self._download_video_url(
                    video_url, output_path
                )

            else:
                preview = response.text[:1000]
                raise RuntimeError(
                    "The API response was not a recognised video or "
                    f"JSON response. Content-Type: {content_type}\n"
                    f"Response: {preview}"
                )

        except Exception:
            output_path.unlink(missing_ok=True)
            raise

        finally:
            if response is not None:
                response.close()

        elapsed = round(time.time() - start_time, 2)

        if not output_path.exists() or output_path.stat().st_size == 0:
            raise RuntimeError("Video generation failed: output is empty.")

        print("\nVideo generated successfully.")
        print(f"File: {output_path}")
        print(f"Size: {output_path.stat().st_size / (1024 * 1024):.2f} MB")
        print(f"Elapsed time: {elapsed} seconds")

        return {
            "path": str(output_path),
            "filename": output_path.name,
            "model": self.model,
            "requested_duration_seconds": duration,
            "file_size_bytes": output_path.stat().st_size,
            "generation_time_seconds": elapsed,
        }

    def generate_explainer(self, project_name="Startup Intelligence"):
        """Generate one continuous video covering the complete workflow."""

        prompt = f"""
Create one continuous, polished, widescreen 16:9 explainer video
for a software project named "{project_name}".

PROJECT PURPOSE:
An AI agent system that accepts a startup category from a user,
researches startups in that category, evaluates their information,
ranks candidates, and presents the top 10 startups in a report.
The system also has a logo-generation agent and a video-generation agent.

VISUAL STORY, IN THIS ORDER:
1. INTRODUCTION:
   Show the title "{project_name}" over a modern technology-themed
   background with connected AI nodes and subtle animated data.

2. USER INPUT:
   Show a user entering a startup category into a clean dashboard.
   Display example categories such as FinTech, HealthTech, and EdTech.

3. RESEARCH AGENT:
   Show an AI research agent collecting startup information from
   web sources, company profiles, funding announcements, and news.
   Visualise data flowing into a central research pipeline.

4. CODING AGENT:
   Show a local open-source language model running on a computer,
   with a developer terminal and Python automation representing
   the local coding agent.

5. RANKING AGENT:
   Show startup profiles being evaluated against criteria such as
   financial performance, funding, customer traction, recent
   developments, and market position. Visualise a clear ranking process.

6. TOP 10 RESULTS:
   Transition to a professional dashboard with ten ranked startup
   cards, company names represented as generic placeholders,
   scores, and concise business information.

7. IMAGE GENERATION AGENT:
   Show an AI system creating a clean, modern logo for the project.

8. VIDEO GENERATION AGENT AND FINAL OUTPUT:
   Show the explainer video being generated and the final report
   appearing on a computer screen. End on the title
   "{project_name}" and the message "Research. Evaluate. Rank. Report."

STYLE AND QUALITY:
Use a consistent navy-blue, cyan, and white technology aesthetic.
Use smooth transitions, professional motion graphics, clean layouts,
realistic computer screens, subtle data visualisations, and cinematic
lighting. Keep the composition uncluttered and suitable for a university
project demonstration.

Make this a single coherent video with the stages flowing naturally
from one to the next. Avoid abrupt cuts, unrelated imagery, excessive
text, distorted interface elements, and random company logos.
Use readable English labels only where appropriate.

If the selected model supports audio, include clear English narration
and subtle background technology music. Do not rely on audio for the
story to make sense. End with a clean title screen.
""".strip()

        video_result = self.generate_clip(
            prompt=prompt,
            filename="startup_workflow_explainer.mp4",
            duration=8,
            aspect_ratio="16:9",
        )

        report = {
            "project": project_name,
            "agent": "VideoAgent",
            "status": "success",
            "video": video_result,
            "description": (
                "One continuous explainer video covering the user input, "
                "research agent, coding agent, ranking agent, top 10 results, "
                "logo generation, and final report."
            ),
        }

        report_path = self.output_dir / "video_report.json"

        with report_path.open("w", encoding="utf-8") as report_file:
            json.dump(report, report_file, indent=4, ensure_ascii=False)

        print(f"Report saved to: {report_path}")
        return report


def main():
    agent = VideoAgent()

    try:
        report = agent.generate_explainer()
        print("\nVIDEO GENERATION REPORT")
        print(json.dumps(report, indent=4, ensure_ascii=False))

    except KeyboardInterrupt:
        print("\nVideo generation cancelled by user.")
        sys.exit(130)

    except Exception as exc:
        print("\nVIDEO GENERATION FAILED")
        print(f"{type(exc).__name__}: {exc}")
        print(
            "\nCheck your .env API key, model access, internet connection, "
            "and the Pollinations API error details above."
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
