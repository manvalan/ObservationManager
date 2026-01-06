from __future__ import annotations

import csv
import json
import os
import pathlib
import re
from dataclasses import dataclass
from functools import lru_cache
from typing import Iterable, List, Optional, Tuple
import subprocess

from .protocol import parse_ra, parse_dec


@dataclass
class NameEntry:
    name: str
    ra_deg: float
    dec_deg: float
    mag: Optional[float] = None
    designations: Optional[str] = None


CANDIDATE_FILENAMES = (
    "names.json",
    "names.ndjson",
    "names.csv",
    "iau_names.json",
    "iau_names.csv",
    "crossref.json",
    "crossref.csv",
)


def expand_home(p: str) -> str:
    return os.path.expanduser(p)


def default_catalog_paths() -> List[str]:
    base = expand_home("~/.catalog/crossreference")
    if not os.path.isdir(base):
        base = expand_home("~/.catalog")
    paths: List[str] = []
    for fname in CANDIDATE_FILENAMES:
        p = os.path.join(base, fname)
        if os.path.isfile(p):
            paths.append(p)
    # fallback: cerca .csv/.json nella cartella
    try:
        for p in pathlib.Path(base).glob("*.csv"):
            paths.append(str(p))
        for p in pathlib.Path(base).glob("*.json"):
            paths.append(str(p))
    except Exception:
        pass
    # de-dup preservando ordine
    seen = set()
    uniq: List[str] = []
    for p in paths:
        if p not in seen:
            uniq.append(p)
            seen.add(p)
    return uniq


def which(cmd: str) -> Optional[str]:
    from shutil import which as _which
    return _which(cmd)


def _gaia_lookup_exec_candidates() -> List[str]:
    cands: List[str] = []
    # in PATH
    w = which("gaia_lookup")
    if w:
        cands.append(w)
    # in repo build tree (common local path suggestion)
    local = os.path.join(os.path.dirname(os.path.dirname(__file__)), "gaia", "build", "gaia_lookup")
    if os.path.isfile(local) and os.access(local, os.X_OK):
        cands.append(local)
    return cands


def resolve_name_via_gaia(name: str) -> Optional[NameEntry]:
    for exe in _gaia_lookup_exec_candidates():
        try:
            proc = subprocess.run([exe, "--name", name], capture_output=True, text=True, timeout=5)
            if proc.returncode == 0 and proc.stdout:
                obj = json.loads(proc.stdout.strip())
                if obj.get("ok"):
                    return NameEntry(
                        name=name,
                        ra_deg=float(obj.get("ra_deg")),
                        dec_deg=float(obj.get("dec_deg")),
                        mag=_to_float(obj.get("mag_g")),
                        designations=obj.get("designations"),
                    )
        except Exception:
            continue
    return None


def resolve_id_via_gaia(kind: str, value: str) -> Optional[NameEntry]:
    flag = {
        "sao": "--sao",
        "hip": "--hip",
        "hd": "--hd",
    }.get(kind.lower())
    if not flag:
        return None
    for exe in _gaia_lookup_exec_candidates():
        try:
            proc = subprocess.run([exe, flag, str(value)], capture_output=True, text=True, timeout=5)
            if proc.returncode == 0 and proc.stdout:
                obj = json.loads(proc.stdout.strip())
                if obj.get("ok"):
                    return NameEntry(
                        name=str(obj.get("name") or f"{kind.upper()} {value}"),
                        ra_deg=float(obj.get("ra_deg")),
                        dec_deg=float(obj.get("dec_deg")),
                        mag=_to_float(obj.get("mag_g")),
                        designations=obj.get("designations"),
                    )
        except Exception:
            continue
    return None


def _to_float(v) -> Optional[float]:
    if v is None:
        return None
    try:
        return float(v)
    except Exception:
        return None


def _normalize_name(s: str) -> str:
    return re.sub(r"\s+", " ", s.strip()).lower()


def _parse_row_to_entry(row: dict) -> Optional[NameEntry]:
    # possibili chiavi per nome
    name = row.get("name") or row.get("designation") or row.get("iauname") or row.get("Name")
    if not name:
        # prova comporre da colonne HD/HIP/SAO
        for key in ("HD", "HIP", "SAO", "hd", "hip", "sao"):
            if row.get(key):
                name = f"{key.upper()} {row.get(key)}"
                break
    if not name:
        return None

    # RA/Dec: accetta gradi o formati stringa LX200
    ra = row.get("ra") or row.get("RA") or row.get("ra_deg") or row.get("RAdeg")
    dec = row.get("dec") or row.get("DEC") or row.get("dec_deg") or row.get("DEdeg")

    ra_deg: Optional[float] = None
    dec_deg: Optional[float] = None

    if isinstance(ra, (int, float)):
        ra_deg = float(ra)
    elif isinstance(ra, str) and ra:
        try:
            # prova come gradi
            ra_deg = float(ra)
        except Exception:
            # prova come HH:MM:SS
            ra_hms = parse_ra(ra)
            # converte a gradi
            hh, mm, ss = [int(p) for p in ra_hms.split(":")]
            ra_deg = (hh + mm/60 + ss/3600) * 15.0

    if isinstance(dec, (int, float)):
        dec_deg = float(dec)
    elif isinstance(dec, str) and dec:
        try:
            dec_deg = float(dec)
        except Exception:
            dec_dms = parse_dec(dec)
            # converte a gradi
            sign = -1 if dec_dms.startswith('-') else 1
            rest = dec_dms[1:]
            d_str, mmss = rest.split('*')
            m_str, s_str = mmss.split(':')
            d = int(d_str); m = int(m_str); s = int(s_str)
            dec_deg = sign * (d + m/60 + s/3600)

    if ra_deg is None or dec_deg is None:
        return None

    mag = _to_float(row.get("mag") or row.get("Gmag") or row.get("phot_g_mean_mag"))
    designations = row.get("designations") or row.get("all_designations")

    return NameEntry(name=str(name), ra_deg=float(ra_deg), dec_deg=float(dec_deg), mag=mag, designations=designations)


def _load_json_file(path: str) -> List[NameEntry]:
    out: List[NameEntry] = []
    with open(path, "r", encoding="utf-8") as f:
        first = f.read(1)
        f.seek(0)
        if first == "[":
            data = json.load(f)
            if isinstance(data, list):
                for obj in data:
                    if isinstance(obj, dict):
                        ent = _parse_row_to_entry(obj)
                        if ent:
                            out.append(ent)
            return out
        # NDJSON
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                if isinstance(obj, dict):
                    ent = _parse_row_to_entry(obj)
                    if ent:
                        out.append(ent)
            except Exception:
                continue
    return out


def _load_csv_file(path: str) -> List[NameEntry]:
    out: List[NameEntry] = []
    with open(path, "r", encoding="utf-8") as f:
        try:
            dialect = csv.Sniffer().sniff(f.read(2048))
            f.seek(0)
        except Exception:
            dialect = csv.excel
        reader = csv.DictReader(f, dialect=dialect)
        for row in reader:
            ent = _parse_row_to_entry(row)
            if ent:
                out.append(ent)
    return out


@lru_cache(maxsize=1)
def load_names_index(paths: Optional[Tuple[str, ...]] = None) -> List[NameEntry]:
    files: List[str] = list(paths) if paths else default_catalog_paths()
    entries: List[NameEntry] = []
    for p in files:
        try:
            if p.lower().endswith(".json"):
                entries.extend(_load_json_file(p))
            elif p.lower().endswith(".csv"):
                entries.extend(_load_csv_file(p))
        except Exception:
            # ignora file non parsabili
            continue
    # indicizzazione semplice: rimuovi duplicati name+coords
    seen = set()
    uniq: List[NameEntry] = []
    for e in entries:
        key = (e.name.lower(), round(e.ra_deg, 6), round(e.dec_deg, 6))
        if key in seen:
            continue
        uniq.append(e)
        seen.add(key)
    return uniq


def resolve_name(name: str, limit: int = 5, paths: Optional[List[str]] = None) -> List[NameEntry]:
    # Preferisci Gaia per match diretto
    g = resolve_name_via_gaia(name)
    if g:
        return [g]
    idx = load_names_index(tuple(paths) if paths else None)
    q = _normalize_name(name)
    # 1) match esatto case-insensitive
    exact = [e for e in idx if _normalize_name(e.name) == q]
    if exact:
        return exact[:limit]
    # 2) contiene (preferisci inizio parola)
    starts = [e for e in idx if _normalize_name(e.name).startswith(q)]
    contains = [e for e in idx if q in _normalize_name(e.name)]
    out = starts + [e for e in contains if e not in starts]
    return out[:limit]


def best_entry(entries: List[NameEntry]) -> Optional[NameEntry]:
    if not entries:
        return None
    # preferisci quella con magnitudine disponibile e più luminosa
    with_mag = [e for e in entries if e.mag is not None]
    if with_mag:
        return sorted(with_mag, key=lambda e: e.mag)[0]
    return entries[0]
