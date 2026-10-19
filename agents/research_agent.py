
# agents/research_agent.py

import json
import re
from urllib.parse import urlparse

from tools.web_search import search_web
from agents.coding_agent import LocalCodingAgent


class ResearchAgent:
    """
    Researches startups using web search and a local Ollama LLM.

    Expected web_search result fields:
        title, url, content, snippet, retrieval_status

    Output:
        A list of startups with source evidence.
    """

    INDUSTRY_QUERIES = {
        "healthtech": [
            "HealthTech startups India funding growth",
            "Indian digital health startups recently funded",
            "healthcare technology startups India official website",
            "HealthTech companies India revenue customers",
        ],
        "fintech": [
            "FinTech startups India funding growth",
            "Indian fintech startups recently funded",
            "fintech companies India revenue customers",
            "FinTech startups India official website",
        ],
        "edtech": [
            "EdTech startups India funding growth",
            "Indian education technology startups funded",
            "EdTech companies India customers revenue",
        ],
        "agritech": [
            "Agritech startups India funding growth",
            "Indian agriculture technology startups funded",
            "Agritech companies India customers revenue",
        ],
        "climatetech": [
            "ClimateTech startups India funding growth",
            "Indian climate technology startups funded",
            "ClimateTech companies India customers revenue",
        ],
        "saas": [
            "SaaS startups India funding growth",
            "Indian SaaS companies customers revenue",
            "B2B software startups India funding",
        ],
        "ai": [
            "AI startups India funding growth",
            "Indian artificial intelligence startups funded",
            "AI companies India customers revenue",
        ],
        "ecommerce": [
            "ecommerce startups India funding growth",
            "Indian ecommerce companies recently funded",
            "D2C startups India revenue customers",
        ],
    }

    def __init__(self, llm=None):
        self.llm = llm or LocalCodingAgent()

    # ---------------------------------------------------------
    # General utilities
    # ---------------------------------------------------------

    @staticmethod
    def normalize_text(value):
        """Normalize text for comparison."""
        value = str(value or "").lower()
        value = re.sub(r"https?://\S+", " ", value)
        value = re.sub(r"[^a-z0-9&.+ -]", " ", value)
        return re.sub(r"\s+", " ", value).strip()

    @staticmethod
    def normalize_name(name):
        """Create a normalized company name for deduplication."""
        name = str(name or "").strip().lower()
        name = re.sub(r"\b(private limited|pvt ltd|pvt\. ltd|limited|ltd)\b", "", name)
        name = re.sub(r"[^a-z0-9]", "", name)
        return name

    @staticmethod
    def valid_name(name):
        """Reject empty, generic, or obviously invalid company names."""
        if not isinstance(name, str):
            return False

        name = name.strip()

        if len(name) < 2 or len(name) > 100:
            return False

        generic_names = {
            "startup",
            "startups",
            "company",
            "companies",
            "business",
            "businesses",
            "healthcare",
            "technology",
            "fintech",
            "healthtech",
            "edtech",
            "saas",
            "india",
            "global",
            "market",
            "industry",
            "funding",
            "investment",
            "report",
            "website",
            "unknown",
            "n/a",
            "none",
        }

        if name.lower().strip(" .,-") in generic_names:
            return False

        if name.startswith(("http://", "https://", "www.")):
            return False

        return True

    @classmethod
    def name_appears_in_source(cls, name, title, content):
        """
        Verify that the proposed name appears in the source text.

        This checks textual presence only; it does not prove that
        every claim about the company is true.
        """
        name_normalized = cls.normalize_name(name)

        if not name_normalized:
            return False

        source = cls.normalize_name(f"{title} {content}")

        if name_normalized in source:
            return True

        # Handle some punctuation and spacing differences.
        words = re.findall(r"[A-Za-z0-9]+", name.lower())

        if not words:
            return False

        pattern = r"[\W_]+".join(re.escape(word) for word in words)
        return bool(
            re.search(
                pattern,
                f"{title} {content}",
                flags=re.IGNORECASE,
            )
        )

    # ---------------------------------------------------------
    # Search
    # ---------------------------------------------------------

    def search(self, query, max_results=6):
        """Run web search and normalize its output."""
        print(f"[SEARCH] {query}")

        try:
            results = search_web(query, max_results=max_results)
        except TypeError:
            # Compatibility if the existing function uses a
            # different parameter name or accepts only one argument.
            results = search_web(query)
        except Exception as exc:
            print(f"[SEARCH WARNING] {exc}")
            return []

        if not isinstance(results, list):
            print("[SEARCH WARNING] Search function did not return a list.")
            return []

        normalized = []

        for item in results:
            if not isinstance(item, dict):
                continue

            title = str(item.get("title") or "").strip()
            url = str(
                item.get("url")
                or item.get("href")
                or ""
            ).strip()

            content = str(
                item.get("content")
                or item.get("body")
                or ""
            ).strip()

            snippet = str(item.get("snippet") or "").strip()

            if not content:
                content = snippet

            if not title and not content:
                continue

            normalized.append(
                {
                    "title": title,
                    "url": url,
                    "href": url,
                    "content": content,
                    "body": content,
                    "snippet": snippet,
                    "retrieval_status": item.get(
                        "retrieval_status",
                        "unknown",
                    ),
                }
            )

        print(f"[SEARCH] Received {len(normalized)} usable results.")
        return normalized

    # ---------------------------------------------------------
    # Query planning
    # ---------------------------------------------------------

    def build_queries(
        self,
        industry,
        geography="India",
        priority="funding and growth",
        custom_queries=None,
    ):
        """Build relevant queries without relying entirely on the LLM."""
        industry_text = str(industry).strip()
        geography_text = str(geography).strip() or "India"
        priority_text = str(priority).strip() or "funding and growth"

        industry_key = industry_text.lower().replace(" ", "")
        base_queries = self.INDUSTRY_QUERIES.get(industry_key, [])

        queries = []

        # Include custom queries first when supplied.
        if custom_queries:
            if isinstance(custom_queries, str):
                custom_queries = [custom_queries]

            queries.extend(
                query.strip()
                for query in custom_queries
                if isinstance(query, str) and query.strip()
            )

        # Generate focused queries for the requested industry,
        # geography, and evaluation priority.
        queries.extend(
            [
                f"{industry_text} startups in {geography_text} {priority_text}",
                f"{industry_text} companies {geography_text} funding customers revenue",
                f"best {industry_text} startups {geography_text} recent developments",
            ]
        )

        for query in base_queries:
            queries.append(f"{query} {geography_text}")

        # Preserve order while removing duplicate queries.
        unique_queries = []
        seen = set()

        for query in queries:
            key = self.normalize_text(query)

            if key and key not in seen:
                seen.add(key)
                unique_queries.append(query)

        return unique_queries[:8]

    # ---------------------------------------------------------
    # Company extraction
    # ---------------------------------------------------------

    def extract_companies_batch(self, industry, geography, batch):
        """
        Extract candidates one source at a time.

        Smaller prompts are generally more reliable with a local
        3B model than asking it to process many full web pages at once.
        """
        output = []

        for index, result in enumerate(batch, start=1):
            title = str(result.get("title") or "").strip()
            url = str(
                result.get("url")
                or result.get("href")
                or ""
            ).strip()

            content = str(
                result.get("content")
                or result.get("body")
                or result.get("snippet")
                or ""
            ).strip()

            if not url or not content:
                print(f"[EXTRACT SKIP] Missing URL/content: {title[:60]}")
                continue

            source_text = content[:3500]

            prompt = f"""
You extract startup names from source text.

Task:
Identify up to 5 real company or startup names explicitly mentioned
in the source. Prefer companies relevant to the requested industry
and geography.

Industry: {industry}
Geography: {geography}
Source title: {title}

Rules:
- Use only names actually present in the source.
- Do not invent companies.
- Do not treat an industry, country, article title, or generic phrase
  as a company name.
- Do not guess funding, revenue, customers, or financial performance.
- If there are no suitable company names, return an empty list.
- Return valid JSON only, without Markdown fences.

Required format:
{{
  "companies": [
    {{
      "name": "Exact company name as written in the source",
      "description": "Short description supported by the source"
    }}
  ]
}}

SOURCE TEXT:
{source_text}
"""

            try:
                response = self.llm.generate(prompt)
                parsed = self.llm.extract_json(
                    response,
                    {"companies": []},
                )
            except Exception as exc:
                print(
                    f"[EXTRACT WARNING] "
                    f"{title[:45]}: {exc}"
                )
                continue

            if not isinstance(parsed, dict):
                print(f"[EXTRACT WARNING] Invalid JSON structure: {title[:50]}")
                continue

            candidates = parsed.get("companies", [])

            if not isinstance(candidates, list):
                continue

            accepted_from_source = 0

            for item in candidates:
                if not isinstance(item, dict):
                    continue

                name = str(item.get("name") or "").strip()
                description = str(
                    item.get("description") or ""
                ).strip()

                if not self.valid_name(name):
                    continue

                if not self.name_appears_in_source(
                    name,
                    title,
                    content,
                ):
                    print(f"[EXTRACT REJECT] Name not found: {name}")
                    continue

                # Do not accept an LLM-generated description as
                # verified evidence unless it can be located in
                # the source text. Keep it blank otherwise.
                if description:
                    if description.lower() not in content.lower():
                        description = ""

                domain = urlparse(url).hostname or ""

                output.append(
                    {
                        "name": name,
                        "industry": industry,
                        "geography": geography,
                        "description": description,
                        "industry_match_reason": "",
                        "source_evidence": [
                            {
                                "title": title,
                                "url": url,
                                "content": content,
                                "domain": domain,
                                "retrieval_status": result.get(
                                    "retrieval_status",
                                    "unknown",
                                ),
                            }
                        ],
                        "funding_claims": [],
                    }
                )

                accepted_from_source += 1

            print(
                f"[EXTRACT] Source {index}/{len(batch)}: "
                f"{accepted_from_source} candidates — {title[:55]}"
            )

        print(f"[EXTRACT] Accepted {len(output)} source-matched candidates.")
        return output

    # ---------------------------------------------------------
    # Deduplication
    # ---------------------------------------------------------

    def deduplicate_companies(self, companies):
        """Merge records for the same normalized company name."""
        merged = {}
        order = []

        for company in companies:
            name = str(company.get("name") or "").strip()
            key = self.normalize_name(name)

            if not key:
                continue

            if key not in merged:
                merged[key] = dict(company)
                merged[key]["source_evidence"] = list(
                    company.get("source_evidence") or []
                )
                merged[key]["funding_claims"] = list(
                    company.get("funding_claims") or []
                )
                order.append(key)
                continue

            existing = merged[key]

            if not existing.get("description") and company.get("description"):
                existing["description"] = company["description"]

            evidence_seen = {
                item.get("url")
                for item in existing.get("source_evidence", [])
                if isinstance(item, dict)
            }

            for evidence in company.get("source_evidence", []):
                if not isinstance(evidence, dict):
                    continue

                evidence_url = evidence.get("url")

                if evidence_url not in evidence_seen:
                    existing["source_evidence"].append(evidence)
                    evidence_seen.add(evidence_url)

            existing_claims = existing.setdefault("funding_claims", [])

            for claim in company.get("funding_claims", []):
                if claim not in existing_claims:
                    existing_claims.append(claim)

        return [merged[key] for key in order]

    # ---------------------------------------------------------
    # Main research workflow
    # ---------------------------------------------------------

    def research(
        self,
        industry,
        geography="India",
        priority="funding and growth",
        max_results_per_query=6,
        custom_queries=None,
        max_companies=30,
    ):
        """
        Search for startups and return deduplicated candidates.

        This stage discovers candidates. It does not independently
        establish that every candidate meets all ranking criteria.
        """
        print("\n" + "=" * 65)
        print("STARTUP RESEARCH")
        print(f"Industry: {industry}")
        print(f"Geography: {geography}")
        print(f"Priority: {priority}")
        print("=" * 65)

        queries = self.build_queries(
            industry=industry,
            geography=geography,
            priority=priority,
            custom_queries=custom_queries,
        )

        all_results = []
        seen_urls = set()

        for query in queries:
            results = self.search(
                query,
                max_results=max_results_per_query,
            )

            for result in results:
                url = str(result.get("url") or "").strip()

                if url:
                    normalized_url = url.rstrip("/").lower()

                    if normalized_url in seen_urls:
                        continue

                    seen_urls.add(normalized_url)

                all_results.append(result)

        print(f"\n[RESEARCH] Total unique search results: {len(all_results)}")

        if not all_results:
            print("[RESEARCH] No usable web results were found.")
            return []

        # Process each source independently to reduce prompt size
        # and improve extraction reliability for smaller local models.
        extracted = self.extract_companies_batch(
            industry,
            geography,
            all_results,
        )

        companies = self.deduplicate_companies(extracted)

        # Sort by number of distinct sources. This is a discovery
        # heuristic, not a measure of financial quality.
        companies.sort(
            key=lambda company: len(
                {
                    evidence.get("url")
                    for evidence in company.get("source_evidence", [])
                    if isinstance(evidence, dict)
                    and evidence.get("url")
                }
            ),
            reverse=True,
        )

        if max_companies is not None and max_companies > 0:
            companies = companies[:max_companies]

        print("\n" + "=" * 65)
        print(f"[RESEARCH] Found {len(companies)} unique companies.")
        print("=" * 65)

        for index, company in enumerate(companies, start=1):
            source_count = len(company.get("source_evidence", []))
            print(
                f"{index:02d}. {company['name']} "
                f"({source_count} source(s))"
            )

        return companies


# -------------------------------------------------------------
# Standalone test
# -------------------------------------------------------------

if __name__ == "__main__":
    agent = ResearchAgent()

    results = agent.research(
        industry="HealthTech",
        geography="India",
        priority="funding and growth",
        max_results_per_query=4,
        max_companies=30,
    )

    print("\nRESEARCH SUMMARY")
    print(f"Candidates discovered: {len(results)}")

    with open(
        "research_results.json",
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            results,
            file,
            indent=2,
            ensure_ascii=False,
        )

    print("Saved results to research_results.json")
