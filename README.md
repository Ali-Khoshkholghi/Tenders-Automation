# Tenders Automation

An enterprise-grade multi-agent workflow, built with [LangGraph](https://github.com/langchain-ai/langgraph) and served by a [Groq](https://groq.com/)-hosted LLM (`llama-3.3-70b-versatile`), that automatically vets local-council tender documents against a company's own qualification profile — running a parallel panel of expert auditors, halting on any compliance failure for human sign-off, and supporting a **time-travel fork** so an administrator can retroactively override a failure and resume the run without losing the original audit trail.

## How it works

The system is a parent graph with an embedded parallel subgraph:

```
Ingest -> ParallelPanelReview (subgraph) -> route_after_panel_review --(clean)--> GenerateReport -> END
                                                       |
                                                (blockers found)
                                                       v
                                                 HumanTriage -> GenerateReport -> END
```

### Parent graph (`app.py`)

1. **Ingest** — reads the target tender document from `incoming_files/` (`.txt` or `.pdf`, via `pypdf`).
2. **ParallelPanelReview** — loads `client_profile.json` (the bidding company's own metrics) and invokes the review subgraph synchronously, feeding it the raw tender text and the company profile.
3. **Router** (`route_after_panel_review`) — a deterministic gate: any `compliance_flags` returned by the panel route to `HumanTriage`; a clean panel routes straight to `GenerateReport`.
4. **HumanTriage** — a safety-valve node. It deliberately does nothing and lets the graph run to `END`, freezing the checkpointed state so a human administrator can inspect and correct it out-of-band (see Time-Travel below).
5. **GenerateReport** — prompts the LLM to draft a formal board memo on bid eligibility, incorporating any `executive_remedy_context` an administrator injected during a time-travel override.

### Review subgraph (`review_subgraph.py` / `review_state.py`)

A **fan-out / fan-in** panel that runs three domain experts concurrently against the same tender text and client profile, then consolidates their findings:

- **FinancialExpert** — extracts minimum turnover/insurance thresholds and flags `FAIL_TURNOVER` / `FAIL_INSURANCE` if the client profile falls short.
- **SecurityExpert** — checks whether Cyber Essentials (Plus) is mandatory and flags `FAIL_CYBER_ESSENTIALS` if the profile lacks it.
- **LegalExpert** — checks whether UK registration is mandatory and flags `FAIL_UK_REGISTRATION` if the profile isn't UK-registered.
- **Consolidator** — merges the three experts' outputs (via `Annotated[list, operator.add]` reducer channels so parallel writes don't clobber each other) into a single `final_panel_review` summary (`status`, `blockers`, `metrics_map`) that the parent graph reads back.

### Time-travel administration (`time_travel_admin.py`)

Because the graph is compiled with a `MemorySaver` checkpointer, every step of a run is a recoverable snapshot. This script demonstrates the full human-in-the-loop recovery pattern:

1. Runs the pipeline forward on a tender the company currently fails (e.g. Camden's UK-registration requirement).
2. Lists every checkpoint LangGraph recorded via `app.get_state_history(...)`.
3. Programmatically rewrites the paused state with `app.update_state(..., as_node="HumanTriage")` — clearing `compliance_errors` and injecting an `executive_remedy_context` (e.g. "commits to providing cross-border insurance indemnity") — without touching the original audit trail.
4. Resumes execution (`app.invoke(None, config=target_checkpoint)`) from that forked checkpoint straight through to a final, remediated memo.

There is also a standalone pre-qualification gatekeeper prompt (`prompts_tenders.py: GATEKEEPER_SYSTEM_PROMPT`) and a single-pass analyst/auditor prompt pair, both written for a simpler linear variant of this workflow.

## Project structure

| File | Purpose |
|---|---|
| `app.py` | Parent graph assembly: ingestion, subgraph invocation, triage, and report generation nodes, plus routing logic. |
| `review_subgraph.py` | The parallel expert-panel subgraph (financial, security, legal) and its fan-in consolidator. |
| `review_state.py` | `SubgraphState` — the review panel's state schema, with reducer channels for safe parallel writes. |
| `state.py` | `AgentState` — the parent graph's shared state schema. |
| `prompts_tenders.py` | Prompt templates for the gatekeeper, analyst, auditor, and report-generator LLM calls. |
| `time_travel_admin.py` | Demo script for the checkpoint-inspect → override → resume (time-travel fork) admin workflow. |
| `client_profile.json` | The bidding company's own qualification profile (turnover, insurance, certifications, registration). |
| `incoming_files/` | Drop zone for tender documents (`.txt` or `.pdf`) to be vetted. |
| `completed_memos/` | Intended output location for finalized board memos (not yet wired up in code). |

## Setup

**Requirements:** Python 3.12, and API keys for Groq and LangChain/LangSmith.

```bash
python3 -m venv venv
source venv/bin/activate
pip install langgraph langchain-groq langchain-core python-dotenv pypdf
```

Create a `.env` file in the project root:

```
GROQ_API_KEY=your-groq-api-key
LANGCHAIN_API_KEY=your-langchain-api-key
```

Edit `client_profile.json` to reflect your own company's turnover, insurance, and certification status.

## Usage

Drop a tender document into `incoming_files/` and run the time-travel demo pipeline:

```bash
python time_travel_admin.py
```

This runs the full pipeline against `tender_camden_it.txt` (a tender the sample `client_profile.json` fails on UK registration), shows the recorded checkpoint history, forks the timeline with an administrator override, and prints the final, remediated board memo.

To run the parent graph directly against a different file, invoke `app.app.invoke(...)` with `current_file` set to the desired filename in `incoming_files/`.

## Notes

- Expert-node LLM outputs are parsed with `eval()` on the assumption the model returns a clean Python literal; a malformed response is treated as no findings (fails silently) rather than crashing the pipeline.
- `HumanTriage` intentionally has no downstream edge back into the graph in the normal run path — the only way past a compliance failure is the explicit time-travel override in `time_travel_admin.py`, which preserves the original (failed) audit trail alongside the forked (remediated) one.
- `completed_memos/` exists as a placeholder output directory; wire up a write step in `report_generator_node` if you want memos persisted to disk automatically.
