from __future__ import annotations

import math
from typing import Tuple, Optional

from .connection import SerialConnection


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def format_ra_hms(ra_hours: float) -> str:
    """Format RA in ore decimali → "HH:MM:SS"."""
    ra_hours = ra_hours % 24.0
    total_sec = int(round(ra_hours * 3600))
    hh = (total_sec // 3600) % 24
    mm = (total_sec % 3600) // 60
    ss = total_sec % 60
    return f"{hh:02d}:{mm:02d}:{ss:02d}"


def parse_ra(value: str | float) -> str:
    """Accetta stringa "HH:MM:SS" o float (ore o gradi > 24 ⇒ assume gradi)."""
    if isinstance(value, (int, float)):
        v = float(value)
        # heuristica: se supera 24, trattalo come gradi → converti a ore
        if abs(v) > 24.0:
            v = (v / 15.0)
        return format_ra_hms(v)
    s = value.strip().lower().replace("h", ":").replace("°", "*")
    if any(c in s for c in [":",]) and "*" not in s:
        # HH:MM[:SS]
        parts = [int(p) for p in s.split(":")]
        while len(parts) < 3:
            parts.append(0)
        hh, mm, ss = parts[:3]
        return f"{hh:02d}:{mm:02d}:{ss:02d}"
    # formato in gradi? converti a ore
    try:
        deg = float(s)
        return format_ra_hms(deg / 15.0)
    except ValueError:
        raise ValueError(f"Formato RA non riconosciuto: {value}")


def format_dec_dms(dec_deg: float) -> str:
    """Format Dec in gradi decimali → "+DD*MM:SS" con segno."""
    sign = "+" if dec_deg >= 0 else "-"
    dec_deg = abs(dec_deg)
    d = int(dec_deg)
    m_f = (dec_deg - d) * 60
    m = int(m_f)
    s = int(round((m_f - m) * 60))
    if s == 60:
        s = 0
        m += 1
    if m == 60:
        m = 0
        d += 1
    return f"{sign}{d:02d}*{m:02d}:{s:02d}"


def parse_dec(value: str | float) -> str:
    """Accetta "+DD*MM:SS", "+DD:MM:SS", o float (gradi)."""
    if isinstance(value, (int, float)):
        return format_dec_dms(float(value))
    s = value.strip().replace("°", "*").replace("\u00b0", "*")
    # Sostieni anche notazione DD:MM:SS senza '*'
    if "*" not in s and ":" in s:
        # Inserisci '*'
        parts = s
        # Trova primo ':' per separare gradi-minuti
        first_colon = parts.find(":")
        s = parts[:first_colon].rjust(3, "+") + "*" + parts[first_colon + 1:]
    # Ora attendiamo segno +DD*MM:SS (o -DD*MM:SS)
    try:
        sign = 1
        if s.startswith("-"):
            sign = -1
            s2 = s[1:]
        elif s.startswith("+"):
            s2 = s[1:]
        else:
            s2 = s
        deg_part, mmss = s2.split("*")
        mm, ss = mmss.split(":")
        deg = int(deg_part)
        minutes = int(mm)
        seconds = int(ss)
        dec = sign * (deg + minutes / 60 + seconds / 3600)
        return format_dec_dms(dec)
    except Exception:
        # prova come numero decimale con segno
        try:
            dec = float(s)
            return format_dec_dms(dec)
        except Exception:
            raise ValueError(f"Formato Dec non riconosciuto: {value}")


class LX200:
    def __init__(self, conn: SerialConnection):
        self.conn = conn

    # ----- Query -----
    def get_version(self) -> str:
        return self.conn.query(":GV")

    def get_ra(self) -> str:
        return self.conn.query(":GR")

    def get_dec(self) -> str:
        return self.conn.query(":GD")

    # ----- Slew / Goto -----
    def set_target_ra_dec(self, ra: str | float, dec: str | float) -> None:
        ra_fmt = parse_ra(ra)
        dec_fmt = parse_dec(dec)
        ok_ra = self.conn.query(f":Sr{ra_fmt}")
        ok_dec = self.conn.query(f":Sd{dec_fmt}")
        if ok_ra != "1" or ok_dec != "1":
            raise RuntimeError("Montatura ha rifiutato RA/Dec target")

    def goto(self) -> str:
        return self.conn.query(":MS")  # "0" su successo (comando accettato)

    def stop_all(self) -> None:
        # Stop immediato di tutti i motori
        self.conn.query(":Q")

    # ----- Manual motion -----
    def set_rate(self, rate: str) -> None:
        # rate in {guide, center, find, slew}
        cmd = {
            "guide": ":RG",
            "center": ":RC",
            "find": ":RM",
            "slew": ":RS",
        }.get(rate.lower())
        if not cmd:
            raise ValueError("Rate non valido. Usa: guide|center|find|slew")
        self.conn.query(cmd)

    def move_dir(self, direction: str) -> None:
        cmd = {
            "n": ":Mn",
            "s": ":Ms",
            "e": ":Me",
            "w": ":Mw",
        }.get(direction.lower())
        if not cmd:
            raise ValueError("Direzione non valida. Usa: N|S|E|W")
        self.conn.query(cmd)

    def stop_dir(self, direction: Optional[str] = None) -> None:
        if not direction:
            self.stop_all()
            return
        cmd = {
            "n": ":Qn",
            "s": ":Qs",
            "e": ":Qe",
            "w": ":Qw",
        }.get(direction.lower())
        if not cmd:
            raise ValueError("Direzione non valida. Usa: N|S|E|W")
        self.conn.query(cmd)

    # ----- Sync -----
    def sync_to(self, ra: str | float, dec: str | float) -> str:
        # Imposta target poi sincronizza (calibra) con :CM
        self.set_target_ra_dec(ra, dec)
        return self.conn.query(":CM")

    # ----- Focuser -----
    def focus_in(self) -> None:
        """Start moving focuser inward (slower speed)."""
        self.conn.query(":F+")

    def focus_out(self) -> None:
        """Start moving focuser outward (faster speed)."""
        self.conn.query(":F-")

    def focus_stop(self) -> None:
        """Stop focuser movement."""
        self.conn.query(":FQ")

    def set_focus_speed(self, speed: str) -> None:
        """Set focuser speed: 'slow' or 'fast'."""
        cmd = {
            "slow": ":FS",
            "fast": ":FF",
        }.get(speed.lower())
        if not cmd:
            raise ValueError("Speed non valido. Usa: slow|fast")
        self.conn.query(cmd)
