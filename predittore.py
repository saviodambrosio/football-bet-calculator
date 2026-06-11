import pandas as pd
import numpy as np
from scipy.stats import poisson
import requests
import os
from datetime import datetime
import warnings

warnings.filterwarnings('ignore')

# Carica le variabili d'ambiente da .env (richiede: pip install python-dotenv)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# ==========================================
# CONFIGURAZIONE PREDITTORE V7.1 (STABILE)
# ==========================================
API_KEY = os.getenv('THE_ODDS_API_KEY', '')
BANKROLL = 1000
STAKE_FISSO_EURO = 15
SOGLIA_EDGE = 0.10
MIN_PROB = 0.30
MIN_ODDS = 1.60
MAX_ODDS = 4.00

# Mapping chiavi The Odds API → codici football-data.co.uk
CAMPIONATI = {
    'soccer_italy_serie_a':        'I1',
    'soccer_italy_serie_b':        'I2',
    'soccer_epl':                  'E0',
    'soccer_efl_championship':     'E1',
    'soccer_spain_la_liga':        'SP1',
    'soccer_germany_bundesliga':   'D1',
    'soccer_france_ligue_one':     'F1',
    'soccer_netherlands_eredivisie': 'N1',
    'soccer_portugal_primeira_liga': 'P1'
}

def pulisci_nome(nome):
    n = str(nome).replace(" ", "").lower()
    if 'milan' in n and 'inter' not in n: return 'milan'
    if 'inter' in n: return 'inter'
    if 'roma' in n: return 'roma'
    return n

def scarica_elo_oggi():
    print("Recupero Ranking ELO attuale...")
    try:
        df_elo = pd.read_csv("http://api.clubelo.com/api/api.php")
        return {pulisci_nome(row['Club']): row['Elo'] for _, row in df_elo.iterrows()}
    except: return {}

def calcola_prob_v7(casa, ospite, df_storico, diz_elo):
    try:
        avg_hg = df_storico['FTHG'].mean()
        avg_ag = df_storico['FTAG'].mean()
        s_c = df_storico[df_storico['HomeTeam'] == casa]
        s_o = df_storico[df_storico['AwayTeam'] == ospite]
        if len(s_c) < 4 or len(s_o) < 4: return None

        # --- POISSON BASE (Dixon-Coles style) ---
        # lambda = (forza_attacco * forza_difesa_avversaria) / media_lega
        # Lo shrinkage 80/20 verso la media di lega riduce il rumore su campioni piccoli
        l_c = (s_c['FTHG'].mean() * 0.8 + avg_hg * 0.2) * (s_o['FTAG'].mean() * 0.8 + avg_ag * 0.2) / avg_ag
        l_o = (s_o['FTAG'].mean() * 0.8 + avg_ag * 0.2) * (s_c['FTHG'].mean() * 0.8 + avg_hg * 0.2) / avg_hg

        # --- CORREZIONE ELO ---
        # I +80 punti simulano il vantaggio campo (calibrato empiricamente su dati storici)
        # La divisione per 1000 scala adj nell'intervallo ≈ [-0.5, +0.5] per differenze ELO realistiche
        elo_c, elo_o = diz_elo.get(pulisci_nome(casa), 1500), diz_elo.get(pulisci_nome(ospite), 1500)
        adj = ((elo_c + 80) - elo_o) / 1000.0
        l_c_corr, l_o_corr = max(0.1, l_c * (1 + adj)), max(0.1, l_o * (1 - adj))

        p1, px, p2, u25, o25 = 0, 0, 0, 0, 0
        for i in range(8):  # somma su tutti gli scoreline possibili fino a 7-7
            for j in range(8):
                p = poisson.pmf(i, l_c_corr) * poisson.pmf(j, l_o_corr)
                # DIXON-COLES: il Poisson puro sottostima i pareggi bassi (0-0 e 1-1); +12% corregge
                if i == j and i <= 1: p *= 1.12
                if i > j: p1 += p
                elif i == j: px += p
                else: p2 += p
                if (i + j) <= 2: u25 += p  # Under 2.5 = al massimo 2 gol totali
                else: o25 += p

        tot_1x2, tot_ou = p1 + px + p2, u25 + o25
        # Normalizzazione separata per 1X2 e Over/Under: sono mercati indipendenti
        return {'1': p1/tot_1x2, 'X': px/tot_1x2, '2': p2/tot_1x2, 'U2.5': u25/tot_ou, 'O2.5': o25/tot_ou}
    except: return None

def avvia_predittore():
    if not API_KEY:
        print("Errore: THE_ODDS_API_KEY non impostata. Controlla il file .env")
        return

    diz_elo = scarica_elo_oggi()
    pronostici = []

    for api_league, csv_code in CAMPIONATI.items():
        print(f"-> Analizzando {api_league}...")
        try:
            url_csv = f"https://www.football-data.co.uk/mmz4281/2526/{csv_code}.csv"
            df_storico = pd.read_csv(url_csv).dropna(subset=['FTHG'])
        except: continue

        url_api = f"https://api.the-odds-api.com/v4/sports/{api_league}/odds/?apiKey={API_KEY}&regions=eu&markets=h2h,totals"
        res = requests.get(url_api)

        if res.status_code != 200:
            print(f"   ERRORE API ({res.status_code}): {res.text}")
            continue

        for match in res.json():
            casa, ospite = match['home_team'], match['away_team']
            mie_p = calcola_prob_v7(casa, ospite, df_storico, diz_elo)
            if not mie_p: continue

            q_max = {'1': 0, 'X': 0, '2': 0, 'O2.5': 0, 'U2.5': 0}
            for bookie in match['bookmakers']:
                for m in bookie['markets']:
                    if m['key'] == 'h2h':
                        for o in m['outcomes']:
                            if o['name'] == casa:    q_max['1'] = max(q_max['1'], o['price'])
                            elif o['name'] == 'Draw': q_max['X'] = max(q_max['X'], o['price'])
                            elif o['name'] == ospite: q_max['2'] = max(q_max['2'], o['price'])
                    elif m['key'] == 'totals':
                        for o in m['outcomes']:
                            if o.get('point') == 2.5:
                                if o['name'] == 'Over':  q_max['O2.5'] = max(q_max['O2.5'], o['price'])
                                elif o['name'] == 'Under': q_max['U2.5'] = max(q_max['U2.5'], o['price'])

            for segno, prob in mie_p.items():
                quota = q_max.get(segno, 0)
                if MIN_ODDS <= quota <= MAX_ODDS and prob > MIN_PROB:
                    # Edge = rendimento atteso - 1: positivo significa valore reale contro il bookmaker
                    edge = (quota * prob) - 1
                    if edge > SOGLIA_EDGE:
                        pronostici.append({
                            'Match':   f"{casa} - {ospite}",
                            'Mercato': segno,
                            'Quota':   quota,
                            'Prob %':  round(prob * 100, 1),
                            'Edge %':  round(edge * 100, 1)
                        })

    if pronostici:
        df = pd.DataFrame(pronostici).sort_values(by='Edge %', ascending=False)
        print("\nVALORI TROVATI:\n", df)
        df.to_excel(f"data/Pronostici_V7_Finale_{datetime.now().strftime('%d%m')}.xlsx", index=False)
    else:
        print("\nNessuna Value Bet trovata al momento.")

if __name__ == "__main__":
    avvia_predittore()
