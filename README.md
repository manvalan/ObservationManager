# ObservationManager – Controllo Telescopio LX200 con Web UI

Sistema completo per controllo montatura Meade LX200 con interfaccia web moderna, allineamento multi-stella, planetario interattivo, e integrazione cataloghi Gaia.

## ✨ Features

- 🎮 **Web UI completa** - Controllo remoto via browser
- 🎯 **Allineamento multi-stella** - Workflow guidato con camera overlay
- 🌌 **Mini Planetario** - Canvas interattivo Alt/Az con pan/zoom
- 📊 **Precisione topocentric** - Skyfield + refrazione atmosferica
- 📚 **Cataloghi Gaia** - 231M stelle + SAO/HIP/HD resolution
- 🎥 **Camera streaming** - MJPEG con reticle overlay
- 🧪 **Mock driver** - Sviluppo senza hardware fisico
- 📱 **Responsive** - Desktop, tablet, mobile

## 🚀 Quick Start

### 1. Installazione

```bash
# Clone repository
git clone https://github.com/manvalan/ObservationManager.git
cd ObservationManager

# Installa dipendenze Python
pip install -r requirements.txt

# (Opzionale) Compila Gaia lookup per cataloghi
cd gaia && mkdir build && cd build
cmake .. && make
cd ../..
```

### 2. Avvio Server

**Con montatura fisica:**
```bash
python -m uvicorn server.app:app --reload --host 127.0.0.1 --port 8000
# Apri http://127.0.0.1:8000/ui/
# Connetti dalla UI usando auto-detected serial port
```

**Senza montatura (Mock Driver):**
```bash
# Stesso comando - il mock driver è integrato
python -m uvicorn server.app:app --reload --host 127.0.0.1 --port 8000
# Dalla UI clicca "Connect" e seleziona "Mock" come porta
```

### 3. Primi Passi

1. **Settings** (`/ui/control.html`): Configura lat/lon/alt osservatorio
2. **Alignment** (`/ui/align.html`): Allinea su 1-3 stelle luminose
3. **Sky Map** (`/ui/sky.html`): Naviga cielo e GOTO stelle
4. **Camera** (`/ui/camera.html`): Verifica centratura target

## 🧪 Mock Driver per Testing

Il progetto include `MockConnection` che simula realisticamente una montatura LX200:

**Features del Mock:**
- Simulazione posizione RA/Dec con tracking
- Risposte realistiche a tutti i comandi LX200
- Slewing delays e stato allineamento
- History comandi per debugging

**Utilizzo in Python:**
```python
from lx200.connection import MockConnection
from lx200.protocol import LX200

# Usa mock invece di SerialConnection
conn = MockConnection()
lx = LX200(conn)

# Tutti i comandi funzionano normalmente
lx.slew_to("12:00:00", "+45*30:00")
print(lx.get_ra())  # "12:00:00"

# Vedi history comandi inviati
print(conn.history)
```

**Utilizzo via Web UI:**
- Avvia server normalmente
- In `/ui/control.html` clicca "Connect"
- Porta: lascia vuoto o scrivi "mock"
- Il sistema userà automaticamente MockConnection

## 📋 CLI Usage (legacy)

Il progetto mantiene CLI per quick testing:

```bash
# Mostra versione firmware (o mock)
python -m lx200.cli version

# Status RA/Dec
python -m lx200.cli status

# GOTO coordinata
python -m lx200.cli goto --ra 10:30:00 --dec +45:30:00

# Cerca oggetto
python -m lx200.cli find --name "HD 48915" --names-file ~/.catalog/crossreference/names.csv
```

Goto per nome (risolve nome → RA/Dec → :MS):
```bash
python -m lx200.cli goto-name --name Vega
```

Goto a coordinate (accetta diversi formati):
```bash
# RA/Dec come stringhe
python -m lx200.cli goto --ra "10:12:30" --dec "+20*30:00"

# Oppure in gradi
python -m lx200.cli goto --ra-deg 153.125 --dec-deg -12.5
```

Movimento manuale (N/S/E/W) a velocità:
```bash
# Avvio movimento a velocità massima (slew) verso Est per 2.5 s
python -m lx200.cli move --dir E --rate slew --seconds 2.5

# Avvio continuo (ferma con stop)
python -m lx200.cli move --dir N --rate center
```

Stop dei motori:
```bash
# Ferma tutto
python -m lx200.cli stop
# Ferma solo una direzione
python -m lx200.cli stop --dir E
```

Sync su coordinate note (tipicamente puntando una stella nota):
```bash
python -m lx200.cli sync --ra "05:35:17" --dec "-05*23:28"
```

## Opzioni globali

- `--port` dispositivo seriale (se omesso, tenta auto-detect)
- `--baud` baud rate, default 9600
- `--timeout` timeout lettura, default 2.0 s
- `--dry-run` non invia comandi reali; utile per provare la CLI

Esempio dry-run:
```bash
python -m lx200.cli --dry-run status
```

## Note protocollo LX200

- I comandi terminano con `#` e le risposte sono terminanti `#`.
- RA è in formato `HH:MM:SS` (ore 0–23), Dec è `+DD*MM:SS` con `*` come separatore gradi/minuti.
- GOTO: `:SrHH:MM:SS#`, `:Sd+DD*MM:SS#`, poi `:MS#`.
- Movimenti manuali: rate `:RG#` (guide), `:RC#` (center), `:RM#` (find), `:RS#` (slew); direzioni `:Mn#/:Ms#/:Me#/:Mw#`; stop `:Q#` o `:Qn#/:Qs#/:Qe#/:Qw#`.

## Avvertenze

- Verifica sempre che l'area sia sgombra durante i movimenti.
- Alcune varianti LX200/Autostar possono differire leggermente nei comandi e risposte.

## Integrazione Gaia (IOC_GaiaLib)

Per prestazioni e copertura massime, puoi usare IOC_GaiaLib (C++). Costruiamo un piccolo wrapper `gaia_lookup` incluso in questa repo.

1) Installa IOC_GaiaLib (seguirne le istruzioni):
```bash
git clone https://github.com/manvalan/IOC_GaiaLib.git
cd IOC_GaiaLib && mkdir build && cd build
cmake .. -DCMAKE_BUILD_TYPE=Release
make -j8
sudo make install
```

2) Prepara il catalogo locale (es: `~/.catalog/gaia_mag18_v2_multifile` come da README IOC_GaiaLib).

3) Costruisci `gaia_lookup` di questa repo:
```bash
cd gaia
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build -j8
# opzionale: install
sudo cmake --install build
```

4) Test veloce:
```bash
./gaia/build/gaia_lookup --name Vega
```

Se il binario è nel `PATH`, la CLI userà automaticamente Gaia per `find`/`goto-name`, altrimenti userà i file CSV/JSON in `~/.catalog/crossreference`.

## Prossimi passi

- Integrazione diretta con IOC_GaiaLib (C++) via wrapper/CLI opzionale.
- Aggiungere server HTTP locale (REST) per integrazione con altri strumenti.
- Supporto impostazione data/orario/sito.
- Migliorare auto-rilevamento porta con filtri Vendor/Product.

## Interfaccia Web (HTML)

Avvia il server FastAPI e apri le pagine HTML locali:

```bash
# attiva venv e installa deps (vedi sopra)
uvicorn server.app:app --reload
```

Apri il browser su:
- http://127.0.0.1:8000/ui/ → Home
- http://127.0.0.1:8000/ui/control.html → Connessione, stato, GOTO, sync
- http://127.0.0.1:8000/ui/move.html → Movimenti manuali
- http://127.0.0.1:8000/ui/catalog.html → Ricerca per nome (Gaia/CSV) e GOTO
- http://127.0.0.1:8000/ui/camera.html → Streaming MJPEG (se OpenCV/camera disponibili)
- http://127.0.0.1:8000/ui/align.html → Allineamento 1-3 stelle (GOTO + :CM sync)

Allineamento:
- Suggerimenti stelle sopra l’orizzonte (Gaia se disponibile, altrimenti lista bright) con alt/az calcolati via Skyfield.
- Flusso: GOTO → centratura (reticolo su camera MJPEG) → Sync `:CM`; lo storico mostra il residuo angolare in arcsec se letto dal mount.
- Countdown opzionale per il Sync.

Note:
- Se `gaia_lookup` è nel PATH, la ricerca nomi usa Gaia; altrimenti, CSV/JSON in `~/.catalog/crossreference`.
- Il server mantiene una singola connessione alla montatura; usa il riquadro Connessione per avviare/chiudere.
- La camera richiede `opencv-python` e un dispositivo video compatibile.

## Impostazioni sito e calcoli di puntamento

- Impostazioni: `GET/POST /api/settings` con lat/lon/alt/pressione/temperatura/tz (persistenza `server/data/settings.json`).
- Conversioni topocentriche + refrazione: `POST /api/altaz` (da ra/dec in gradi) e `POST /api/apparent` (da alt/az in gradi).
- GOTO accetta RA/Dec o Alt/Az: `POST /api/goto` con ra/dec (stringhe o gradi) oppure alt_deg/az_deg.
- Risoluzione ID: `GET /api/resolve?sao=...|hip=...|hd=...|name=...` → RA/Dec via Gaia o fallback.

---

## 📚 Documentation

- **[PLAN.md](PLAN.md)** - Milestones tattiche e stato progetto
- **[ROADMAP.md](ROADMAP.md)** - Piano completo 4 phases (10-12 mesi)
- **[CONTRIBUTING.md](CONTRIBUTING.md)** - Guide per contributors

### Per Utenti
- Quick start: Questo README
- Web UI: Naviga da `/ui/` homepage
- Troubleshooting: Vedi sezione sotto

### Per Developers
- Mock driver usage: Sezione "🧪 Mock Driver" sopra
- Development workflow: [CONTRIBUTING.md](CONTRIBUTING.md)
- Architecture: Vedi [ROADMAP.md](ROADMAP.md) Phase sections
- API reference: OpenAPI docs a `/docs` (FastAPI auto-generated)

---

## 🤝 Contributing

Contributions benvenute! Vedi [CONTRIBUTING.md](CONTRIBUTING.md) per:
- Setup ambiente di sviluppo
- Coding standards (Python, JS, C++)
- Testing guidelines
- Good first issues
- Feature request process

---

## 🗺️ Roadmap

**Versione corrente**: 0.3.0 (Phase 1 completato)

**Prossima milestone**: Star-Hopping Planner (Milestone 4)

Vedi [ROADMAP.md](ROADMAP.md) per timeline completo con:
- Phase 2: Advanced features (6-8 settimane)
- Phase 3: Automation & sequencing (10-12 settimane)
- Phase 4: Professional features (15-20 settimane)

---

## 📜 License

MIT License - Vedi [LICENSE](LICENSE) file per dettagli

---

## 🙏 Acknowledgments

- **IOC_GaiaLib** - Gaia DR3 catalog access
- **Skyfield** - High-precision astronomy calculations
- **FastAPI** - Modern web framework
- **Meade LX200** - Protocol documentation

---

**Happy Observing!** 🔭✨
