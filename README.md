# OpsKit — Cognitive Analyst Playbooks

Encodes how experienced analysts think about recurring operational data — 
not just commands, but the mental model behind them.

**The core idea:** the dataset changes between jobs. The recurring 
analytical questions do not. OpsKit automates the questions.

- Playbook engine with step dependencies validated at load time
- Honest conditional drill-down: contribution analysis computed inside 
  parent segments, not ranked independently
- Metric-aware: count, sum, avg — with principled refusal to drill on 
  averages (Simpson's paradox)  
- TOML-composable domain playbooks: new domain = six lines of config
- mypy --strict zero errors | ruff clean | 18 unit tests

## Run it

pip install duckdb openpyxl pandas

python opskit4.py demo

python opskit4.py run weekly-review demo_data/incidents.csv

python opskit4.py run weekly-review demo_data/incidents.csv --metric sum:loss_amount
