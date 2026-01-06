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


@app.post("/api/altaz")
def api_altaz(body: AltAzBody) -> dict:
    try:
        cfg = _read_settings()
        alt, az = ra_dec_to_altaz(body.ra_deg, body.dec_deg, cfg)
        return {"ok": True, "alt_deg": alt, "az_deg": az, "settings": cfg}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/apparent")
def api_apparent(body: ApparentBody) -> dict:
    try:
        cfg = _read_settings()
        ra, dec = altaz_to_ra_dec(body.alt_deg, body.az_deg, cfg)
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
        results = resolve_name(name, limit=limit)
        out = [
            {
                "name": e.name,
                "ra_deg": e.ra_deg,
                "dec_deg": e.dec_deg,
                "mag": e.mag,
                "designations": e.designations,
            }
            for e in results
        ]
        return {"ok": True, "results": out}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/goto-name")
def api_goto_name(name: str) -> dict:
    try:
        results = resolve_name(name, limit=10)
        if not results:
            raise ValueError("Nessun risultato trovato")
        target = results[0]
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
def api_sky_stars(ra_deg: float = None, dec_deg: float = None, radius: float = 60.0, maxmag: float = 5.0):
    try:
        if ra_deg is None or dec_deg is None:
            cfg = _read_settings()
            ra_deg, dec_deg = zenith_radec(cfg)
        gaia_stars = _gaia_lookup_cone(float(ra_deg), float(dec_deg), float(radius), float(maxmag), limit=500)
        if not gaia_stars:
            stars = _load_bright_stars()
        else:
            stars = gaia_stars
        cfg = _read_settings()
        out = []
        for s in stars:
            try:
                alt, az = ra_dec_to_altaz(s["ra_deg"], s["dec_deg"], cfg)
                if alt < -2:
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
        return {"ok": True, "center_ra": ra_deg, "center_dec": dec_deg, "radius": radius, "stars": out}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# -------- Settings (site/time/atmo) --------
SETTINGS_PATH = os.path.join(os.path.dirname(__file__), "data", "settings.json")
os.makedirs(os.path.dirname(SETTINGS_PATH), exist_ok=True)
BRIGHT_PATH = pathlib.Path(os.path.join(os.path.dirname(__file__), "data", "bright_stars.json"))
GAIA_EXE_CANDIDATES = [
    shutil.which("gaia_lookup"),
    os.path.join(os.path.dirname(os.path.dirname(__file__)), "gaia", "build", "gaia_lookup"),
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


def _observer_and_time(now_ts=None):
    cfg = _read_settings()
    ts = load.timescale()
    t = ts.now() if now_ts is None else now_ts
    obs = wgs84.latlon(cfg["latitude"], cfg["longitude"], cfg.get("altitude_m", 0.0))
    return obs, t, cfg


def ra_dec_to_altaz(ra_deg: float, dec_deg: float, cfg: dict):
    obs, t, _ = _observer_and_time()
    star = Star(ra_hours=ra_deg / 15.0, dec_degrees=dec_deg)
    app = obs.at(t).observe(star).apparent()
    alt, az, _ = app.altaz(temperature_C=cfg.get("temperature_c", 10.0), pressure_mbar=cfg.get("pressure_mbar", 1013.25))
    return alt.degrees, az.degrees


def altaz_to_ra_dec(alt_deg: float, az_deg: float, cfg: dict):
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
    t = ts.now()
    lst_deg = t.gast.degrees  # GAST in degrees
    ra = (lst_deg - math.degrees(h)) % 360.0
    return ra, math.degrees(dec)


def zenith_radec(cfg: dict):
    obs, t, _ = _observer_and_time()
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


def _gaia_lookup_cone(ra_deg: float, dec_deg: float, radius_deg: float, maxmag: float = 4.0, limit: int = 50):
    exe = next((e for e in GAIA_EXE_CANDIDATES if e and os.path.isfile(e)), None)
    if not exe:
        return []
    try:
        proc = subprocess.run(
            [exe, "--cone", str(ra_deg), str(dec_deg), str(radius_deg), "--maxmag", str(maxmag)],
            capture_output=True,
            text=True,
            timeout=4,
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
                    "ra_deg": float(s.get("ra_deg")),
                    "dec_deg": float(s.get("dec_deg")),
                    "mag": s.get("mag_g") if s.get("mag_g") is not None else s.get("phot_g_mean_mag"),
                })
            except Exception:
                continue
        return out
    except Exception:
        return []


@app.get("/api/settings")
def api_get_settings() -> dict:
    return {"ok": True, "settings": _read_settings()}


@app.post("/api/settings")
def api_set_settings(body: SettingsBody) -> dict:
    body.validate_ranges()
    data = body.model_dump()
    _write_settings(data)
    return {"ok": True, "settings": data}


# -------- Resolve by ID --------
@app.get("/api/resolve")
def api_resolve(
    sao: str | None = None,
    hip: str | None = None,
    hd: str | None = None,
    name: str | None = None,
):
    try:
        if sao:
            e = resolve_id_via_gaia("sao", sao)
            if e:
                return {"ok": True, "result": e.__dict__}
        if hip:
            e = resolve_id_via_gaia("hip", hip)
            if e:
                return {"ok": True, "result": e.__dict__}
        if hd:
            e = resolve_id_via_gaia("hd", hd)
            if e:
                return {"ok": True, "result": e.__dict__}
        if name:
            res = resolve_name(name, limit=1)
            if res:
                return {"ok": True, "result": res[0].__dict__}
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
