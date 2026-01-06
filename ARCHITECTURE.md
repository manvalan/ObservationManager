# Architecture Overview

## System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      Web Browser (Client)                    │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐       │
│  │ control  │ │  align   │ │   sky    │ │  camera  │       │
│  │  .html   │ │  .html   │ │  .html   │ │  .html   │       │
│  └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘       │
│       │            │            │            │               │
│       └────────────┴────────────┴────────────┘               │
│                     │ HTTP/REST/MJPEG                        │
└─────────────────────┼────────────────────────────────────────┘
                      │
┌─────────────────────┼────────────────────────────────────────┐
│              FastAPI Server (Python)                         │
│  ┌───────────────────────────────────────────────────────┐  │
│  │                   server/app.py                        │  │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ │  │
│  │  │ Settings │ │  GOTO    │ │ Catalog  │ │  Align   │ │  │
│  │  │   API    │ │   API    │ │   API    │ │   API    │ │  │
│  │  └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘ │  │
│  │       │            │            │            │         │  │
│  │  ┌────┴────────────┴────────────┴────────────┴─────┐  │  │
│  │  │        ConnectionManager (Singleton)            │  │  │
│  │  │  - Persistent LX200 connection                  │  │  │
│  │  │  - Thread-safe with RLock                       │  │  │
│  │  └─────────────────┬───────────────────────────────┘  │  │
│  └────────────────────┼──────────────────────────────────┘  │
│                       │                                      │
│  ┌────────────────────┼──────────────────────────────────┐  │
│  │           lx200/ (Protocol Layer)                     │  │
│  │  ┌────────────────┴────────────────┐                  │  │
│  │  │  protocol.py (LX200 Commands)   │                  │  │
│  │  │  - parse_ra/dec, format_ra/dec  │                  │  │
│  │  │  - slew_to, sync_to, move, stop │                  │  │
│  │  └────────────────┬────────────────┘                  │  │
│  │                   │                                    │  │
│  │  ┌────────────────┴────────────────┐                  │  │
│  │  │  connection.py (I/O Layer)      │                  │  │
│  │  │  ┌──────────────┐ ┌───────────┐│                  │  │
│  │  │  │Serial        │ │Mock       ││                  │  │
│  │  │  │Connection    │ │Connection ││                  │  │
│  │  │  │(pyserial)    │ │(simulator)││                  │  │
│  │  │  └──────┬───────┘ └─────┬─────┘│                  │  │
│  │  └─────────┼───────────────┼──────┘                  │  │
│  └────────────┼───────────────┼─────────────────────────┘  │
└───────────────┼───────────────┼────────────────────────────┘
                │               │
    ┌───────────┴────┐      (No hardware)
    │                │
┌───┴─────┐    ┌─────┴──────┐
│ LX200   │    │ Virtual    │
│ Mount   │    │ Simulator  │
│(serial) │    │ (MockConn) │
└─────────┘    └────────────┘
```

## Component Details

### Frontend (HTML/JS)

**Location**: `web/*.html`

**Architecture**:
- Static HTML pages con vanilla JavaScript
- No build step, no framework dependencies
- Direct DOM manipulation
- Fetch API per REST calls

**Key Pages**:
- `index.html`: Homepage con navigation
- `control.html`: Connection management, status, GOTO
- `align.html`: Multi-star alignment workflow
- `sky.html`: Interactive Alt/Az sky map (Canvas)
- `camera.html`: MJPEG video stream
- `catalog.html`: Name/ID search
- `move.html`: Manual direction controls

**Design Principles**:
- Mobile-first responsive
- Progressive enhancement
- Graceful degradation senza JS
- Accessibility (keyboard nav, ARIA labels)

### Backend (FastAPI)

**Location**: `server/app.py`

**Layers**:
1. **API Layer**: REST endpoints, request validation (Pydantic)
2. **Business Logic**: Coordinate conversions, alignment tracking
3. **Connection Management**: Singleton ConnectionManager
4. **Protocol Layer**: LX200 command abstraction

**Key Components**:

#### ConnectionManager
```python
class ConnectionManager:
    _conn: Optional[Union[SerialConnection, MockConnection]]
    _lock: threading.RLock  # Thread-safe access
```
- Singleton pattern
- Manages single persistent connection
- Auto-reconnect on failure
- Thread-safe for concurrent API calls

#### Settings Management
```python
# server/data/settings.json
{
  "latitude": 45.0,
  "longitude": 11.0,
  "altitude_m": 0,
  "pressure_mbar": 1013.25,
  "temperature_c": 15.0,
  "tz_offset_hours": 1
}
```
- Validated on POST
- Used for topocentric calculations
- Persisted to JSON file

#### Alignment Session
```python
align_session = {
    "current": None,  # Current target being aligned
    "history": []     # List of past syncs with residuals
}
```
- In-memory session state
- Tracks alignment quality
- Residual angular distance calculation

### LX200 Protocol Layer

**Location**: `lx200/protocol.py`

**Responsibilities**:
- LX200 command formatting/parsing
- RA/Dec coordinate conversion
- Command sequencing (e.g., set target → slew)

**Key Methods**:
```python
class LX200:
    def slew_to(ra: str, dec: str) -> str
    def sync_to(ra: str, dec: str) -> str
    def get_ra() -> str
    def get_dec() -> str
    def move(direction: str) -> None
    def stop() -> None
```

### Connection Abstraction

**Location**: `lx200/connection.py`

**Implementations**:

#### SerialConnection
- Wraps `pyserial` for real hardware
- Auto-detect serial ports (macOS `/dev/cu.*`)
- Configurable baud, timeout
- Read/write with `#` terminator handling

#### MockConnection
- Simulates LX200 responses
- No hardware required
- Realistic state tracking (RA/Dec, slewing, aligned)
- Command history for debugging

**Interface**:
```python
class Connection:
    def open() -> None
    def close() -> None
    def query(cmd: str) -> str
    def write_command(cmd: str) -> None
```

### Coordinate Calculations

**Location**: `server/app.py` (helpers)

**Libraries**:
- **Skyfield**: High-precision ephemeris, topocentric conversions
- **numpy**: Matrix operations (future use)

**Key Functions**:
```python
def ra_dec_to_altaz(ra_deg, dec_deg, cfg) -> (alt, az)
    # ICRS → Topocentric + refraction
    
def altaz_to_ra_dec(alt_deg, az_deg, cfg) -> (ra, dec)
    # Inverse transform with trig
    
def zenith_radec(cfg) -> (ra, dec)
    # Calculate zenith coordinates
```

### Catalog Integration

**Location**: `lx200/catalog.py`, `gaia/src/gaia_lookup.cpp`

**Architecture**:
- **Primary**: Gaia DR3 via C++ subprocess (`gaia_lookup`)
- **Fallback**: Local CSV/JSON files
- **Cache**: None (stateless queries)

**Query Types**:
1. **Name search**: `resolve_name("M42")`
2. **ID resolution**: `resolve_id_via_gaia(sao=113271)`
3. **Cone search**: `gaia_lookup --cone RA DEC RADIUS`

**Performance**:
- C++ subprocess: ~50-200ms per query
- Local catalog: ~2TB Gaia index
- Future: Redis cache for frequent queries

### Camera Streaming

**Location**: `server/app.py` `/api/video.mjpg`

**Architecture**:
- OpenCV capture from UVC device
- MJPEG encoding in Python
- Streaming response (chunked transfer)

**Frame Pipeline**:
```
Camera → OpenCV capture → JPEG encode → HTTP chunks → Browser
```

**Overlay**:
- Red reticle (cross + circle)
- Drawn on server-side before encoding
- Future: Client-side canvas overlay for performance

## Data Flow Examples

### GOTO Workflow

```
User clicks star in sky.html
    ↓
fetch('/api/sky/stars')  [Get stars in view]
    ↓
User clicks star
    ↓
fetch('/api/goto', {ra_deg, dec_deg})
    ↓
FastAPI validates request
    ↓
ConnectionManager.get_lx200()
    ↓
LX200.slew_to(ra, dec)
    ↓
Connection.query(':SrHH:MM:SS#')
Connection.query(':Sd+DD*MM:SS#')
Connection.query(':MS#')
    ↓
[SerialConnection: writes to /dev/cu.*]
[MockConnection: updates internal state]
    ↓
Mount slews (physical or simulated)
    ↓
API returns {ok: true, ra_deg, dec_deg, alt_deg, az_deg}
    ↓
UI displays confirmation message
```

### Alignment Workflow

```
User loads align.html
    ↓
fetch('/api/align/suggestions')  [Get bright stars]
    ↓
Server queries Gaia cone near zenith
    ↓
Filter by alt > 20°, mag < 4
    ↓
Return sorted list
    ↓
User clicks GOTO on star
    ↓
fetch('/api/align/goto', {name})
    ↓
Server performs GOTO (see above)
    ↓
Sets align_session.current = {name, ra, dec}
    ↓
User centers star in camera view
    ↓
User clicks Sync countdown button
    ↓
After 3 seconds, fetch('/api/align/sync')
    ↓
Server calls LX200.sync_to()
    ↓
Reads back mount position
    ↓
Calculates residual_arcsec (angular distance)
    ↓
Appends to align_session.history
    ↓
UI displays residual and updates history table
```

## Security Considerations

**Current State** (Development):
- No authentication
- CORS: Allow all origins
- Direct hardware access

**Future Enhancements** (Production):
- API key authentication
- HTTPS/TLS encryption
- Rate limiting
- Input sanitization (already via Pydantic)
- CORS whitelist
- User roles (admin, observer, viewer)

## Performance

**Current Metrics**:
- API response: 10-50ms (local)
- Gaia query: 50-200ms (C++ subprocess)
- MJPEG frame: 30fps @ 640x480
- Coordinate calc: <5ms (Skyfield cached)

**Bottlenecks**:
- Gaia subprocess spawn overhead
- Serial I/O latency (9600 baud)
- No caching for repeated queries

**Optimizations Planned**:
- Redis cache for catalogs
- Connection pooling (if multi-mount)
- Async I/O for serial comms
- WebSocket for real-time updates

## Testing Strategy

**Current Coverage**: ~30%

**Test Pyramid**:
1. **Unit Tests** (70%):
   - Coordinate conversions
   - RA/Dec parsing/formatting
   - MockConnection behavior
   
2. **Integration Tests** (20%):
   - API endpoints (TestClient)
   - Database/file I/O
   - Catalog queries
   
3. **E2E Tests** (10%):
   - Full workflows (alignment, GOTO)
   - UI interaction (Selenium/Playwright)
   - Real hardware smoke tests

**CI/CD**:
- GitHub Actions (future)
- Automated testing on push
- Code coverage reports
- Docker builds

## Deployment

**Development**:
```bash
python -m uvicorn server.app:app --reload
```

**Production** (future):
```bash
# Gunicorn with workers
gunicorn server.app:app -w 4 -k uvicorn.workers.UvicornWorker

# Docker container
docker build -t observation-manager .
docker run -p 8000:8000 -v /dev:/dev --privileged observation-manager

# Systemd service
systemctl start observation-manager
```

## Extensibility

**Plugin System** (future):
- Driver plugins for ASCOM/INDI
- Catalog plugins (custom sources)
- UI themes (CSS variables)
- Sequence scripts (YAML/Python)

**API Versioning**:
- `/api/v1/...` namespace
- Backward compatibility guarantee
- Deprecation warnings

## Technology Choices

| Component | Technology | Rationale |
|-----------|-----------|-----------|
| Backend | FastAPI | Modern, fast, OpenAPI, async support |
| Frontend | Vanilla JS | No build step, lightweight, fast iteration |
| Astronomy | Skyfield | High precision, well-maintained |
| Catalog | IOC_GaiaLib | Local DR3 access, C++ performance |
| Camera | OpenCV | Cross-platform, mature, USB support |
| Testing | pytest | De-facto standard, good ecosystem |
| Docs | Markdown | Simple, version-controlled |

---

**Last Updated**: January 2026  
**Version**: 0.3.0
