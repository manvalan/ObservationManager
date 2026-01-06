# 📊 Analytics Dashboard Guide

## Panoramica

L'**Analytics Dashboard** fornisce una visualizzazione completa dei dati osservazionali raccolti, permettendo di:

- 📈 Monitorare qualità allineamenti nel tempo
- 📋 Analizzare statistiche osservazioni
- 🎯 Tracciare efficienza sessioni
- 🔍 Identificare trend osservazionali

**Accesso**: http://127.0.0.1:8000/ui/analytics.html

---

## 🚀 Avvio Rapido

### 1. Apri Dashboard

Naviga a `analytics.html` dalla pagina principale. La dashboard carica automaticamente tutte le sessioni registrate.

### 2. Seleziona Sessione (Opzionale)

Dal dropdown **Session**, scegli una sessione specifica per visualizzare dettagli:

```
📋 Session: Jupiter (6 genn 2026)
             ↓
             Mostra statistiche per quella sessione
```

### 3. Interpreta i Grafici

La dashboard mostra 4 grafici principali:

| Grafico | Cosa Mostra | Asse X | Asse Y |
|---------|-----------|--------|--------|
| **Session Timeline** | Osservazioni per giorno (ultimi 30gg) | Data | N° Osservazioni |
| **Alignment Quality** | Residui di allineamento per sessione | N° Sessione | Residuo (arcmin) |
| **Observation Stats** | Conteggio osservazioni per tipo | Tipo Oggetto | Conteggio |
| **Magnitude Distribution** | Distribuzione magnitudini osservate | Magnitudine | Frequenza |

---

## 📊 Componenti Dashboard

### Overview Statistics (Top)

Quattro metriche aggregate:

```
┌─────────────┬──────────────┬────────────────┬─────────────┐
│ Total       │ Total        │ Avg Residual   │ Integr.     │
│ Sessions    │ Observations │ (arcsec)       │ Time        │
├─────────────┼──────────────┼────────────────┼─────────────┤
│      12     │      156     │      2.1"      │    48.5h    │
└─────────────┴──────────────┴────────────────┴─────────────┘
```

- **Total Sessions**: Numero di sessioni osservative registrate
- **Total Observations**: Numero di oggetti osservati (somma globale)
- **Avg Residual**: Residuo medio di allineamento (target: < 2 arcmin)
- **Integr. Time**: Tempo totale di integrazione (somma durate)

### Session Timeline

**Scopo**: Visualizzare frequenza osservazioni nel tempo

- **X-axis**: Date (ultimi 30 giorni)
- **Y-axis**: Numero osservazioni al giorno
- **Colore**: Gradiente ciano

**Interpretazione**:
- 📈 Picchi = giorni di cielo buono
- 📉 Valli = cattive condizioni o assenza osservazioni
- 🔄 Trend crescente = attività osservativa in aumento

### Alignment Quality (Scatter)

**Scopo**: Tracciare precisione allineamento per sessione

- **X-axis**: N° sessione (tempo)
- **Y-axis**: Residuo allineamento (arcmin)
- **Target**: < 2 arcmin (eccellente), < 5 arcmin (buono)

**Interpretazione**:
- 🎯 Punti bassi = allineamento preciso
- 📍 Trend decrescente = tecniche di allineamento migliorate
- ⚠️ Punti alti = problemi mount/procedure

### Observation Statistics (Bar)

**Scopo**: Distribuzione osservazioni per tipo oggetto

- **X-axis**: Tipo oggetto (NGC, Messier, named)
- **Y-axis**: Conteggio osservazioni

**Interpretazione**:
- 🌟 Bar alta = oggetto frequentemente osservato
- 📊 Bilancia = varietà osservazioni
- 🎯 Concentrazione = focus su target specifico

### Magnitude Distribution (Histogram)

**Scopo**: Range magnitudini osservate

- **X-axis**: Magnitudine (più bassa = più brillante)
- **Y-axis**: Frequenza osservazioni

**Interpretazione**:
- 🔭 Picchi bassi (mag 0-5) = stelle luminose
- 🌙 Picchi alti (mag 8-12) = oggetti deboli
- 📈 Larghezza distribuzione = range magnitudini coperto

---

## 🔍 Session Details

Selezionando una sessione, visualizzi:

```
┌────────────────────────────────────┐
│ Target      │ Jupiter             │
│ RA/Dec      │ 12.45° / -3.23°     │
│ Created     │ 6 genn 2026 22:45   │
│ Alignments  │ 3                   │
│ Observations│ 5                   │
│ Total Time  │ 45 min              │
│ Avg Residual│ 2.1"                │
│ Notes       │ Clear skies, excellent conditions │
└────────────────────────────────────┘
```

### Alignment History

Tabella con tutti gli allineamenti della sessione:

```
┌──────────┬───────────────┬──────────┬──────────────┐
│ Star     │ RA/Dec        │ Residual │ Time         │
├──────────┼───────────────┼──────────┼──────────────┤
│ Vega     │ 279.23°/38.78°│ 2.1"     │ 22:47:15     │
│ Altair   │ 297.70°/8.87° │ 1.8"     │ 22:52:30     │
│ Deneb    │ 310.36°/45.28°│ 2.5"     │ 23:01:45     │
└──────────┴───────────────┴──────────┴──────────────┘
```

Colonna "Residual" mostra: meno è meglio ✓

---

## 🔗 API Endpoints (Backend)

L'analytics dashboard si alimenta da questi endpoint:

### `/api/analytics/summary`

**Descrizione**: Statistiche globali aggregate

**Risposta**:
```json
{
  "ok": true,
  "data": {
    "total_sessions": 12,
    "total_observations": 156,
    "total_alignments": 45,
    "mean_alignment_residual": 2.1,
    "total_observation_time_sec": 174600,
    "unique_objects": 28,
    "objects": ["Jupiter", "Saturn", "M31", ...]
  }
}
```

### `/api/analytics/sessions?limit=100`

**Descrizione**: Lista sessioni con statistiche

**Risposta**:
```json
{
  "ok": true,
  "data": {
    "sessions": [
      {
        "id": "sess_abc123",
        "target_name": "Jupiter",
        "created_at": "2026-01-06T22:45:00",
        "observation_count": 5,
        "alignment_count": 3,
        "alignment_residual_mean": 2.1,
        "total_observation_time_sec": 2700
      }
    ],
    "total": 12
  }
}
```

### `/api/analytics/alignments?session_id=sess_abc123`

**Descrizione**: Statistiche allineamento per sessione

**Parametri**:
- `session_id` (opzionale): Se omesso, ritorna globali

**Risposta**:
```json
{
  "ok": true,
  "data": {
    "alignment_count": 3,
    "mean_residual": 2.1,
    "min_residual": 1.8,
    "max_residual": 2.5,
    "alignments": [...]
  }
}
```

### `/api/analytics/observations?session_id=sess_abc123`

**Descrizione**: Statistiche osservazioni

**Risposta**:
```json
{
  "ok": true,
  "data": {
    "observation_count": 5,
    "total_duration_sec": 2700,
    "mean_duration_sec": 540,
    "objects": {
      "Jupiter": 3,
      "Saturn": 2
    },
    "unique_objects": 2
  }
}
```

### `/api/analytics/timeline?days=30`

**Descrizione**: Timeline osservazioni ultimi N giorni

**Risposta**:
```json
{
  "ok": true,
  "data": {
    "dates": ["2026-01-06", "2026-01-05", ...],
    "counts": [5, 3, 2, ...],
    "days": 30
  }
}
```

### `/api/analytics/magnitude-distribution`

**Descrizione**: Distribuzione magnitudini osservate

**Risposta**:
```json
{
  "ok": true,
  "data": {
    "objects": ["Jupiter", "Saturn", "M31", ...],
    "counts": [5, 3, 2, ...],
    "total": 156
  }
}
```

### `/api/analytics/quality-metrics?session_id=sess_abc123`

**Descrizione**: Metriche di qualità sessione

**Risposta**:
```json
{
  "ok": true,
  "data": {
    "alignment_quality": {
      "count": 3,
      "mean_residual": 2.1,
      "std_residual": 0.3,
      "status": "good"
    },
    "observation_statistics": {
      "count": 5,
      "total_duration_sec": 2700,
      "mean_duration_sec": 540
    }
  }
}
```

---

## 📈 Interpretazione Metriche

### Alignment Residual (Standard: < 2 arcmin)

La *residual* misura l'errore di allineamento post-sync.

| Valore | Qualità | Azione |
|--------|---------|--------|
| < 1.0" | 🟢 Eccellente | Perfetto, nessuna azione |
| 1.0"-2.0" | 🟡 Buono | Accettabile, procedura OK |
| 2.0"-5.0" | 🟠 Medio | Migliorare centratura/sync |
| > 5.0" | 🔴 Scarso | Riallineare completamente |

### Observation Duration (Target: ∝ exposures)

La *duration* dipende da:
- Numero exposures nella sequenza
- Tempo singolo exposure (exposure time)
- Overhead meccanico (read-out time)

Tipici:
- **Jupiter imaging** (bright): 5-10 min
- **Planetary nebula** (faint): 20-60 min
- **Galaxies** (very faint): 60-120+ min

### Session Timeline Insights

Analizza pattern per:

1. **Frequenza osservazione**: Quanto spesso osservi?
   - Giornaliero = 💪 Dedizione alta
   - Settimanale = 🎯 Regolare
   - Sporadico = 📍 Opportunistico

2. **Stagionalità**: Quando osservi di più?
   - Inverno (notti lunghe) vs Estate (notti corte)
   - Picchi lunari (luna nuova)
   - Condizioni meteorologiche locali

3. **Correlazione tempo-qualità**:
   - Sesioni lunghe = residui maggiori (stanchezza, deriva)?
   - Sesioni brevi = residui minori?

---

## 💡 Best Practices

### 1. Monitoraggio Regolare

Controlla dashboard 1-2 volte a settimana:
- ✓ Identificare trend problemi
- ✓ Celebrare buone sessioni
- ✓ Motivazione per osservazioni future

### 2. Analisi Residui

Se residui aumentano:
1. Verifica **collimazione** del telescopio
2. Controlla **tracking** della montatura
3. Centra meglio le stelle prima di SYNC
4. Usa stelle più vicine allo zenit

### 3. Diversità Osservazioni

Mantieni variety nel targets:
- 🌟 Mix di stelle e oggetti deep-sky
- 🎯 Range magnitudini diverse
- 🔍 Alcuni target ripetuti (per comparare)

### 4. Documentazione

Usa **Notes** field della sessione per:
- Condizioni cielo (seeing, trasparenza)
- Equipment used (filter, eyepiece)
- Particularità osservate

---

## 🐛 Troubleshooting

### "No sessions available"

- **Causa**: Nessuna sessione registrata nel database
- **Soluzione**: Esegui almeno una sessione osservativa completa

### Grafici vuoti

- **Causa**: Sessione selezionata senza dati
- **Soluzione**: Seleziona "-- All Sessions --" dal dropdown

### Residui molto alti (> 10")

- **Causa**: Allineamento scarso, drift during night
- **Soluzione**: 
  - Riallinea mount dopo 1-2 ore
  - Centra meglio stelle prima di sync
  - Verifica collimazione

### Timeline piatta

- **Causa**: Poche osservazioni nel periodo
- **Soluzione**: Aumenta range giorni (30, 60, 90)

---

## 🔄 Flusso di Dati

```
┌──────────────────┐
│  Web UI          │
│  (align.html)    │
└────────┬─────────┘
         │ log-alignment
         ↓
┌──────────────────┐
│  SessionManager  │
│  (SQLite)        │
└────────┬─────────┘
         │ get_session_alignments()
         ↓
┌──────────────────┐
│  Analytics       │
│  Endpoints       │
└────────┬─────────┘
         │ JSON response
         ↓
┌──────────────────┐
│  Dashboard UI    │
│  Charts.js       │
└──────────────────┘
```

---

## 📚 Link Correlati

- [Align Tool Guide](STAR_HOPPING_GUIDE.md) - Come eseguire allineamenti
- [Sequence Automation](SEQUENCE_AUTOMATION_GUIDE.md) - Automazione osservazioni
- [Session Export](SEQUENCE_AUTOMATION_GUIDE.md#session-export) - Esportare dati JSON

---

## 🎓 Esempi Reali

### Scenario 1: Monitorare Qualità Allineamento

```
Sessione 1: Jupiter - Residuo 2.1"
  └─ Primo allineamento serata, OK

Sessione 2: M31 (dopo 2h) - Residuo 4.5"
  └─ Mount driftato, performance degradata

Azione: Riallineare mount ogni 2 ore per:
  - Mantenere residuo < 2"
  - Assicurare tracking stabile
```

### Scenario 2: Analizzare Pattern Osservazioni

```
Timeline ultimi 30 giorni:
  - Picchi: Fine settimana (sabato sera)
  - Valli: Giorni lavorativi
  
Conclusione: Osservazioni hobby, non professional
Insight: Pianificare sequenze per fine settimana
```

### Scenario 3: Tracking Efficienza Sequenze

```
Sequenza Jupiter imaging (100 frames):
  - Durata: 15 minuti
  - Allineamenti pre: 3 (residuo 2.0")
  - Allineamenti mid: 1 (after 2h, residuo 3.5")
  
Miglioramento:
  - Aggiungere sync-check ogni 5 frame
  - Ridurre exposure time (drift minore)
```

---

## 🚀 Prossimi Passi

Phase 3 enhancements:
- [ ] Export CSV per analisi external (Excel)
- [ ] PDF report con charts e summary
- [ ] Trend prediction (ML) per quality forecast
- [ ] Object catalog con storia osservazioni
- [ ] Comparison multi-sessioni

---

**Milestone 9 Status**: ✅ COMPLETATO

- ✓ Analytics Dashboard UI (web/analytics.html)
- ✓ Backend endpoints (/api/analytics/*)
- ✓ Charts.js integration (4 chart types)
- ✓ Session statistics aggregation
- ✓ Quality metrics calculation
- ✓ Test suite (test_analytics.py - 6/6 passing)

**Next**: Milestone 8 (Advanced Imaging) - Filter Wheel + Live Stacking
