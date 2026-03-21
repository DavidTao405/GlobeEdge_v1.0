# GlobeEdge

**Social Belief Dynamics World Model** — 社會信念動態世界模型

GlobeEdge models how public opinion evolves across Taiwan's social landscape using the Friedkin-Johnsen opinion dynamics framework, Monte Carlo simulation, and real-time data from PTT, Bluesky, USGS, and GDELT.

---

## Key Features

- **Friedkin-Johnsen Engine** — agent-based belief propagation with 8-dimensional belief vectors
- **MoE Monte Carlo** — stratified noise by agent type (media/KOL/demographic/forum), GPU-accelerated with PyTorch
- **Multi-Expert EWS** — Early Warning Signals using Welford online z-scores across structural/belief/velocity experts
- **6 Issue Scenarios** — energy policy, AI regulation, geopolitics, trade war, Iran war impact, Taiwan recall movement
- **Real-time Crawlers** — PTT push/boo parsing, Bluesky AT Protocol, RSS news, GDELT/USGS geopolitical signals
- **AI Belief Estimation** — local LLM (Ollama qwen3.5:9b) suggests initial belief vectors from reference texts
- **Vue 3 Frontend** — full scenario design workflow with D3 radar charts and W matrix heatmaps

## Architecture

```
┌─────────────┐    ┌──────────────┐    ┌──────────────┐
│  Frontend   │───▶│  Flask API   │───▶│  PostgreSQL  │
│  Vue 3      │    │  :5001       │    │  :5432       │
└─────────────┘    └──────┬───────┘    └──────────────┘
                          │
              ┌───────────┼───────────┐
              ▼           ▼           ▼
        ┌──────────┐ ┌─────────┐ ┌─────────┐
        │  Celery  │ │ Crawler │ │ Signals │
        │  Worker  │ │ Sched.  │ │ Sched.  │
        │  (GPU)   │ │ PTT/BS  │ │USGS/GDT │
        └──────────┘ └─────────┘ └─────────┘
              │
              ▼
        ┌──────────┐
        │  Redis   │
        │  :6379   │
        └──────────┘
```

## Quick Start

### Prerequisites

- Python 3.11+
- Docker (for PostgreSQL + Redis)
- Node.js 18+ (for frontend)
- Ollama with `qwen3.5:9b` (optional, for AI belief estimation)

### Setup

```bash
# Clone
git clone https://github.com/DavidTao405/GlobeEdge_v1.0.git
cd GlobeEdge_v1.0

# Python environment
python -m venv .venv
.venv/Scripts/activate  # Windows
pip install flask flask-sqlalchemy psycopg2-binary python-dotenv \
            httpx numpy statsmodels apscheduler celery redis torch curl_cffi

# Environment variables
cp .env.example .env  # Edit with your settings

# Start infrastructure
docker compose up -d

# Initialize database
python scripts/init_db.py

# Start API
python scripts/start_api.py

# Start crawlers + signal monitors
python scripts/start_crawlers.py

# Frontend (separate terminal)
cd frontend
npm install
npm run dev
```

### Run a Scenario

```bash
# List available scenarios
python scripts/run_scenario.py --list

# Run energy policy scenario
python scripts/run_scenario.py --scenario energy_policy

# Run all 6 scenarios
python scripts/run_scenario.py --all

# Calibrate with historical events
python scripts/calibrate.py --all

# EWS backtest
python scripts/backtest.py --all
```

## Calibration Results

Granger causality analysis across 3 historical events determined the optimal alpha parameter:

| Event | Significant Edges | Optimal Alpha | MSE |
|---|---|---|---|
| Hualien M7.2 Earthquake (2024-04) | 7 | 0.3 | 0.0077 |
| Taiwan Presidential Election (2024-01) | 5 | 0.3 | 0.0110 |
| Pelosi Taiwan Visit (2022-08) | 13 | 0.3 | 0.0074 |

**Key finding: alpha = 0.3** — Taiwanese society shows stronger individual belief anchoring than social influence, distinct from Western-calibrated defaults (0.6).

## Six Issue Analyses

| # | Issue | Type | Lambda Max | Strongest Polarization |
|---|---|---|---|---|
| 5 | Iran War Impact | real-time | **0.791** | Economic anxiety |
| 6 | Taiwan Recall | real-time | 0.752 | Government trust (spread=0.881) |
| 1 | Energy Policy | backtest | 0.760 | Nuclear acceptance (spread=**1.015**) |
| 2 | AI Regulation | backtest | 0.726 | AI regulation support |
| 3 | Geopolitics | backtest | 0.745 | Government trust |
| 4 | Trade War | backtest | 0.634 | US alliance trust |

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/projects` | Create project |
| GET | `/api/projects` | List projects |
| GET | `/api/projects/:id` | Get project |
| PATCH | `/api/projects/:id` | Update project |
| DELETE | `/api/projects/:id` | Archive project |
| POST | `/api/agents` | Create agent |
| GET | `/api/agents` | List agents by project |
| POST | `/api/agents/edges` | Create influence edge |
| GET | `/api/agents/edges/matrix` | Get W matrix |
| POST | `/api/agents/estimate-belief` | AI belief estimation |
| POST | `/api/simulations` | Submit simulation |
| GET | `/api/simulations/:id/status` | Poll status (Redis-first) |
| GET | `/api/simulations/:id/result/summary` | Get results |

## Data Sources

| Source | Type | Frequency | Cost |
|---|---|---|---|
| PTT (Gossiping, HatePolitics) | Behavioral edges | 8h | Free |
| Bluesky AT Protocol | Behavioral edges | Daily | Free |
| RSS (ETtoday, CNA) | Structural edges | 6h | Free |
| USGS Earthquake API | External events | 1h | Free |
| GDELT Project | External events | 6h | Free |
| Ollama (qwen3.5:9b) | Belief estimation | On demand | Free (local) |

## Tech Stack

**Backend:** Python 3.13, Flask, SQLAlchemy, Celery, APScheduler, NumPy, PyTorch, statsmodels

**Frontend:** Vue 3, TypeScript, Pinia, D3.js, Observable Plot, Vite

**Infrastructure:** PostgreSQL 16, Redis 7, Docker Compose, Ollama

**Crawlers:** curl_cffi (PTT TLS), httpx (Bluesky/USGS/GDELT), feedparser (RSS)

## Research Limitations

1. **Social media coverage gap** — Facebook and LINE (Taiwan's dominant platforms) have closed APIs; PTT/Bluesky provide partial coverage
2. **W matrix representativeness** — influence graph reflects observable public interactions, not private messaging networks
3. **b(0) subjectivity** — initial belief vectors are AI-estimated or researcher-judged, not from structured surveys
4. **Reflexivity** — social systems change when predictions are published; outputs should be framed as "unintervened trajectories"
5. **Backtesting ground truth** — Taiwan lacks standardized opinion time-series data; proxy indicators (Google Trends, news volume) are used

See `GLOBEEDGE_PLAN.md` Section 13 for full discussion.

## License

Research use only. Not intended for production deployment or as a basis for public opinion manipulation.

## Citation

If you use GlobeEdge in your research, please cite:

```
GlobeEdge: Social Belief Dynamics World Model for Taiwan
https://github.com/DavidTao405/GlobeEdge_v1.0
```
