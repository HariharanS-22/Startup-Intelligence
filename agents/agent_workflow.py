
from datetime import datetime, timezone

from agents.coding_agent import LocalCodingAgent
from agents.research_agent import ResearchAgent
from agents.validation_agent import ValidationAgent
from agents.scoring_agent import ScoringAgent
from agents.ranking_agent import RankingAgent


class StartupIntelligenceWorkflow:
    def __init__(self, model="qwen2.5-coder:3b"):
        llm = LocalCodingAgent(model=model)

        self.research_agent = ResearchAgent(llm)
        self.validation_agent = ValidationAgent()
        self.scoring_agent = ScoringAgent(llm)
        self.ranking_agent = RankingAgent(minimum_coverage=80.0)

    def run(
        self,
        industry,
        geography="India",
        priority="Overall performance",
        count=10,
    ):
        industry = str(industry or "").strip()
        geography = str(geography or "").strip()
        priority = str(priority or "").strip()

        if not industry:
            raise ValueError("Industry cannot be empty.")

        if not geography:
            raise ValueError("Geography cannot be empty.")

        count = max(1, min(int(count), 50))

        # Build queries separately because research() returns only a list.
        queries = self.research_agent.build_queries(
            industry=industry,
            geography=geography,
            priority=priority,
        )

        # IMPORTANT:
        # The fourth positional parameter is max_results_per_query,
        # not the requested number of startups.
        candidates = self.research_agent.research(
            industry=industry,
            geography=geography,
            priority=priority,
            max_results_per_query=6,
            max_companies=max(30, count * 5),
        )

        # ResearchAgent.research() returns a list.
        if not isinstance(candidates, list):
            raise TypeError(
                "ResearchAgent.research() must return a list, "
                f"but returned {type(candidates).__name__}."
            )

        candidates = [
            candidate
            for candidate in candidates
            if isinstance(candidate, dict)
        ]

        print("\n[WORKFLOW] Validating candidates...")

        validation = self.validation_agent.validate(
            candidates,
            industry=industry,
            geography=geography,
        )

        if not isinstance(validation, dict):
            raise TypeError(
                "ValidationAgent.validate() must return a dictionary."
            )

        accepted = validation.get("accepted", [])
        rejected = validation.get("rejected", [])

        if not isinstance(accepted, list):
            raise TypeError(
                "Validation result 'accepted' must be a list."
            )

        if not isinstance(rejected, list):
            rejected = []

        print(f"[WORKFLOW] Accepted after validation: {len(accepted)}")
        print("[WORKFLOW] Scoring candidates...")

        scored = self.scoring_agent.score(
            accepted,
            priority,
        )

        if not isinstance(scored, list):
            raise TypeError(
                "ScoringAgent.score() must return a list, "
                f"but returned {type(scored).__name__}."
            )

        print("[WORKFLOW] Ranking candidates...")

        ranked = self.ranking_agent.rank(
            scored,
            priority=priority,
        )

        if not isinstance(ranked, list):
            raise TypeError(
                "RankingAgent.rank() must return a list, "
                f"but returned {type(ranked).__name__}."
            )

        ranked = [
            startup
            for startup in ranked
            if isinstance(startup, dict)
        ]

        fully_evidenced = [
            startup
            for startup in ranked
            if startup.get("ranking_status") == "ranked"
            and startup.get("evidence_coverage") == 100.0
            and startup.get("ranking_score") is not None
        ]

        report = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "industry": industry,
            "geography": geography,
            "priority": priority,
            "requested_count": count,
            "status": (
                "completed"
                if len(fully_evidenced) >= count
                else "insufficient_evidence"
            ),
            "search_queries": queries,
            # ResearchAgent currently does not expose this metadata.
            "search_result_count": None,
            "candidate_count": len(candidates),
            "validated_count": len(accepted),
            "rejected_candidates": rejected,
            "fully_evidenced_count": len(fully_evidenced),
            "startups": ranked[:count],
            "limitations": (
                "The research agent returns candidate records but does not "
                "currently report the number of unique web search results. "
                "Candidate discovery does not prove that a company belongs "
                "to the requested industry or geography. Evidence coverage "
                "and scores depend on the validation and scoring agents; "
                "they do not independently establish factual accuracy, "
                "source authority, freshness, or financial performance."
            ),
        }

        print("\n[WORKFLOW] Completed.")
        print(f"[WORKFLOW] Candidates discovered: {len(candidates)}")
        print(f"[WORKFLOW] Candidates validated: {len(accepted)}")
        print(f"[WORKFLOW] Fully evidenced: {len(fully_evidenced)}")

        return report
