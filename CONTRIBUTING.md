# Contributing to ObservationManager

Grazie per il tuo interesse nel contribuire a ObservationManager! Questo documento fornisce linee guida per contribuire efficacemente al progetto.

---

## 🚀 Quick Start per Contributors

### 1. Setup Ambiente di Sviluppo

```bash
# Clone repository
git clone https://github.com/manvalan/ObservationManager.git
cd ObservationManager

# Setup virtual environment (opzionale ma raccomandato)
python3 -m venv venv
source venv/bin/activate  # Linux/macOS
# oppure
.\venv\Scripts\activate   # Windows

# Installa dipendenze
pip install -r requirements.txt

# Compila Gaia lookup (opzionale, per catalog features)
cd gaia
mkdir build && cd build
cmake ..
make
cd ../..

# Verifica installazione
python -c "from server.app import app; print('✓ Setup OK')"
```

### 2. Avvia Server di Sviluppo

```bash
# Con mock driver (senza hardware)
python -m uvicorn server.app:app --reload --host 127.0.0.1 --port 8000

# Apri browser
open http://127.0.0.1:8000/ui/
```

### 3. Test del Mock Driver

Il progetto include `MockConnection` in `lx200/connection.py` per simulare la montatura:

```python
from lx200.connection import MockConnection
from lx200.protocol import LX200

# Usa mock invece di SerialConnection
conn = MockConnection()
lx = LX200(conn)

# Tutti i comandi funzionano come con hardware reale
lx.slew_to("12:00:00", "+45*30:00")
print(lx.get_ra())  # Simula risposta

# Vedi history dei comandi inviati
print(conn.history)
```

---

## 🔧 Development Workflow

### Branch Strategy

- **main**: Codice stabile e testato
- **develop**: Branch di integrazione per nuove features
- **feature/nome-feature**: Branch per singola feature
- **fix/nome-bug**: Branch per bugfix

### Workflow Tipico

```bash
# 1. Crea branch per tua feature
git checkout -g feature/star-hopping

# 2. Sviluppa e testa
# ... modifica codice ...
python -m pytest tests/  # Run tests

# 3. Commit con messaggi descrittivi
git add .
git commit -m "feat: add star-hopping planner API endpoint"

# 4. Push e crea Pull Request
git push origin feature/star-hopping
# Apri PR su GitHub
```

### Commit Message Convention

Seguiamo [Conventional Commits](https://www.conventionalcommits.org/):

- `feat:` Nuova feature
- `fix:` Bugfix
- `docs:` Documentazione
- `style:` Formatting, no code change
- `refactor:` Code refactoring
- `test:` Aggiunta/modifica tests
- `chore:` Maintenance tasks

**Esempi:**
```
feat: add meridian flip detection
fix: correct Alt/Az conversion for southern hemisphere
docs: update API reference for /api/sky/stars
refactor: extract coordinate conversion to utils module
test: add unit tests for MockConnection
```

---

## 📝 Coding Standards

### Python

- **Style**: PEP 8 (usa `black` per auto-formatting)
- **Type Hints**: Obbligatori per nuove funzioni
- **Docstrings**: Google style per funzioni pubbliche
- **Imports**: Ordinati con `isort`

```python
from typing import List, Optional, Tuple

def calculate_angular_distance(
    ra1: float, 
    dec1: float, 
    ra2: float, 
    dec2: float
) -> float:
    """
    Calculate angular distance between two celestial coordinates.
    
    Args:
        ra1: Right ascension of first point (degrees)
        dec1: Declination of first point (degrees)
        ra2: Right ascension of second point (degrees)
        dec2: Declination of second point (degrees)
        
    Returns:
        Angular distance in degrees
        
    Example:
        >>> calculate_angular_distance(0, 0, 10, 10)
        14.142135623730951
    """
    # Implementation...
```

### JavaScript/HTML

- **Style**: Standard JS con 2 spazi indentation
- **Naming**: camelCase per variabili, PascalCase per classi
- **Async**: Preferisci `async/await` su Promises
- **Comments**: JSDoc per funzioni complesse

```javascript
/**
 * Fetch stars in cone around specified coordinates
 * @param {number} ra - Right ascension in degrees
 * @param {number} dec - Declination in degrees
 * @param {number} radius - Search radius in degrees
 * @returns {Promise<Array>} Array of star objects
 */
async function fetchStarsInCone(ra, dec, radius) {
  const resp = await fetch(`/api/sky/stars?ra_deg=${ra}&dec_deg=${dec}&radius=${radius}`);
  return resp.json();
}
```

### C++

- **Style**: Google C++ Style Guide
- **Memory**: Preferisci smart pointers
- **Naming**: snake_case per funzioni, PascalCase per classi

---

## 🧪 Testing Guidelines

### Unit Tests

```python
# tests/test_coordinates.py
import pytest
from lx200.protocol import parse_ra, parse_dec

def test_parse_ra_hms_format():
    """Test RA parsing from HH:MM:SS format"""
    assert parse_ra("12:30:45") == pytest.approx(12.5125, rel=1e-4)

def test_parse_ra_degrees():
    """Test RA parsing from decimal degrees"""
    assert parse_ra(180.0) == pytest.approx(12.0, rel=1e-4)
```

### Integration Tests

```python
# tests/test_api.py
from fastapi.testclient import TestClient
from server.app import app

client = TestClient(app)

def test_api_sky_stars_endpoint():
    """Test /api/sky/stars returns valid data"""
    resp = client.get("/api/sky/stars?ra_deg=0&dec_deg=45&radius=30")
    assert resp.status_code == 200
    data = resp.json()
    assert "stars" in data
    assert isinstance(data["stars"], list)
```

### Test con Mock Hardware

```python
def test_slew_command_with_mock():
    """Test GOTO command usando MockConnection"""
    conn = MockConnection()
    lx = LX200(conn)
    
    # Esegui slew
    result = lx.slew_to("10:30:00", "+25*30:00")
    
    # Verifica comandi inviati
    assert ":Sr10:30:00#" in conn.history
    assert ":Sd+25*30:00#" in conn.history
    assert ":MS#" in conn.history
```

---

## 📚 Areas Needing Contributions

### 🟢 Good First Issues

Perfette per iniziare:

1. **Documentation improvements**
   - Aggiungere esempi a README
   - Tradurre docs in altre lingue
   - Creare tutorial video scripts

2. **UI enhancements**
   - Migliorare CSS styling
   - Aggiungere dark mode toggle
   - Responsive design fixes

3. **Error messages**
   - Rendere messaggi più user-friendly
   - Aggiungere traduzioni i18n
   - Standardizzare formato errori

### 🟡 Intermediate Tasks

Richiedono familiarità col progetto:

1. **Testing**
   - Aumentare test coverage
   - Aggiungere integration tests
   - Mock per external dependencies

2. **Performance**
   - Ottimizzare cone queries
   - Cache per Gaia lookups
   - Reduce API response times

3. **Features minori**
   - Export session logs a CSV
   - Custom star catalogs import
   - Keyboard shortcuts in UI

### 🔴 Advanced Contributions

Richiedono expertise tecnica:

1. **Star-hopping algorithm**
   - Implementare pathfinding A*
   - Ottimizzare per low-latency
   - Gestire edge cases

2. **Plate solving integration**
   - Interfaccia con astrometry.net
   - Local plate solver
   - Automatic sync da immagini

3. **Multi-mount support**
   - Architettura per più devices
   - ASCOM/INDI drivers
   - Concurrent session management

---

## 🐛 Bug Reports

Quando apri un Issue per bug:

### Template

```markdown
**Descrizione**
Breve descrizione del problema

**Steps to Reproduce**
1. Vai a /ui/align.html
2. Clicca su "Load Suggestions"
3. Osserva errore console

**Expected Behavior**
Lista di stelle dovrebbe apparire

**Actual Behavior**
Errore "Failed to fetch"

**Environment**
- OS: macOS 14.2
- Browser: Chrome 120
- Python: 3.11.5
- ObservationManager version: 0.3.0

**Logs**
```
ERROR: Connection refused
...
```

**Screenshots**
[Se applicabile]
```

---

## 💡 Feature Requests

Per proporre nuove features:

1. **Controlla Roadmap**: Verifica se già pianificata in [ROADMAP.md](ROADMAP.md)
2. **Apri Discussion**: Usa GitHub Discussions per discutere idea
3. **Scrivi Proposal**: Se approvata, crea Issue dettagliato con:
   - Use case chiaro
   - Mockups UI (se applicabile)
   - API design proposal
   - Stima complessità

---

## 📖 Documentation Contributions

La documentazione è cruciale! Contributi benvenuti su:

- **README.md**: Setup e quick start
- **API docs**: OpenAPI/Swagger specs
- **User guides**: Tutorial step-by-step
- **Architecture docs**: Design decisions
- **Troubleshooting**: Common issues & fixes

---

## 🤝 Code Review Process

### Per Reviewers

- **Tempestività**: Review entro 2-3 giorni
- **Constructive**: Suggerimenti specifici
- **Testing**: Verifica che tests passino
- **Standards**: Check coding style compliance

### Per Contributors

- **Patience**: Reviews richiedono tempo
- **Responsive**: Rispondi a feedback prontamente
- **Iterate**: Multiple rounds sono normali
- **Learn**: Ogni review è occasione di crescita

---

## 🎉 Recognition

Contributors vengono riconosciuti:

- Nome in `CONTRIBUTORS.md`
- Menzione in release notes
- Badge "Contributor" su profilo GitHub
- Credits nell'app (About page)

---

## 📞 Getting Help

- **Questions**: GitHub Discussions Q&A
- **Chat**: Discord server (link in README)
- **Email**: maintainer@observationmanager.dev

---

## 📜 License

Contribuendo, accetti che il tuo codice sia rilasciato sotto la stessa licenza del progetto (MIT License).

---

**Grazie per contribuire a ObservationManager!** 🔭✨

Ogni contributo, grande o piccolo, aiuta a rendere l'astronomia amatoriale più accessibile e divertente.
