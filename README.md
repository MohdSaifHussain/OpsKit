# OpsKit
<img width="2816" height="1536" alt="Gemini_Generated_Image_m4lvitm4lvitm4lv" src="https://github.com/user-attachments/assets/487f6570-608b-4d91-8363-6bddb40e6427" />

**Never report a delta without its driver.**

Most analytics tools tell you volume went up or down. OpsKit tells you which segment drove the change, conditions on it, and recurses inside that segment to find the next level of explanation. Every attribution arrow in the output is a computed path, not a label placed on an independent ranking.

Built on the analyst review sequence that applies identically to incidents, transactions, claims, shipments, and support tickets. Datasets change. The questions do not.

One deliberate omission: **average metrics never trigger drill-down.** Averages do not decompose additively across segments. Attributing an average delta to a sub-segment produces Simpson's paradox errors — the wrong segment can appear to drive the change while masking the real cause. OpsKit refuses, documents the statistical reason in the finding, and suggests comparing segment averages directly instead. This is not a missing feature. It is the analytically correct answer.

---

## Who this is for

**Operations analysts** who run the same review sequence every Monday on incidents, transactions, or claims. OpsKit encodes that sequence as a named playbook and runs it in one command — shape check, trust layer, volume change with conditional driver analysis, anomaly detection, concentration flagging, and a recommendations summary. The output is a re-performable Excel report with a Methodology tab embedding who ran it, when (IST-timestamped), on what source, with what config, and exactly how the drill-down contribution was computed.

**Controls testers and auditors** who need documented, re-performable change analysis. Volume changed — when did it change, which segment drove it, and what is the evidence? OpsKit answers all three and embeds the computational method in every finding. A reviewer can re-perform the work from the document alone and get the same result. There is no AI layer in the core engine: same data, same config, same findings, every time.

**Managers and leads** who need to explain volume shifts to leadership with defensible attribution. The contribution analysis reports which segment explains what percentage of the parent delta — and if other segments declined and partially offset the change, that is shown too. The output is in plain language, not query results.

**Data engineers and CI pipeline owners** who want automated data quality gates with structured output. Exit code 2 on critical findings means OpsKit integrates directly into GitHub Actions, Jenkins, or any shell-based pipeline. Schema-versioned JSON lines (`opskit.finding/v1`) make findings machine-readable without parsing. `--no-fail` suppresses the non-zero exit for reporting-only contexts.

**Domain teams** who need custom review sequences without touching Python. A six-line TOML file composes a domain playbook from the built-in step library — title, description, and step sequence configurable without code changes. Configuration mistakes (unknown threshold keys, unknown step names) raise clean errors at load time before analysis runs.

---

## What it does

The sequence this automates is the same across every operational domain:

**SHAPE → TRUST → CHANGE → DRIVER → CONCENTRATION → ACTION**

Three built-in playbooks encode that sequence for different analytical contexts:

| Playbook | Description | Steps |
|---|---|---|
| `weekly-review` | The Monday-morning checklist, with the drill-down reflex built in | shape, missing, duplicates, time coverage, volume change + drill, anomaly days, concentration |
| `data-quality` | Trust the data before analysing it | shape, missing, duplicates, numeric sanity, time coverage |
| `trend-investigation` | Something changed: find what, where, and how concentrated | shape, time coverage, volume change + drill, anomaly days, concentration |
| Custom (TOML) | Any sequence you compose from the step library | configurable |

And four CLI commands:

| Command | What it does |
|---|---|
| `run <playbook> <source>` | Runs a playbook; writes an Excel report; optionally writes JSON findings |
| `demo` | Generates a planted-answer dataset with a printed answer key |
| `list` | Lists all available playbooks including custom TOML packs |
| `explain <playbook>` | Shows each step's question, rationale, and declared dependencies |

---

## The conditional drill-down

This is the part most tools get wrong.

The standard approach ranks every categorical column independently by volume change, picks the top one, and draws an arrow. The arrow implies conditioning that was never computed. A column can rank first in independent analysis while being entirely explained by another column that was never examined inside it.

OpsKit's approach: find the segment explaining the largest share of the parent delta, condition on it — restrict the data to only that segment — then find the next segment inside the conditioned data. Each level is computed inside its parent. Each arrow is a computed path.

The output reads: `service='payments' explains 84% of the change (312 → 578) → within that, severity='P2' explains 67% (198 → 412)`. Both numbers are independently verifiable against the source data, and the Methodology tab in the Excel report documents the method: "contribution = segment delta / parent delta, each level computed inside its parent segment."

**Metric support:** `--metric count` (default), `--metric sum:<column>`, `--metric avg:<column>`.

For `sum`, the recursion carries the metric correctly — level-two values are column sums computed inside the parent segment, not row counts. A regression test in the test suite proves this: it verifies that level-two values are in the expected numerical range for the metric type, not dressed-up counts.

For `avg`, the drill is refused with the statistical explanation. The volume change finding still runs and reports the overall average movement. Only the attribution is withheld, because attribution would be wrong.

---

## Data sources

Any input becomes DuckDB view `t`. The SQL dialect is PostgreSQL-compatible and transfers directly to Snowflake, BigQuery, and Redshift.

| Source | Example |
|---|---|
| CSV | `python opskit4.py run weekly-review data.csv` |
| Excel (.xlsx) | `python opskit4.py run weekly-review data.xlsx` |
| SQLite | `python opskit4.py run weekly-review data.sqlite --table incidents` |
| Parquet | `python opskit4.py run weekly-review data.parquet` |

---

## Install

```bash
pip install duckdb openpyxl pandas
python opskit4.py demo
```

Requires Python 3.12+.

---

## Quick start

```bash
python opskit4.py demo
# Prints the planted story: which service surges, which severity drives it within
# that service. Then verify the tool finds exactly that path:

python opskit4.py run weekly-review demo_data/incidents.csv
python opskit4.py run weekly-review demo_data/incidents.csv --metric sum:loss_amount
python opskit4.py run weekly-review demo_data/incidents.csv --json findings.jsonl
python opskit4.py explain trend-investigation
python opskit4.py list
```

---

## TOML domain playbooks

Custom domain packs compose in six lines without touching Python:

```toml
[thresholds]
drill_threshold = 0.15

[playbooks.claims-review]
title = "Insurance Claims Weekly Review"
description = "Domain pack composed in TOML, zero code changes"
steps = ["shape", "missing", "duplicates", "time_coverage", "volume_change"]
```

Save as `opskit.toml` in the working directory, then run:

```bash
python opskit4.py run claims-review data.csv
```

Every threshold in `Config` is overridable from `[thresholds]`. Unknown keys raise a clean error at load time with the full list of valid keys. Unknown step names raise a clean error with the full step library. Configuration mistakes surface before analysis runs, not during it.

---

## Security and SQL correctness

**Validated identifier quoting:** every column name passes through `qident()`, which validates the name against the actual schema allowlist before quoting it with SQL-standard double-quote doubling. This is an allowlist, not an escape function. A column name that does not exist in the schema raises a clean `OpsKitError` with the list of available columns — it never becomes a SQL string.

**Parameterised values:** all user-supplied segment values from the drill-down recursion bind as `?` parameters. They never enter the SQL text.

**No raw f-string identifiers anywhere in the codebase.** Identifiers go through `qident()`. Values go through parameter binding. These are two different surfaces requiring two different mechanisms — applying one fix to both would leave one surface open.

---

## Engineering standards

- `mypy --strict` zero errors, `ruff` clean across all rule sets (E, F, W, I, N, UP, B, C4, SIM, RUF)
- **18 pytest tests on the planted-answer principle:** every fixture contains a known conditional path; every test verifies the algorithm finds exactly that path in the correct order. Tests include:
  - The conditional drill must find `service='payments'` at level one, `severity='P2'` at level two — in that order, with contributions in the right direction
  - The metric recursion must carry sums correctly: level-two values must be column-scale sums, not row counts
  - `avg` metric must return an empty drill path, not a fabricated attribution
  - Pure step functions must return identical results when run twice — no shared mutable state
  - Playbooks with steps in the wrong dependency order must raise at load time, not mid-analysis
- Declared step dependencies validated at playbook load — `volume_change` requires `shape` and `time_coverage`; the registry enforces this, not a tuple-ordering convention
- Frozen slots dataclasses, StrEnum, PEP 695 type aliases, timezone-aware IST timestamps via `zoneinfo`, atomic Excel writes via `os.replace` (no partial file on crash), SIGPIPE handled, no side effects on import
- Single file by deliberate choice: module boundaries are drawn so a split into `steps/`, `playbooks/`, `report/` is mechanical when the project grows to a package. This is documented as a decision, not left as inertia
- GitHub Actions CI runs ruff, mypy strict, and pytest on every push — green on first commit

---

## Honest limitations

Single-analyst CLI, not a production monitoring platform. No schema drift handling between runs — if the source schema changes, assumptions are re-detected from scratch. No semantic duplicate detection (exact-row only). No cross-column validation rules (e.g. resolved date must be after opened date). No streaming or chunked processing — DuckDB handles most practical file sizes, but this is not a distributed engine. Concentration detection checks up to three categorical columns; columns beyond that are skipped. Average metric drill-down is refused on statistical grounds, not missing by oversight — the finding documents the reason and the correct alternative.

---

## Development approach

Designed, specified, and governed by Mohd Saif Hussain. Implementation AI-directed.

Every architectural decision was human-made and verified: the conditional recursion design and the requirement that each level be computed inside its parent; the statistical basis for the Simpson's paradox refusal and the decision to document it in the finding rather than silently skip; the allowlist-not-escape-function distinction in `qident()` and the requirement to apply separate mechanisms to identifier and value surfaces; the planted-answer test philosophy and the specific regression guard proving metric recursion carries sums and not row counts.

The planted-answer principle runs throughout: `demo` prints its answer key before running so you always know what the tool should find before it runs. The tests plant a known surge path (service at level one, severity within service at level two) and verify the algorithm finds exactly that path, in that order, with contributions in the correct direction. A test you cannot independently verify is not a test.

---

## License

MIT
