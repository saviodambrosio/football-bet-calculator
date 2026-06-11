# PLAN.md — football-bet-calculator
**Contesto di progetto per Claude Code e sessioni future**
*Ultimo aggiornamento: Giugno 2026*

---

## 🎯 OBIETTIVO DEL PROGETTO

Sistema di **value betting calcistico** basato su arbitraggio statistico quantitativo. Il software identifica Value Bet nei mercati 1X2 e Over/Under 2.5 confrontando le probabilità calcolate internamente con le quote dei bookmaker (Bet365 / The Odds API).

**Stato attuale: Chiuso / Portfolio** — Il sistema è funzionante ma il backtest su 3 anni (~1200 partite) ha restituito ROI 0.23% (break-even). Il progetto viene pubblicato come portfolio tecnico con risultato onesto documentato, non come sistema profittevole.

---

## 🏗️ ARCHITETTURA DEL MOTORE MATEMATICO

Il cuore del sistema è la funzione `calcola_prob_v7()`, presente in tutti i moduli principali.

### Layer 1 — Distribuzione di Poisson
Calcola i **gol attesi (λ)** per casa e trasferta:
- Ponderazione **80/20**: 80% storico squadra, 20% media campionato
- Incrocio attacco/difesa: forza offensiva squadra A × debolezza difensiva squadra B

### Layer 2 — Ranking ELO (ClubElo API)
Corregge il λ in base alla qualità reale delle squadre:
- **+80 punti ELO** fissi alla squadra di casa (home field advantage)
- Aggiustamento proporzionale: `adj = (elo_casa + 80 - elo_ospite) / 1000`
- λ corretti: `λ_casa × (1 + adj)`, `λ_ospite × (1 - adj)`

### Layer 3 — Correzione Dixon-Coles
Adatta il modello alla realtà tattica europea:
- Moltiplicatore **+12%** sui risultati 0-0 e 1-1 (pareggi a basso punteggio sovrarappresentati nel calcio europeo)

### Output probabilità
```
{'1': p_casa, 'X': p_pareggio, '2': p_ospite, 'O2.5': p_over, 'U2.5': p_under}
```

---

## 📁 STRUTTURA FILE (POST-PULIZIA)

```
football-bet-calculator/
│
├── backtester.py              # Backtester principale V8 "Triple Threat" (3 stagioni)
├── predittore.py              # Modulo live: scarica quote API e trova Value Bet
├── estrattore_elo_multi.py    # Scarica e aggiorna database ELO storico
│
├── .env                       # API key (NON su GitHub)
├── .env.example               # Template con placeholder
├── .gitignore                 # Esclude .env, /data, __pycache__, *.xlsx
│
├── /data                      # CSV storici (esclusi da git — troppo pesanti)
│   ├── database_elo_storico.csv
│   └── I1.csv, SP1.csv, F1.csv, ecc.
│
├── /archive                   # Versioni precedenti (per documentare l'evoluzione)
│   ├── backtester_v1.py
│   ├── backtester_open_odds_v2.py
│   └── backtest_opening_odds_v6.py
│
├── /output                    # Excel generati (esclusi da git)
│
├── README.md                  # Documentazione pubblica (EN)
├── README.it.md               # Documentazione pubblica (IT)
└── PLAN.md                    # Questo file
```

---

## ⚙️ CONFIGURAZIONE CHIAVE (backtester.py)

```python
# Strategia "The Specialist" — mercati target per campionato
CONFIG_CAMPIONATI = {
    'E0':  {'edge': 0.12, 'mercati': ['1X2']},   # Premier League
    'SP1': {'edge': 0.16, 'mercati': ['1X2']},   # La Liga
    'I1':  {'edge': 0.16, 'mercati': ['OU']},    # Serie A
    'F1':  {'edge': 0.10, 'mercati': ['OU']}     # Ligue 1
}

STAGIONI = ["2223", "2324", "2425"]  # 3 anni di backtest
STAKE_FISSO = 10                      # €10 per scommessa (flat betting)
```

---

## 🔑 VARIABILI D'AMBIENTE (.env)

```env
ODDS_API_KEY=your_key_here
```

Ottenere chiave su: https://the-odds-api.com/#get-access
Il file `.env` viene letto con `python-dotenv`:
```python
from dotenv import load_dotenv
import os
load_dotenv()
API_KEY = os.getenv('ODDS_API_KEY')
```

---

## 📊 RISULTATI BACKTEST (DEFINITIVI)

| Stagioni | Partite analizzate | Scommesse | ROI |
|---|---|---|---|
| 2022/23 + 2023/24 + 2024/25 | ~1200+ | ~300+ | **+0.23%** |

**Interpretazione:** Il modello annulla l'aggio del bookmaker (risultato tecnicamente valido) ma non genera profitto scalabile. Causa principale: efficienza dei mercati top europei + alta varianza del calcio a basso punteggio.

**CLV:** Positivo — il sistema batte sistematicamente le opening odds prima che il mercato le aggiusti. Questo conferma che il modello legge correttamente la direzione del mercato, ma il margine è insufficiente per generare profitto netto.

---

## 🔄 FONTI DATI

| Fonte | Uso | URL |
|---|---|---|
| football-data.co.uk | CSV storici partite + quote B365 | https://www.football-data.co.uk |
| ClubElo API | Rating ELO storici per data | http://api.clubelo.com/{YYYY-MM-DD} |
| The Odds API | Quote live per predittore | https://the-odds-api.com |

**Colonne CSV usate:** `HomeTeam`, `AwayTeam`, `FTHG`, `FTAG`, `FTR`, `B365H`, `B365D`, `B365A`, `B365>2.5`, `B365<2.5`

---

## 🛠️ SETUP LOCALE

```bash
# Installa dipendenze
pip install pandas numpy scipy requests openpyxl python-dotenv

# Aggiorna database ELO (prima esecuzione — richiede ~10 minuti)
python estrattore_elo_multi.py

# Esegui backtest completo 3 stagioni
python backtester.py

# Trova value bet live (richiede API key valida in .env)
python predittore.py
```

---

## 📋 TODO — PUBBLICAZIONE PORTFOLIO

- [x] Codice funzionante e backtest completato
- [x] Post-mortem analitico scritto (ROI 0.23%, cause diagnosticate)
- [x] API key spostate in .env
- [x] .gitignore configurato
- [x] Versioni precedenti archiviate in /archive
- [x] Commenti aggiunti ai blocchi matematici chiave
- [x] README.md scritto (EN) — focus sul modello matematico
- [x] README.it.md scritto (IT)
- [ ] Screenshot output aggiunto ad /assets
- [ ] Push su GitHub pubblico
- [ ] Topic tags: `python` `statistics` `poisson` `sports-analytics` `mathematical-modeling` `dixon-coles` `elo-rating`
- [ ] Post LinkedIn

---

## 💡 LEZIONI APPRESE (da includere nel README)

1. **Poisson + ELO + Dixon-Coles funziona** — il modello è matematicamente corretto e batte le opening odds (CLV positivo)
2. **I mercati top europei sono troppo efficienti** — Bet365 usa dati GPS, Expected Threat, flussi asiatici inaccessibili ai modelli pubblici
3. **Alta varianza del calcio** — un'espulsione al 10', un rigore dubbio distrugge qualsiasi λ pre-calcolato
4. **ROI 0.23% ≠ fallimento** — annullare l'aggio è un risultato tecnico valido; il problema è la scalabilità
5. **Mercati alternativi promettenti** — prop bets (tiri, angoli) e sport ad alta frequenza (basket, tennis) sono meno presidiati

---

## 🔗 RIFERIMENTI PROGETTO

- **GitHub:** da creare — `github.com/saviodambrosio/football-bet-calculator`
- **Linguaggio:** Python 3.9+
- **Librerie:** pandas, numpy, scipy, requests, openpyxl, python-dotenv
- **Sviluppato con:** Gemini (sviluppo iniziale), Claude (refactoring e pubblicazione)
- **Progetto correlato:** [tennis-scanner](https://github.com/saviodambrosio/tennis-scanner) — stesso approccio, stesso risultato onesto