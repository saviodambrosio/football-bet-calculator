import pandas as pd
import numpy as np
from scipy.stats import poisson
from datetime import datetime, timedelta
import warnings

warnings.filterwarnings('ignore')

# --- SETTAGGI V6 (IL MODELLO COMPLETO) ---
BANKROLL_INIZIALE = 1000
SOGLIA_EDGE = 0.10        
MIN_PROB = 0.30           
MAX_ODDS = 4.00           
FRAZIONE_KELLY = 0.03     
MAX_STAKE_PERC = 0.015    

# Cache per non intasarci con le richieste API
cache_elo = {}

def ottieni_diz_elo(data_match):
    """Scarica o recupera dalla cache l'ELO di una specifica data"""
    # Usiamo il giorno prima del match per avere i dati pre-partita
    data_precedente = (data_match - timedelta(days=1)).strftime('%Y-%m-%d')
    
    if data_precedente not in cache_elo:
        url = f"http://api.clubelo.com/{data_precedente}"
        try:
            df_elo = pd.read_csv(url)
            cache_elo[data_precedente] = {str(row['Club']).replace(" ", "").lower(): row['Elo'] for _, row in df_elo.iterrows()}
        except:
            cache_elo[data_precedente] = {} # Se fallisce, dizionario vuoto
            
    return cache_elo[data_precedente]

def pulisci_nome(nome):
    """Normalizza i nomi per farli combaciare con ClubElo"""
    n = str(nome).replace(" ", "").lower()
    if 'bayern' in n: return 'bayern'
    if 'milan' in n and 'inter' not in n: return 'milan'
    if 'inter' in n: return 'inter'
    if 'roma' in n: return 'roma'
    return n

def calcola_v6(casa, ospite, df_storico, diz_elo):
    try:
        avg_hg = df_storico['FTHG'].mean()
        avg_ag = df_storico['FTAG'].mean()

        s_c = df_storico[df_storico['HomeTeam'] == casa]
        s_o = df_storico[df_storico['AwayTeam'] == ospite]

        if len(s_c) < 4 or len(s_o) < 4: return None

        # Poisson Base
        l_c = (s_c['FTHG'].mean() * 0.8 + avg_hg * 0.2) * (s_o['FTAG'].mean() * 0.8 + avg_ag * 0.2) / avg_ag
        l_o = (s_o['FTAG'].mean() * 0.8 + avg_ag * 0.2) * (s_c['FTHG'].mean() * 0.8 + avg_hg * 0.2) / avg_hg

        # --- INTEGRAZIONE ELO STORICO ---
        elo_c = diz_elo.get(pulisci_nome(casa), 1500)
        elo_o = diz_elo.get(pulisci_nome(ospite), 1500)
        
        # Differenza ELO + Vantaggio in casa (circa 80 punti)
        diff_elo = (elo_c + 80) - elo_o
        adj = diff_elo / 1000.0  # Fattore di correzione
        
        # Correzione delle aspettative di gol
        l_c_corr = max(0.1, l_c * (1 + adj))
        l_o_corr = max(0.1, l_o * (1 - adj))

        p1, px, p2 = 0, 0, 0
        for i in range(8):
            for j in range(8):
                p = poisson.pmf(i, l_c_corr) * poisson.pmf(j, l_o_corr)
                if i == j and i <= 1: p *= 1.12 # Dixon-Coles
                if i > j: p1 += p
                elif i == j: px += p
                else: p2 += p
        
        tot = p1 + px + p2
        return {'1': p1/tot, 'X': px/tot, '2': p2/tot}
    except:
        return None

def test_finale():
    bankroll = BANKROLL_INIZIALE
    scommesse = 0
    vinte = 0
    
    print("🚀 Avvio Backtester V6 (Poisson + Storico ELO)...")
    print("Attenzione: Il download dell'ELO storico richiede qualche minuto in più.\n")

    for league in ['I1', 'E0', 'SP1', 'D1', 'F1']:
        url = f"https://www.football-data.co.uk/mmz4281/2526/{league}.csv"
        try:
            df = pd.read_csv(url).dropna(subset=['AvgH', 'AvgD', 'AvgA', 'FTR', 'Date'])
            # Convertiamo la data in formato datetime per l'API ClubElo
            df['DateObj'] = pd.to_datetime(df['Date'], dayfirst=True)
            print(f"-> Analizzando {league}...")
        except Exception as e:
            continue
        
        for i in range(40, len(df)): 
            partita = df.iloc[i]
            storico = df.iloc[:i]
            data_match = partita['DateObj']
            
            # Recuperiamo l'ELO per quel giorno esatto
            diz_elo = ottieni_diz_elo(data_match)
            
            mie_p = calcola_v6(partita['HomeTeam'], partita['AwayTeam'], storico, diz_elo)
            if not mie_p: continue

            quote_bookie = {'1': partita['AvgH'], 'X': partita['AvgD'], '2': partita['AvgA']}
            risultato_reale_mappato = str(partita['FTR']).replace('H', '1').replace('D', 'X').replace('A', '2')
            
            for esito_testato in ['1', 'X', '2']:
                p_mia = mie_p[esito_testato]
                q_b = quote_bookie[esito_testato]
                
                edge = (q_b * p_mia) - 1

                if edge > SOGLIA_EDGE and p_mia > MIN_PROB and q_b < MAX_ODDS:
                    b = q_b - 1
                    stake_perc = ((p_mia * q_b - 1) / b) * FRAZIONE_KELLY
                    stake_perc = min(max(0, stake_perc), MAX_STAKE_PERC)
                    
                    if stake_perc > 0:
                        scommesse += 1
                        puntata = bankroll * stake_perc
                        
                        if esito_testato == risultato_reale_mappato:
                            bankroll += puntata * (q_b - 1)
                            vinte += 1
                        else:
                            bankroll -= puntata

    print("\n" + "="*35)
    if scommesse > 0:
        print(f"Scommesse totali: {scommesse}")
        print(f"Win Rate: {round((vinte/scommesse)*100, 1)}%")
        print(f"Bankroll Finale: {round(bankroll, 2)}€")
        roi = ((bankroll-1000)/1000)*100
        print(f"ROI: {round(roi, 2)}%")
        if roi > 0:
            print("🟢 PROFITTO RAGGIUNTO! IL MODELLO BATTE IL BANCO.")
    else:
        print("Nessuna scommessa trovata.")
    print("="*35)

if __name__ == "__main__":
    test_finale()