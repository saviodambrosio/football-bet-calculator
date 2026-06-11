import pandas as pd
from datetime import datetime, timedelta
import time
import os

# ==========================================
# 🚀 ESTRATTORE ELO MASSIVO
# ==========================================
GIORNI_DA_SCARICARE = 400  # Copriamo abbondantemente l'ultimo anno e mezzo
FILE_DESTINAZIONE = "database_elo_storico.csv"

def scarica_tutto_elo():
    data_fine = datetime.now()
    data_inizio = data_fine - timedelta(days=GIORNI_DA_SCARICARE)
    
    lista_df = []
    
    current_date = data_inizio
    print(f"⏳ Inizio estrazione massiva per {GIORNI_DA_SCARICARE} giorni...")

    while current_date <= data_fine:
        date_str = current_date.strftime('%Y-%m-%d')
        url = f"http://api.clubelo.com/{date_str}"
        
        try:
            print(f"📥 Scaricamento ELO del: {date_str}...")
            df = pd.read_csv(url)
            # Teniamo solo le colonne fondamentali per risparmiare spazio
            df = df[['Club', 'Elo']]
            df['Data'] = date_str
            lista_df.append(df)
            
            # Piccolo delay per non farsi bannare dal server (fondamentale!)
            time.sleep(0.5) 
            
        except Exception as e:
            print(f"❌ Errore per la data {date_str}: {e}")
        
        current_date += timedelta(days=1)

    if lista_df:
        full_df = pd.concat(lista_df)
        full_df.to_csv(FILE_DESTINAZIONE, index=False)
        print(f"\n✅ DATABASE COMPLETATO! Salvato come: {FILE_DESTINAZIONE}")
        print(f"Dimensione totale: {len(full_df)} righe.")
    else:
        print("❌ Nessun dato scaricato.")

if __name__ == "__main__":
    scarica_tutto_elo()