import requests

# Test rapido per verificare che la chiave API funzioni
# Imposta THE_ODDS_API_KEY nell'ambiente o in .env prima di eseguire
API_KEY = 'your_api_key_here'
url = f'https://api.the-odds-api.com/v4/sports/soccer_italy_serie_a/odds/?apiKey={API_KEY}&regions=eu&markets=h2h'

r = requests.get(url)
print(f"Status: {r.status_code}")
if r.status_code == 200:
    print("Successo! La chiave funziona in Python.")
else:
    print(f"Errore: {r.text}")
