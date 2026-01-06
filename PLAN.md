# Piano di lavoro

## Milestone 1 – Precisione e risoluzione target ✓ COMPLETATO
- [x] API sito/meteo: /api/settings (lat, lon, alt, pressione, temperatura, tz) con persistenza JSON e validazioni.
- [x] Conversioni precise: RA/Dec ↔ Alt/Az topocentrico con Skyfield + refrazione; API /api/altaz e /api/apparent.
- [x] GOTO robusto: /api/goto-coords (RA/Dec o Alt/Az, epoch di data) con messaggi di errore chiari.
- [x] Risoluzione ID: estendere gaia_lookup a --sao/--hip/--hd e servire /api/resolve (fallback CSV/JSON se Gaia non disponibile).

## Milestone 2 – Allineamento guidato ✓ COMPLETATO
- [x] Pagina ui/align.html: proposta stelle luminose sopra l'orizzonte, GOTO → centratura (joystick/camera) → :CM (sync) su 1–3 stelle.
- [x] Stato qualità allineamento e log sessione; reset allineamento.
- [x] Safety: stop rapidi, limiti Alt/Az.
- [x] Gaia cone search near zenith per suggerimenti intelligenti
- [x] Residual angular distance tracking post-sync
- [x] Camera reticle overlay con cross + circle
- [x] Countdown timer per sync manuale

## Milestone 3 – Mini planetario ✓ COMPLETATO
- [x] Pagina ui/sky.html: canvas Alt/Az con pan/zoom, query "cone" Gaia filtrata per magnitudine, overlay griglie/orizzonte/target.
- [x] Click su stella → info → GOTO; stereographic projection.
- [x] Star list sidebar with magnitude sorting
- [x] Grid overlay (Alt/Az, cardinal directions, horizon)
- [x] Interactive pan/zoom + cursor position tracking
- [x] Fallback a bright stars list se Gaia unavailable

## Milestone 4 – Star hopping ✓ COMPLETATO
- [x] Planner /api/plan-hop e /api/next-hop: corridoi Gaia con vincoli magnitudine/distanza/altezza; tempo di risposta < 200 ms con catalogo locale.
- [x] Pagina ui/hop.html: lista passi, GOTO/Confermato→:CM→prossimo, re-plan e skip passo.
- [x] Algoritmo greedy arc-length minimization con constraint alt>20° e mag<4
- [x] UI moderna con gradiente, animazioni, progress bar interattiva
- [x] Workflow completo: GOTO → Center → SYNC → NEXT con possibilità di skip
- [x] Test suite completo con MockConnection (test_hop.py)

## Milestone 5 – Automation & Sequencing (NEXT)
- [ ] Sequence editor: CRUD su sequenze (name, steps con parametri)
- [ ] Execution engine: esegui step-by-step con pause/resume/abort
- [ ] Imaging integration: trigger camera, metadata FITS, real-time preview
- [ ] Scripting support (optional): DSL semplice per sequenze avanzate

## Milestone 6 – Camera Control ✓ COMPLETATO
- [x] CameraController class: gestione multi-device, settings (exposure/gain/binning)
- [x] API complete: /api/camera/devices, open, settings, capture, statistics, fwhm, save-fits
- [x] UI camera.html: device selection, controls, live preview, histogram, FWHM
- [x] FITS export con metadata completo (target, coords, site, exposure)
- [x] Statistiche avanzate: histogram, SNR, FWHM per focus assist

## Milestone 7 – Logging, test, docs
- [x] Virtual mount driver (MockConnection) con simulazione realistica
- [x] Test suite: test_mock.py, test_hop.py, test_camera.py
- [ ] Persistenza sessione completa (allineamenti, sync, target), export JSON.
- [ ] Unit test conversioni, mock LX200, smoke REST uvicorn+httpx.
- [ ] Documentazione flussi Align/Planetario/Hop, setup Gaia/camera, troubleshooting.
- [x] Contributing guide con development workflow
- [x] Roadmap completa per Phase 2-4

---

## 🎯 Stato Attuale
- **Star Hopping completo: UI moderna, algoritmo efficiente, workflow guidato GOTO→SYNC→NEXT**
- **Camera control completo: device mgmt, exposure/gain/binning, FITS export, statistics**
- **Watec 910BD: controllo TACOS completo, recording video, sequenze immagini**

### 🔄 In Corso (Phase 2)
- **Milestone 5**: Automation & Sequencing (prossima)
- **Milestone 7**: Session Management & Persistence (test coverage)

### 📋 Prossimi Passi Immediati
1. **Sequence Automation**: Editor e execution engine per sequenze osservative
2. **Session Persistence**: SQLite/JSON per log osservazioni e export dati

### 🔄 In Corso (Phase 2)
- **Milestone 5**: Automation & Sequencing (prossima)
- **Milestone 7**: Session Management & Persistence

### 📋 Prossimi Passi Immediati
1. **Session Persistence**: SQLite/JSON per log osservazioni
2. **Sequence Editor**: CRUD operations per sequenze automatiche
3. **Unit Tests**: Aumentare coverage > 80%

---

## 📚 Documentazione Disponibile

- **[README.md](README.md)**: Setup e utilizzo base
- **[ROADMAP.md](ROADMAP.md)**: Piano completo 4 phases (10-12 mesi)
- **[CONTRIBUTING.md](CONTRIBUTING.md)**: Guide per contributors
- **[PLAN.md](PLAN.md)**: Questo file - milestones tattiche

---

## 🔧 Utilizzo Mock Driver

Per sviluppare senza hardware fisico:

```python
# Nel codice Python
from lx200.connection import MockConnection
from lx200.protocol import LX200

conn = MockConnection()
lx = LX200(conn)

# Tutti i comandi funzionano
lx.slew_to("10:30:00", "+45*00:00")
print(lx.get_ra())  # "10:30:00"

# Vedi comandi inviati
print(conn.history)
```

Nel server web, usa `--dry-run` o imposta `DRY_RUN=true`:
```bash
# Avvia server con mock
python -m uvicorn server.app:app --reload
# Poi connetti con "Mock" dalla UI
```

---

## 🎓 Per Contributors

Vedi **[CONTRIBUTING.md](CONTRIBUTING.md)** per:
- Setup ambiente di sviluppo
- Workflow Git (branches, commits, PR)
- Coding standards (Python, JS, C++)
- Testing guidelines
- Areas needing contributions

Vedi **[ROADMAP.md](ROADMAP.md)** per:
- Timeline completo (Phase 1-4)
- Dettagli tecnici milestones future
- Architecture decisions
- Success metrics

---

**Prossima milestone**: Automation & Sequencing (Milestone 5)  
**Versione corrente**: 0.4.0 (Phase 2 - 40%)  
**Ultimo aggiornamento**: Gennaio 2026

Vedi [ROADMAP.md](ROADMAP.md) per roadmap completa con timeline e dettagli architetturali.
Vedi [CONTRIBUTING.md](CONTRIBUTING.md) per linee guida di sviluppo e workflow.
