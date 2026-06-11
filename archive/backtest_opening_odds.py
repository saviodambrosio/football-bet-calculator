import pandas as pd
import numpy as np
from scipy.stats import poisson
from datetime import datetime, timedelta
import warnings

warnings.filterwarnings('ignore')

# --- CONFIGURAZIONE NINJA V6 (OTTIMIZZATA PER APERTURA) ---
BANKROLL_INIZIALE = 1000
SOGLIA_EDGE = 0.10        # Mantieni il 10% di vantaggio
MIN_PROB = 0.30           
MAX_ODDS = 4.00           
FRAZIONE_KELLY = 0.03     
MAX_STAKE_PERC = 0.015    

cache_elo = {}

def ottieni_diz_elo(data_match):
    data_precedente = (data_match - timedelta(days=1)).strftime('%Y-%m-%d')
    if data_precedente not in cache_elo:
        url = f"http://api.clubelo.com/{data_precedente}"
        try:
            df_elo = pd.read_csv(url)
            cache_elo[data_precedente] = {str(row['Club']).replace(" ", "").lower(): row['Elo'] for _, row in df_elo.iterrows()}
        except: cache_elo[data_precedente] = {}
    return cache_elo[data_precedente]

def pulisci_nome(nome):
    n = str(nome).replace(" ", "").lower()
    if 'bayern' in n: return 'bayern'
    if 'milan' in n and 'inter' not in n: return 'milan'
    if 'inter' in n: return 'inter'
    return n

def calcola_v6(casa, ospite, df_storico, diz_elo):
    try:
        avg_hg = df_storico['FTHG'].mean()
        avg_ag = df_storico['FTAG'].mean()
        s_c = df_storico[df_storico['HomeTeam'] == casa]
        s_o = df_storico[df_storico['AwayTeam'] == ospite]
        if len(s_c) < 4 or len(s_o) < 4: return None

        l_c = (s_c['FTHG'].mean() * 0.8 + avg_hg * 0.2) * (s_o['FTAG'].mean() * 0.8 + avg_ag * 0.2) / avg_ag
        l_o = (s_o['FTAG'].mean() * 0.8 + avg_ag * 0.2) * (s_c['FTHG'].mean() * 0.8 + avg_hg * 0.2) / avg_hg

        elo_c = diz_elo.get(pulisci_nome(casa), 1500)
        elo_o = diz_elo.get(pulisci_nome(ospite), 1500)
        adj = ((elo_c + 80) - elo_o) / 1000.0
        
        l_c_corr, l_o_corr = max(0.1, l_c * (1 + adj)), max(0.1, l_o * (1 - adj))

        p1, px, p2 = 0, 0, 0
        for i in range(8):
            for j in range(8):
                p = poisson.pmf(i, l_c_corr) * poisson.pmf(j, l_o_corr)
                if i == j and i <= 1: p *= 1.12 
                if i > j: p1 += p
                elif i == j: px += p
                else: p2 += p
        tot = p1 + px + p2
        return {'1': p1/tot, 'X': px/tot, '2': p2/tot}
    except: return None

def test_apertura():
    bankroll = BANKROLL_INIZIALE
    scommesse = 0
    vinte = 0
    
    print("🏟️ BACKTESTER V6 - MODALITÀ QUOTE APERTURA (Bet365)")
    print("Analizziamo l'efficienza del modello quando il mercato è ancora fresco...\n")

    for league in ['I1', 'E0', 'SP1', 'D1', 'F1']:
        url = f"https://www.football-data.co.uk/mmz4281/2526/{league}.csv"
        try:
            # Carichiamo anche le quote B365 che rappresentano l'apertura standard
            df = pd.read_csv(url).dropna(subset=['B365H', 'B365D', 'B365A', 'FTR', 'Date'])
            df['DateObj'] = pd.to_datetime(df['Date'], dayfirst=True)
            print(f"-> Analizzando {league}...")
        except: continue
        
        for i in range(40, len(df)): 
            partita = df.iloc[i]
            diz_elo = ottieni_diz_elo(partita['DateObj'])
            mie_p = calcola_v6(partita['HomeTeam'], partita['AwayTeam'], df.iloc[:i], diz_elo)
            if not mie_p: continue

            # USIAMO LE QUOTE DI APERTURA DI BET365
            quote_open = {'1': partita['B365H'], 'X': partita['B365D'], '2': partita['B365A']}
            res_reale = str(partita['FTR']).replace('H', '1').replace('D', 'X').replace('A', '2')
            
            for esito in ['1', 'X', '2']:
                p_mia, q_o = mie_p[esito], quote_open[esito]
                edge = (q_o * p_mia) - 1

                if edge > SOGLIA_EDGE and p_mia > MIN_PROB and q_o < MAX_ODDS:
                    b = q_o - 1
                    stake = min(max(0, ((p_mia * q_o - 1) / b) * FRAZIONE_KELLY), MAX_STAKE_PERC)
                    
                    if stake > 0:
                        scommesse += 1
                        puntata = bankroll * stake
                        if esito == res_reale:
                            bankroll += puntata * (q_o - 1)
                            vinte += 1
                        else:
                            bankroll -= puntata

    print("\n" + "="*40)
    print(f"RISULTATI (OPENING ODDS):")
    print(f"Scommesse: {scommesse} | Win Rate: {round((vinte/scommesse)*100, 1)}%")
    print(f"Bankroll Finale: {round(bankroll, 2)}€")
    print(f"ROI: {round(((bankroll-1000)/1000)*100, 2)}%")
    print("="*40)

if __name__ == "__main__":
    test_apertura()