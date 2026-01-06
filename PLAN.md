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

## Milestone 5 – Automation & Sequencing ✓ COMPLETATO
- [x] Sequence editor: CRUD su sequenze (name, steps con parametri)
- [x] Execution engine: esegui step-by-step con pause/resume/abort
- [x] 6 step types: GOTO, SYNC, IMAGE, WAIT, FILTER, FOCUS
- [x] Modern UI con sidebar, form builder, real-time monitoring
- [x] Full API endpoints per gestione sequenze
- [x] Test suite completo (test_automation.py)

## Milestone 6 – Camera Control ✓ COMPLETATO
- [x] CameraController class: gestione multi-device, settings (exposure/gain/binning)
- [x] API complete: /api/camera/devices, open, settings, capture, statistics, fwhm, save-fits
- [x] UI camera.html: device selection, controls, live preview, histogram, FWHM
- [x] FITS export con metadata completo (target, coords, site, exposure)
- [x] Statistiche avanzate: histogram, SNR, FWHM per focus assist

## Milestone 7 – Logging, test, docs ✓ COMPLETATO
- [x] Virtual mount driver (MockConnection) con simulazione realistica
- [x] Test suite: test_mock.py, test_hop.py, test_camera.py, test_automation.py
- [x] Persistenza sessione completa (allineamenti, sync, target) con SQLite
- [x] JSON export per analisi offline e archivio
- [x] Unit test conversioni, mock LX200, smoke REST completo
- [x] Documentazione completa: Guide per tutti i moduli + troubleshooting
- [x] Contributing guide con development workflow
- [x] Roadmap completa per Phase 2-4

## Milestone 8 – Advanced Imaging ✓ COMPLETATO
- [x] Filter wheel support (seriale/USB)
- [x] Live stacking con alignment automatico
- [x] Calibration automation (dark, flat, bias)
- [x] FITS metadata + WCS projection

## Milestone 9 – Analytics Dashboard ✓ COMPLETATO
- [x] Analytics Dashboard UI (web/analytics.html con Charts.js)
- [x] Session timeline (osservazioni per giorno)
- [x] Alignment quality scatter plot (residui nel tempo)
- [x] Observation statistics (conteggio per oggetto)
- [x] Magnitude distribution histogram
- [x] Quality metrics aggregation
- [x] Backend endpoints (/api/analytics/*)
- [x] Session details e alignment history tables
- [x] Test suite (test_analytics.py - 6/6 passing)
- [x] Documentazione (ANALYTICS_GUIDE.md)

## Milestone 10 – Mobile App
- [ ] CORS + WebSocket per real-time updates
- [ ] React Native setup
- [ ] Mobile device control UI
- [ ] Live preview su dispositivi mobili

---

## 🎯 Stato Attuale
- **✓ Star Hopping**: UI moderna, algoritmo efficiente, GOTO→SYNC→NEXT workflow
- **✓ Camera Control**: multi-device, FITS export, live preview, statistics
- **✓ Watec 910BD**: TACOS control, video recording, image sequences
- **✓ Sequence Automation**: Editor, 6 step types, execution monitoring
- **✓ Session Management**: SQLite persistence, alignments, syncs, observations

### 🎓 Phase 2 Complete!
Tutte le funzionalità principali implementate e testate. Pronto per:
- Osservazioni reali con mount LX200
- Automazione sequenze complesse
- Archiviazione dati persistente

### 📋 Prossimi Passi (Phase 3)
1. **Advanced Imaging**: Filter wheel, live stacking, calibration
2. **Mobile App**: Remote operations

---

## 📚 Documentazione Disponibile

- **[README.md](README.md)**: Setup e utilizzo base
- **[ROADMAP.md](ROADMAP.md)**: Piano completo 4 phases (10-12 mesi)
- **[CONTRIBUTING.md](CONTRIBUTING.md)**: Guide per contributors
- **[PLAN.md](PLAN.md)**: Questo file - milestones tattiche
- **[STAR_HOPPING_GUIDE.md](STAR_HOPPING_GUIDE.md)**: Star hopping navigator (M4)
- **[SEQUENCE_AUTOMATION_GUIDE.md](SEQUENCE_AUTOMATION_GUIDE.md)**: Sequence editor & execution (M5)
- **[ANALYTICS_GUIDE.md](ANALYTICS_GUIDE.md)**: Analytics dashboard (M9)

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

**Prossima milestone**: Advanced Imaging (Milestone 8)  
**Versione corrente**: 0.5.0 (Phase 3 - 50% - Analytics Dashboard ✓)  
**Ultimo aggiornamento**: Gennaio 2026

Vedi [ROADMAP.md](ROADMAP.md) per roadmap completa con timeline e dettagli architetturali.
Vedi [CONTRIBUTING.md](CONTRIBUTING.md) per linee guida di sviluppo e workflow.
