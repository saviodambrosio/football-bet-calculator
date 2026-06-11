import pandas as pd
import numpy as np
from scipy.stats import poisson
from datetime import datetime, timedelta
import os
import warnings

warnings.filterwarnings('ignore')

# ==========================================
# CONFIGURAZIONE V8 "TRIPLE THREAT" (3 STAGIONI)
# ==========================================
STAGIONI = ["2223", "2324", "2425"]
FILE_ELO = "data/database_elo_storico.csv"
STAKE_FISSO = 10

# Per ogni campionato: edge minimo, probabilità minima, quota massima, mercati attivi
CONFIG_CAMPIONATI = {
    'E0':  {'edge': 0.12, 'prob': 0.35, 'max_q': 4.0, 'mercati': ['1X2']},
    'SP1': {'edge': 0.16, 'prob': 0.38, 'max_q': 3.5, 'mercati': ['1X2']},
    'I1':  {'edge': 0.16, 'prob': 0.38, 'max_q': 3.5, 'mercati': ['OU']},
    'F1':  {'edge': 0.10, 'prob': 0.33, 'max_q': 4.0, 'mercati': ['OU']}
}

def carica_db_elo_locale():
    if not os.path.exists(FILE_ELO): return {}
    df = pd.read_csv(FILE_ELO)
    db = {}
    for data, group in df.groupby('Data'):
        db[data] = {str(row['Club']).replace(" ", "").lower(): row['Elo'] for _, row in group.iterrows()}
    return db

def pulisci_nome(nome):
    n = str(nome).replace(" ", "").lower()
    if 'milan' in n and 'inter' not in n: return 'milan'
    if 'inter' in n: return 'inter'
    if 'roma' in n: return 'roma'
    return n

def calcola_prob_v7(casa, ospite, df_storico, diz_elo_giorno):
    try:
        # Supporta sia il formato HomeTeam che Home_Team (dipende dall'anno del CSV)
        h_col = 'HomeTeam' if 'HomeTeam' in df_storico.columns else 'Home_Team'
        a_col = 'AwayTeam' if 'AwayTeam' in df_storico.columns else 'Away_Team'

        avg_hg, avg_ag = df_storico['FTHG'].mean(), df_storico['FTAG'].mean()
        s_c = df_storico[df_storico[h_col] == casa]
        s_o = df_storico[df_storico[a_col] == ospite]

        if len(s_c) < 5 or len(s_o) < 5: return None

        # --- POISSON BASE (Dixon-Coles style) ---
        # lambda_casa = (attacco_casa / media_lega) * (difesa_ospite / media_lega) * media_lega
        # Lo shrinkage 80/20 verso la media di lega riduce il rumore su campioni piccoli
        l_c = (s_c['FTHG'].mean() * 0.8 + avg_hg * 0.2) * (s_o['FTAG'].mean() * 0.8 + avg_ag * 0.2) / avg_ag
        l_o = (s_o['FTAG'].mean() * 0.8 + avg_ag * 0.2) * (s_c['FTAG'].mean() * 0.8 + avg_hg * 0.2) / avg_hg

        # --- CORREZIONE ELO ---
        # I +80 punti simulano il vantaggio campo (calibrato empiricamente su dati storici)
        # La divisione per 1000 scala adj nell'intervallo ≈ [-0.5, +0.5] per differenze ELO realistiche
        elo_c = diz_elo_giorno.get(pulisci_nome(casa), 1500)
        elo_o = diz_elo_giorno.get(pulisci_nome(ospite), 1500)
        adj = ((elo_c + 80) - elo_o) / 1000.0
        lc, lo = max(0.1, l_c * (1 + adj)), max(0.1, l_o * (1 - adj))

        p1, px, p2, u25, o25 = 0, 0, 0, 0, 0
        for i in range(8):  # somma su tutti gli scoreline possibili fino a 7-7
            for j in range(8):
                p = poisson.pmf(i, lc) * poisson.pmf(j, lo)
                # DIXON-COLES: il Poisson puro sottostima i pareggi bassi (0-0 e 1-1); +12% corregge
                if i == j and i <= 1: p *= 1.12
                if i > j: p1 += p
                elif i == j: px += p
                else: p2 += p
                if (i + j) <= 2: u25 += p  # Under 2.5 = al massimo 2 gol totali
                else: o25 += p

        t1x2, tou = p1 + px + p2, u25 + o25
        # Normalizzazione separata per 1X2 e Over/Under: sono mercati indipendenti
        return {'1': p1/t1x2, 'X': px/t1x2, '2': p2/t1x2, 'U2.5': u25/tou, 'O2.5': o25/tou}
    except: return None

def esegui_test():
    db_elo = carica_db_elo_locale()
    if not db_elo:
        print("Database ELO non trovato! Esegui prima estrattore_elo_multi.py")
        return

    report = {lg: {'p': 0, 'v': 0, 'inv': 0, 'rit': 0, 'q': 0} for lg in CONFIG_CAMPIONATI.keys()}

    print(f"\nAnalisi su 3 Stagioni: {STAGIONI}")

    for stagione in STAGIONI:
        print(f"  Processando stagione {stagione}...")
        for league, settaggi in CONFIG_CAMPIONATI.items():
            url = f"https://www.football-data.co.uk/mmz4281/{stagione}/{league}.csv"
            try:
                df = pd.read_csv(url)
                df['DateObj'] = pd.to_datetime(df['Date'], dayfirst=True, errors='coerce')
                df = df.dropna(subset=['DateObj'])

                h_col = 'HomeTeam' if 'HomeTeam' in df.columns else 'Home_Team'
                a_col = 'AwayTeam' if 'AwayTeam' in df.columns else 'Away_Team'

                n_sq = len(pd.concat([df[h_col], df[a_col]]).unique())
                skip = 5 * (n_sq // 2)  # salta le prime N giornate per avere storico sufficiente

                for i in range(skip, len(df) - skip):
                    match = df.iloc[i]
                    data_elo = (match['DateObj'] - timedelta(days=1)).strftime('%Y-%m-%d')
                    diz_g = db_elo.get(data_elo, {})

                    mie_p = calcola_prob_v7(match[h_col], match[a_col], df.iloc[:i], diz_g)
                    if not mie_p: continue

                    scelte = [
                        ('1',    match.get('B365H'),    str(match.get('FTR')) == 'H', '1X2'),
                        ('X',    match.get('B365D'),    str(match.get('FTR')) == 'D', '1X2'),
                        ('2',    match.get('B365A'),    str(match.get('FTR')) == 'A', '1X2'),
                        ('O2.5', match.get('B365>2.5'), (float(match.get('FTHG', 0)) + float(match.get('FTAG', 0))) > 2.5,  'OU'),
                        ('U2.5', match.get('B365<2.5'), (float(match.get('FTHG', 0)) + float(match.get('FTAG', 0))) <= 2.5, 'OU')
                    ]

                    for segno, quota, vinta, tipo in scelte:
                        if tipo not in settaggi['mercati']: continue
                        if pd.isna(quota) or not (1.60 <= quota <= settaggi['max_q']): continue

                        prob = mie_p.get(segno, 0)
                        # Value bet: probabilità implicita del bookmaker < nostra stima (edge > soglia)
                        if prob > settaggi['prob'] and (quota * prob - 1) > settaggi['edge']:
                            r = report[league]
                            r['p'] += 1
                            r['inv'] += STAKE_FISSO
                            r['q'] += quota
                            if vinta:
                                r['rit'] += (STAKE_FISSO * quota)
                                r['v'] += 1
            except Exception as e:
                print(f"Errore {league} {stagione}: {e}")

    print("\n" + "═"*75)
    print(f"{'LEAGUE':<10} | {'BETS':<5} | {'WIN %':<7} | {'ROI %':<8}")
    print("─"*75)
    t_inv, t_rit = 0, 0
    for lg, s in report.items():
        if s['p'] > 0:
            roi = ((s['rit'] - s['inv']) / s['inv']) * 100
            print(f"{lg:<10} | {s['p']:<5} | {s['v']/s['p']*100:>6.1f}% | {roi:>7.1f}%")
            t_inv += s['inv']; t_rit += s['rit']

    if t_inv > 0:
        final_roi = ((t_rit - t_inv) / t_inv * 100)
        print("\n" + "═"*75)
        print(f"RISULTATO FINALE 3 ANNI:")
        print(f"Scommesse totali: {int(t_inv/STAKE_FISSO)}")
        print(f"ROI TOTALE: {final_roi:.2f}%")
        print(f"PROFITTO NETTO: {round(t_rit - t_inv, 2)}€")
    print("═"*75)

if __name__ == "__main__":
    esegui_test()
