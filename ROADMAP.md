# ObservationManager - Roadmap Completa

## Panoramica
Sistema completo di controllo telescopio con interfaccia web, allineamento multi-stella, planetario interattivo, e pianificazione osservazioni intelligente.

---

## ✅ Phase 1: Fondamenta (COMPLETATO)

### Milestone 1: Core Infrastructure ✓
- [x] Protocollo LX200 completo (Python)
- [x] Interfaccia seriale con auto-detection
- [x] Mock driver per testing senza hardware
- [x] CLI con subcommands (detect, goto, move, sync, find)
- [x] Web server FastAPI con API REST
- [x] Static file serving per UI HTML/JS

### Milestone 2: Precision Pointing ✓
- [x] Settings API (lat/lon/alt/temp/pressure/tz)
- [x] Skyfield integration per coordinate topocentriche
- [x] Refraction correction
- [x] RA/Dec ↔ Alt/Az conversions
- [x] Robust GOTO con supporto mixed format

### Milestone 3: Catalog Integration ✓
- [x] Gaia catalog C++ wrapper (IOC_GaiaLib)
- [x] SAO/HIP/HD ID resolution
- [x] Local CSV/JSON fallback
- [x] Name search endpoint
- [x] Cone search per zone query

### Milestone 4: Multi-Star Alignment ✓
- [x] Pagina UI align.html con workflow guidato
- [x] Bright star suggestions con filtro Alt/Az
- [x] Gaia cone search per stelle vicine allo zenith
- [x] Camera MJPEG streaming con reticle overlay
- [x] Sync con countdown timer
- [x] Residual angular distance tracking
- [x] Session history con persistenza

### Milestone 5: Interactive Sky Map ✓
- [x] Canvas-based planetario (sky.html)
- [x] Stereographic projection Alt/Az
- [x] Pan/zoom con mouse wheel
- [x] Grid overlay (Alt/Az lines, cardinal directions)
- [x] Click-to-GOTO su stelle
- [x] Star list sidebar con magnitude sorting
- [x] Cursor position tracking in tempo reale

---

## 🔄 Phase 2: Advanced Features (IN CORSO)

### Milestone 6: Star-Hopping Planner
**Timeline**: 2-3 settimane  
**Priorità**: Alta

#### Obiettivi
- [ ] Algoritmo di pathfinding tra stelle visibili
- [ ] Cone queries ottimizzate con cache locale
- [ ] Vincoli configurabili (mag, Alt, spacing)
- [ ] Step-by-step guided navigation
- [ ] Re-planning dinamico se stella non visibile

#### Dettagli Tecnici
```python
# API Endpoints
POST /api/plan-hop
{
  "target_ra": 10.5,
  "target_dec": 45.2,
  "max_steps": 5,
  "max_mag": 4.0,
  "min_alt": 20.0,
  "max_spacing": 10.0  # degrees
}
→ returns: { steps: [{name, ra, dec, mag, alt, az}, ...] }

GET /api/next-hop?session_id=...
→ returns: next step in sequence

POST /api/hop-confirm
{ "step_id": 3 }
→ marks step complete, advances to next
```

#### UI Components
- `web/hop.html`: step list, progress bar, GOTO buttons
- Real-time step status indicators
- Skip/back navigation
- Automatic re-plan button

### Milestone 7: Session Management & Persistence
**Timeline**: 1-2 settimane  
**Priorità**: Media

- [ ] Session storage in SQLite o JSON
- [ ] Observation log con timestamps
- [ ] Export session data (JSON/CSV/FITS)
- [ ] Session restore on server restart
- [ ] Multiple user sessions (optional multi-user)

### Milestone 8: Camera Integration Enhancements
**Timeline**: 2-3 settimane  
**Priorità**: Alta

- [ ] Multiple camera sources (UVC, ASCOM, INDI)
- [ ] Camera controls (exposure, gain, binning)
- [ ] Live stacking con plate solving
- [ ] FITS metadata embedding
- [ ] Image save con auto-naming (target + timestamp)
- [ ] Histogram stretch controls

---

## 🚀 Phase 3: Automation & Sequencing (PIANIFICATO)

### Milestone 9: Observation Sequences
**Timeline**: 3-4 settimane  
**Priorità**: Media-Alta

#### Features
- [ ] Sequence editor UI (CRUD operations)
- [ ] Step types: GOTO, SYNC, IMAGE, WAIT, FILTER
- [ ] Conditional logic (if Alt > X then...)
- [ ] Loop support (repeat N times)
- [ ] Execution engine con pause/resume/abort
- [ ] Progress tracking e ETA calculation

#### Example Sequence
```json
{
  "name": "M42 RGB Imaging",
  "steps": [
    { "type": "goto", "target": "M42" },
    { "type": "sync", "method": "plate_solve" },
    { "type": "filter", "value": "R" },
    { "type": "image", "count": 10, "exposure": 120 },
    { "type": "filter", "value": "G" },
    { "type": "image", "count": 10, "exposure": 120 },
    { "type": "filter", "value": "B" },
    { "type": "image", "count": 10, "exposure": 120 }
  ]
}
```

### Milestone 10: Advanced Imaging
**Timeline**: 4-5 settimane  
**Priorità**: Media

- [ ] Filter wheel support (ASCOM/INDI)
- [ ] Focuser control con autofocus
- [ ] Dithering tra exposures
- [ ] Flat/dark/bias calibration automation
- [ ] Live stacking con alignment
- [ ] Plate solving integration (astrometry.net locale)

### Milestone 11: Meridian Flip & Safety
**Timeline**: 2 settimane  
**Priorità**: Alta

- [ ] Meridian flip detection e automatic flip
- [ ] Horizon/obstacle limits configuration
- [ ] Weatherproofing integration (API per sensori meteo)
- [ ] Emergency stop button prominente
- [ ] Automatic park su chiusura/errore
- [ ] Collision detection (Alt/Az limits)

---

## 🎯 Phase 4: Professional Features (FUTURO)

### Milestone 12: Scripting & API Extensions
**Timeline**: 3-4 settimane  
**Priorità**: Bassa

- [ ] DSL semplice per sequenze (YAML-based)
- [ ] Python scripting support con sandbox
- [ ] WebSocket API per real-time updates
- [ ] GraphQL query layer (optional)
- [ ] Webhook notifications (Telegram, Slack, email)

### Milestone 13: Multi-Mount Support
**Timeline**: 4-5 settimane  
**Priorità**: Bassa

- [ ] Support per più montature simultaneamente
- [ ] ASCOM Alpaca bridge
- [ ] INDI driver support
- [ ] Mount profiles con configurazioni separate

### Milestone 14: Observatory Automation
**Timeline**: 6-8 settimane  
**Priorità**: Bassa

- [ ] Roof/dome control integration
- [ ] Weather station monitoring
- [ ] Automatic shutdown procedures
- [ ] Night scheduler con priorità targets
- [ ] Cloud detection e automatic abort
- [ ] All-sky camera integration

### Milestone 15: Collaborative Features
**Timeline**: 3-4 settimane  
**Priorità**: Bassa

- [ ] Multi-user support con roles
- [ ] Remote observation sharing
- [ ] Real-time collaboration (shared sessions)
- [ ] Observation planning calendar
- [ ] Target suggestions basate su condizioni

---

## 📊 Testing & Quality Assurance

### Continuous Improvements
- [ ] Unit test coverage > 80%
- [ ] Integration tests con mock hardware
- [ ] E2E tests con Playwright/Selenium
- [ ] Performance profiling e optimization
- [ ] Load testing per multi-user scenarios
- [ ] Security audit (input validation, auth)

### Documentation
- [ ] API reference completo (OpenAPI/Swagger)
- [ ] User manual con screenshots
- [ ] Developer guide per contributors
- [ ] Troubleshooting wiki
- [ ] Video tutorials

---

## 🛠️ Technical Debt & Refactoring

### Priorità Alta
- [ ] Type hints completi su tutto Python codebase
- [ ] Error handling standardizzato
- [ ] Logging strutturato (JSON logs)
- [ ] Configuration management centralizzato
- [ ] Database migration strategy

### Priorità Media
- [ ] Frontend migration a framework moderno (Vue/React)
- [ ] State management (Vuex/Redux)
- [ ] Component library (reusable UI elements)
- [ ] API versioning strategy
- [ ] Docker containerization

### Priorità Bassa
- [ ] Microservices architecture (optional)
- [ ] Kubernetes deployment configs
- [ ] CI/CD pipeline completa
- [ ] Monitoring stack (Prometheus, Grafana)

---

## 📅 Timeline Complessivo

| Phase | Duration | Status |
|-------|----------|--------|
| Phase 1 | 8-10 settimane | ✅ Completato |
| Phase 2 | 6-8 settimane | 🔄 In corso (30%) |
| Phase 3 | 10-12 settimane | 📋 Pianificato |
| Phase 4 | 15-20 settimane | 💡 Futuro |

**Tempo totale stimato**: 10-12 mesi per implementazione completa professionale

---

## 🎓 Learning Resources

### Per utenti
- [Guida rapida al primo utilizzo](docs/quickstart.md) (da creare)
- [Video tutorial allineamento](docs/videos/alignment.md) (da creare)
- [FAQ comune problemi](docs/faq.md) (da creare)

### Per developers
- [Architecture overview](ARCHITECTURE.md) (da creare)
- [Contributing guide](CONTRIBUTING.md) ✓ Disponibile
- [API documentation](docs/api.md) (da creare)
- [Testing strategy](docs/testing.md) (da creare)

---

## 📞 Community & Support

- **Issues**: GitHub Issues per bug reports
- **Discussions**: GitHub Discussions per feature requests
- **Pull Requests**: Contributions benvenuti!
- **Documentation**: Wiki in continuo aggiornamento

---

## 🏆 Success Metrics

### Phase 1 (Completato)
- ✅ Sistema funzionante end-to-end
- ✅ Mock driver per testing
- ✅ Web UI completa e responsive
- ✅ Documentazione base presente

### Phase 2 (Target)
- [ ] Star-hopping utilizzabile in sessione reale
- [ ] < 200ms response time per cone queries
- [ ] Session persistence affidabile
- [ ] Camera integration stabile

### Phase 3 (Target)
- [ ] Sequences eseguibili senza intervento
- [ ] Meridian flip automatico
- [ ] Zero data loss su crash
- [ ] Professional-grade imaging workflow

### Phase 4 (Target)
- [ ] Multi-mount support testato
- [ ] Observatory automation completa
- [ ] 10+ installazioni attive
- [ ] Community contributions attive

---

**Ultimo aggiornamento**: Gennaio 2026  
**Versione corrente**: 0.3.0 (Phase 2 in corso)  
**Prossima milestone**: Star-Hopping Planner (M6)
