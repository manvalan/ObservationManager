from __future__ import annotations

import threading
import time
from typing import Optional, List

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from lx200.connection import SerialConnection, MockConnection, detect_serial_ports
from lx200.protocol import LX200, parse_ra, parse_dec
from lx200.catalog import resolve_name
from lx200.catalog import resolve_id_via_gaia
from server.catalog_local import local_catalog
from server.camera import camera_controller
from server.session_manager import SessionManager
from server.filter_wheel import SerialFilterWheel, MockFilterWheel, filter_wheel_manager
from server.calibration import calibration_manager
from server.sequence import (
    ObservingSequence, SequenceStep, StepType, StepStatus,
    SequenceExecutor, get_executor, register_executor, unregister_executor
)

import os
import json
import math
import pathlib
import subprocess
import shutil

try:
    import cv2  # type: ignore
except Exception:
    cv2 = None  # optional

from skyfield.api import wgs84, load, Star  # type: ignore


class ConnectionManager:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._conn: Optional[SerialConnection | MockConnection] = None
        self._port: Optional[str] = None
        self._baud: int = 9600
        self._timeout: float = 2.0
        self._dry_run: bool = False

    def connect(self, port: Optional[str], baud: int, timeout: float, dry_run: bool) -> None:
        with self._lock:
            if self._conn:
                # already connected: close and reopen
                try:
                    self._conn.close()  # type: ignore[attr-defined]
                except Exception:
                    pass
                self._conn = None
            if dry_run:
                conn = MockConnection()
                conn.open()
                self._conn = conn
            else:
                if not port:
                    raise RuntimeError("Nessuna porta specificata")
                conn = SerialConnection(port=port, baudrate=baud, timeout=timeout)
                conn.open()
                self._conn = conn
            self._port = port
            self._baud = baud
            self._timeout = timeout
            self._dry_run = dry_run

    def disconnect(self) -> None:
        with self._lock:
            if self._conn:
                try:
                    self._conn.close()  # type: ignore[attr-defined]
                finally:
                    self._conn = None

    def is_connected(self) -> bool:
        return self._conn is not None

    def get_lx200(self) -> LX200:
        with self._lock:
            if not self._conn:
                raise RuntimeError("Non connesso")
            return LX200(self._conn)  # type: ignore[arg-type]

    def info(self) -> dict:
        return {
            "connected": self._conn is not None,
            "port": self._port,
            "baud": self._baud,
            "timeout": self._timeout,
            "dry_run": self._dry_run,
        }


manager = ConnectionManager()

app = FastAPI(title="LX200 Web Controller")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve static web UI under /ui to not shadow /api
app.mount("/ui", StaticFiles(directory="web", html=True), name="web")


@app.get("/")
def root_redirect():
    return RedirectResponse(url="/ui/")


class ConnectBody(BaseModel):
    port: Optional[str] = None
    baud: int = 9600
    timeout: float = 2.0
    dry_run: bool = False


class GotoBody(BaseModel):
    ra: Optional[str] = None
    dec: Optional[str] = None
    ra_deg: Optional[float] = None
    dec_deg: Optional[float] = None
    alt_deg: Optional[float] = None
    az_deg: Optional[float] = None


class MoveBody(BaseModel):
    dir: str = Field(pattern="^[NSEWnsew]$")
    rate: str = Field(default="slew")
    seconds: float = 0.0


class StopBody(BaseModel):
    dir: Optional[str] = Field(default=None, pattern="^[NSEWnsew]$")


class SyncBody(BaseModel):
    ra: str
    dec: str


@app.get("/api/ports")
def api_ports() -> List[str]:
    return list(detect_serial_ports())


@app.get("/api/connection")
def api_connection() -> dict:
    return manager.info()


@app.post("/api/connect")
def api_connect(body: ConnectBody) -> dict:
    try:
        manager.connect(body.port, body.baud, body.timeout, body.dry_run)
        return {"ok": True, **manager.info()}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/disconnect")
def api_disconnect() -> dict:
    manager.disconnect()
    return {"ok": True, **manager.info()}


@app.get("/api/status")
def api_status() -> dict:
    try:
        lx = manager.get_lx200()
        return {
            "ok": True,
            "version": lx.get_version(),
            "ra": lx.get_ra(),
            "dec": lx.get_dec(),
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/goto")
def api_goto(body: GotoBody) -> dict:
    try:
        ra_deg_val: Optional[float] = None
        dec_deg_val: Optional[float] = None
        if body.alt_deg is not None and body.az_deg is not None:
            cfg = _read_settings()
            ra_deg_val, dec_deg_val = altaz_to_ra_dec(body.alt_deg, body.az_deg, cfg)
        if ra_deg_val is None:
            if body.ra_deg is not None:
                ra_deg_val = float(body.ra_deg)
            elif body.ra is not None:
                ra_fmt = parse_ra(body.ra)
                hh, mm, ss = [int(p) for p in ra_fmt.split(":")]
                ra_deg_val = (hh + mm / 60 + ss / 3600) * 15.0
        if dec_deg_val is None:
            if body.dec_deg is not None:
                dec_deg_val = float(body.dec_deg)
            elif body.dec is not None:
                dec_fmt = parse_dec(body.dec)
                sign = -1 if dec_fmt.startswith("-") else 1
                d_str, mmss = dec_fmt[1:].split("*")
                m_str, s_str = mmss.split(":")
                dec_deg_val = sign * (int(d_str) + int(m_str)/60 + int(s_str)/3600)
        if ra_deg_val is None or dec_deg_val is None:
            raise ValueError("Specificare RA/Dec o Alt/Az")
        ra_s = parse_ra(ra_deg_val / 15.0)
        dec_s = parse_dec(dec_deg_val)
        lx = manager.get_lx200()
        lx.set_target_ra_dec(ra_s, dec_s)
        res = lx.goto()
        return {"ok": True, "response": res, "ra": ra_s, "dec": dec_s, "ra_deg": ra_deg_val, "dec_deg": dec_deg_val}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


class AltAzBody(BaseModel):
    ra_deg: float
    dec_deg: float


class ApparentBody(BaseModel):
    alt_deg: float
    az_deg: float
    timestamp: float | None = None


@app.post("/api/altaz")
def api_altaz(body: AltAzBody, timestamp: float | None = None) -> dict:
    try:
        cfg = _read_settings()
        alt, az = ra_dec_to_altaz(body.ra_deg, body.dec_deg, cfg, timestamp)
        return {"ok": True, "alt_deg": alt, "az_deg": az, "settings": cfg}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/apparent")
def api_apparent(body: ApparentBody) -> dict:
    try:
        cfg = _read_settings()
        ra, dec = altaz_to_ra_dec(body.alt_deg, body.az_deg, cfg, body.timestamp)
        return {"ok": True, "ra_deg": ra, "dec_deg": dec, "settings": cfg}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/move")
def api_move(body: MoveBody) -> dict:
    try:
        lx = manager.get_lx200()
        lx.set_rate(body.rate)
        lx.move_dir(body.dir)
        if body.seconds and body.seconds > 0:
            def stopper(dir_: str, delay: float):
                time.sleep(delay)
                try:
                    lx2 = manager.get_lx200()
                    lx2.stop_dir(dir_)
                except Exception:
                    pass
            threading.Thread(target=stopper, args=(body.dir, body.seconds), daemon=True).start()
        return {"ok": True}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/stop")
def api_stop(body: StopBody) -> dict:
    try:
        lx = manager.get_lx200()
        if body.dir:
            lx.stop_dir(body.dir)
        else:
            lx.stop_all()
        return {"ok": True}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# -------- Focuser --------
class FocuserSpeedBody(BaseModel):
    speed: str = Field(default="slow", description="Focuser speed: slow|fast")


@app.post("/api/focuser/in")
def api_focuser_in():
    """Start moving focuser inward."""
    try:
        lx = manager.get_lx200()
        lx.focus_in()
        return {"ok": True, "message": "Focuser moving in"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/focuser/out")
def api_focuser_out():
    """Start moving focuser outward."""
    try:
        lx = manager.get_lx200()
        lx.focus_out()
        return {"ok": True, "message": "Focuser moving out"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/focuser/stop")
def api_focuser_stop():
    """Stop focuser movement."""
    try:
        lx = manager.get_lx200()
        lx.focus_stop()
        return {"ok": True, "message": "Focuser stopped"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/focuser/speed")
def api_focuser_speed(body: FocuserSpeedBody):
    """Set focuser speed (slow|fast)."""
    try:
        lx = manager.get_lx200()
        lx.set_focus_speed(body.speed)
        return {"ok": True, "speed": body.speed}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/focuser/status")
def api_focuser_status():
    """Get focuser status (position, temperature if available)."""
    try:
        lx = manager.get_lx200()
        conn = manager._conn
        status = {}
        
        # Try to get position (not all mounts support this)
        try:
            pos_str = conn.query(":FG")  # type: ignore
            if pos_str and pos_str.isdigit():
                status["position"] = int(pos_str)
        except Exception:
            status["position"] = None
        
        # Try to get temperature (not all focusers have sensor)
        try:
            temp_str = conn.query(":FT")  # type: ignore
            if temp_str:
                status["temperature_c"] = float(temp_str)
        except Exception:
            status["temperature_c"] = None
        
        return {"ok": True, "status": status}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/sync")
def api_sync(body: SyncBody) -> dict:
    try:
        lx = manager.get_lx200()
        ra = parse_ra(body.ra)
        dec = parse_dec(body.dec)
        msg = lx.sync_to(ra, dec)
        return {"ok": True, "message": msg}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/find")
def api_find(name: str = Query(..., min_length=1), limit: int = 5) -> dict:
    try:
        # Prova catalogo locale Gaia/Crossreference prima
        results = local_catalog.search_by_name(name, limit=limit)
        if results:
            out = [{
                "name": r["name"], 
                "ra_deg": r["ra_deg"], 
                "dec_deg": r["dec_deg"], 
                "mag": r.get("mag"), 
                "catalog": r.get("catalog", "Local")
            } for r in results]
            return {"ok": True, "results": out, "source": "local"}
        
        # Fallback a risoluzione online
        results = resolve_name(name, limit=limit)
        out = [
            {
                "name": e.name,
                "ra_deg": e.ra_deg,
                "dec_deg": e.dec_deg,
                "mag": e.mag,
                "designations": e.designations,
                "catalog": "Online",
            }
            for e in results
        ]
        return {"ok": True, "results": out, "source": "online"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/goto-name")
def api_goto_name(name: str) -> dict:
    try:
        # Prova catalogo locale prima
        target = None
        local_results = local_catalog.search_by_name(name, limit=1)
        if local_results:
            r = local_results[0]
            target = type('obj', (), {"name": r["name"], "ra_deg": r["ra_deg"], "dec_deg": r["dec_deg"]})
        else:
            # Fallback online
            results = resolve_name(name, limit=10)
            if results:
                target = results[0]
        
        if not target:
            raise ValueError("Nessun risultato trovato")
        
        ra_s = parse_ra(target.ra_deg / 15.0)
        dec_s = parse_dec(target.dec_deg)
        lx = manager.get_lx200()
        lx.set_target_ra_dec(ra_s, dec_s)
        res = lx.goto()
        return {"ok": True, "response": res, "name": target.name, "ra": ra_s, "dec": dec_s}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# -------- Align suggestions and session --------
align_session = {"current": None, "history": []}


@app.get("/api/align/suggestions")
def api_align_suggestions(limit: int = 5, min_alt: float = 20.0):
    try:
        cfg = _read_settings()
        # prefer Gaia cone near zenith
        ra_z, dec_z = zenith_radec(cfg)
        gaia_stars = _gaia_lookup_cone(ra_z, dec_z, radius_deg=80.0, maxmag=4.0, limit=limit*3)
        stars = gaia_stars if gaia_stars else _load_bright_stars()
        scored = []
        for s in stars:
            alt, az = ra_dec_to_altaz(s["ra_deg"], s["dec_deg"], cfg)
            if alt < min_alt:
                continue
            mag = s.get("mag", 2.5) if s.get("mag") is not None else 2.5
            score = alt - (mag * 2)
            scored.append({**s, "alt_deg": alt, "az_deg": az, "score": score})
        scored.sort(key=lambda x: x["score"], reverse=True)
        return {"ok": True, "results": scored[:limit]}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/align/status")
def api_align_status():
    return {"ok": True, "session": align_session}


class AlignGotoBody(BaseModel):
    name: str
    ra_deg: float
    dec_deg: float


@app.post("/api/align/goto")
def api_align_goto(body: AlignGotoBody):
    try:
        ra_s = parse_ra(body.ra_deg / 15.0)
        dec_s = parse_dec(body.dec_deg)
        lx = manager.get_lx200()
        lx.set_target_ra_dec(ra_s, dec_s)
        res = lx.goto()
        align_session["current"] = {
            "name": body.name,
            "ra_deg": body.ra_deg,
            "dec_deg": body.dec_deg,
            "goto_response": res,
            "timestamp": time.time(),
        }
        return {"ok": True, "response": res, "target": align_session["current"]}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


class AlignSyncBody(BaseModel):
    ra_deg: float
    dec_deg: float


@app.post("/api/align/sync")
def api_align_sync(body: AlignSyncBody):
    try:
        ra_s = parse_ra(body.ra_deg / 15.0)
        dec_s = parse_dec(body.dec_deg)
        lx = manager.get_lx200()
        msg = lx.sync_to(ra_s, dec_s)
        residual_arcsec = None
        try:
            ra_now = lx.get_ra()
            dec_now = lx.get_dec()
            # convert to degrees for residual
            hh, mm, ss = [float(p) for p in ra_now.split(":")]
            ra_now_deg = (hh + mm/60 + ss/3600) * 15.0
            sign = -1 if dec_now.startswith('-') else 1
            d_str, mmss = dec_now[1:].split('*')
            m_str, s_str = mmss.split(":")
            dec_now_deg = sign * (float(d_str) + float(m_str)/60 + float(s_str)/3600)
            # angular separation
            def angsep(ra1, dec1, ra2, dec2):
                ra1r = math.radians(ra1); dec1r = math.radians(dec1)
                ra2r = math.radians(ra2); dec2r = math.radians(dec2)
                cosd = math.sin(dec1r)*math.sin(dec2r) + math.cos(dec1r)*math.cos(dec2r)*math.cos(ra1r-ra2r)
                cosd = max(-1.0, min(1.0, cosd))
                return math.degrees(math.acos(cosd)) * 3600.0  # arcsec
            residual_arcsec = angsep(ra_now_deg, dec_now_deg, body.ra_deg, body.dec_deg)
        except Exception:
            residual_arcsec = None
        entry = {
            "name": align_session.get("current", {}).get("name", ""),
            "ra_deg": body.ra_deg,
            "dec_deg": body.dec_deg,
            "sync_msg": msg,
            "residual_arcsec": residual_arcsec,
            "timestamp": time.time(),
        }
        align_session["history"].append(entry)
        align_session["current"] = None
        return {"ok": True, "message": msg, "synced": entry}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# -------- Sky (planetario) --------
@app.get("/api/sky/stars")
def api_sky_stars(ra_deg: float = None, dec_deg: float = None, radius: float = 60.0, maxmag: float = 5.0, timestamp: float | None = None, show_below_horizon: bool = False, density: float = 1.0):
    try:
        if ra_deg is None or dec_deg is None:
            cfg = _read_settings()
            ra_deg, dec_deg = zenith_radec(cfg, timestamp)
        gaia_stars = _gaia_lookup_cone(float(ra_deg), float(dec_deg), float(radius), float(maxmag), limit=1000)
        if not gaia_stars:
            stars = _load_bright_stars()
        else:
            stars = gaia_stars
        cfg = _read_settings()
        out = []
        # Applica densità: riduci numero di stelle in base a density (0.1..1.0)
        if density is None:
            density = 1.0
        step = max(1, int(1.0 / max(0.1, min(1.0, density))))
        for i, s in enumerate(stars):
            if i % step != 0:
                continue
            try:
                alt, az = ra_dec_to_altaz(s["ra_deg"], s["dec_deg"], cfg, timestamp)
                if not show_below_horizon and alt < 0:
                    continue
                mag = s.get("mag")
                if mag is None:
                    mag = 5.0
                out.append({
                    "name": s.get("name", ""),
                    "ra_deg": s["ra_deg"],
                    "dec_deg": s["dec_deg"],
                    "alt_deg": alt,
                    "az_deg": az,
                    "mag": mag,
                })
            except Exception:
                continue
        return {"ok": True, "center_ra": ra_deg, "center_dec": dec_deg, "radius": radius, "stars": out, "count": len(out)}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# -------- Settings (site/time/atmo) --------
SETTINGS_PATH = os.path.join(os.path.dirname(__file__), "data", "settings.json")
os.makedirs(os.path.dirname(SETTINGS_PATH), exist_ok=True)
BRIGHT_PATH = pathlib.Path(os.path.join(os.path.dirname(__file__), "data", "bright_stars.json"))
CONSTELLATIONS_PATH = pathlib.Path(os.path.join(os.path.dirname(__file__), "data", "constellations.json"))
CONSTELLATION_BOUNDARIES_PATH = pathlib.Path(os.path.join(os.path.dirname(__file__), "data", "constellation_boundaries.json"))
# Se presente variabile d'ambiente GAIA_LOOKUP_PATH, usa quella. Altrimenti preferisci binario del workspace.
GAIA_EXE_CANDIDATES = [
    os.environ.get("GAIA_LOOKUP_PATH"),
    os.path.join(os.path.dirname(os.path.dirname(__file__)), "gaia", "build", "gaia_lookup"),
    shutil.which("gaia_lookup"),
]


class SettingsBody(BaseModel):
    latitude: float
    longitude: float
    altitude_m: float = 0.0
    pressure_mbar: float = 1013.25
    temperature_c: float = 10.0
    tz_offset_hours: float = 0.0

    def validate_ranges(self) -> None:
        if not (-90 <= self.latitude <= 90):
            raise ValueError("Latitudine fuori range (-90..90)")
        if not (-180 <= self.longitude <= 180):
            raise ValueError("Longitudine fuori range (-180..180)")
        if not (-500 <= self.altitude_m <= 9000):
            raise ValueError("Altitudine fuori range (-500..9000 m)")
        if not (0 <= self.pressure_mbar <= 1100):
            raise ValueError("Pressione fuori range")
        if not (-60 <= self.temperature_c <= 60):
            raise ValueError("Temperatura fuori range")
        if not (-14 <= self.tz_offset_hours <= 14):
            raise ValueError("TZ offset fuori range")

class SkyConfigBody(BaseModel):
    maxmag: float = 5.0
    radius: float = 60.0
    show_below_horizon: bool = False
    label_mag_threshold: float = 3.0
    density: float = 1.0

    def validate_ranges(self) -> None:
        if not (0.0 <= self.maxmag <= 20.0):
            raise ValueError("maxmag fuori range (0..20)")
        if not (5.0 <= self.radius <= 180.0):
            raise ValueError("radius fuori range (5..180)")
        if not (0.1 <= self.density <= 1.0):
            raise ValueError("density fuori range (0.1..1.0)")


def _read_settings() -> dict:
    if os.path.isfile(SETTINGS_PATH):
        try:
            with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "latitude": 44.5,
        "longitude": 11.3,
        "altitude_m": 0.0,
        "pressure_mbar": 1013.25,
        "temperature_c": 10.0,
        "tz_offset_hours": 1.0,
    }


def _write_settings(data: dict) -> None:
    with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f)

# Sky config (planetario)
SKY_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "data", "sky_config.json")
os.makedirs(os.path.dirname(SKY_CONFIG_PATH), exist_ok=True)

def _read_sky_config() -> dict:
    if os.path.isfile(SKY_CONFIG_PATH):
        try:
            with open(SKY_CONFIG_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "maxmag": 5.0,
        "radius": 60.0,
        "show_below_horizon": False,
        "label_mag_threshold": 3.0,
        "density": 1.0,
    }

def _write_sky_config(data: dict) -> None:
    with open(SKY_CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f)


def _observer_and_time(now_ts: float | None = None):
    cfg = _read_settings()
    ts = load.timescale()
    if now_ts is None:
        t = ts.now()
    else:
        import datetime
        t = ts.from_datetime(datetime.datetime.utcfromtimestamp(float(now_ts)))
    obs = wgs84.latlon(cfg["latitude"], cfg["longitude"], cfg.get("altitude_m", 0.0))
    return obs, t, cfg


def ra_dec_to_altaz(ra_deg: float, dec_deg: float, cfg: dict, timestamp: float | None = None):
    obs, t, _ = _observer_and_time(timestamp)
    star = Star(ra_hours=ra_deg / 15.0, dec_degrees=dec_deg)
    app = obs.at(t).observe(star).apparent()
    alt, az, _ = app.altaz(temperature_C=cfg.get("temperature_c", 10.0), pressure_mbar=cfg.get("pressure_mbar", 1013.25))
    return alt.degrees, az.degrees


def altaz_to_ra_dec(alt_deg: float, az_deg: float, cfg: dict, timestamp: float | None = None):
    # Invert observing geometry numerically: approximate by local sidereal time and trig (no planetary kernel)
    lat = math.radians(cfg["latitude"])
    alt = math.radians(alt_deg)
    az = math.radians(az_deg)
    # hour angle formula
    sin_dec = math.sin(alt) * math.sin(lat) + math.cos(alt) * math.cos(lat) * math.cos(az)
    dec = math.asin(max(-1.0, min(1.0, sin_dec)))
    cos_h = (math.sin(alt) - math.sin(lat) * sin_dec) / (math.cos(lat) * math.cos(dec) + 1e-12)
    cos_h = max(-1.0, min(1.0, cos_h))
    h = math.acos(cos_h)
    if math.sin(az) > 0:
        h = 2 * math.pi - h
    # approximate LST via Skyfield timescale and sidereal_time()
    ts = load.timescale()
    if timestamp is None:
        t = ts.now()
    else:
        import datetime
        t = ts.from_datetime(datetime.datetime.utcfromtimestamp(float(timestamp)))
    lst_deg = t.gast.degrees  # GAST in degrees
    ra = (lst_deg - math.degrees(h)) % 360.0
    return ra, math.degrees(dec)


def zenith_radec(cfg: dict, timestamp: float | None = None):
    obs, t, _ = _observer_and_time(timestamp)
    radec = obs.at(t).from_altaz(alt_degrees=90.0, az_degrees=0.0).radec()
    return radec[0].hours * 15.0, radec[1].degrees


def _load_bright_stars():
    stars = []
    if BRIGHT_PATH.is_file():
        try:
            with open(BRIGHT_PATH, "r", encoding="utf-8") as f:
                stars = json.load(f)
        except Exception:
            stars = []
    return stars


def _load_constellations():
    consts = []
    if CONSTELLATIONS_PATH.is_file():
        try:
            with open(CONSTELLATIONS_PATH, "r", encoding="utf-8") as f:
                consts = json.load(f)
        except Exception:
            consts = []
    return consts


def _load_constellation_boundaries():
    consts = []
    if CONSTELLATION_BOUNDARIES_PATH.is_file():
        try:
            with open(CONSTELLATION_BOUNDARIES_PATH, "r", encoding="utf-8") as f:
                consts = json.load(f)
        except Exception:
            consts = []
    return consts


_GAIA_CONE_CACHE: dict[tuple, dict] = {}

def _gaia_lookup_cone(ra_deg: float, dec_deg: float, radius_deg: float, maxmag: float = 4.0, limit: int = 50):
    # Cache chiave arrotondata per ridurre duplicati
    key = (round(float(ra_deg), 2), round(float(dec_deg), 2), round(float(radius_deg), 1), round(float(maxmag), 1))
    now = time.time()
    cache_entry = _GAIA_CONE_CACHE.get(key)
    if cache_entry and (now - cache_entry.get("ts", 0)) < 300:
        return cache_entry.get("stars", [])

    exe = next((e for e in GAIA_EXE_CANDIDATES if e and os.path.isfile(e)), None)
    if not exe:
        return []
    try:
        proc = subprocess.run(
            [exe, "--cone", str(ra_deg), str(dec_deg), str(radius_deg), "--maxmag", str(maxmag)],
            capture_output=True,
            text=True,
            timeout=6,
        )
        if proc.returncode != 0 or not proc.stdout:
            return []
        data = json.loads(proc.stdout)
        if not isinstance(data, list):
            return []
        # Normalize keys
        out = []
        for s in data[:limit * 5]:  # take some extra before filtering alt
            try:
                out.append({
                    "name": s.get("designation") or s.get("name") or str(s.get("source_id", "")),
                    "ra_deg": float(s.get("ra") or s.get("ra_deg")),
                    "dec_deg": float(s.get("dec") or s.get("dec_deg")),
                    "mag": s.get("mag") if s.get("mag") is not None else s.get("phot_g_mean_mag") or s.get("mag_g"),
                })
            except Exception:
                continue
        _GAIA_CONE_CACHE[key] = {"stars": out, "ts": now}
        return out
    except Exception:
        return []


@app.get("/api/sky/constellations")
def api_sky_constellations(timestamp: float | None = None, show_below_horizon: bool = False):
    """Ritorna linee delle costellazioni come segmenti Alt/Az."""
    try:
        cfg = _read_settings()
        consts = _load_constellations()
        out = []
        for c in consts:
            segments_out = []
            for seg in c.get("lines", []):
                if not isinstance(seg, list) or len(seg) != 2:
                    continue
                try:
                    (ra1, dec1), (ra2, dec2) = seg
                    alt1, az1 = ra_dec_to_altaz(float(ra1), float(dec1), cfg, timestamp)
                    alt2, az2 = ra_dec_to_altaz(float(ra2), float(dec2), cfg, timestamp)
                    if not show_below_horizon and alt1 < 0 and alt2 < 0:
                        continue
                    segments_out.append({
                        "from": {"alt": alt1, "az": az1},
                        "to": {"alt": alt2, "az": az2}
                    })
                except Exception:
                    continue
            if segments_out:
                out.append({
                    "name": c.get("name", ""),
                    "abbrev": c.get("abbrev"),
                    "segments": segments_out
                })
        return {"ok": True, "constellations": out}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/sky/constellations/boundaries")
def api_sky_constellation_boundaries(timestamp: float | None = None, show_below_horizon: bool = False):
    """Ritorna confini delle costellazioni come segmenti Alt/Az."""
    try:
        cfg = _read_settings()
        consts = _load_constellation_boundaries()
        out = []
        for c in consts:
            segs_out = []
            boundary = c.get("boundary", [])
            if not boundary or len(boundary) < 2:
                continue
            # connect consecutive points
            for i in range(len(boundary) - 1):
                try:
                    ra1, dec1 = boundary[i]
                    ra2, dec2 = boundary[i + 1]
                    alt1, az1 = ra_dec_to_altaz(float(ra1), float(dec1), cfg, timestamp)
                    alt2, az2 = ra_dec_to_altaz(float(ra2), float(dec2), cfg, timestamp)
                    if not show_below_horizon and alt1 < 0 and alt2 < 0:
                        continue
                    segs_out.append({"from": {"alt": alt1, "az": az1}, "to": {"alt": alt2, "az": az2}})
                except Exception:
                    continue
            if segs_out:
                out.append({
                    "name": c.get("name", ""),
                    "abbrev": c.get("abbrev"),
                    "segments": segs_out
                })
        return {"ok": True, "constellations": out}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/settings")
def api_get_settings() -> dict:
    return {"ok": True, "settings": _read_settings()}


@app.post("/api/settings")
def api_set_settings(body: SettingsBody) -> dict:
    body.validate_ranges()
    data = body.model_dump()
    _write_settings(data)
    return {"ok": True, "settings": data}


# -------- Sky Config (planetario) --------
@app.get("/api/sky/config")
def api_get_sky_config() -> dict:
    """Ritorna la configurazione del planetario (sky)."""
    return {"ok": True, "config": _read_sky_config()}


@app.post("/api/sky/config")
def api_set_sky_config(body: SkyConfigBody) -> dict:
    """Aggiorna la configurazione del planetario (sky)."""
    body.validate_ranges()
    data = body.model_dump()
    _write_sky_config(data)
    return {"ok": True, "config": data}


# -------- Resolve by ID --------
@app.get("/api/resolve")
def api_resolve(
    sao: str | None = None,
    hip: str | None = None,
    hd: str | None = None,
    name: str | None = None,
):
    try:
        # Prova catalogo locale (Crossreference)
        if sao:
            e = local_catalog.lookup_sao(sao)
            if e:
                return {"ok": True, "result": e, "source": "local"}
            # Fallback online
            e = resolve_id_via_gaia("sao", sao)
            if e:
                return {"ok": True, "result": e.__dict__, "source": "online"}
        if hip:
            e = local_catalog.lookup_hip(hip)
            if e:
                return {"ok": True, "result": e, "source": "local"}
            # Fallback online
            e = resolve_id_via_gaia("hip", hip)
            if e:
                return {"ok": True, "result": e.__dict__, "source": "online"}
        if hd:
            e = local_catalog.lookup_hd(hd)
            if e:
                return {"ok": True, "result": e, "source": "local"}
            # Fallback online
            e = resolve_id_via_gaia("hd", hd)
            if e:
                return {"ok": True, "result": e.__dict__, "source": "online"}
        if name:
            # Prova locale prima
            res_local = local_catalog.search_by_name(name, limit=1)
            if res_local:
                return {"ok": True, "result": res_local[0], "source": "local"}
            # Fallback online
            res = resolve_name(name, limit=1)
            if res:
                return {"ok": True, "result": res[0].__dict__, "source": "online"}
        return {"ok": False}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# -------- Camera MJPEG stream --------
def _mjpeg_generator(camera_index: int = 0):
    if cv2 is None:
        raise RuntimeError("OpenCV non installato. Installa opencv-python o configura ffmpeg.")
    cap = cv2.VideoCapture(camera_index)
    if not cap.isOpened():
        raise RuntimeError(f"Impossibile aprire la camera index {camera_index}")
    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                continue
            ok2, enc = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
            if not ok2:
                continue
            data = enc.tobytes()
            yield (b"--frame\r\n"
                   b"Content-Type: image/jpeg\r\n\r\n" + data + b"\r\n")
    finally:
        cap.release()


@app.get("/api/video.mjpg")
def api_video(camera_index: int = 0):
    try:
        return StreamingResponse(_mjpeg_generator(camera_index), media_type='multipart/x-mixed-replace; boundary=frame')
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# -------- Camera Control API --------

@app.get("/api/camera/devices")
def api_camera_list_devices():
    """Lista tutti i device video disponibili."""
    try:
        devices = camera_controller.list_devices(max_check=10)
        return {"devices": devices, "count": len(devices)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/camera/open")
def api_camera_open(device_index: int = 0):
    """Apre device camera e ritorna capabilities."""
    try:
        result = camera_controller.open_device(device_index)
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/camera/close")
def api_camera_close():
    """Chiude device camera corrente."""
    try:
        camera_controller.close_device()
        return {"status": "closed"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


class CameraSettingsBody(BaseModel):
    exposure: Optional[int] = Field(None, description="Esposizione ms (-1=auto)")
    gain: Optional[int] = Field(None, description="Gain 0-100 (-1=auto)")
    binning: Optional[int] = Field(None, description="Binning 1/2/4")
    width: Optional[int] = Field(None, description="Larghezza frame")
    height: Optional[int] = Field(None, description="Altezza frame")
    fps: Optional[float] = Field(None, description="Frame rate")
    brightness: Optional[int] = Field(None, description="Luminosità 0-100 (-1=auto)")
    contrast: Optional[int] = Field(None, description="Contrasto 0-100 (-1=auto)")
    saturation: Optional[int] = Field(None, description="Saturazione 0-100 (-1=auto)")
    hue: Optional[int] = Field(None, description="Tonalità -180 to 180 (-1=auto)")
    sharpness: Optional[int] = Field(None, description="Nitidezza 0-100 (-1=auto)")
    gamma: Optional[int] = Field(None, description="Gamma 0-300 (-1=auto)")
    white_balance: Optional[int] = Field(None, description="Bilanciamento bianco 2000-7500K (-1=auto)")
    backlight: Optional[int] = Field(None, description="Compensazione controluce 0-1 (-1=auto)")
    focus: Optional[int] = Field(None, description="Fuoco 0-255 (-1=auto)")
    zoom: Optional[int] = Field(None, description="Zoom digitale 100-500 (-1=auto)")
    iso: Optional[int] = Field(None, description="Sensibilità ISO 100-6400 (-1=auto)")


@app.get("/api/camera/settings")
def api_camera_get_settings():
    """Ritorna settings camera correnti."""
    return camera_controller.get_settings()


@app.post("/api/camera/settings")
def api_camera_update_settings(body: CameraSettingsBody):
    """Aggiorna settings camera."""
    try:
        kwargs = {k: v for k, v in body.dict().items() if v is not None}
        settings = camera_controller.update_settings(**kwargs)
        return {"status": "updated", "settings": settings}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/camera/start")
def api_camera_start_capture():
    """Avvia capture continua."""
    try:
        camera_controller.start_capture()
        return {"status": "capturing", "message": "Capture started"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/camera/stop")
def api_camera_stop_capture():
    """Ferma capture continua."""
    try:
        camera_controller.stop_capture()
        return {"status": "stopped", "message": "Capture stopped"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/camera/frame")
def api_camera_get_frame():
    """Ritorna ultimo frame come base64 JPEG."""
    try:
        import base64
        frame = camera_controller.get_frame()
        if frame is None:
            raise HTTPException(status_code=404, detail="No frame available")
        
        # Encode come JPEG
        ok, buffer = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
        if not ok:
            raise HTTPException(status_code=500, detail="JPEG encode failed")
        
        # Base64 encode
        jpg_base64 = base64.b64encode(buffer).decode('utf-8')
        
        return {
            "frame": jpg_base64,
            "width": frame.shape[1],
            "height": frame.shape[0],
            "format": "jpeg"
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/camera/capture")
def api_camera_capture_single():
    """Cattura singolo frame e ritorna statistics."""
    try:
        frame = camera_controller.capture_single(timeout=5.0)
        stats = camera_controller.compute_statistics(frame)
        
        return {
            "status": "captured",
            "width": frame.shape[1],
            "height": frame.shape[0],
            "statistics": stats
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/camera/statistics")
def api_camera_statistics():
    """Calcola e ritorna statistiche ultimo frame."""
    try:
        stats = camera_controller.compute_statistics()
        if not stats:
            raise HTTPException(status_code=404, detail="No frame available")
        return stats
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/camera/fwhm")
def api_camera_fwhm():
    """Stima FWHM per valutazione focus."""
    try:
        fwhm = camera_controller.estimate_fwhm()
        return {
            "fwhm": fwhm,
            "unit": "pixels",
            "quality": "good" if 2.0 < fwhm < 5.0 else "poor" if fwhm > 0 else "no_stars"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class SaveFitsBody(BaseModel):
    filename: Optional[str] = Field(None, description="Nome file (auto se omesso)")
    target: Optional[str] = Field(None, description="Nome target")
    ra: Optional[float] = Field(None, description="RA gradi")
    dec: Optional[float] = Field(None, description="Dec gradi")
    telescope: Optional[str] = Field(None, description="Nome telescopio")
    observer: Optional[str] = Field(None, description="Nome osservatore")
    pixel_scale_arcsec: Optional[float] = Field(None, description="Arcsec/pixel per WCS")
    rotation_deg: Optional[float] = Field(None, description="Rotazione immagine (deg)")
    output_dir: str = Field("data/images", description="Directory output")


@app.post("/api/camera/save-fits")
def api_camera_save_fits(body: SaveFitsBody):
    """Cattura frame e salva come FITS con metadata."""
    try:
        # Cattura frame
        frame = camera_controller.capture_single(timeout=5.0)
        
        # Prepara metadata
        metadata = {}
        if body.target:
            metadata['OBJECT'] = body.target
        if body.ra is not None:
            metadata['RA'] = body.ra
        if body.dec is not None:
            metadata['DEC'] = body.dec
        if body.telescope:
            metadata['TELESCOP'] = body.telescope
        if body.observer:
            metadata['OBSERVER'] = body.observer
        
        # Aggiungi sito da settings
        if site_settings.get("latitude"):
            metadata['SITELAT'] = site_settings["latitude"]
            metadata['SITELONG'] = site_settings["longitude"]
            metadata['SITEELEV'] = site_settings["elevation"]
        
        # Salva FITS
        wcs_info = None
        if body.pixel_scale_arcsec and body.ra is not None and body.dec is not None:
            wcs_info = {
                "ra_deg": body.ra,
                "dec_deg": body.dec,
                "pixel_scale_arcsec": body.pixel_scale_arcsec,
                "rotation_deg": body.rotation_deg or 0.0,
            }

        filepath = camera_controller.save_fits(
            frame,
            body.filename or "",
            metadata,
            output_dir=body.output_dir,
            wcs_info=wcs_info,
        )
        
        # Calcola statistiche
        stats = camera_controller.compute_statistics(frame)
        
        return {
            "status": "saved",
            "filepath": filepath,
            "filename": pathlib.Path(filepath).name,
            "statistics": stats
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# -------- Video Recording & Image Sequences API --------

class StartRecordingBody(BaseModel):
    filename: Optional[str] = Field(None, description="Nome file (senza estensione)")
    codec: str = Field("mp4v", description="Codec: mp4v, XVID, MJPEG, H264")
    output_dir: str = Field("data/recordings", description="Directory output")


class StartSequenceBody(BaseModel):
    count: int = Field(..., description="Numero immagini da catturare")
    interval: float = Field(0.0, description="Intervallo tra catture (secondi)")
    filename_prefix: Optional[str] = Field(None, description="Prefisso nome file")
    save_format: str = Field("fits", description="Formato: fits, png, jpg")
    output_dir: str = Field("data/sequences", description="Directory output")
    target: Optional[str] = Field(None, description="Nome target per metadata FITS")
    ra: Optional[float] = Field(None, description="RA target (gradi)")
    dec: Optional[float] = Field(None, description="Dec target (gradi)")


class LiveStackStartBody(BaseModel):
    interval: float = Field(0.5, description="Intervallo polling frame (s)")
    max_frames: Optional[int] = Field(None, description="Stop automatico dopo N frame (0=illimitato)")
    normalize: bool = Field(True, description="Normalizza preview 0-255")


class LiveStackSaveBody(BaseModel):
    filename: Optional[str] = Field(None, description="Nome file senza estensione")
    fmt: str = Field("fits", description="Formato fits o png")
    target: Optional[str] = Field(None, description="Nome target")
    ra: Optional[float] = Field(None, description="RA centro (deg)")
    dec: Optional[float] = Field(None, description="Dec centro (deg)")
    pixel_scale_arcsec: Optional[float] = Field(None, description="Arcsec/pixel per WCS")
    rotation_deg: Optional[float] = Field(None, description="Rotazione immagine (deg)")
    output_dir: str = Field("data/stacking", description="Directory output")


class CalibrationStartBody(BaseModel):
    calib_type: str = Field(..., description="Tipo calibrazione: dark, flat, bias")
    count: int = Field(10, description="Numero frame")
    interval: float = Field(0.0, description="Intervallo tra frame (s)")
    exposure: Optional[float] = Field(None, description="Esposizione ms (override)")
    gain: Optional[int] = Field(None, description="Gain (override)")
    output_dir: str = Field("data/calibration", description="Directory base")
    metadata: Optional[dict] = Field(None, description="Metadata aggiuntivi per FITS")


@app.post("/api/camera/recording/start")
def api_camera_start_recording(body: StartRecordingBody):
    """Avvia registrazione video."""
    try:
        info = camera_controller.start_recording(
            filename=body.filename,
            codec=body.codec,
            output_dir=body.output_dir
        )
        return info
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/camera/recording/stop")
def api_camera_stop_recording():
    """Ferma registrazione video."""
    try:
        result = camera_controller.stop_recording()
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/camera/recording/status")
def api_camera_recording_status():
    """Ritorna stato registrazione corrente."""
    try:
        return camera_controller.get_recording_status()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/camera/sequence/start")
def api_camera_start_sequence(body: StartSequenceBody):
    """Avvia acquisizione sequenza immagini."""
    try:
        # Prepara metadata per FITS
        metadata = {}
        if body.target:
            metadata['OBJECT'] = body.target
        if body.ra is not None:
            metadata['RA'] = body.ra
        if body.dec is not None:
            metadata['DEC'] = body.dec
        
        # Aggiungi sito
        if site_settings.get("latitude"):
            metadata['SITELAT'] = site_settings["latitude"]
            metadata['SITELONG'] = site_settings["longitude"]
            metadata['SITEELEV'] = site_settings["elevation"]
        
        info = camera_controller.start_image_sequence(
            count=body.count,
            interval=body.interval,
            filename_prefix=body.filename_prefix,
            save_format=body.save_format,
            output_dir=body.output_dir,
            metadata=metadata if body.save_format == "fits" else None
        )
        return info
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/camera/sequence/stop")
def api_camera_stop_sequence():
    """Ferma acquisizione sequenza."""
    try:
        result = camera_controller.stop_image_sequence()
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/camera/sequence/status")
def api_camera_sequence_status():
    """Ritorna stato sequenza corrente."""
    try:
        return camera_controller.get_sequence_status()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# -------- Live Stacking API --------

@app.post("/api/camera/live-stack/start")
def api_live_stack_start(body: LiveStackStartBody):
    try:
        status = camera_controller.start_live_stack(
            interval=body.interval,
            max_frames=body.max_frames or 0,
            normalize=body.normalize,
        )
        return status
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/camera/live-stack/stop")
def api_live_stack_stop():
    try:
        return camera_controller.stop_live_stack()
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/camera/live-stack/status")
def api_live_stack_status():
    try:
        return camera_controller.get_live_stack_status()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/camera/live-stack/save")
def api_live_stack_save(body: LiveStackSaveBody):
    try:
        metadata = {}
        if body.target:
            metadata['OBJECT'] = body.target
        if site_settings.get("latitude"):
            metadata['SITELAT'] = site_settings["latitude"]
            metadata['SITELONG'] = site_settings["longitude"]
            metadata['SITEELEV'] = site_settings["elevation"]

        wcs_info = None
        if body.pixel_scale_arcsec and body.ra is not None and body.dec is not None:
            wcs_info = {
                "ra_deg": body.ra,
                "dec_deg": body.dec,
                "pixel_scale_arcsec": body.pixel_scale_arcsec,
                "rotation_deg": body.rotation_deg or 0.0,
            }

        filepath = camera_controller.save_live_stack(
            filename=body.filename,
            fmt=body.fmt,
            metadata=metadata,
            wcs_info=wcs_info,
            output_dir=body.output_dir,
        )
        return {"status": "saved", "filepath": filepath}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# -------- Calibration Automation API --------

@app.post("/api/calibration/start")
def api_calibration_start(body: CalibrationStartBody):
    try:
        return calibration_manager.start(
            calib_type=body.calib_type,
            count=body.count,
            interval=body.interval,
            exposure=body.exposure,
            gain=body.gain,
            output_dir=body.output_dir,
            metadata=body.metadata,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/calibration/stop")
def api_calibration_stop():
    try:
        return calibration_manager.stop()
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/calibration/status")
def api_calibration_status():
    try:
        return calibration_manager.get_status()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# -------- Watec 910BD Control API --------

class WatecConnectBody(BaseModel):
    port: Optional[str] = Field(None, description="Porta seriale (auto-detect se None)")


class WatecGammaBody(BaseModel):
    gamma: str = Field(..., description="Gamma: 0.45, 0.50, o OFF")


class WatecShutterBody(BaseModel):
    multiplier: int = Field(..., description="Moltiplicatore shutter: 1-256 (potenze di 2)")


class WatecAGCBody(BaseModel):
    enabled: bool = Field(..., description="AGC abilitato/disabilitato")


class WatecGainBody(BaseModel):
    gain: int = Field(..., description="Gain manuale 0-255 (solo se AGC disabilitato)")


class WatecAWBBody(BaseModel):
    enabled: bool = Field(..., description="Auto White Balance abilitato/disabilitato")


class WatecBLCBody(BaseModel):
    enabled: bool = Field(..., description="Back Light Compensation abilitato/disabilitato")


class WatecPresetBody(BaseModel):
    preset: str = Field(..., description="Preset: lunar, planetary, deepsky, occultation")


@app.post("/api/camera/watec/connect")
def api_watec_connect(body: WatecConnectBody):
    """Connette alla Watec 910BD via USB (sistema TACOS Arduino)."""
    if not camera_controller.watec:
        raise HTTPException(status_code=503, detail="Supporto Watec non disponibile (pyserial mancante)")
    
    try:
        success = camera_controller.watec.connect(body.port)
        if not success:
            raise HTTPException(status_code=404, detail="Watec 910BD non trovata o non risponde")
        
        # Marca che stiamo usando Watec (per logica ibrida)
        camera_controller.is_watec_camera = True
        
        return {
            "status": "connected",
            "port": camera_controller.watec.port_name,
            "config": camera_controller.watec.get_status()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/camera/watec/disconnect")
def api_watec_disconnect():
    """Disconnette dalla Watec 910BD."""
    if not camera_controller.watec:
        raise HTTPException(status_code=503, detail="Supporto Watec non disponibile")
    
    camera_controller.watec.disconnect()
    camera_controller.is_watec_camera = False
    
    return {"status": "disconnected"}


@app.get("/api/camera/watec/status")
def api_watec_status():
    """Ritorna stato corrente Watec 910BD."""
    if not camera_controller.watec:
        raise HTTPException(status_code=503, detail="Supporto Watec non disponibile")
    
    return camera_controller.watec.get_status()


@app.post("/api/camera/watec/gamma")
def api_watec_set_gamma(body: WatecGammaBody):
    """Imposta curva gamma Watec."""
    if not camera_controller.watec or not camera_controller.is_watec_camera:
        raise HTTPException(status_code=503, detail="Watec non connessa")
    
    try:
        success = camera_controller.watec.set_gamma(body.gamma)
        if not success:
            raise HTTPException(status_code=400, detail="Comando gamma fallito")
        return {"status": "ok", "gamma": body.gamma}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/camera/watec/shutter")
def api_watec_set_shutter(body: WatecShutterBody):
    """Imposta velocità shutter Watec."""
    if not camera_controller.watec or not camera_controller.is_watec_camera:
        raise HTTPException(status_code=503, detail="Watec non connessa")
    
    try:
        success = camera_controller.watec.set_shutter(body.multiplier)
        if not success:
            raise HTTPException(status_code=400, detail="Comando shutter fallito")
        
        status = camera_controller.watec.get_status()
        return {
            "status": "ok",
            "multiplier": body.multiplier,
            "shutter_speed": status["shutter_speed"]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/camera/watec/agc")
def api_watec_set_agc(body: WatecAGCBody):
    """Imposta AGC (Automatic Gain Control) Watec."""
    if not camera_controller.watec or not camera_controller.is_watec_camera:
        raise HTTPException(status_code=503, detail="Watec non connessa")
    
    try:
        success = camera_controller.watec.set_agc(body.enabled)
        if not success:
            raise HTTPException(status_code=400, detail="Comando AGC fallito")
        return {"status": "ok", "agc_enabled": body.enabled}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/camera/watec/gain")
def api_watec_set_gain(body: WatecGainBody):
    """Imposta gain manuale Watec (solo se AGC disabilitato)."""
    if not camera_controller.watec or not camera_controller.is_watec_camera:
        raise HTTPException(status_code=503, detail="Watec non connessa")
    
    try:
        success = camera_controller.watec.set_gain(body.gain)
        if not success:
            raise HTTPException(status_code=400, detail="Comando gain fallito (AGC abilitato?)")
        return {"status": "ok", "gain": body.gain}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/camera/watec/awb")
def api_watec_set_awb(body: WatecAWBBody):
    """Imposta Auto White Balance Watec."""
    if not camera_controller.watec or not camera_controller.is_watec_camera:
        raise HTTPException(status_code=503, detail="Watec non connessa")
    
    try:
        success = camera_controller.watec.set_awb(body.enabled)
        if not success:
            raise HTTPException(status_code=400, detail="Comando AWB fallito")
        return {"status": "ok", "awb_enabled": body.enabled}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/camera/watec/blc")
def api_watec_set_blc(body: WatecBLCBody):
    """Imposta Back Light Compensation Watec."""
    if not camera_controller.watec or not camera_controller.is_watec_camera:
        raise HTTPException(status_code=503, detail="Watec non connessa")
    
    try:
        success = camera_controller.watec.set_blc(body.enabled)
        if not success:
            raise HTTPException(status_code=400, detail="Comando BLC fallito")
        return {"status": "ok", "blc_enabled": body.enabled}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/camera/watec/preset")
def api_watec_apply_preset(body: WatecPresetBody):
    """Applica preset ottimizzato Watec (lunar, planetary, deepsky, occultation)."""
    if not camera_controller.watec or not camera_controller.is_watec_camera:
        raise HTTPException(status_code=503, detail="Watec non connessa")
    
    try:
        success = camera_controller.watec.apply_preset(body.preset)
        if not success:
            raise HTTPException(status_code=400, detail=f"Preset {body.preset} non valido o fallito")
        
        return {
            "status": "ok",
            "preset": body.preset,
            "config": camera_controller.watec.get_status()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# -------- Star-Hopping Planner --------
hop_session = {
    "active": False,
    "target_ra": None,
    "target_dec": None,
    "target_name": None,
    "steps": [],
    "current_step": 0,
    "completed_steps": []
}


# -------- Sequence Automation API --------

@app.get("/api/sequences")
def api_list_sequences():
    """Lista tutte le sequenze salvate."""
    try:
        sequences = ObservingSequence.list_all()
        return {"sequences": sequences, "count": len(sequences)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/sequences/{sequence_id}")
def api_get_sequence(sequence_id: str):
    """Ottiene sequenza completa con steps."""
    try:
        seq = ObservingSequence.load(sequence_id)
        if not seq:
            raise HTTPException(status_code=404, detail="Sequence not found")
        return seq.to_dict()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class CreateSequenceBody(BaseModel):
    name: str
    description: Optional[str] = ""
    target: Optional[str] = None


@app.post("/api/sequences")
def api_create_sequence(body: CreateSequenceBody):
    """Crea nuova sequenza."""
    try:
        seq = ObservingSequence(
            name=body.name,
            description=body.description or "",
            target=body.target
        )
        seq.save()
        return {"status": "created", "sequence": seq.to_dict()}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


class UpdateSequenceBody(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    target: Optional[str] = None


@app.put("/api/sequences/{sequence_id}")
def api_update_sequence(sequence_id: str, body: UpdateSequenceBody):
    """Aggiorna metadata sequenza."""
    try:
        seq = ObservingSequence.load(sequence_id)
        if not seq:
            raise HTTPException(status_code=404, detail="Sequence not found")
        
        if body.name:
            seq.name = body.name
        if body.description is not None:
            seq.description = body.description
        if body.target is not None:
            seq.target = body.target
        
        seq.modified_at = time.time()
        seq.save()
        
        return {"status": "updated", "sequence": seq.to_dict()}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.delete("/api/sequences/{sequence_id}")
def api_delete_sequence(sequence_id: str):
    """Elimina sequenza."""
    try:
        seq = ObservingSequence.load(sequence_id)
        if not seq:
            raise HTTPException(status_code=404, detail="Sequence not found")
        
        seq.delete()
        return {"status": "deleted", "sequence_id": sequence_id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


class AddStepBody(BaseModel):
    type: str
    name: Optional[str] = None
    params: dict


@app.post("/api/sequences/{sequence_id}/steps")
def api_add_step(sequence_id: str, body: AddStepBody):
    """Aggiunge step a sequenza."""
    try:
        seq = ObservingSequence.load(sequence_id)
        if not seq:
            raise HTTPException(status_code=404, detail="Sequence not found")
        
        step = SequenceStep(
            step_type=StepType(body.type),
            params=body.params,
            name=body.name
        )
        seq.add_step(step)
        seq.save()
        
        return {"status": "added", "step": step.to_dict()}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.delete("/api/sequences/{sequence_id}/steps/{step_id}")
def api_delete_step(sequence_id: str, step_id: str):
    """Rimuove step da sequenza."""
    try:
        seq = ObservingSequence.load(sequence_id)
        if not seq:
            raise HTTPException(status_code=404, detail="Sequence not found")
        
        seq.remove_step(step_id)
        seq.save()
        
        return {"status": "deleted", "step_id": step_id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/sequences/{sequence_id}/execute")
def api_execute_sequence(sequence_id: str):
    """Avvia esecuzione sequenza."""
    try:
        seq = ObservingSequence.load(sequence_id)
        if not seq:
            raise HTTPException(status_code=404, detail="Sequence not found")
        
        # Check if already executing
        existing = get_executor(sequence_id)
        if existing and existing.is_running:
            raise HTTPException(status_code=400, detail="Sequence already executing")
        
        # Reset step status
        seq.reset_status()
        
        # Create executor
        executor = SequenceExecutor(
            sequence=seq,
            lx200_getter=lambda: manager.get_lx200(),
            camera_controller=camera_controller
        )
        
        register_executor(sequence_id, executor)
        executor.start()
        
        return {"status": "started", "sequence_id": sequence_id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/sequences/{sequence_id}/pause")
def api_pause_sequence(sequence_id: str):
    """Mette in pausa esecuzione."""
    try:
        executor = get_executor(sequence_id)
        if not executor:
            raise HTTPException(status_code=404, detail="No active execution")
        
        executor.pause()
        return {"status": "paused"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/sequences/{sequence_id}/resume")
def api_resume_sequence(sequence_id: str):
    """Riprende esecuzione."""
    try:
        executor = get_executor(sequence_id)
        if not executor:
            raise HTTPException(status_code=404, detail="No active execution")
        
        executor.resume()
        return {"status": "resumed"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/sequences/{sequence_id}/abort")
def api_abort_sequence(sequence_id: str):
    """Interrompe esecuzione."""
    try:
        executor = get_executor(sequence_id)
        if not executor:
            raise HTTPException(status_code=404, detail="No active execution")
        
        executor.abort()
        unregister_executor(sequence_id)
        return {"status": "aborted"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/sequences/{sequence_id}/status")
def api_sequence_status(sequence_id: str):
    """Ottiene stato esecuzione corrente."""
    try:
        executor = get_executor(sequence_id)
        if not executor:
            return {"status": "not_running", "sequence_id": sequence_id}
        
        return executor.get_status()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def _angular_distance(ra1, dec1, ra2, dec2):
    """Calculate angular distance in degrees between two points."""
    ra1r = math.radians(ra1)
    dec1r = math.radians(dec1)
    ra2r = math.radians(ra2)
    dec2r = math.radians(dec2)
    cosd = math.sin(dec1r) * math.sin(dec2r) + math.cos(dec1r) * math.cos(dec2r) * math.cos(ra1r - ra2r)
    cosd = max(-1.0, min(1.0, cosd))
    return math.degrees(math.acos(cosd))


def _plan_star_hop(start_ra, start_dec, target_ra, target_dec, max_steps=5, max_mag=4.0, max_spacing=10.0):
    """
    Plan a star-hopping path from current position to target.
    Uses greedy algorithm to find bright stars along the great circle path.
    """
    steps = []
    current_ra = start_ra
    current_dec = start_dec
    
    total_distance = _angular_distance(start_ra, start_dec, target_ra, target_dec)
    if total_distance < max_spacing:
        # Direct hop possible
        return []
    
    for i in range(max_steps):
        remaining = _angular_distance(current_ra, current_dec, target_ra, target_dec)
        if remaining < max_spacing:
            # Close enough to target
            break
        
        # Search for stars in corridor toward target
        # Use cone search centered on midpoint between current and target
        mid_ra = (current_ra + target_ra) / 2
        mid_dec = (current_dec + target_dec) / 2
        radius = min(remaining / 2 + 5, 30.0)  # Adaptive search radius
        
        candidates = _gaia_lookup_cone(mid_ra, mid_dec, radius, max_mag, limit=100)
        if not candidates:
            # No stars found, fallback to direct hop
            break
        
        # Filter and score candidates
        cfg = _read_settings()
        best_star = None
        best_score = float('inf')
        
        for star in candidates:
            # Check if star is above horizon
            alt, az = ra_dec_to_altaz(star["ra_deg"], star["dec_deg"], cfg)
            if alt < 20:
                continue
            
            # Calculate distances
            dist_from_current = _angular_distance(current_ra, current_dec, star["ra_deg"], star["dec_deg"])
            dist_to_target = _angular_distance(star["ra_deg"], star["dec_deg"], target_ra, target_dec)
            
            # Skip if too close or too far
            if dist_from_current < 2 or dist_from_current > max_spacing:
                continue
            
            # Score: prefer stars that reduce distance to target and are bright
            # Lower score is better
            progress = remaining - dist_to_target
            if progress < 0:
                continue  # Star moves us away from target
            
            score = dist_to_target + (star.get("mag", 5.0) * 2) - (progress * 3)
            
            if score < best_score:
                best_score = score
                best_star = star
        
        if not best_star:
            # No suitable star found
            break
        
        # Add to path
        alt, az = ra_dec_to_altaz(best_star["ra_deg"], best_star["dec_deg"], cfg)
        steps.append({
            "name": best_star.get("name", f"HOP-{i+1}"),
            "ra_deg": best_star["ra_deg"],
            "dec_deg": best_star["dec_deg"],
            "alt_deg": alt,
            "az_deg": az,
            "mag": best_star.get("mag", 5.0),
            "distance_from_prev": _angular_distance(current_ra, current_dec, best_star["ra_deg"], best_star["dec_deg"]),
            "distance_to_target": _angular_distance(best_star["ra_deg"], best_star["dec_deg"], target_ra, target_dec)
        })
        
        current_ra = best_star["ra_deg"]
        current_dec = best_star["dec_deg"]
    
    return steps


class PlanHopBody(BaseModel):
    target_ra: float = Field(..., description="Target RA in degrees")
    target_dec: float = Field(..., description="Target Dec in degrees")
    target_name: Optional[str] = None
    max_steps: int = Field(5, ge=1, le=10)
    max_mag: float = Field(4.0, ge=0, le=10)
    max_spacing: float = Field(10.0, ge=2, le=30)


@app.post("/api/plan-hop")
def api_plan_hop(body: PlanHopBody):
    """
    Plan star-hopping path to target.
    Returns list of intermediate stars to guide telescope.
    """
    try:
        # Get current position
        lx = manager.get_lx200()
        ra_str = lx.get_ra()
        dec_str = lx.get_dec()
        
        # Parse to degrees
        hh, mm, ss = [float(p) for p in ra_str.split(":")]
        start_ra = (hh + mm/60 + ss/3600) * 15.0
        
        sign = -1 if dec_str.startswith('-') else 1
        d_str, mmss = dec_str[1:].split('*')
        m_str, s_str = mmss.split(":")
        start_dec = sign * (float(d_str) + float(m_str)/60 + float(s_str)/3600)
        
        # Plan path
        steps = _plan_star_hop(
            start_ra, start_dec,
            body.target_ra, body.target_dec,
            body.max_steps, body.max_mag, body.max_spacing
        )
        
        # Add final target
        cfg = _read_settings()
        target_alt, target_az = ra_dec_to_altaz(body.target_ra, body.target_dec, cfg)
        final_step = {
            "name": body.target_name or "TARGET",
            "ra_deg": body.target_ra,
            "dec_deg": body.target_dec,
            "alt_deg": target_alt,
            "az_deg": target_az,
            "mag": None,
            "distance_from_prev": _angular_distance(
                steps[-1]["ra_deg"] if steps else start_ra,
                steps[-1]["dec_deg"] if steps else start_dec,
                body.target_ra, body.target_dec
            ),
            "distance_to_target": 0.0
        }
        steps.append(final_step)
        
        # Update session
        hop_session["active"] = True
        hop_session["target_ra"] = body.target_ra
        hop_session["target_dec"] = body.target_dec
        hop_session["target_name"] = body.target_name
        hop_session["steps"] = steps
        hop_session["current_step"] = 0
        hop_session["completed_steps"] = []
        
        return {
            "ok": True,
            "steps": steps,
            "total_steps": len(steps),
            "estimated_time_minutes": len(steps) * 2  # Rough estimate
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/hop/status")
def api_hop_status():
    """Get current star-hopping session status."""
    return {
        "ok": True,
        "session": hop_session
    }


@app.get("/api/hop/next")
def api_hop_next():
    """Get next step in star-hopping sequence."""
    if not hop_session["active"]:
        raise HTTPException(status_code=400, detail="No active hop session")
    
    if hop_session["current_step"] >= len(hop_session["steps"]):
        return {
            "ok": True,
            "completed": True,
            "message": "Star-hopping sequence complete!"
        }
    
    step = hop_session["steps"][hop_session["current_step"]]
    return {
        "ok": True,
        "step": step,
        "step_number": hop_session["current_step"] + 1,
        "total_steps": len(hop_session["steps"])
    }


class HopConfirmBody(BaseModel):
    step_number: int


@app.post("/api/hop/confirm")
def api_hop_confirm(body: HopConfirmBody):
    """Mark current step as completed and advance to next."""
    if not hop_session["active"]:
        raise HTTPException(status_code=400, detail="No active hop session")
    
    if body.step_number != hop_session["current_step"] + 1:
        raise HTTPException(status_code=400, detail="Step number mismatch")
    
    # Mark completed
    hop_session["completed_steps"].append(body.step_number)
    hop_session["current_step"] += 1
    
    # Check if done
    if hop_session["current_step"] >= len(hop_session["steps"]):
        return {
            "ok": True,
            "completed": True,
            "message": "Star-hopping complete! Target reached."
        }
    
    # Return next step
    next_step = hop_session["steps"][hop_session["current_step"]]
    return {
        "ok": True,
        "completed": False,
        "next_step": next_step,
        "step_number": hop_session["current_step"] + 1,
        "total_steps": len(hop_session["steps"])
    }


@app.post("/api/hop/reset")
def api_hop_reset():
    """Reset star-hopping session."""
    hop_session["active"] = False
    hop_session["target_ra"] = None
    hop_session["target_dec"] = None
    hop_session["target_name"] = None
    hop_session["steps"] = []
    hop_session["current_step"] = 0
    hop_session["completed_steps"] = []
    return {"ok": True, "message": "Hop session reset"}


# -------- Session Management API --------

session_state = {
    "current_session_id": None,
    "session": None
}


@app.post("/api/sessions")
def api_create_session():
    """Create new observing session."""
    cfg = _read_settings()
    session_id = SessionManager.create_session(site_id=cfg.get("site_id", "Observatory"))
    session_state["current_session_id"] = session_id
    return {
        "ok": True,
        "session_id": session_id
    }


@app.get("/api/sessions")
def api_list_sessions(limit: int = 50):
    """List observing sessions."""
    sessions = SessionManager.list_sessions(limit=limit)
    return {
        "ok": True,
        "sessions": sessions
    }


@app.get("/api/sessions/{session_id}")
def api_get_session(session_id: str):
    """Get session details."""
    session = SessionManager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    summary = SessionManager.get_session_summary(session_id)
    return {
        "ok": True,
        "session": session,
        "summary": summary
    }


@app.post("/api/sessions/{session_id}/set-target")
def api_session_set_target(session_id: str, body: dict):
    """Set target for session."""
    SessionManager.update_session(
        session_id,
        target_name=body.get("name"),
        target_ra=body.get("ra_deg"),
        target_dec=body.get("dec_deg")
    )
    return {"ok": True}


@app.post("/api/sessions/{session_id}/log-alignment")
def api_session_log_alignment(session_id: str, body: dict):
    """Log alignment point."""
    align_id = SessionManager.log_alignment(
        session_id,
        star_name=body.get("star_name"),
        ra_deg=body.get("ra_deg"),
        dec_deg=body.get("dec_deg"),
        alt_deg=body.get("alt_deg"),
        az_deg=body.get("az_deg"),
        residual_arcmin=body.get("residual_arcmin", 0)
    )
    return {"ok": True, "alignment_id": align_id}


@app.post("/api/sessions/{session_id}/log-sync")
def api_session_log_sync(session_id: str, body: dict):
    """Log mount sync."""
    sync_id = SessionManager.log_sync(
        session_id,
        ra_deg=body.get("ra_deg"),
        dec_deg=body.get("dec_deg"),
        pointing_ra=body.get("pointing_ra"),
        pointing_dec=body.get("pointing_dec"),
        alignment_quality=body.get("alignment_quality", 0)
    )
    return {"ok": True, "sync_id": sync_id}


@app.post("/api/sessions/{session_id}/log-observation")
def api_session_log_observation(session_id: str, body: dict):
    """Log observation."""
    obs_id = SessionManager.log_observation(
        session_id,
        object_name=body.get("object_name"),
        ra_deg=body.get("ra_deg"),
        dec_deg=body.get("dec_deg"),
        obs_type=body.get("obs_type"),
        duration_sec=body.get("duration_sec"),
        exposure_sec=body.get("exposure_sec"),
        gain=body.get("gain"),
        binning=body.get("binning"),
        notes=body.get("notes", "")
    )
    return {"ok": True, "observation_id": obs_id}


@app.get("/api/sessions/{session_id}/alignments")
def api_get_session_alignments(session_id: str):
    """Get alignment log."""
    alignments = SessionManager.get_session_alignments(session_id)
    return {"ok": True, "alignments": alignments}


@app.get("/api/sessions/{session_id}/syncs")
def api_get_session_syncs(session_id: str):
    """Get sync log."""
    syncs = SessionManager.get_session_syncs(session_id)
    return {"ok": True, "syncs": syncs}


@app.get("/api/sessions/{session_id}/observations")
def api_get_session_observations(session_id: str):
    """Get observation log."""
    observations = SessionManager.get_session_observations(session_id)
    return {"ok": True, "observations": observations}


@app.get("/api/sessions/{session_id}/export")
def api_export_session(session_id: str):
    """Export session as JSON."""
    export_data = SessionManager.export_session_json(session_id)
    if not export_data:
        raise HTTPException(status_code=404, detail="Session not found")
    
    return {"ok": True, "data": export_data}


# ============================================================================
# Analytics Endpoints (M9)
# ============================================================================

@app.get("/api/analytics/summary")
def api_analytics_summary():
    """Get global analytics summary.
    
    Returns:
        - total_sessions: Number of recorded sessions
        - total_observations: Total observations across all sessions
        - total_alignments: Total alignment points
        - mean_alignment_residual: Average residual in arcminutes
        - total_observation_time: Total integration time in seconds
        - unique_objects: Number of unique objects observed
    """
    sessions = SessionManager.get_all_sessions_with_stats()
    
    total_sessions = len(sessions)
    total_observations = sum(s.get("observation_count", 0) for s in sessions)
    total_alignments = sum(s.get("alignment_count", 0) for s in sessions)
    
    residuals = [s.get("alignment_residual_mean", 0) for s in sessions if s.get("alignment_residual_mean")]
    mean_residual = sum(residuals) / len(residuals) if residuals else 0
    
    total_time = sum(s.get("total_observation_time_sec", 0) for s in sessions)
    
    # Count unique objects
    unique_objects = set()
    for session in sessions:
        if session.get("observations"):
            for obs in session.get("observations", []):
                unique_objects.add(obs.get("object_name", "Unknown"))
    
    return {
        "ok": True,
        "data": {
            "total_sessions": total_sessions,
            "total_observations": total_observations,
            "total_alignments": total_alignments,
            "mean_alignment_residual": round(mean_residual, 2),
            "total_observation_time_sec": total_time,
            "unique_objects": len(unique_objects),
            "objects": list(unique_objects)[:20]  # Top 20 objects
        }
    }


@app.get("/api/analytics/sessions")
def api_analytics_sessions(limit: int = Query(100, ge=1, le=1000)):
    """Get sessions with computed statistics for dashboard.
    
    Returns list of sessions with:
        - id, target_name, target_ra, target_dec
        - created_at, observation_count, alignment_count
        - alignment_residual_mean, total_observation_time_sec
    """
    sessions = SessionManager.get_all_sessions_with_stats()
    
    # Sort by date, newest first
    sessions.sort(key=lambda s: s.get("created_at", ""), reverse=True)
    
    return {
        "ok": True,
        "data": {
            "sessions": sessions[:limit],
            "total": len(sessions)
        }
    }


@app.get("/api/analytics/alignments")
def api_analytics_alignments(session_id: Optional[str] = None):
    """Get alignment statistics.
    
    If session_id provided, returns alignments for that session.
    Otherwise returns stats across all sessions.
    """
    if session_id:
        alignments = SessionManager.get_session_alignments(session_id)
        residuals = [a.get("residual_arcmin", 0) for a in alignments]
        
        return {
            "ok": True,
            "data": {
                "session_id": session_id,
                "alignment_count": len(alignments),
                "mean_residual": round(sum(residuals) / len(residuals), 2) if residuals else 0,
                "min_residual": min(residuals) if residuals else 0,
                "max_residual": max(residuals) if residuals else 0,
                "alignments": alignments
            }
        }
    else:
        # Global alignment stats
        sessions = SessionManager.get_all_sessions_with_stats()
        all_residuals = []
        
        for session in sessions:
            if session.get("alignments"):
                for align in session.get("alignments", []):
                    all_residuals.append(align.get("residual_arcmin", 0))
        
        return {
            "ok": True,
            "data": {
                "total_alignments": len(all_residuals),
                "mean_residual": round(sum(all_residuals) / len(all_residuals), 2) if all_residuals else 0,
                "min_residual": min(all_residuals) if all_residuals else 0,
                "max_residual": max(all_residuals) if all_residuals else 0
            }
        }


@app.get("/api/analytics/observations")
def api_analytics_observations(session_id: Optional[str] = None):
    """Get observation statistics.
    
    Returns:
        - observation_count, total_integration_time
        - objects observed and their frequencies
        - duration statistics
    """
    if session_id:
        observations = SessionManager.get_session_observations(session_id)
        
        object_counts = {}
        total_duration = 0
        durations = []
        
        for obs in observations:
            obj = obs.get("object_name", "Unknown")
            object_counts[obj] = object_counts.get(obj, 0) + 1
            duration = obs.get("duration_sec", 0)
            total_duration += duration
            durations.append(duration)
        
        return {
            "ok": True,
            "data": {
                "session_id": session_id,
                "observation_count": len(observations),
                "total_duration_sec": total_duration,
                "mean_duration_sec": sum(durations) / len(durations) if durations else 0,
                "objects": object_counts,
                "observations": observations
            }
        }
    else:
        # Global observation stats
        sessions = SessionManager.get_all_sessions_with_stats()
        object_counts = {}
        total_duration = 0
        
        for session in sessions:
            for obs in session.get("observations", []):
                obj = obs.get("object_name", "Unknown")
                object_counts[obj] = object_counts.get(obj, 0) + 1
                total_duration += obs.get("duration_sec", 0)
        
        return {
            "ok": True,
            "data": {
                "total_observations": sum(len(s.get("observations", [])) for s in sessions),
                "total_duration_sec": total_duration,
                "objects": object_counts,
                "unique_objects": len(object_counts)
            }
        }


@app.get("/api/analytics/timeline")
def api_analytics_timeline(days: int = Query(30, ge=1, le=365)):
    """Get observation timeline for last N days.
    
    Returns daily observation counts for graphing.
    """
    from datetime import datetime, timedelta
    
    sessions = SessionManager.get_all_sessions_with_stats()
    timeline = {}
    
    # Initialize last N days
    today = datetime.now().date()
    for i in range(days):
        date = today - timedelta(days=i)
        timeline[date.isoformat()] = 0
    
    # Count observations by day
    for session in sessions:
        try:
            created = datetime.fromisoformat(session.get("created_at", "")).date()
            date_key = created.isoformat()
            
            if date_key in timeline:
                timeline[date_key] += session.get("observation_count", 0)
        except:
            pass
    
    # Sort by date
    sorted_timeline = sorted(timeline.items())
    
    return {
        "ok": True,
        "data": {
            "dates": [item[0] for item in sorted_timeline],
            "counts": [item[1] for item in sorted_timeline],
            "days": days
        }
    }


@app.get("/api/analytics/magnitude-distribution")
def api_analytics_magnitude_distribution(session_id: Optional[str] = None):
    """Get magnitude distribution of observed objects.
    
    Returns histogram data for magnitude ranges.
    """
    if session_id:
        observations = SessionManager.get_session_observations(session_id)
    else:
        sessions = SessionManager.get_all_sessions_with_stats()
        observations = []
        for session in sessions:
            observations.extend(session.get("observations", []))
    
    # Bin magnitudes into ranges
    bins = {}
    for obs in observations:
        # Use estimated magnitude from object database if available
        # For now, just count by object name
        obj = obs.get("object_name", "Unknown")
        bins[obj] = bins.get(obj, 0) + 1
    
    return {
        "ok": True,
        "data": {
            "objects": list(bins.keys()),
            "counts": list(bins.values()),
            "total": len(observations)
        }
    }


@app.get("/api/analytics/quality-metrics")
def api_analytics_quality_metrics(session_id: Optional[str] = None):
    """Get quality metrics: alignment residuals, observation duration, etc.
    
    Useful for assessing observation session quality.
    """
    if session_id:
        session_data = SessionManager.get_session_summary(session_id)
        alignments = SessionManager.get_session_alignments(session_id)
        observations = SessionManager.get_session_observations(session_id)
    else:
        sessions = SessionManager.get_all_sessions_with_stats()
        session_data = None
        alignments = []
        observations = []
        for s in sessions:
            alignments.extend(s.get("alignments", []))
            observations.extend(s.get("observations", []))
    
    residuals = [a.get("residual_arcmin", 0) for a in alignments]
    durations = [o.get("duration_sec", 0) for o in observations]
    
    return {
        "ok": True,
        "data": {
            "alignment_quality": {
                "count": len(alignments),
                "mean_residual": round(sum(residuals) / len(residuals), 2) if residuals else 0,
                "std_residual": round((sum((x - (sum(residuals)/len(residuals)))**2 for x in residuals) / len(residuals))**0.5, 2) if residuals else 0,
                "status": "excellent" if (sum(residuals)/len(residuals) if residuals else 0) < 2 else "good" if (sum(residuals)/len(residuals) if residuals else 0) < 5 else "fair"
            },
            "observation_statistics": {
                "count": len(observations),
                "total_duration_sec": sum(durations),
                "mean_duration_sec": round(sum(durations) / len(durations), 1) if durations else 0
            }
        }
    }


# Helper method to get all sessions with computed stats
class _SessionStatsHelper:
    @staticmethod
    def get_all_sessions_with_stats():
        """Internal helper to get sessions with stats for analytics."""
        import sqlite3
        db_path = "data/sessions.db"
        
        sessions = []
        try:
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            
            # Get all sessions
            cur.execute("SELECT * FROM sessions ORDER BY created_at DESC")
            session_rows = cur.fetchall()
            
            for row in session_rows:
                session_id = row["id"]
                session = dict(row)
                
                # Count alignments
                cur.execute("SELECT COUNT(*) as cnt, AVG(residual_arcmin) as mean_res FROM alignments WHERE session_id = ?", (session_id,))
                align = cur.fetchone()
                session["alignment_count"] = align["cnt"] or 0
                session["alignment_residual_mean"] = align["mean_res"] or 0
                
                # Count observations
                cur.execute("SELECT COUNT(*) as cnt, SUM(duration_sec) as total FROM observations WHERE session_id = ?", (session_id,))
                obs = cur.fetchone()
                session["observation_count"] = obs["cnt"] or 0
                session["total_observation_time_sec"] = obs["total"] or 0
                
                # Get alignments detail
                cur.execute("SELECT * FROM alignments WHERE session_id = ? ORDER BY timestamp", (session_id,))
                session["alignments"] = [dict(a) for a in cur.fetchall()]
                
                # Get observations detail
                cur.execute("SELECT * FROM observations WHERE session_id = ? ORDER BY timestamp", (session_id,))
                session["observations"] = [dict(o) for o in cur.fetchall()]
                
                sessions.append(session)
            
            conn.close()
        except Exception as e:
            print(f"Error getting sessions: {e}")
        
        return sessions


# Monkey patch SessionManager with helper
SessionManager.get_all_sessions_with_stats = _SessionStatsHelper.get_all_sessions_with_stats


# ============================================================================
# Filter Wheel Endpoints (M8.1)
# ============================================================================

@app.post("/api/filter-wheel/init")
def api_filter_wheel_init(port: Optional[str] = None, name: str = "main"):
    """Initialize filter wheel connection.
    
    Args:
        port: Serial port (e.g., '/dev/ttyUSB0', 'COM3')
              If None, uses mock driver for testing
        name: Wheel identifier
    """
    try:
        if port is None:
            # Mock mode for testing
            wheel = MockFilterWheel()
        else:
            # Real hardware
            wheel = SerialFilterWheel(port=port)
        
        filter_wheel_manager._wheels[name] = wheel
        if filter_wheel_manager._default_wheel is None:
            filter_wheel_manager._default_wheel = name
        
        if wheel.connect():
            return {"ok": True, "wheel": name, "connected": True}
        else:
            raise HTTPException(status_code=500, detail="Failed to connect to filter wheel")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/filter-wheel/status")
def api_filter_wheel_status(name: Optional[str] = None):
    """Get filter wheel status."""
    wheel = filter_wheel_manager.get_wheel(name)
    if not wheel:
        raise HTTPException(status_code=404, detail="Filter wheel not found")
    
    status = wheel.get_status()
    return {"ok": True, "status": status}


@app.post("/api/filter-wheel/select/{position}")
def api_filter_wheel_select(position: int, name: Optional[str] = None):
    """Select filter by position."""
    wheel = filter_wheel_manager.get_wheel(name)
    if not wheel:
        raise HTTPException(status_code=404, detail="Filter wheel not found")
    
    if not wheel.is_connected():
        raise HTTPException(status_code=503, detail="Filter wheel not connected")
    
    if wheel.select_filter(position):
        return {"ok": True, "position": position, "filter": wheel.get_filter_name(position)}
    else:
        raise HTTPException(status_code=400, detail="Failed to select filter")


@app.get("/api/filter-wheel/filters")
def api_filter_wheel_filters(name: Optional[str] = None):
    """Get available filters."""
    wheel = filter_wheel_manager.get_wheel(name)
    if not wheel:
        raise HTTPException(status_code=404, detail="Filter wheel not found")
    
    return {
        "ok": True,
        "filters": wheel.get_filters(),
        "count": wheel.get_filter_count()
    }


@app.post("/api/filter-wheel/wait/{position}")
def api_filter_wheel_wait(position: int, timeout: float = 10.0, name: Optional[str] = None):
    """Wait for filter wheel to reach position."""
    wheel = filter_wheel_manager.get_wheel(name)
    if not wheel:
        raise HTTPException(status_code=404, detail="Filter wheel not found")
    
    if wheel.wait_for_position(position, timeout):
        return {"ok": True, "reached": True, "position": position}
    else:
        return {"ok": False, "reached": False, "message": "Timeout waiting for position"}


@app.get("/api/filter-wheel/statistics")
def api_filter_wheel_statistics(name: Optional[str] = None):
    """Get filter wheel operation statistics."""
    wheel = filter_wheel_manager.get_wheel(name)
    if not wheel:
        raise HTTPException(status_code=404, detail="Filter wheel not found")
    
    stats = wheel.get_statistics()
    return {"ok": True, "statistics": stats}


@app.post("/api/filter-wheel/disconnect")
def api_filter_wheel_disconnect(name: Optional[str] = None):
    """Disconnect filter wheel."""
    wheel = filter_wheel_manager.get_wheel(name)
    if not wheel:
        raise HTTPException(status_code=404, detail="Filter wheel not found")
    
    wheel.disconnect()
    return {"ok": True, "disconnected": True}

