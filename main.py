
import json
import csv
import traceback
from pathlib import Path

from agents.agent_workflow import StartupIntelligenceWorkflow


def ask_non_empty(prompt, default=None):
    while True:
        suffix = f" [{default}]" if default else ""
        value = input(f"{prompt}{suffix}: ").strip()

        if not value and default is not None:
            value = default

        if value:
            return value

        print("This field cannot be empty.")


def ask_count():
    while True:
        raw = input("How many startups should be ranked? [10]: ").strip() or "10"

        try:
            count = int(raw)
            if 1 <= count <= 50:
                return count
        except ValueError:
            pass

        print("Enter a whole number from 1 to 50.")


def main():
    print("=" * 68)
    print("             STARTUP INTELLIGENCE SYSTEM")
    print("=" * 68)
    print("Research startups in an industry of your choice.")
    print("The system uses web search and your local Ollama model.\n")

    industry = ask_non_empty(
        "Enter industry (e.g. FinTech, EdTech, HealthTech)"
    )
    geography = ask_non_empty("Geographic scope", "India")

    print("\nRanking priority:")

    priorities = [
        "Overall performance",
        "Funding and growth",
        "Revenue and profitability",
        "Customer traction",
        "Innovation and recent developments",
        "Market position",
    ]

    for index, item in enumerate(priorities, 1):
        print(f"  {index}. {item}")

    while True:
        raw = input("Choose priority [1]: ").strip() or "1"

        if raw.isdigit() and 1 <= int(raw) <= len(priorities):
            priority = priorities[int(raw) - 1]
            break

        print(f"Enter a number from 1 to {len(priorities)}.")

    count = ask_count()
    model = "qwen2.5-coder:3b"

    print("\n" + "=" * 68)
    print(f"Industry : {industry}")
    print(f"Region   : {geography}")
    print(f"Priority : {priority}")
    print(f"Target   : {count} startups")
    print("=" * 68)
    print("Research can take several minutes. Please wait...\n")

    try:
        workflow = StartupIntelligenceWorkflow(model=model)
        report = workflow.run(
            industry,
            geography,
            priority,
            count,
        )

    except KeyboardInterrupt:
        print("\nResearch cancelled by user.")
        return

    except Exception as exc:
        print("\nERROR:", exc)
        print("\nFULL ERROR TRACEBACK:")
        traceback.print_exc()

        print("\nDiagnostic checklist:")
        print("  1. Confirm Ollama is running.")
        print(f"  2. Confirm {model} is installed using: ollama list")
        print("  3. Confirm internet access is available.")
        print("  4. Check the traceback above for the failing file and line.")
        return

    # Validate the workflow output before accessing its fields.
    if not isinstance(report, dict):
        print("\nERROR: workflow.run() did not return a dictionary.")
        print("Actual return type:", type(report).__name__)
        print("Returned value:", repr(report)[:2000])
        return

    required_fields = [
        "industry",
        "geography",
        "candidate_count",
        "validated_count",
        "fully_evidenced_count",
        "status",
        "startups",
    ]

    missing_fields = [
        field for field in required_fields
        if field not in report
    ]

    if missing_fields:
        print("\nERROR: Workflow report is missing fields:", missing_fields)
        print("Available fields:", list(report.keys()))
        return

    if not isinstance(report["startups"], list):
        print("\nERROR: report['startups'] must be a list.")
        print("Actual type:", type(report["startups"]).__name__)
        print("Returned value:", repr(report["startups"])[:2000])
        return

    print("\n" + "=" * 68)
    print(f"RESULTS: {report['industry']} | {report['geography']}")
    print("=" * 68)
    print(f"Candidates discovered : {report['candidate_count']}")
    print(f"Candidates validated  : {report['validated_count']}")
    print(f"Fully evidenced       : {report['fully_evidenced_count']}")
    print(f"Report status         : {str(report['status']).upper()}")

    if report["status"] != "completed":
        print(
            "\nNOTICE: The requested number of fully evidenced startups "
            "was not reached. The list may contain partial-evidence candidates."
        )

    if not report["startups"]:
        print("\nNo candidates passed validation.")
        print("Try broader industry or geography terms.")

    else:
        for startup in report["startups"]:
            # Prevent a malformed record from crashing the display.
            if not isinstance(startup, dict):
                print("\nWARNING: Skipping malformed startup record:")
                print(repr(startup)[:500])
                continue

            score = startup.get("ranking_score")

            score_text = (
                f"{score:.2f}/100"
                if isinstance(score, (int, float))
                else "N/A"
            )

            print("\n" + "-" * 68)
            print(
                f"#{startup.get('rank', 'N/A')}  "
                f"{startup.get('name', 'Unknown')}  | "
                f"Score: {score_text}"
            )
            print(
                f"Evidence coverage: "
                f"{startup.get('evidence_coverage', 0)}%"
            )
            print(
                f"Ranking status: "
                f"{startup.get('ranking_status', 'unknown')}"
            )

            if startup.get("description"):
                print(f"Description: {startup['description']}")

            print("Criterion scores:")

            scores = startup.get("scores", {})

            if isinstance(scores, dict):
                for criterion, value in scores.items():
                    label = criterion.replace("_", " ").title()
                    displayed_value = (
                        value
                        if value is not None
                        else "Insufficient evidence"
                    )
                    print(f"  - {label}: {displayed_value}")
            else:
                print("  Scores unavailable: invalid score structure.")

            print("Sources:")

            sources = startup.get("source_evidence", [])

            if isinstance(sources, list):
                for source in sources:
                    if not isinstance(source, dict):
                        continue

                    print(
                        f"  - {source.get('title') or source.get('url', 'Unknown source')}"
                    )

                    if source.get("url"):
                        print(f"    {source['url']}")
            else:
                print("  Source list unavailable.")

    print("\n" + "=" * 68)
    print("Search queries used:")

    queries = report.get("search_queries", [])

    if isinstance(queries, list):
        for query in queries:
            print(f"  - {query}")

    # Save reports.
    try:
        output_dir = Path("output")
        output_dir.mkdir(parents=True, exist_ok=True)

        json_path = output_dir / "startup_report.json"
        json_path.write_text(
            json.dumps(report, indent=2, ensure_ascii=False, default=str),
            encoding="utf-8",
        )

        csv_path = output_dir / "startup_rankings.csv"

        fields = [
            "rank",
            "name",
            "industry",
            "geography",
            "ranking_score",
            "evidence_coverage",
            "available_criteria",
            "ranking_status",
            "description",
        ]

        with csv_path.open(
            "w",
            newline="",
            encoding="utf-8-sig",
        ) as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()

            for startup in report["startups"]:
                if not isinstance(startup, dict):
                    continue

                writer.writerow({
                    field: startup.get(field, "")
                    for field in fields
                })

        print(f"\nFull JSON report saved to: {json_path.resolve()}")
        print(f"Ranking CSV saved to: {csv_path.resolve()}")

    except Exception:
        print("\nERROR: Failed to save report files.")
        traceback.print_exc()


if __name__ == "__main__":
    main()
