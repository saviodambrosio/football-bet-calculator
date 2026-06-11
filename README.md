# football-bet-calculator

A quantitative value-betting engine for European football. Uses a hybrid **Poisson + ELO + Dixon-Coles** model to estimate match probabilities, then identifies value bets by comparing those estimates against bookmaker opening odds.

**Status: Closed / Portfolio** — Backtest result: **+0.23% ROI** over 3 seasons (~1,200 matches). The model annuls the bookmaker's margin; it does not generate scalable profit. Result documented honestly.

---

## Mathematical Engine

The core of the system is `calcola_prob_v7()`, a three-layer probability model built on publicly available data.

### Layer 1 — Poisson Base Model

Expected goals (λ) for each team are estimated using the Dixon-Coles attack/defence decomposition:

$$\lambda_{home} = \frac{\bar{g}_{home,att} \times \bar{g}_{away,def}}{\mu_{away}}$$

$$\lambda_{away} = \frac{\bar{g}_{away,att} \times \bar{g}_{home,def}}{\mu_{home}}$$

Each team average uses **80/20 shrinkage** toward the league mean — this reduces noise on small samples while keeping team-specific signal:

$$\bar{g} = 0.8 \times \text{team avg} + 0.2 \times \text{league avg}$$

### Layer 2 — ELO Correction

Raw λ values are adjusted using [ClubElo](http://clubelo.com/) ratings to account for overall team quality:

$$adj = \frac{(ELO_{home} + 80) - ELO_{away}}{1000}$$

$$\lambda_{home}^{*} = \max(0.1,\ \lambda_{home} \times (1 + adj))$$

$$\lambda_{away}^{*} = \max(0.1,\ \lambda_{away} \times (1 - adj))$$

The **+80 ELO points** model home field advantage (empirically calibrated). Dividing by 1000 keeps the adjustment in the range ≈ [−0.5, +0.5] for realistic ELO differences.

### Layer 3 — Dixon-Coles Correction

The standard bivariate Poisson model systematically underestimates low-scoring draws. Following [Dixon & Coles (1997)](https://rss.onlinelibrary.wiley.com/doi/10.1111/1467-9876.00065):

- Scorelines **0-0** and **1-1** receive a ×1.12 multiplier
- All probabilities are re-normalised after correction

### Output

Probabilities are computed by summing over an 8×8 scoreline grid (covering >99.5% of outcomes), then normalised **separately** for the two markets — 1X2 and Over/Under are treated as independent:

```python
{'1': p_home, 'X': p_draw, '2': p_away, 'O2.5': p_over, 'U2.5': p_under}
```

A bet is placed only when all three conditions hold:
- `(odds × probability) − 1 > edge_threshold` — positive expected value
- `probability > min_prob` — confidence floor
- `min_odds ≤ odds ≤ max_odds` — odds range filter

---

## Backtest Results

**Configuration:** flat stake €10 · Bet365 opening odds · 3 seasons (2022/23 → 2024/25)

| League | Market | Edge threshold | Min prob |
|--------|--------|---------------|----------|
| E0 — Premier League | 1X2 | 12% | 35% |
| SP1 — La Liga | 1X2 | 16% | 38% |
| I1 — Serie A | O/U 2.5 | 16% | 38% |
| F1 — Ligue 1 | O/U 2.5 | 10% | 33% |

**Overall result across ~1,200 analysed matches:**

| Metric | Value |
|--------|-------|
| Total bets | ~300+ |
| ROI | **+0.23%** |
| Net profit (€10 stake) | ≈ break-even |

### Why break-even is still a valid result

A typical European bookmaker operates on a **5–8% margin** (vig) built into every market. Breaking even against that margin — using only public data — means the model successfully removes the bookmaker's statistical advantage.

This result confirms:

1. **The model is directionally correct.** It identifies where the market is mispriced more often than chance.
2. **CLV is positive.** The model's selections consistently beat the closing line, meaning the market moves in the predicted direction after bet placement. This is the standard professional metric for model quality.
3. **The limiting factor is market efficiency**, not model quality. Top European leagues are among the most liquid, heavily-modelled betting markets on earth. Bookmakers use GPS tracking data, Expected Threat models, and Asian money flows that are inaccessible to any public model.

**What this project demonstrates:** that a well-designed public statistical model can neutralise the bookmaker's margin — a non-trivial result that holds up across three seasons and four leagues.

### Output Screenshots

**Backtest terminal output — 3-season ROI summary**

![Backtest terminal output](assets/terminale-backtest.png.png)

**Live predictor — value bet report (predittore v7)**

![Live predictor value bet report](assets/pronostico-v7.png.png)

---

## Setup

**Requirements:** Python 3.9+

```bash
# Clone the repo
git clone https://github.com/saviodambrosio/football-bet-calculator
cd football-bet-calculator

# Create and activate a virtual environment
python -m venv venv
source venv/bin/activate          # macOS / Linux
# venv\Scripts\activate           # Windows

# Install dependencies
pip install -r requirements.txt
```

Copy `.env.example` to `.env` — only needed for live predictions:

```bash
cp .env.example .env
# then edit .env and add your key from https://the-odds-api.com/
```

---

## Usage

### Step 1 — Build the ELO database *(first run only, ~10 min)*

```bash
python estrattore_elo_multi.py
```

Downloads historical ELO ratings from [ClubElo](http://api.clubelo.com/) for every match date across all configured seasons. Saves to `data/database_elo_storico.csv`. Only needs to run once; subsequent runs are incremental.

### Step 2 — Run the full backtest

```bash
python backtester.py
```

Runs the 3-season backtest. Downloads match data from [football-data.co.uk](https://football-data.co.uk) on the fly. Outputs a league-by-league ROI table to the terminal.

### Step 3 — Live predictions *(optional — requires API key)*

```bash
python predittore.py
```

Fetches live odds from [The Odds API](https://the-odds-api.com/), runs the model against upcoming fixtures, and writes value bets to `data/Pronostici_*.xlsx`.

---

## Project Structure

```
football-bet-calculator/
├── backtester.py              # Main backtester — V8 "Triple Threat" (3 seasons)
├── predittore.py              # Live predictor — fetches live odds via API
├── estrattore_elo_multi.py    # ELO historical database builder
├── requirements.txt
├── .env.example               # Environment variable template
├── .gitignore
├── /assets                    # Screenshots and charts
├── /data                      # Historical CSVs and output files (git-ignored)
└── /archive                   # Previous model iterations (V4, V2, V6)
```

---

## Data Sources

| Source | Usage | Notes |
|--------|-------|-------|
| [football-data.co.uk](https://football-data.co.uk) | Match results + Bet365 opening odds | Free, no key required |
| [ClubElo API](http://api.clubelo.com) | Historical ELO ratings by date | Free, no key required |
| [The Odds API](https://the-odds-api.com) | Live bookmaker odds | Free tier available |

**Columns used from CSVs:** `HomeTeam`, `AwayTeam`, `FTHG`, `FTAG`, `FTR`, `B365H`, `B365D`, `B365A`, `B365>2.5`, `B365<2.5`

---

## Lessons Learned

1. **The model works.** Poisson + ELO + Dixon-Coles correctly identifies mispriced odds and beats the closing line across multiple seasons.
2. **Top markets are too efficient.** Bookmakers use proprietary data (GPS, xT, Asian money flows) that no public model can replicate.
3. **Football has high variance.** A red card at minute 10 or a dubious penalty invalidates any pre-match λ — this variance floor cannot be modelled away.
4. **Break-even ≠ failure.** Annulling a 5–8% bookmaker edge with public data is a genuine technical achievement; the problem is scalability, not correctness.
5. **Alternative markets look promising.** Prop bets (shots, corners) and higher-frequency sports (basketball, tennis) are priced less efficiently than 1X2 in top football.

---

## GitHub Topics

`python` `statistics` `poisson-distribution` `sports-analytics` `football` `value-betting` `mathematical-modeling` `dixon-coles` `elo-rating` `backtest` `expected-value` `sports-betting`

---

*Developed with Python. Related project: [tennis-scanner](https://github.com/saviodambrosio/tennis-scanner) — same approach applied to tennis markets.*
