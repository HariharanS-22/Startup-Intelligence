
import json
import os
import requests


class LocalCodingAgent:
    def __init__(
        self,
        model="qwen2.5-coder:3b",
        endpoint="http://localhost:11434/api/chat",
        timeout=None,
    ):
        self.model = model
        self.endpoint = endpoint
        self.timeout = timeout or int(
            os.getenv("OLLAMA_TIMEOUT", "600")
        )

    def generate(self, prompt, system=None, temperature=0.1):
        messages = []

        if system:
            messages.append({
                "role": "system",
                "content": system
            })

        messages.append({
            "role": "user",
            "content": prompt
        })

        try:
            response = requests.post(
                self.endpoint,
                json={
                    "model": self.model,
                    "messages": messages,
                    "stream": False,
                    "options": {
                        "temperature": temperature,
                        "num_predict": 512,
                        "num_ctx": 4096
                    }
                },
                timeout=self.timeout
            )

            if response.status_code == 404:
                raise RuntimeError(
                    f"Ollama returned 404. Check that Ollama is running "
                    f"and model '{self.model}' is installed."
                )

            response.raise_for_status()
            payload = response.json()

            answer = payload.get("message", {}).get("content", "")

            if not isinstance(answer, str) or not answer.strip():
                raise RuntimeError(
                    "Ollama returned an empty response."
                )

            return answer.strip()

        except requests.exceptions.ConnectionError as exc:
            raise RuntimeError(
                "Cannot connect to Ollama at http://localhost:11434. "
                "Start Ollama and try again."
            ) from exc

        except requests.exceptions.Timeout as exc:
            raise RuntimeError(
                f"Ollama did not respond within {self.timeout} seconds. "
                "Try a smaller model or check CPU/RAM usage."
            ) from exc

        except requests.exceptions.HTTPError as exc:
            raise RuntimeError(
                f"Ollama HTTP error: {exc}"
            ) from exc

        except (ValueError, json.JSONDecodeError) as exc:
            raise RuntimeError(
                "Ollama returned invalid JSON."
            ) from exc

    @staticmethod
    def extract_json(text, default=None):
        if default is None:
            default = {}

        cleaned = text.strip()

        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[-1]

            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]

        for opening, closing in (("{", "}"), ("[", "]")):
            start = cleaned.find(opening)
            end = cleaned.rfind(closing)

            if start >= 0 and end >= start:
                try:
                    return json.loads(
                        cleaned[start:end + 1]
                    )
                except json.JSONDecodeError:
                    continue

        return default

    def plan_search(
        self,
        industry,
        geography,
        priority,
        count
    ):
        prompt = f"""
            Create 6 concise web search queries for real startups.

            Industry: {industry}
            Geography: {geography}
            Ranking priority: {priority}
            Target number: {count}

            Discover named companies and evidence about funding, financial
            performance, customer traction, market position and recent
            developments.

            Do not invent company names.

            Return JSON only:
            {{"queries": ["query one", "query two"]}}
            """

        parsed = self.extract_json(
            self.generate(prompt),
            {"queries": []}
        )

        queries = (
            parsed.get("queries", [])
            if isinstance(parsed, dict)
            else []
        )

        return [
            query.strip()
            for query in queries
            if isinstance(query, str) and query.strip()
        ][:8]
