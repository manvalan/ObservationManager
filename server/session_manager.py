"""
Session Persistence Module - ObservationManager
Gestisce il salvataggio persistente di sessioni osservative con SQLite
"""
import sqlite3
import json
import threading
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List, Any

DB_PATH = Path("data/sessions.db")
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

_db_lock = threading.Lock()


def _init_db():
    """Inizializza database con schema."""
    with _db_lock:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        
        # Sessions table
        c.execute('''CREATE TABLE IF NOT EXISTS sessions (
            id TEXT PRIMARY KEY,
            created_at REAL,
            modified_at REAL,
            site_id TEXT,
            target_ra REAL,
            target_dec REAL,
            target_name TEXT,
            notes TEXT,
            metadata TEXT
        )''')
        
        # Alignments table
        c.execute('''CREATE TABLE IF NOT EXISTS alignments (
            id TEXT PRIMARY KEY,
            session_id TEXT,
            timestamp REAL,
            star_name TEXT,
            ra_deg REAL,
            dec_deg REAL,
            alt_deg REAL,
            az_deg REAL,
            residual_arcmin REAL,
            pointing_error TEXT,
            FOREIGN KEY(session_id) REFERENCES sessions(id)
        )''')
        
        # Syncs table
        c.execute('''CREATE TABLE IF NOT EXISTS syncs (
            id TEXT PRIMARY KEY,
            session_id TEXT,
            timestamp REAL,
            ra_deg REAL,
            dec_deg REAL,
            pointing_ra REAL,
            pointing_dec REAL,
            alignment_quality REAL,
            FOREIGN KEY(session_id) REFERENCES sessions(id)
        )''')
        
        # Observations table
        c.execute('''CREATE TABLE IF NOT EXISTS observations (
            id TEXT PRIMARY KEY,
            session_id TEXT,
            timestamp REAL,
            object_name TEXT,
            ra_deg REAL,
            dec_deg REAL,
            obs_type TEXT,
            duration_sec REAL,
            notes TEXT,
            exposure_sec REAL,
            gain INT,
            binning TEXT,
            FOREIGN KEY(session_id) REFERENCES sessions(id)
        )''')
        
        # Sequences table
        c.execute('''CREATE TABLE IF NOT EXISTS sequences_log (
            id TEXT PRIMARY KEY,
            session_id TEXT,
            sequence_id TEXT,
            timestamp REAL,
            status TEXT,
            steps_total INT,
            steps_completed INT,
            duration_sec REAL,
            FOREIGN KEY(session_id) REFERENCES sessions(id)
        )''')
        
        conn.commit()
        conn.close()


# Inizializza database al primo import
_init_db()


class SessionManager:
    """Gestisce sessioni osservative persistenti."""
    
    @staticmethod
    def create_session(site_id: str, notes: str = "") -> str:
        """Crea nuova sessione."""
        import uuid
        session_id = f"sess_{uuid.uuid4().hex[:12]}"
        now = datetime.now().timestamp()
        
        with _db_lock:
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute('''
                INSERT INTO sessions 
                (id, created_at, modified_at, site_id, notes, metadata)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (session_id, now, now, site_id, notes, '{}'))
            conn.commit()
            conn.close()
        
        return session_id
    
    @staticmethod
    def get_session(session_id: str) -> Optional[Dict[str, Any]]:
        """Carica sessione."""
        with _db_lock:
            conn = sqlite3.connect(DB_PATH)
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            c.execute('SELECT * FROM sessions WHERE id = ?', (session_id,))
            row = c.fetchone()
            conn.close()
        
        if not row:
            return None
        
        return dict(row)
    
    @staticmethod
    def list_sessions(limit: int = 50) -> List[Dict[str, Any]]:
        """Lista sessioni recenti."""
        with _db_lock:
            conn = sqlite3.connect(DB_PATH)
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            c.execute(
                'SELECT * FROM sessions ORDER BY modified_at DESC LIMIT ?',
                (limit,)
            )
            rows = c.fetchall()
            conn.close()
        
        return [dict(row) for row in rows]
    
    @staticmethod
    def update_session(session_id: str, **kwargs) -> bool:
        """Aggiorna campi sessione."""
        update_fields = ', '.join([f'{k} = ?' for k in kwargs.keys()])
        values = list(kwargs.values()) + [session_id]
        
        with _db_lock:
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute(
                f'UPDATE sessions SET {update_fields}, modified_at = ? WHERE id = ?',
                values + [datetime.now().timestamp()]
            )
            conn.commit()
            conn.close()
        
        return c.rowcount > 0
    
    @staticmethod
    def log_alignment(
        session_id: str,
        star_name: str,
        ra_deg: float,
        dec_deg: float,
        alt_deg: float,
        az_deg: float,
        residual_arcmin: float
    ) -> str:
        """Registra allineamento."""
        import uuid
        align_id = f"align_{uuid.uuid4().hex[:12]}"
        now = datetime.now().timestamp()
        
        with _db_lock:
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute('''
                INSERT INTO alignments 
                (id, session_id, timestamp, star_name, ra_deg, dec_deg, alt_deg, az_deg, residual_arcmin)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (align_id, session_id, now, star_name, ra_deg, dec_deg, alt_deg, az_deg, residual_arcmin))
            conn.commit()
            conn.close()
        
        return align_id
    
    @staticmethod
    def get_session_alignments(session_id: str) -> List[Dict[str, Any]]:
        """Ottiene tutti gli allineamenti di una sessione."""
        with _db_lock:
            conn = sqlite3.connect(DB_PATH)
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            c.execute(
                'SELECT * FROM alignments WHERE session_id = ? ORDER BY timestamp',
                (session_id,)
            )
            rows = c.fetchall()
            conn.close()
        
        return [dict(row) for row in rows]
    
    @staticmethod
    def log_sync(
        session_id: str,
        ra_deg: float,
        dec_deg: float,
        pointing_ra: float,
        pointing_dec: float,
        alignment_quality: float
    ) -> str:
        """Registra sync del mount."""
        import uuid
        sync_id = f"sync_{uuid.uuid4().hex[:12]}"
        now = datetime.now().timestamp()
        
        with _db_lock:
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute('''
                INSERT INTO syncs 
                (id, session_id, timestamp, ra_deg, dec_deg, pointing_ra, pointing_dec, alignment_quality)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (sync_id, session_id, now, ra_deg, dec_deg, pointing_ra, pointing_dec, alignment_quality))
            conn.commit()
            conn.close()
        
        return sync_id
    
    @staticmethod
    def get_session_syncs(session_id: str) -> List[Dict[str, Any]]:
        """Ottiene tutti i sync di una sessione."""
        with _db_lock:
            conn = sqlite3.connect(DB_PATH)
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            c.execute(
                'SELECT * FROM syncs WHERE session_id = ? ORDER BY timestamp',
                (session_id,)
            )
            rows = c.fetchall()
            conn.close()
        
        return [dict(row) for row in rows]
    
    @staticmethod
    def log_observation(
        session_id: str,
        object_name: str,
        ra_deg: float,
        dec_deg: float,
        obs_type: str,
        duration_sec: float,
        exposure_sec: Optional[float] = None,
        gain: Optional[int] = None,
        binning: Optional[str] = None,
        notes: str = ""
    ) -> str:
        """Registra osservazione."""
        import uuid
        obs_id = f"obs_{uuid.uuid4().hex[:12]}"
        now = datetime.now().timestamp()
        
        with _db_lock:
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute('''
                INSERT INTO observations 
                (id, session_id, timestamp, object_name, ra_deg, dec_deg, obs_type, 
                 duration_sec, exposure_sec, gain, binning, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (obs_id, session_id, now, object_name, ra_deg, dec_deg, obs_type,
                  duration_sec, exposure_sec, gain, binning, notes))
            conn.commit()
            conn.close()
        
        return obs_id
    
    @staticmethod
    def get_session_observations(session_id: str) -> List[Dict[str, Any]]:
        """Ottiene tutte le osservazioni di una sessione."""
        with _db_lock:
            conn = sqlite3.connect(DB_PATH)
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            c.execute(
                'SELECT * FROM observations WHERE session_id = ? ORDER BY timestamp',
                (session_id,)
            )
            rows = c.fetchall()
            conn.close()
        
        return [dict(row) for row in rows]
    
    @staticmethod
    def log_sequence_execution(
        session_id: str,
        sequence_id: str,
        status: str,
        steps_total: int,
        steps_completed: int,
        duration_sec: float
    ) -> str:
        """Registra esecuzione sequenza."""
        import uuid
        log_id = f"seqlog_{uuid.uuid4().hex[:12]}"
        now = datetime.now().timestamp()
        
        with _db_lock:
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute('''
                INSERT INTO sequences_log 
                (id, session_id, sequence_id, timestamp, status, steps_total, steps_completed, duration_sec)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (log_id, session_id, sequence_id, now, status, steps_total, steps_completed, duration_sec))
            conn.commit()
            conn.close()
        
        return log_id
    
    @staticmethod
    def export_session_json(session_id: str) -> Dict[str, Any]:
        """Esporta sessione completa in JSON."""
        session = SessionManager.get_session(session_id)
        if not session:
            return {}
        
        alignments = SessionManager.get_session_alignments(session_id)
        syncs = SessionManager.get_session_syncs(session_id)
        observations = SessionManager.get_session_observations(session_id)
        
        return {
            'session': {
                'id': session['id'],
                'created_at': session['created_at'],
                'modified_at': session['modified_at'],
                'target_name': session['target_name'],
                'target_ra': session['target_ra'],
                'target_dec': session['target_dec'],
                'notes': session['notes']
            },
            'alignments': alignments,
            'syncs': syncs,
            'observations': observations,
            'summary': {
                'total_alignments': len(alignments),
                'total_syncs': len(syncs),
                'total_observations': len(observations),
                'observation_duration': sum(o['duration_sec'] for o in observations) if observations else 0
            }
        }
    
    @staticmethod
    def get_session_summary(session_id: str) -> Dict[str, Any]:
        """Ottiene riepilogo sessione."""
        alignments = SessionManager.get_session_alignments(session_id)
        syncs = SessionManager.get_session_syncs(session_id)
        observations = SessionManager.get_session_observations(session_id)
        
        return {
            'total_alignments': len(alignments),
            'alignment_residual_mean': sum(a['residual_arcmin'] for a in alignments) / len(alignments) if alignments else 0,
            'total_syncs': len(syncs),
            'total_observations': len(observations),
            'observation_duration_sec': sum(o['duration_sec'] for o in observations) if observations else 0,
            'objects_observed': list(set(o['object_name'] for o in observations)) if observations else []
        }
