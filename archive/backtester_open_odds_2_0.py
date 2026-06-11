import pandas as pd
import numpy as np
from scipy.stats import poisson
from datetime import datetime, timedelta
import os
import warnings

warnings.filterwarnings('ignore')

# ==========================================
# 💎 CONFIGURAZIONE V4 "ULTIMATE SETUP" 
# (Top 4 Leagues + 1X2 + O/U + Max Odds)
# ==========================================
STAKE_FISSO = 10          
SOGLIA_EDGE = 0.12        # Edge reale del 12% (ottimale sulle Max Odds)
MIN_PROB = 0.35           # Tagliamo le scommesse troppo azzardate
MIN_ODDS = 1.60           # Quota minima di rispetto
MAX_ODDS = 3.90           # Tetto massimo 
STAGIONE = "2425"

# Via la Bundesliga! Solo l'élite europea più stabile.
CAMPIONATI = ['E0', 'I1', 'SP1', 'F1'] 
FILE_ELO = "database_elo_storico.csv"

def carica_db_elo_locale():
    print(f"📂 Caricamento database ELO ({FILE_ELO})...")
    if not os.path.exists(FILE_ELO):
        print("❌ FILE NON TROVATO! Assicurati che il CSV sia nella cartella.")
        return {}
    
    try:
        df = pd.read_csv(FILE_ELO)
        db = {}
        for data, group in df.groupby('Data'):
            db[data] = {str(row['Club']).replace(" ", "").lower(): row['Elo'] for _, row in group.iterrows()}
        print("✅ Database ELO pronto.")
        return db
    except Exception as e:
        print(f"❌ Errore caricamento: {e}")
        return {}

def pulisci_nome(nome):
    n = str(nome).replace(" ", "").lower()
    if 'milan' in n and 'inter' not in n: return 'milan'
    if 'inter' in n: return 'inter'
    if 'roma' in n: return 'roma'
    return n

def calcola_prob_v7(casa, ospite, df_storico, diz_elo_giorno):
    try:
        avg_hg = df_storico['FTHG'].mean()
        avg_ag = df_storico['FTAG'].mean()
        s_c = df_storico[df_storico['HomeTeam'] == casa]
        s_o = df_storico[df_storico['AwayTeam'] == ospite]
        if len(s_c) < 5 or len(s_o) < 5: return None

        # Base Poisson
        l_c = (s_c['FTHG'].mean() * 0.8 + avg_hg * 0.2) * (s_o['FTAG'].mean() * 0.8 + avg_ag * 0.2) / avg_ag
        l_o = (s_o['FTAG'].mean() * 0.8 + avg_ag * 0.2) * (s_c['FTAG'].mean() * 0.8 + avg_hg * 0.2) / avg_hg

        # Correzione ELO
        elo_c = diz_elo_giorno.get(pulisci_nome(casa), 1500)
        elo_o = diz_elo_giorno.get(pulisci_nome(ospite), 1500)
        adj = ((elo_c + 80) - elo_o) / 1000.0
        l_c_corr, l_o_corr = max(0.1, l_c * (1 + adj)), max(0.1, l_o * (1 - adj))

        p1, px, p2, u25, o25 = 0, 0, 0, 0, 0
        for i in range(8):
            for j in range(8):
                p = poisson.pmf(i, l_c_corr) * poisson.pmf(j, l_o_corr)
                if i == j and i <= 1: p *= 1.12 # Dixon-Coles
                if i > j: p1 += p
                elif i == j: px += p
                else: p2 += p
                
                # Calcolo Gol per l'Over/Under
                if (i + j) <= 2: u25 += p
                else: o25 += p
        
        tot_1x2 = p1 + px + p2
        tot_ou = u25 + o25
        
        return {
            '1': p1/tot_1x2, 'X': px/tot_1x2, '2': p2/tot_1x2,
            'U2.5': u25/tot_ou, 'O2.5': o25/tot_ou
        }
    except: return None

def esegui_test():
    db_elo = carica_db_elo_locale()
    if not db_elo: return

    report_campionati = {lg: {'p': 0, 'v': 0, 'inv': 0, 'rit': 0} for lg in CAMPIONATI}
    report_mercati = {'1X2': {'p': 0, 'v': 0, 'inv': 0, 'rit': 0}, 
                      'OU': {'p': 0, 'v': 0, 'inv': 0, 'rit': 0}}
    
    print(f"\n🚀 Avvio Backtest 'Ultimate Setup' su {len(CAMPIONATI)} campionati Top...")

    for league in CAMPIONATI:
        url = f"https://www.football-data.co.uk/mmz4281/{STAGIONE}/{league}.csv"
        try:
            df = pd.read_csv(url)
            df['DateObj'] = pd.to_datetime(df['Date'], dayfirst=True)
            print(f"📊 Elaborazione {league} ({len(df)} partite)...")
        except Exception as e:
            print(f"⚠️ Errore download {league}: {e}")
            continue

        count = 0
        for i in range(35, len(df)):
            match = df.iloc[i]
            data_str = (match['DateObj'] - timedelta(days=1)).strftime('%Y-%m-%d')
            diz_giorno = db_elo.get(data_str, {})
            
            home = match['Home_Team'] if 'Home_Team' in match else match['HomeTeam']
            away = match['Away_Team'] if 'Away_Team' in match else match['AwayTeam']
            
            mie_p = calcola_prob_v7(home, away, df.iloc[:i], diz_giorno)
            if not mie_p: continue

            # Max Odds per 1X2
            q_1 = match.get('MaxH') if pd.notna(match.get('MaxH')) else match.get('B365H')
            q_X = match.get('MaxD') if pd.notna(match.get('MaxD')) else match.get('B365D')
            q_2 = match.get('MaxA') if pd.notna(match.get('MaxA')) else match.get('B365A')
            
            # Max Odds per Over/Under
            q_O = match.get('Max>2.5') if pd.notna(match.get('Max>2.5')) else match.get('B365>2.5')
            q_U = match.get('Max<2.5') if pd.notna(match.get('Max<2.5')) else match.get('B365<2.5')

            # Prevenzione errori su valori vuoti nei Gol
            hg = float(match.get('FTHG', 0)) if pd.notna(match.get('FTHG')) else 0
            ag = float(match.get('FTAG', 0)) if pd.notna(match.get('FTAG')) else 0
            tot_gol = hg + ag

            scelte = [
                ('1', q_1, str(match.get('FTR')) == 'H', '1X2'),
                ('X', q_X, str(match.get('FTR')) == 'D', '1X2'),
                ('2', q_2, str(match.get('FTR')) == 'A', '1X2'),
                ('O2.5', q_O, tot_gol > 2.5, 'OU'),
                ('U2.5', q_U, tot_gol <= 2.5, 'OU')
            ]

            for segno, quota, vinta, tipo in scelte:
                if pd.isna(quota) or not (MIN_ODDS <= quota <= MAX_ODDS): continue
                
                prob = mie_p.get(segno, 0)
                if prob > MIN_PROB:
                    edge = (quota * prob) - 1
                    if edge > SOGLIA_EDGE:
                        report_campionati[league]['p'] += 1
                        report_campionati[league]['inv'] += STAKE_FISSO
                        report_mercati[tipo]['p'] += 1
                        report_mercati[tipo]['inv'] += STAKE_FISSO
                        if vinta:
                            rit = (STAKE_FISSO * quota)
                            report_campionati[league]['rit'] += rit
                            report_campionati[league]['v'] += 1
                            report_mercati[tipo]['rit'] += rit
            
            count += 1
            if count % 50 == 0:
                print(f"  > Analizzate {i}/{len(df)} partite...", end="\r")

    # ==========================================
    # 🏁 RISULTATI FINALI 
    # ==========================================
    print("\n" + "═"*60)
    print(f"{'CAMPIONATO':<15} | {'BETS':<5} | {'WIN %':<8} | {'ROI %':<8}")
    print("─"*60)
    tot_p, tot_inv, tot_rit = 0, 0, 0
    
    for lg, s in report_campionati.items():
        if s['p'] > 0:
            roi = ((s['rit'] - s['inv']) / s['inv']) * 100
            win = (s['v'] / s['p']) * 100
            print(f"{lg:<15} | {s['p']:<5} | {win:>6.1f}% | {roi:>6.1f}%")
            tot_p += s['p']
            tot_inv += s['inv']
            tot_rit += s['rit']

    print("\n" + "═"*60)
    print(f"{'MERCATO':<15} | {'BETS':<5} | {'ROI %':<8}")
    print("─"*60)
    for m, s in report_mercati.items():
        if s['p'] > 0:
            roi = ((s['rit'] - s['inv']) / s['inv']) * 100
            print(f"{m:<15} | {s['p']:<5} | {roi:>6.1f}%")

    print("\n" + "═"*60)
    if tot_p > 0:
        final_roi = ((tot_rit - tot_inv) / tot_inv) * 100
        print(f"🏆 RISULTATO FINALE ULTIMATE SETUP (Top 4 + O/U):")
        print(f"Scommesse totali: {tot_p}")
        print(f"Profitto Netto: {round(tot_rit - tot_inv, 2)}€")
        print(f"ROI Totale: {round(final_roi, 2)}%")
    print("═"*60)

if __name__ == "__main__":
    esegui_test()