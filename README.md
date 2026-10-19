# Startup Intelligence System — Command-Line Version

A Python command-line multi-agent system. The user enters the industry and geographic scope in CMD/PowerShell, chooses ranking priority and the number of startups, and receives an evidence-based ranked list in the terminal.

## Technology

- Python
- Local Ollama model: `qwen2.5-coder:3b`
- DuckDuckGo web search through `ddgs`
- Research, validation, scoring, ranking, and workflow agents
- JSON and CSV output files

## Windows setup

Open CMD or PowerShell in this project directory.

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
ollama pull qwen2.5-coder:3b
ollama list
```

If using Command Prompt (CMD) rather than PowerShell, activate with:

```bat
.venv\\Scripts\\activate.bat
```

Start Ollama using the desktop application, or run `ollama serve` if it is not already running. Then run:

```powershell
python main.py
```

## Example terminal session

```text
STARTUP INTELLIGENCE SYSTEM
Enter industry (e.g. FinTech, EdTech, HealthTech): EdTech
Geographic scope [India]: India
Choose priority [1]: 1
How many startups should be ranked? [10]: 10
Ollama model [qwen2.5-coder:3b]: qwen2.5-coder:3b
```

The actual companies and scores are generated from live search results and will vary. The example above shows only the input format.

## Project structure

```text
Startup_Intelligence_CMD/
├── main.py
├── requirements.txt
├── README.md
├── output/                  # Created automatically
└── agents/
    ├── __init__.py
    ├── coding_agent.py
    ├── research_agent.py
    ├── validation_agent.py
    ├── scoring_agent.py
    ├── ranking_agent.py
    └── agent_workflow.py
```

## Ranking

Default weights:
- Financial performance: 30%
- Funding: 25%
- Customer traction: 20%
- Recent developments: 15%
- Market position: 10%

Criteria with missing or unverifiable evidence are not assigned a numeric score. Evidence coverage shows the share of total criterion weight backed by accepted exact-quote evidence. If the requested number of fully evidenced startups is unavailable, the report status is `insufficient_evidence`.

An exact quote found in a search result is only a text traceability check. It does not independently prove that the source is authoritative, current, or factually correct. Review source links before using the ranking for business or investment decisions.

## Troubleshooting

- **Cannot connect to Ollama:** Start the Ollama app and verify `ollama list`.
- **Model missing:** Run `ollama pull qwen2.5-coder:3b`.
- **Search error:** Check internet access and update `ddgs` with `pip install --upgrade ddgs`.
- **Few results:** Try a broader industry or geography; the system avoids inventing missing candidates.
