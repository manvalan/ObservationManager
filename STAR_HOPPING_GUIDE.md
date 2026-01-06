# 🌟 Star Hopping Guide

## Panoramica

Il sistema di **Star Hopping** ti aiuta a navigare verso oggetti deboli usando stelle brillanti come "indicatori" lungo il percorso. Ogni SYNC migliora la precisione dell'allineamento del telescopio.

## 🚀 Come Funziona

### 1. **Pianificazione del Percorso**

Vai su `http://127.0.0.1:8000/ui/hop.html` e inserisci:

- **Target RA/Dec**: Coordinate dell'oggetto (usa Sky Map per trovarle)
- **Target Name**: Nome dell'oggetto (es. M31, NGC 7293)
- **Max Steps**: Numero massimo di stelle intermedie (default: 5)
- **Max Magnitude**: Luminosità massima stelle guida (default: 4.0)
- **Max Spacing**: Distanza massima tra stelle (default: 10°)

Clicca **🗺️ Plan Route** per calcolare il percorso.

### 2. **Navigazione Passo-Passo**

Il sistema mostra una lista di passi con:

```
Step 1: ⭐ Vega (Mag 0.0)
  RA 279.234° / Dec 38.783°
  📏 8.5° from prev | 🎯 42.3° to target
  
  [🎯 GOTO]
```

#### Workflow Completo:

1. **🎯 GOTO** → Il telescopio punta alla stella
2. **Center** → Centra la stella nell'oculare/camera
3. **🔄 SYNC** → Sincronizza telescopio con coordinate stella
4. **✓ NEXT** → Avanza al prossimo passo

#### Opzioni Alternative:

- **⏭️ Skip** → Salta il passo senza SYNC (se stella nascosta)
- **↺ Reset** → Ricomincia da capo

### 3. **Monitoraggio Progresso**

La UI mostra:

- **Progress Bar**: Barra animata con gradiente
- **Statistiche**:
  - `3/5` → Passi completati/totali
  - `38.5°` → Distanza totale percorsa
  - `60%` → Percentuale completamento

## 🎨 Interfaccia Moderna

### Design Features

- **Gradiente Dinamico**: Background con sfumature blu/verde
- **Animazioni Fluide**: Transizioni smooth su hover e click
- **Progress Bar Animata**: Effetto shimmer luminoso
- **Icone Emoji**: Simboli intuitivi per azioni rapide
- **Effetti 3D**: Bottoni con ombre e movimento

### Step States

1. **Attivo** → Bordo blu, sfondo illuminato
2. **Completato** → Bordo verde, opacità ridotta
3. **In Attesa** → Grigio, pronto per essere attivato

## 🧪 Test con Mock Driver

```bash
# Avvia server con mock
python -m uvicorn server.app:app --reload

# Connetti alla UI
# Seleziona "Mock" come dispositivo
```

Il mock driver simula il movimento del telescopio per testare senza hardware.

## 📊 Algoritmo di Pianificazione

### Strategia Greedy

1. **Ricerca Stelle Candidate**: Cone search Gaia nel corridoio verso target
2. **Filtraggio**: Solo stelle sopra orizzonte (Alt > 20°) e visibili (Mag < 4)
3. **Scoring**: Minimizza distanza al target + considera luminosità
4. **Selezione**: Sceglie stella che massimizza progresso verso target

### Vincoli

- **Altezza minima**: 20° sopra orizzonte
- **Magnitudine massima**: 4.0 (stelle visibili a occhio nudo)
- **Spaziatura**: 2-30° tra stelle
- **Max passi**: 1-10 stelle intermedie

### Performance

- ⚡ **< 200ms**: Tempo di calcolo medio
- 🎯 **Alta precisione**: Usa catalogo Gaia DR3
- 🔄 **Real-time**: Ricalcolo dinamico se necessario

## 💡 Suggerimenti

### Quando Usare Star Hopping

- ✅ Oggetti deboli (< mag 8)
- ✅ Galassie, nebulose planetarie, ammassi aperti
- ✅ Migliorare allineamento telescopio
- ✅ Imparare il cielo stellato

### Quando NON Serve

- ❌ Oggetti brillanti (Giove, Luna, Venere)
- ❌ Telescopio già perfettamente allineato
- ❌ GoTo già preciso (< 5 arcmin)

### Best Practices

1. **Parti da Zenith**: Prima stella vicino allo zenit per miglior accuratezza
2. **SYNC Frequente**: Ogni 2-3 stelle per massima precisione
3. **Verifica Camera**: Usa camera per verificare centratura prima di SYNC
4. **Condizioni Cielo**: Stelle guida devono essere visibili (no nuvole)
5. **Magnitude Adaptive**: Aumenta max_mag se poche stelle disponibili

## 🔧 API Endpoints

### Pianificazione

```bash
# Plan hop to target
curl -X POST http://127.0.0.1:8000/api/plan-hop \
  -H "Content-Type: application/json" \
  -d '{
    "target_ra": 10.6847,
    "target_dec": 41.2688,
    "target_name": "M31",
    "max_steps": 5,
    "max_mag": 4.0,
    "max_spacing": 10.0
  }'
```

### Status & Navigation

```bash
# Get current hop session
GET /api/hop/status

# Get next step
GET /api/hop/next

# Confirm step (after SYNC)
POST /api/hop/confirm
  Body: {"step_number": 1}

# Reset session
POST /api/hop/reset
```

## 🐛 Troubleshooting

### "No path found"

- **Causa**: Nessuna stella luminosa nel corridoio
- **Soluzione**: 
  - Aumenta `max_mag` (es. 5.0)
  - Aumenta `max_spacing` (es. 15°)
  - Target troppo vicino (< 10° da posizione corrente)

### "GOTO failed"

- **Causa**: Telescopio non connesso o coordinata invalida
- **Soluzione**: Verifica connessione mount in Control panel

### Stelle non visibili

- **Causa**: Stelle sotto orizzonte o nascoste
- **Soluzione**: Usa **Skip** button e passa alla prossima

### Path troppo lungo

- **Causa**: Target molto distante
- **Soluzione**: Riduci `max_steps` o aumenta `max_spacing`

## 📸 Screenshot Flow

```
┌─────────────────────────────────────────┐
│  Star-Hopping Navigator                 │
│                                         │
│  📍 Plan Star-Hopping Route             │
│  ┌─────────┬─────────┬────────────┐    │
│  │ RA: 180 │ Dec: 45 │ Name: M31  │    │
│  └─────────┴─────────┴────────────┘    │
│  [🗺️ Plan Route]  [↺ Reset]            │
│  ✓ Route planned! 5 steps (10 min)     │
└─────────────────────────────────────────┘

┌─────────────────────────────────────────┐
│  📋 Navigation Steps                    │
│                                         │
│  Progress: ████████░░ 80%               │
│  3/5 steps | 38.5° | 80%                │
│                                         │
│  ┌──────────────────────────────────┐  │
│  │ 1 │ ⭐ Vega (Mag 0.0)            │  │
│  │   │ ✓ COMPLETED                 │  │
│  └──────────────────────────────────┘  │
│                                         │
│  ┌──────────────────────────────────┐  │
│  │ 2 │ ⭐ Deneb (Mag 1.2)           │  │
│  │   │ 🔵 ACTIVE                   │  │
│  │   │ [🎯 GOTO] [🔄 SYNC] [⏭️ Skip]│  │
│  └──────────────────────────────────┘  │
│                                         │
│  ┌──────────────────────────────────┐  │
│  │ 3 │ 🎯 M31 (TARGET)              │  │
│  │   │ ⏳ WAITING                  │  │
│  └──────────────────────────────────┘  │
└─────────────────────────────────────────┘
```

## 🎓 Tutorial Video (Future)

Verrà aggiunto video dimostrativo completo con:

1. Pianificazione percorso da Sky Map
2. Navigazione step-by-step reale
3. Centratura e SYNC con camera
4. Raggiungimento target finale
5. Tips & tricks esperti

## 🔗 Link Utili

- [Sky Map](http://127.0.0.1:8000/ui/sky.html) - Trova coordinate target
- [Align Tool](http://127.0.0.1:8000/ui/align.html) - Allineamento iniziale
- [Camera Control](http://127.0.0.1:8000/ui/camera.html) - Verifica centratura
- [Control Panel](http://127.0.0.1:8000/ui/control.html) - Joystick manuale

---

**Milestone 4 Complete** ✓  
*Next: Sequence Automation (Milestone 5)*
