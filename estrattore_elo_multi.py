import pandas as pd
import requests
import time
from datetime import timedelta
import os
from io import StringIO

STAGIONI = ["2223","2324", "2425"]
CAMPIONATI = ['E0', 'I1', 'SP1', 'F1']
FILE_ELO = "data/database_elo_storico.csv"

def scarica_date_necessarie():
    print("📅 Estrazione date dei match dai calendari...")
    date_necessarie = set()
    for st in STAGIONI:
        for lg in CAMPIONATI:
            url = f"https://www.football-data.co.uk/mmz4281/{st}/{lg}.csv"
            try:
                df = pd.read_csv(url)
                df['DateObj'] = pd.to_datetime(df['Date'], dayfirst=True)
                for d in df['DateObj'].dropna():
                    # Giorno prima del match
                    data_elo = (d - timedelta(days=1)).strftime('%Y-%m-%d')
                    date_necessarie.add(data_elo)
            except:
                pass
    return sorted(list(date_necessarie))

def aggiorna_db_elo():
    date_da_scaricare = scarica_date_necessarie()
    print(f"🎯 Trovate {len(date_da_scaricare)} date necessarie per le 2 stagioni.")

    # Carica DB esistente per non riscaricare tutto
    dati_esistenti = pd.DataFrame()
    date_gia_presenti = set()
    if os.path.exists(FILE_ELO):
        dati_esistenti = pd.read_csv(FILE_ELO)
        if 'Data' in dati_esistenti.columns:
            date_gia_presenti = set(dati_esistenti['Data'].unique())
            print(f"📂 DB esistente trovato con {len(date_gia_presenti)} date già salvate.")

    date_mancanti = [d for d in date_da_scaricare if d not in date_gia_presenti]
    print(f"⏳ Da scaricare: {len(date_mancanti)} date...")

    nuovi_dati = []
    for i, data in enumerate(date_mancanti):
        print(f"  > Download ELO per {data} ({i+1}/{len(date_mancanti)})...", end="\r")
        url = f"http://api.clubelo.com/{data}"
        try:
            resp = requests.get(url, timeout=10)
            if resp.status_code == 200 and "Club" in resp.text:
                df_elo = pd.read_csv(StringIO(resp.text))
                df_elo['Data'] = data
                nuovi_dati.append(df_elo[['Data', 'Club', 'Elo']])
            time.sleep(0.5) # Pausa per non farci bloccare l'IP
        except:
            time.sleep(2)
    
    if nuovi_dati:
        df_nuovi = pd.concat(nuovi_dati, ignore_index=True)
        df_finale = pd.concat([dati_esistenti, df_nuovi], ignore_index=True)
        df_finale.to_csv(FILE_ELO, index=False)
        print(f"\n✅ Aggiornamento completato! Salvate {len(nuovi_dati)} nuove date in {FILE_ELO}.")
    else:
        print("\n✅ Il database ELO era già completo e aggiornato.")

if __name__ == "__main__":
    aggiorna_db_elo()