
class RankingAgent:
    WEIGHTS = {
        "overall performance": {
            "financial_performance": 0.30,
            "funding": 0.15,
            "customer_traction": 0.20,
            "recent_developments": 0.15,
            "market_position": 0.20,
        },
        "funding and growth": {
            "financial_performance": 0.20,
            "funding": 0.30,
            "customer_traction": 0.15,
            "recent_developments": 0.15,
            "market_position": 0.20,
        },
        "revenue and profitability": {
            "financial_performance": 0.50,
            "funding": 0.10,
            "customer_traction": 0.10,
            "recent_developments": 0.10,
            "market_position": 0.20,
        },
        "customer traction": {
            "financial_performance": 0.15,
            "funding": 0.10,
            "customer_traction": 0.40,
            "recent_developments": 0.15,
            "market_position": 0.20,
        },
        "innovation and recent developments": {
            "financial_performance": 0.15,
            "funding": 0.10,
            "customer_traction": 0.15,
            "recent_developments": 0.40,
            "market_position": 0.20,
        },
        "market position": {
            "financial_performance": 0.20,
            "funding": 0.10,
            "customer_traction": 0.20,
            "recent_developments": 0.10,
            "market_position": 0.40,
        },
    }

    CRITERIA = [
        "financial_performance",
        "funding",
        "customer_traction",
        "recent_developments",
        "market_position",
    ]

    VALID_VERIFICATION_STATUSES = {
        "exact_quote_found",
        "exact_quote_and_relevance_checked",
    }

    def __init__(self, minimum_coverage=80.0):
        self.minimum_coverage = max(
            0.0, min(100.0, float(minimum_coverage))
        )

    @classmethod
    def get_weights(cls, priority):
        key = str(priority or "overall performance").strip().lower()
        return cls.WEIGHTS.get(
            key,
            cls.WEIGHTS["overall performance"],
        )

    @staticmethod
    def is_valid_score(score):
        return (
            isinstance(score, (int, float))
            and not isinstance(score, bool)
            and 0 <= score <= 100
        )

    @classmethod
    def has_valid_evidence(cls, score, item):
        if not cls.is_valid_score(score):
            return False

        if not isinstance(item, dict):
            return False

        if item.get("verification") not in cls.VALID_VERIFICATION_STATUSES:
            return False

        if len(str(item.get("quote", "")).strip()) < 25:
            return False

        url = str(item.get("source_url", "")).strip()

        # A syntactically valid HTTP(S) URL is required.
        from urllib.parse import urlparse

        try:
            parsed = urlparse(url)
            if (
                parsed.scheme not in {"http", "https"}
                or not parsed.hostname
                or "." not in parsed.hostname
            ):
                return False
        except (TypeError, ValueError):
            return False

        if not str(item.get("reason", "")).strip():
            return False

        return True

    def rank_one(self, startup, priority="overall performance"):
        scores = startup.get("scores", {})
        evidence = startup.get("evidence", {})
        weights = self.get_weights(priority)

        if not isinstance(scores, dict):
            scores = {}

        if not isinstance(evidence, dict):
            evidence = {}

        weighted_total = 0.0
        available_weight = 0.0
        available_criteria = 0

        for criterion in self.CRITERIA:
            score = scores.get(criterion)
            item = evidence.get(criterion, {})

            if not self.has_valid_evidence(score, item):
                continue

            weight = weights[criterion]
            weighted_total += float(score) * weight
            available_weight += weight
            available_criteria += 1

        coverage = available_criteria / len(self.CRITERIA) * 100

        # Diagnostic score based only on criteria with accepted evidence.
        raw_score = (
            weighted_total / available_weight
            if available_weight > 0
            else None
        )

        eligible = (
            raw_score is not None
            and coverage >= self.minimum_coverage
        )

        startup["available_criteria"] = available_criteria
        startup["evidence_coverage"] = round(coverage, 1)
        startup["available_weight"] = round(available_weight, 3)

        # Diagnostic only; not necessarily eligible for the final ranking.
        startup["weighted_score"] = (
            round(raw_score, 2) if raw_score is not None else None
        )

        startup["ranking_score"] = (
            round(raw_score, 2) if eligible else None
        )

        startup["ranking_status"] = (
            "ranked"
            if eligible
            else "partial_evidence"
            if available_criteria > 0
            else "insufficient_evidence"
        )

        return startup

    def rank(self, startups, priority="overall performance"):
        ranked = [
            self.rank_one(item, priority)
            for item in startups
            if isinstance(item, dict)
        ]

        # Eligible companies appear first. Ineligible candidates remain
        # available for inspection but do not receive official rank numbers.
        ranked.sort(
            key=lambda item: (
                item.get("ranking_score") is not None,
                item.get("ranking_score")
                if item.get("ranking_score") is not None
                else -1,
                item.get("evidence_coverage", 0),
            ),
            reverse=True,
        )

        eligible_rank = 0

        for startup in ranked:
            if startup.get("ranking_score") is not None:
                eligible_rank += 1
                startup["rank"] = eligible_rank
            else:
                startup["rank"] = None

        return ranked
