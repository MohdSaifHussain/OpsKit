[![CI](https://github.com/MohdSaifHussain/OpsKit/actions/workflows/ci.yml/badge.svg)](https://github.com/MohdSaifHussain/OpsKit/actions/workflows/ci.yml)

![OpsKit](https://github.com/user-attachments/assets/487f6570-608b-4d91-8363-6bddb40e6427)

# OpsKit

**Never report a delta without its driver.**

Most analytics tools tell you volume went up or down. OpsKit tells you which
segment drove the change, conditions on it, and recurses inside that segment to
find the next level of explanation. Every attribution arrow in the output is a
computed path — not a label placed on an independent ranking.

Built on the analyst review sequence that applies identically to incidents,
transactions, claims, shipments, and support tickets. Datasets change. The
questions do not.

One deliberate omission: **average metrics never trigger drill-down.** Averages
do not decompose additively across segments. Attributing an average delta to a
sub-segment produces Simpson's paradox errors — the wrong segment can appear to
drive the change while masking the real cause. OpsKit refuses, documents the
statistical reason in the finding, and suggests comparing segment averages
directly instead. This is not a missing feature. It is the analytically correct
answer.

---

## Install

```bash
git clone https://github.com/MohdSaifHussain/OpsKit.git
cd OpsKit
pip install -e .
```

This installs the `opskit` CLI command. After install:

```bash
opskit demo
opskit run weekly-review demo_data/incidents.csv
opskit list
```

Or run directly without install:

```bash
python opskit4.py demo
```

Requires **Python 3.12+**.

---

## 60-second start

```bash
# Create a planted-answer dataset — prints the story before you run anything
opskit demo

# Run the Monday-morning review
opskit run weekly-review demo_data/incidents.csv

# Run with a sum metric instead of count
opskit run weekly-review demo_data/incidents.csv --metric sum:loss_amount

# Output machine-readable findings (CI-friendly: exit 2 on criticals)
opskit run weekly-review demo_data/incidents.csv --json findings.jsonl

# Understand what a playbook does, step by step
opskit explain trend-investigation

# List all available playbooks
opskit list
```

---

## Real-world example — a volume surge investigation

An operations analyst opens Monday's review and sees incident volume is up 140%.
OpsKit runs the full `weekly-review` playbook and outputs:

```
[CRITICAL] Volume change: +140% (105 → 252 incidents) in the past 7 days
           Conditional drill:
             service='payments' explains 84% of change (21 → 126 incidents)
             → within that, severity='P2' explains 67% (14 → 98 incidents)
[INFO]     Concentration: service='payments' = 50% of all volume (normal: 30%)
[INFO]     Anomaly day: 2026-07-07 — 42 incidents (Z-score 3.1, threshold 2.5)
```

Every number is a deterministic SQL computation over the source file. Re-run
the same command on the same file: the findings are identical. That is
re-performable evidence. The Excel report embeds who ran it, when (IST), on what
source, and exactly how the contribution percentages were computed — a reviewer
can verify the method from the document alone.

---

## Who this is for

**Operations analysts** who run the same review sequence every Monday on
incidents, transactions, or claims. OpsKit encodes that sequence as a named
playbook and runs it in one command — shape check, trust layer, volume change
with conditional driver analysis, anomaly detection, concentration flagging, and
a recommendations summary.

**Controls testers and auditors** who need documented, re-performable change
analysis. Volume changed — when did it change, which segment drove it, and what
is the evidence? OpsKit answers all three and embeds the computational method in
every finding.

**Managers and leads** who need to explain volume shifts to leadership with
defensible attribution. The contribution analysis reports which segment explains
what percentage of the parent delta — and if other segments declined and
partially offset the change, that is shown too.

**Data engineers and CI pipeline owners** who want automated data quality gates
with structured output. Exit code 2 on critical findings integrates directly into
GitHub Actions, Jenkins, or any shell-based pipeline. Schema-versioned JSON lines
(`opskit.finding/v1`) make findings machine-readable without parsing. `--no-fail`
suppresses the non-zero exit for reporting-only contexts.

**Domain teams** who need custom review sequences without touching Python. A
six-line TOML file composes a domain playbook from the built-in step library —
no code changes.

---

## The sequence

**SHAPE → TRUST → CHANGE → DRIVER → CONCENTRATION → ACTION**

This sequence applies identically across operational domains. OpsKit encodes it
as named playbooks:

| Playbook | Description | Steps |
|---|---|---|
| `weekly-review` | The Monday-morning checklist | shape, missing, duplicates, time coverage, volume change + drill, anomaly days, concentration |
| `data-quality` | Trust the data before analysing it | shape, missing, duplicates, numeric sanity, time coverage |
| `trend-investigation` | Something changed: find what, where, how concentrated | shape, time coverage, volume change + drill, anomaly days, concentration |
| Custom (TOML) | Any sequence you compose | configurable |

---

## The conditional drill-down

This is the part most tools get wrong.

The standard approach ranks every categorical column independently by volume
change, picks the top one, and draws an arrow. The arrow implies conditioning
that was never computed. A column can rank first in independent analysis while
being entirely explained by another column never examined inside it.

OpsKit's approach: find the segment explaining the largest share of the parent
delta, condition on it — restrict the data to only that segment — then find the
next segment inside the conditioned data. Each level is computed inside its
parent. Each arrow is a computed path.

The output reads: `service='payments' explains 84% of the change (312 → 578)
→ within that, severity='P2' explains 67% (198 → 412)`. Both numbers are
independently verifiable against the source data. The Methodology tab in the
Excel report documents the method: "contribution = segment delta / parent delta,
each level computed inside its parent segment."

**Metric support:** `--metric count` (default), `--metric sum:<column>`,
`--metric avg:<column>`. For `avg`, the drill is refused with the statistical
explanation — the volume change finding still runs, only the attribution is
withheld, because attribution would be wrong.

---

## TOML domain playbooks

Custom domain packs compose without touching Python:

```toml
[thresholds]
drill_threshold = 0.15

[playbooks.claims-review]
title = "Insurance Claims Weekly Review"
description = "Domain pack composed in TOML, zero code changes"
steps = ["shape", "missing", "duplicates", "time_coverage", "volume_change"]
```

Save as `opskit.toml` in the working directory:

```bash
opskit run claims-review data.csv
```

Unknown threshold keys and unknown step names raise clean errors at load time
with the full list of valid options. Configuration mistakes surface before
analysis runs, not during it.

---

## Data sources

Any input becomes DuckDB view `t`. The SQL dialect is PostgreSQL-compatible and
transfers to Snowflake, BigQuery, and Redshift.

| Source | Example |
|---|---|
| CSV | `opskit run weekly-review data.csv` |
| Excel (.xlsx) | `opskit run weekly-review data.xlsx` |
| SQLite | `opskit run weekly-review data.sqlite --table incidents` |
| Parquet | `opskit run weekly-review data.parquet` |

---

## Integration with the Delivery Engine

OpsKit is also the operational analysis layer of the
[Delivery Engine](https://github.com/MohdSaifHussain/delivery-engine) — a
governed, AI-assisted workflow system where every number in every deliverable
traces to a hash-verified computation.

In that context, OpsKit runs as an MCP (Model Context Protocol) server. The
Delivery Engine calls it through `opskit-mcp`, which wraps OpsKit's playbooks
in a signed findings envelope (`opskit.envelope/v1`) with a SHA-256 seal on the
payload. The engine verifies the seal before accepting the findings, and the
findings flow into the Findings Store where they can be cited by AI narrative
stages — but never overwritten by them.

This means OpsKit is usable in two ways:
- **Standalone:** `opskit run weekly-review data.csv` — the full sequence, an
  Excel report, optional JSON findings, CI-friendly exit codes
- **As governed infrastructure:** via `opskit-mcp` inside the Delivery Engine,
  where its findings become auditable, hash-locked evidence in a larger
  re-performable package

---

## Security and SQL correctness

**Validated identifier quoting:** every column name passes through `qident()`,
which validates the name against the actual schema allowlist before quoting it
with SQL-standard double-quote doubling. This is an allowlist, not an escape
function. A column name that does not exist raises a clean error — it never
becomes a SQL string.

**Parameterised values:** all segment values from the drill-down recursion bind
as `?` parameters. They never enter the SQL text.

No raw f-string identifiers anywhere. Identifiers go through `qident()`. Values
go through parameter binding. Two different surfaces, two different mechanisms.

---

## Engineering standards

- `mypy --strict` zero errors, `ruff` clean across E, F, W, I, N, UP, B, C4, SIM, RUF
- **18 tests on the planted-answer principle** — every fixture contains a known
  conditional path; every test verifies the algorithm finds exactly that path in
  the correct order with contributions in the correct direction
- Declared step dependencies validated at playbook load time — dependency errors
  surface before analysis runs, not mid-run
- Frozen slots dataclasses, StrEnum, timezone-aware IST timestamps, atomic Excel
  writes (`os.replace`), SIGPIPE handled, no side effects on import
- Single file by deliberate choice — module boundaries drawn so a split into
  `steps/`, `playbooks/`, `report/` is mechanical when needed. A decision,
  documented; not inertia.
- GitHub Actions CI on every push — Node 24, green on first commit

---

## Honest limitations

Single-analyst CLI, not a production monitoring platform. No schema drift
handling between runs. No semantic duplicate detection (exact-row only). No
cross-column validation rules. No streaming or chunked processing. Concentration
checks up to three categorical columns. Average metric drill-down is refused on
statistical grounds — the finding documents the reason and the correct
alternative.

---

## Development approach

Designed, specified, and governed by **Mohd Saif Hussain**. Implementation
AI-directed.

Every architectural decision was human-made and verified: the conditional
recursion design; the statistical basis for the Simpson's paradox refusal; the
allowlist-not-escape-function distinction in `qident()`; the planted-answer test
philosophy. The `demo` command prints its answer key before running so you always
know what the tool should find. A test you cannot independently verify is not a
test.

---

## License

MIT
