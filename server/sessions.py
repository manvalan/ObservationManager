"""
Session Management Module - ObservationManager
Gestisce persistence, logging e export dati sessione osservativa
"""
import sqlite3
import json
import csv
from typing import Optional, List, Dict, Any
from pathlib import Path
from datetime import datetime
import time

# Database path
DB_PATH = Path("data/sessions.db")
DB_PATH.parent.mkdir(parents=True, exist_ok=True)


class SessionManager:
    """
    Gestisce sessioni osservative con SQLite persistence.
    Traccia: allineamenti, GOTO, sync, star-hops, immagini catturate.
    """
    
    def __init__(self):
        self.conn: Optional[sqlite3.Connection] = None
        self.current_session_id: Optional[int] = None
        self._init_db()
    
    def _init_db(self):
        """Inizializza schema database."""
        self.conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row  # Enable column access by name
        
        # Create tables
        cursor = self.conn.cursor()
        
        # Sessions table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                start_time REAL NOT NULL,
                end_time REAL,
                site_latitude REAL,
                site_longitude REAL,
                site_elevation REAL,
                notes TEXT,
                weather_conditions TEXT
            )
        """)
        
        # Alignment events
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS alignments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER NOT NULL,
                timestamp REAL NOT NULL,
                star_name TEXT,
                ra_deg REAL NOT NULL,
                dec_deg REAL NOT NULL,
                residual_arcsec REAL,
                sync_message TEXT,
                FOREIGN KEY (session_id) REFERENCES sessions(id)
            )
        """)
        
        # GOTO events
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS goto_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER NOT NULL,
                timestamp REAL NOT NULL,
                target_name TEXT,
                ra_deg REAL NOT NULL,
                dec_deg REAL NOT NULL,
                alt_deg REAL,
                az_deg REAL,
                response TEXT,
                FOREIGN KEY (session_id) REFERENCES sessions(id)
            )
        """)
        
        # Star-hopping routes
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS star_hops (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER NOT NULL,
                timestamp REAL NOT NULL,
                start_ra REAL NOT NULL,
                start_dec REAL NOT NULL,
                target_ra REAL NOT NULL,
                target_dec REAL NOT NULL,
                step_count INTEGER,
                completed BOOLEAN DEFAULT 0,
                FOREIGN KEY (session_id) REFERENCES sessions(id)
            )
        """)
        
        # Captured images
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS images (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER NOT NULL,
                timestamp REAL NOT NULL,
                target_name TEXT,
                ra_deg REAL,
                dec_deg REAL,
                exposure_ms REAL,
                gain INTEGER,
                binning INTEGER,
                filepath TEXT NOT NULL,
                fwhm REAL,
                snr REAL,
                FOREIGN KEY (session_id) REFERENCES sessions(id)
            )
        """)
        
        self.conn.commit()
    
    def start_session(self, site_config: Dict[str, Any], notes: str = "") -> int:
        """
        Avvia nuova sessione osservativa.
        
        Args:
            site_config: Site settings (latitude, longitude, elevation)
            notes: Note testuali sulla sessione
            
        Returns:
            Session ID
        """
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO sessions (start_time, site_latitude, site_longitude, site_elevation, notes)
            VALUES (?, ?, ?, ?, ?)
        """, (
            time.time(),
            site_config.get("latitude"),
            site_config.get("longitude"),
            site_config.get("altitude_m"),
            notes
        ))
        self.conn.commit()
        
        self.current_session_id = cursor.lastrowid
        return self.current_session_id
    
    def end_session(self, session_id: Optional[int] = None):
        """Chiude sessione osservativa."""
        sid = session_id or self.current_session_id
        if not sid:
            return
        
        cursor = self.conn.cursor()
        cursor.execute("""
            UPDATE sessions SET end_time = ? WHERE id = ?
        """, (time.time(), sid))
        self.conn.commit()
        
        if sid == self.current_session_id:
            self.current_session_id = None
    
    def log_alignment(
        self,
        ra_deg: float,
        dec_deg: float,
        star_name: Optional[str] = None,
        residual_arcsec: Optional[float] = None,
        sync_message: Optional[str] = None,
        session_id: Optional[int] = None
    ):
        """Registra evento allineamento."""
        sid = session_id or self.current_session_id
        if not sid:
            raise RuntimeError("No active session")
        
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO alignments (session_id, timestamp, star_name, ra_deg, dec_deg, residual_arcsec, sync_message)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (sid, time.time(), star_name, ra_deg, dec_deg, residual_arcsec, sync_message))
        self.conn.commit()
    
    def log_goto(
        self,
        ra_deg: float,
        dec_deg: float,
        target_name: Optional[str] = None,
        alt_deg: Optional[float] = None,
        az_deg: Optional[float] = None,
        response: Optional[str] = None,
        session_id: Optional[int] = None
    ):
        """Registra evento GOTO."""
        sid = session_id or self.current_session_id
        if not sid:
            raise RuntimeError("No active session")
        
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO goto_events (session_id, timestamp, target_name, ra_deg, dec_deg, alt_deg, az_deg, response)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (sid, time.time(), target_name, ra_deg, dec_deg, alt_deg, az_deg, response))
        self.conn.commit()
    
    def log_star_hop(
        self,
        start_ra: float,
        start_dec: float,
        target_ra: float,
        target_dec: float,
        step_count: int,
        completed: bool = False,
        session_id: Optional[int] = None
    ):
        """Registra route star-hopping."""
        sid = session_id or self.current_session_id
        if not sid:
            raise RuntimeError("No active session")
        
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO star_hops (session_id, timestamp, start_ra, start_dec, target_ra, target_dec, step_count, completed)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (sid, time.time(), start_ra, start_dec, target_ra, target_dec, step_count, completed))
        self.conn.commit()
    
    def log_image(
        self,
        filepath: str,
        target_name: Optional[str] = None,
        ra_deg: Optional[float] = None,
        dec_deg: Optional[float] = None,
        exposure_ms: Optional[float] = None,
        gain: Optional[int] = None,
        binning: Optional[int] = None,
        fwhm: Optional[float] = None,
        snr: Optional[float] = None,
        session_id: Optional[int] = None
    ):
        """Registra immagine catturata."""
        sid = session_id or self.current_session_id
        if not sid:
            raise RuntimeError("No active session")
        
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO images (session_id, timestamp, target_name, ra_deg, dec_deg, exposure_ms, gain, binning, filepath, fwhm, snr)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (sid, time.time(), target_name, ra_deg, dec_deg, exposure_ms, gain, binning, filepath, fwhm, snr))
        self.conn.commit()
    
    def get_session(self, session_id: int) -> Optional[Dict[str, Any]]:
        """Ottiene dettagli sessione."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM sessions WHERE id = ?", (session_id,))
        row = cursor.fetchone()
        
        if not row:
            return None
        
        return dict(row)
    
    def list_sessions(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Lista sessioni recenti."""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT 
                s.*,
                COUNT(DISTINCT a.id) as alignment_count,
                COUNT(DISTINCT g.id) as goto_count,
                COUNT(DISTINCT i.id) as image_count
            FROM sessions s
            LEFT JOIN alignments a ON s.id = a.session_id
            LEFT JOIN goto_events g ON s.id = g.session_id
            LEFT JOIN images i ON s.id = i.session_id
            GROUP BY s.id
            ORDER BY s.start_time DESC
            LIMIT ?
        """, (limit,))
        
        return [dict(row) for row in cursor.fetchall()]
    
    def get_session_events(self, session_id: int) -> Dict[str, List[Dict[str, Any]]]:
        """Ottiene tutti gli eventi di una sessione."""
        cursor = self.conn.cursor()
        
        # Alignments
        cursor.execute("SELECT * FROM alignments WHERE session_id = ? ORDER BY timestamp", (session_id,))
        alignments = [dict(row) for row in cursor.fetchall()]
        
        # GOTOs
        cursor.execute("SELECT * FROM goto_events WHERE session_id = ? ORDER BY timestamp", (session_id,))
        gotos = [dict(row) for row in cursor.fetchall()]
        
        # Star hops
        cursor.execute("SELECT * FROM star_hops WHERE session_id = ? ORDER BY timestamp", (session_id,))
        hops = [dict(row) for row in cursor.fetchall()]
        
        # Images
        cursor.execute("SELECT * FROM images WHERE session_id = ? ORDER BY timestamp", (session_id,))
        images = [dict(row) for row in cursor.fetchall()]
        
        return {
            "alignments": alignments,
            "gotos": gotos,
            "star_hops": hops,
            "images": images
        }
    
    def export_session_json(self, session_id: int) -> str:
        """Esporta sessione come JSON."""
        session = self.get_session(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")
        
        events = self.get_session_events(session_id)
        
        data = {
            "session": session,
            "events": events,
            "exported_at": datetime.utcnow().isoformat()
        }
        
        export_dir = Path("data/exports")
        export_dir.mkdir(parents=True, exist_ok=True)
        
        filename = f"session_{session_id}_{int(time.time())}.json"
        filepath = export_dir / filename
        
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        
        return str(filepath)
    
    def export_session_csv(self, session_id: int, event_type: str = "gotos") -> str:
        """
        Esporta eventi sessione come CSV.
        
        Args:
            session_id: ID sessione
            event_type: Tipo eventi ('gotos', 'alignments', 'images', 'star_hops')
        """
        events = self.get_session_events(session_id)
        
        if event_type not in events:
            raise ValueError(f"Invalid event type: {event_type}")
        
        rows = events[event_type]
        if not rows:
            raise ValueError(f"No {event_type} events found")
        
        export_dir = Path("data/exports")
        export_dir.mkdir(parents=True, exist_ok=True)
        
        filename = f"session_{session_id}_{event_type}_{int(time.time())}.csv"
        filepath = export_dir / filename
        
        with open(filepath, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows(rows)
        
        return str(filepath)
    
    def restore_session(self, session_id: int):
        """
        Ripristina sessione come current.
        Utile per riprendere sessione dopo restart server.
        """
        session = self.get_session(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")
        
        self.current_session_id = session_id
        return session
    
    def get_statistics(self, session_id: Optional[int] = None) -> Dict[str, Any]:
        """Calcola statistiche sessione."""
        sid = session_id or self.current_session_id
        if not sid:
            raise RuntimeError("No session specified")
        
        cursor = self.conn.cursor()
        
        # Session info
        session = self.get_session(sid)
        if not session:
            return {}
        
        # Count events
        cursor.execute("SELECT COUNT(*) as cnt FROM alignments WHERE session_id = ?", (sid,))
        alignment_count = cursor.fetchone()["cnt"]
        
        cursor.execute("SELECT COUNT(*) as cnt FROM goto_events WHERE session_id = ?", (sid,))
        goto_count = cursor.fetchone()["cnt"]
        
        cursor.execute("SELECT COUNT(*) as cnt FROM star_hops WHERE session_id = ?", (sid,))
        hop_count = cursor.fetchone()["cnt"]
        
        cursor.execute("SELECT COUNT(*) as cnt FROM images WHERE session_id = ?", (sid,))
        image_count = cursor.fetchone()["cnt"]
        
        # Image statistics
        cursor.execute("""
            SELECT 
                AVG(exposure_ms) as avg_exposure,
                AVG(fwhm) as avg_fwhm,
                AVG(snr) as avg_snr,
                MIN(fwhm) as best_fwhm
            FROM images WHERE session_id = ? AND fwhm IS NOT NULL
        """, (sid,))
        image_stats = dict(cursor.fetchone()) if cursor.rowcount > 0 else {}
        
        # Duration
        duration = (session["end_time"] - session["start_time"]) if session.get("end_time") else (time.time() - session["start_time"])
        
        return {
            "session_id": sid,
            "duration_seconds": duration,
            "alignment_count": alignment_count,
            "goto_count": goto_count,
            "star_hop_count": hop_count,
            "image_count": image_count,
            "image_statistics": image_stats,
            "start_time": session["start_time"],
            "end_time": session.get("end_time")
        }
    
    def close(self):
        """Chiude connessione database."""
        if self.conn:
            self.conn.close()


# Singleton globale
session_manager = SessionManager()
