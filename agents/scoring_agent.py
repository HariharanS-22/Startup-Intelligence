
import re
from urllib.parse import urlparse

from agents.coding_agent import LocalCodingAgent


class ScoringAgent:
    CRITERIA = [
        "financial_performance",
        "funding",
        "customer_traction",
        "recent_developments",
        "market_position",
    ]

    WEIGHTS = {
        "overall performance": {
            "financial_performance": 30,
            "funding": 15,
            "customer_traction": 20,
            "recent_developments": 15,
            "market_position": 20,
        },
        "funding and growth": {
            "financial_performance": 20,
            "funding": 30,
            "customer_traction": 15,
            "recent_developments": 15,
            "market_position": 20,
        },
        "revenue and profitability": {
            "financial_performance": 50,
            "funding": 10,
            "customer_traction": 10,
            "recent_developments": 10,
            "market_position": 20,
        },
        "customer traction": {
            "financial_performance": 15,
            "funding": 10,
            "customer_traction": 40,
            "recent_developments": 15,
            "market_position": 20,
        },
        "innovation and recent developments": {
            "financial_performance": 15,
            "funding": 10,
            "customer_traction": 15,
            "recent_developments": 40,
            "market_position": 20,
        },
        "market position": {
            "financial_performance": 20,
            "funding": 10,
            "customer_traction": 20,
            "recent_developments": 10,
            "market_position": 40,
        },
    }

    SCORE_GUIDANCE = """
Score only what the supplied evidence demonstrates.

0-19: Specific evidence of very weak performance.
20-39: Specific evidence of limited performance.
40-59: Specific evidence of moderate performance.
60-79: Specific evidence of strong performance.
80-89: Substantial quantitative or authoritative evidence.
90-100: Exceptional evidence with a clear comparative basis.

Missing evidence must be null, not zero or 50.
Funding does not prove revenue or profitability.
A company's popularity does not prove financial performance.
A company listicle does not establish exceptional performance.
A source mentioning a company does not prove any particular criterion.
Do not treat an announced funding round as revenue.
Do not infer growth from a single undated metric.
"""

    QUANTITATIVE_PATTERNS = {
        "financial_performance": re.compile(
            r"\b(revenue|net profit|profit|loss|profitability|"
            r"operating income|ebitda|margin|year[- ]over[- ]year|"
            r"year[- ]on[- ]year|grew by|growth of)\b",
            re.I,
        ),
        "funding": re.compile(
            r"\b(raised|funding round|series [a-f]|seed round|"
            r"investment of|invested|funding of|million|billion|crore)\b",
            re.I,
        ),
        "customer_traction": re.compile(
            r"\b(customers|users|merchants|transactions|"
            r"customers served|active users|downloads|"
            r"policyholders|businesses onboarded|gmv)\b",
            re.I,
        ),
        "recent_developments": re.compile(
            r"\b(launched|announced|partnered|partnership|"
            r"expanded|expansion|acquired|acquisition|"
            r"introduced|appointed|entered the market)\b",
            re.I,
        ),
        "market_position": re.compile(
            r"\b(market share|ranked|ranking|market leader|"
            r"largest|number one|no\. 1|leading provider|"
            r"market position|market leader)\b",
            re.I,
        ),
    }

    def __init__(self, llm=None, min_evidence_coverage=80):
        self.llm = llm or LocalCodingAgent()
        self.min_evidence_coverage = max(
            0, min(100, float(min_evidence_coverage))
        )

    @staticmethod
    def valid_score(score):
        return (
            isinstance(score, (int, float))
            and not isinstance(score, bool)
            and 0 <= score <= 100
        )

    @staticmethod
    def normalize_url(url):
        try:
            parsed = urlparse(str(url or "").strip())
            if parsed.scheme not in ("http", "https") or not parsed.hostname:
                return None

            return (
                parsed.scheme.lower(),
                parsed.hostname.lower().removeprefix("www."),
                parsed.path.rstrip("/"),
                parsed.query,
            )
        except (TypeError, ValueError):
            return None

    @staticmethod
    def normalize_text(text):
        return re.sub(r"\s+", " ", str(text or "")).strip()

    @classmethod
    def find_source(cls, sources, url):
        normalized_url = cls.normalize_url(url)
        if not normalized_url:
            return None

        for source in sources:
            if not isinstance(source, dict):
                continue

            if cls.normalize_url(source.get("url", "")) == normalized_url:
                return source

        return None

    @classmethod
    def verify_quote(cls, source, quote):
        quote = cls.normalize_text(quote)

        if not source or len(quote) < 25:
            return False

        source_text = cls.normalize_text(
            str(source.get("title", "")) + " " +
            str(source.get("content", ""))
        )

        return quote in source_text

    @staticmethod
    def priority_weights(priority):
        key = str(priority or "overall performance").strip().lower()
        return ScoringAgent.WEIGHTS.get(
            key,
            ScoringAgent.WEIGHTS["overall performance"],
        )

    @staticmethod
    def _empty_evidence(reason):
        return {
            "verification": "insufficient_evidence",
            "quote": "",
            "source_url": "",
            "reason": reason,
        }

    @classmethod
    def quote_supports_criterion(cls, criterion, quote):
        """
        A basic relevance check, not a substitute for human fact-checking.
        The LLM must cite an actual statement about the criterion.
        """
        pattern = cls.QUANTITATIVE_PATTERNS.get(criterion)
        return bool(pattern and pattern.search(quote))

    def score_startup(self, startup, priority):
        sources = startup.get("source_evidence", [])

        if not isinstance(sources, list):
            sources = []

        source_text = []

        for index, source in enumerate(sources[:10], 1):
            if not isinstance(source, dict):
                continue

            source_text.append(
                f"Source {index}\n"
                f"Title: {source.get('title', '')}\n"
                f"URL: {source.get('url', '')}\n"
                f"Text: {str(source.get('content', ''))[:2500]}"
            )

        if not source_text:
            startup["scores"] = {key: None for key in self.CRITERIA}
            startup["evidence"] = {
                key: self._empty_evidence("No usable source material.")
                for key in self.CRITERIA
            }
            startup["evidence_coverage"] = 0.0
            startup["weighted_score"] = None
            startup["ranking_status"] = "insufficient_evidence"
            return startup

        prompt = f"""
Evaluate this startup using only the supplied source material.

Startup: {startup.get('name', 'Unknown')}
Industry: {startup.get('industry', '')}
Geography: {startup.get('geography', '')}
Ranking priority: {priority}
Description: {startup.get('description', '')}

Score these criteria:

financial_performance:
Reported revenue, profit/loss, margins and financial growth.
Funding or valuation alone is not financial performance.

funding:
Disclosed funding rounds, amounts, dates and investors.
Prefer sources that report the round and amount directly.

customer_traction:
Disclosed customers, users, merchants, transactions, deployments or adoption.
Do not equate a claimed potential market with actual customers.

recent_developments:
Specific dated launches, partnerships, expansion, acquisitions or milestones.
Undated generic descriptions are insufficient.

market_position:
Credible market share, independently reported market ranking or
a comparative position supported by specific evidence.
Marketing phrases such as "leading platform" are insufficient alone.

{self.SCORE_GUIDANCE}

Requirements:
1. Return null for unsupported criteria.
2. Every non-null score needs an exact quote, exact source URL and reason.
3. The quote must support the criterion itself, not merely mention the startup.
4. Use only the supplied URLs.
5. Do not invent figures, dates, customers, investors or comparisons.
6. For financial figures, include the measure, amount, currency and period
   in the quote whenever those details are available.
7. Prefer direct disclosures, official filings and reputable reporting.
8. A company listicle is not strong evidence of performance.
9. Score conservatively; missing evidence must never increase a score.
10. Output JSON only, in this schema:

{{
  "scores": {{
    "financial_performance": null,
    "funding": null,
    "customer_traction": null,
    "recent_developments": null,
    "market_position": null
  }},
  "evidence": {{
    "financial_performance": {{"quote":"","source_url":"","reason":""}},
    "funding": {{"quote":"","source_url":"","reason":""}},
    "customer_traction": {{"quote":"","source_url":"","reason":""}},
    "recent_developments": {{"quote":"","source_url":"","reason":""}},
    "market_position": {{"quote":"","source_url":"","reason":""}}
  }}
}}

Sources:
{chr(10).join(source_text)}
"""

        try:
            raw = self.llm.generate(prompt)
            parsed = self.llm.extract_json(raw, {})
        except Exception as exc:
            parsed = {}
            llm_error = str(exc)
        else:
            llm_error = ""

        proposed_scores = (
            parsed.get("scores", {})
            if isinstance(parsed, dict)
            else {}
        )
        proposed_evidence = (
            parsed.get("evidence", {})
            if isinstance(parsed, dict)
            else {}
        )

        if not isinstance(proposed_scores, dict):
            proposed_scores = {}

        if not isinstance(proposed_evidence, dict):
            proposed_evidence = {}

        scores = {}
        evidence = {}

        for criterion in self.CRITERIA:
            score = proposed_scores.get(criterion)
            item = proposed_evidence.get(criterion, {})

            if not isinstance(item, dict):
                item = {}

            quote = self.normalize_text(item.get("quote", ""))
            url = str(item.get("source_url", "") or "").strip()
            reason = str(item.get("reason", "") or "").strip()

            source = self.find_source(sources, url)

            if (
                not self.valid_score(score)
                or not self.verify_quote(source, quote)
                or not reason
            ):
                scores[criterion] = None
                evidence[criterion] = self._empty_evidence(
                    "Score rejected: quote, URL, score, or explanation "
                    "was missing or could not be verified."
                )
                continue

            # Require the quoted passage itself to contain a statement
            # relevant to the criterion. A keyword alone is not proof.
            if not self.quote_supports_criterion(criterion, quote):
                scores[criterion] = None
                evidence[criterion] = self._empty_evidence(
                    "The exact quote does not contain a recognizable "
                    "criterion-specific evidence signal."
                )
                continue

            score = float(score)

            # Without comparative evidence, avoid extreme scores.
            if score > 80:
                score = 80.0

            scores[criterion] = score
            evidence[criterion] = {
                "verification": "exact_quote_and_relevance_checked",
                "quote": quote,
                "source_url": url,
                "reason": reason,
            }

        startup["scores"] = scores
        startup["evidence"] = evidence

        valid_count = sum(
            value is not None for value in scores.values()
        )
        coverage = valid_count / len(self.CRITERIA) * 100
        startup["evidence_coverage"] = coverage

        weights = self.priority_weights(priority)
        available_weight = sum(
            weights[key]
            for key in self.CRITERIA
            if scores[key] is not None
        )

        if available_weight:
            weighted_total = sum(
                scores[key] * weights[key]
                for key in self.CRITERIA
                if scores[key] is not None
            )
            startup["weighted_score"] = round(
                weighted_total / available_weight, 2
            )
        else:
            startup["weighted_score"] = None

        # Partial scores can be displayed for transparency, but are not
        # eligible for a final ranking unless evidence coverage is high.
        if (
            valid_count == len(self.CRITERIA)
            and coverage >= self.min_evidence_coverage
        ):
            startup["ranking_status"] = "ranked"
        elif valid_count:
            startup["ranking_status"] = "partial_evidence"
        else:
            startup["ranking_status"] = "insufficient_evidence"

        if llm_error:
            startup["scoring_error"] = llm_error

        return startup

    def score(self, startups, priority):
        return [
            self.score_startup(startup, priority)
            for startup in startups
        ]
