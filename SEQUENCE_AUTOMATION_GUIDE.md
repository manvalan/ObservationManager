# Sequence Automation & Session Management Guide

## 📊 Milestone 5 & 7 Completion

Guida completa per **Sequence Automation** (Milestone 5) e **Session Management** (Milestone 7).

## 🎯 Sequence Automation

### Cos'è una Sequenza?

Una sequenza è una serie di step automatizzati per osservazioni ripetitive:

```
GOTO Jupiter → Take 10 Images → WAIT 5min → SYNC → GOTO Saturn → Take Images
```

### Tipi di Step Supportati

| Step Type | Funzione | Parametri |
|-----------|----------|-----------|
| **GOTO** | Slew verso coordinate | RA (°), Dec (°) |
| **SYNC** | Sincronizza mount | RA (°), Dec (°) |
| **IMAGE** | Cattura immagini | Count, Exposure (s), Binning |
| **WAIT** | Pausa temporale | Duration (s) |
| **FILTER** | Cambia filtro | Position (1-8) |
| **FOCUS** | Auto-focus | Method (auto/manual) |

### Creare una Sequenza

1. **Apri l'editor**: http://127.0.0.1:8000/ui/sequence.html
2. **Clicca "➕ New Sequence"**
3. **Compila i dettagli**:
   - Nome sequenza
   - Descrizione
   - Target (facoltativo)
4. **Aggiungi step**:
   - Seleziona tipo di step
   - Compila parametri
   - Clicca "Add Step"
5. **Salva** con "💾 Save"

### Esempio: Jupiter Imaging

```
Name: Jupiter High-Resolution Imaging
Description: Collect lunar-style images for stacking

Step 1: GOTO
  RA: 12.456°
  Dec: -3.234°

Step 2: WAIT
  Duration: 30s (for atmosphere to settle)

Step 3: IMAGE
  Count: 50
  Exposure: 0.5s
  Binning: 1x1 (Full Resolution)

Step 4: WAIT
  Duration: 120s (cool down CCD)

Step 5: IMAGE
  Count: 50
  Exposure: 1.0s
  Binning: 1x1
```

### Esecuzione Sequenza

1. **Seleziona sequenza** dalla lista
2. **Clicca "▶️ Execute"**
3. **Monitora progresso**:
   - Current Step
   - Progress %
   - Elapsed Time
4. **Controlli**:
   - ⏸️ **Pause**: Sospendi esecuzione
   - ▶️ **Resume**: Riprendi
   - ⏹️ **Abort**: Interrompi

### API Endpoints

**Creare sequenza**:
```bash
curl -X POST http://127.0.0.1:8000/api/sequences \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Test Sequence",
    "description": "Test",
    "target": null
  }'
```

**Aggiungere step**:
```bash
curl -X POST http://127.0.0.1:8000/api/sequences/{seq_id}/steps \
  -H "Content-Type: application/json" \
  -d '{
    "step_type": "goto",
    "params": {
      "ra_deg": 180.5,
      "dec_deg": 45.2
    }
  }'
```

**Eseguire sequenza**:
```bash
curl -X POST http://127.0.0.1:8000/api/sequences/{seq_id}/execute \
  -H "Content-Type: application/json" \
  -d '{"dry_run": false}'
```

**Controllare status**:
```bash
curl -X GET http://127.0.0.1:8000/api/sequences/{seq_id}/status
```

## 📝 Session Management

### Cosa Sono le Sessioni?

Le sessioni registrano **tutte le attività osservative** in una singola serata:

- 🎯 Allineamenti (con residui)
- 🔄 Sync del mount
- 📸 Osservazioni (oggetti, esposizioni)
- 📋 Sequenze eseguite
- 📊 Statistiche aggregate

### Dati Persistenti (SQLite)

I dati sono salvati in `data/sessions.db` con tabelle:

```
sessions          → Metadati sessione
alignments        → Punti di allineamento
syncs             → Sync del mount
observations      → Osservazioni
sequences_log     → Esecuzioni sequenze
```

### Creare una Sessione

```bash
curl -X POST http://127.0.0.1:8000/api/sessions
# Response: {"session_id": "sess_abc123def456"}
```

### Registrare Allineamenti

Durante l'allineamento iniziale:

```bash
curl -X POST http://127.0.0.1:8000/api/sessions/{session_id}/log-alignment \
  -H "Content-Type: application/json" \
  -d '{
    "star_name": "Vega",
    "ra_deg": 279.234,
    "dec_deg": 38.783,
    "alt_deg": 65.2,
    "az_deg": 180.5,
    "residual_arcmin": 2.3
  }'
```

### Registrare Sync

Ogni volta che sincronizzi il mount:

```bash
curl -X POST http://127.0.0.1:8000/api/sessions/{session_id}/log-sync \
  -H "Content-Type: application/json" \
  -d '{
    "ra_deg": 180.5,
    "dec_deg": 45.2,
    "pointing_ra": 180.6,
    "pointing_dec": 45.3,
    "alignment_quality": 0.95
  }'
```

### Registrare Osservazioni

Dopo ogni osservazione:

```bash
curl -X POST http://127.0.0.1:8000/api/sessions/{session_id}/log-observation \
  -H "Content-Type: application/json" \
  -d '{
    "object_name": "Jupiter",
    "ra_deg": 12.456,
    "dec_deg": -3.234,
    "obs_type": "imaging",
    "duration_sec": 300,
    "exposure_sec": 0.5,
    "gain": 100,
    "binning": "1x1",
    "notes": "Excellent seeing, 50 frames captured"
  }'
```

### Ottenere Dati Sessione

**Riepilogo**:
```bash
curl -X GET http://127.0.0.1:8000/api/sessions/{session_id}
# Response: session metadata + summary statistics
```

**Allineamenti**:
```bash
curl -X GET http://127.0.0.1:8000/api/sessions/{session_id}/alignments
```

**Sync**:
```bash
curl -X GET http://127.0.0.1:8000/api/sessions/{session_id}/syncs
```

**Osservazioni**:
```bash
curl -X GET http://127.0.0.1:8000/api/sessions/{session_id}/observations
```

### Esportare Sessione

Esportazione JSON completa:

```bash
curl -X GET http://127.0.0.1:8000/api/sessions/{session_id}/export > session_export.json
```

Formato JSON:

```json
{
  "session": {
    "id": "sess_abc123",
    "created_at": 1704550800.0,
    "target_name": "Jupiter",
    "target_ra": 12.456,
    "target_dec": -3.234
  },
  "alignments": [
    {
      "star_name": "Vega",
      "residual_arcmin": 2.3,
      "timestamp": 1704550810.0
    }
  ],
  "observations": [
    {
      "object_name": "Jupiter",
      "duration_sec": 300,
      "exposure_sec": 0.5,
      "frames_captured": 50
    }
  ],
  "summary": {
    "total_alignments": 3,
    "total_observations": 2,
    "observation_duration": 600,
    "alignment_residual_mean": 1.8
  }
}
```

## 🔗 Integrazione Completa

### Flusso di Lavoro Tipico

```
1. START SESSION
   POST /api/sessions → session_id

2. SET TARGET
   POST /api/sessions/{id}/set-target
   {"name": "M31", "ra_deg": 10.6847, "dec_deg": 41.2688}

3. ALIGNMENT
   POST /api/sessions/{id}/log-alignment (multiple times)
   
4. CREATE SEQUENCE
   POST /api/sequences
   
5. ADD STEPS
   POST /api/sequences/{id}/steps (multiple)
   
6. EXECUTE SEQUENCE
   POST /api/sequences/{id}/execute
   
7. LOG OBSERVATIONS
   POST /api/sessions/{id}/log-observation (as needed)
   
8. EXPORT SESSION
   GET /api/sessions/{id}/export → JSON file
```

### Esempio Completo (Python)

```python
import requests
import json

API = "http://127.0.0.1:8000/api"

# 1. Crea sessione
resp = requests.post(f"{API}/sessions")
session_id = resp.json()["session_id"]
print(f"Session: {session_id}")

# 2. Imposta target
requests.post(f"{API}/sessions/{session_id}/set-target", json={
    "name": "M31",
    "ra_deg": 10.6847,
    "dec_deg": 41.2688
})

# 3. Crea sequenza
resp = requests.post(f"{API}/sequences", json={
    "name": "M31 Imaging",
    "target": "M31"
})
seq_id = resp.json()["sequence"]["id"]

# 4. Aggiungi step GOTO
requests.post(f"{API}/sequences/{seq_id}/steps", json={
    "step_type": "goto",
    "params": {"ra_deg": 10.6847, "dec_deg": 41.2688}
})

# 5. Aggiungi step IMAGE
requests.post(f"{API}/sequences/{seq_id}/steps", json={
    "step_type": "image",
    "params": {
        "count": 10,
        "exposure": 2.0,
        "binning": "1x1"
    }
})

# 6. Esegui sequenza
requests.post(f"{API}/sequences/{seq_id}/execute")

# 7. Registra osservazione
requests.post(f"{API}/sessions/{session_id}/log-observation", json={
    "object_name": "M31",
    "ra_deg": 10.6847,
    "dec_deg": 41.2688,
    "obs_type": "imaging",
    "duration_sec": 20,
    "exposure_sec": 2.0,
    "gain": 100,
    "notes": "Clear night, excellent seeing"
})

# 8. Esporta
resp = requests.get(f"{API}/sessions/{session_id}/export")
export_data = resp.json()["data"]
with open("session_export.json", "w") as f:
    json.dump(export_data, f, indent=2)
```

## 📊 Statistiche e Analytics

### Riepilogo Sessione

Ogni sessione fornisce:

```json
{
  "total_alignments": 3,
  "alignment_residual_mean": 1.8,  // arcmin
  "total_syncs": 5,
  "total_observations": 2,
  "observation_duration_sec": 600,
  "objects_observed": ["Jupiter", "Saturn"]
}
```

### Analisi Tipica

```python
# Calcolare qualità allineamento medio
summary = requests.get(f"{API}/sessions/{id}").json()["summary"]
mean_residual = summary["alignment_residual_mean"]
print(f"Alignment Quality: {mean_residual:.1f} arcmin")

# Elencare tutti gli oggetti osservati
objects = summary["objects_observed"]
print(f"Observed: {', '.join(objects)}")

# Tempo totale di osservazione
duration_hours = summary["observation_duration_sec"] / 3600
print(f"Observing Time: {duration_hours:.1f} hours")
```

## 🧪 Test

### Test Sequenze

```bash
python test_sequences.py
```

Output atteso:
```
✅ Create sequence
✅ Add steps
✅ Execute sequence
✅ Monitor progress
✅ All tests passed
```

### Test Sessioni

```bash
python test_sessions.py
```

Output:
```
✅ Create session
✅ Log alignment
✅ Log observations
✅ Export JSON
✅ Verify database
✅ All tests passed
```

## 🐛 Troubleshooting

### Sequenza non si esegue

- **Causa**: Nessun mount connesso
- **Soluzione**: Connetti mount o usa MockConnection (`--mock` flag)

### Database corrotto

- **Causa**: Accesso simultaneo o crash
- **Soluzione**: Elimina `data/sessions.db` e ricrea

### JSON export vuoto

- **Causa**: Nessun dato registrato
- **Soluzione**: Log allineamenti/osservazioni prima di esportare

## 📚 File Moduli

- **`server/sequence.py`**: Sequenze e execution engine
- **`server/session_manager.py`**: Persistenza SQLite
- **`web/sequence.html`**: UI editor moderno
- **`server/app.py`**: API endpoints REST

## 🎓 Prossimi Passi

- [ ] UI dashboard sessioni con grafici
- [ ] Stacking automatico dopo imaging
- [ ] Export FITS con WCS
- [ ] Mobile app per remote operations

---

**Milestones 5 & 7 Complete** ✓  
*Next: Phase 2 Feature Expansion*
