"""
Integrazione cataloghi locali: Gaia Unified Catalog e Crossreference databases.
Utilizza il binario compilato gaia_lookup (IOC_GaiaLib) per ricerche Gaia
e crossreference (SQLite) per SAO/HD/HIP match.
"""

import os
import sqlite3
import json
import subprocess
from pathlib import Path
from typing import Optional, List, Dict, Any

CATALOG_HOME = Path.home() / ".catalog"
GAIA_DIR = CATALOG_HOME / "gaia_mag18_v2_multi"
CROSSREF_DIR = CATALOG_HOME / "crossreference"

# Try to find gaia_lookup binary
GAIA_LOOKUP_CANDIDATES = [
    "/usr/local/bin/gaia_lookup",
    os.path.expanduser("~/local/bin/gaia_lookup"),
    "/opt/local/bin/gaia_lookup",
]

GAIA_LOOKUP_EXE = next((p for p in GAIA_LOOKUP_CANDIDATES if os.path.isfile(p)), None)


class LocalCatalogManager:
    """Manager per cataloghi locali Gaia e Crossreference."""

    def __init__(self):
        self.gaia_exe = GAIA_LOOKUP_EXE
        self.crossref_conn = None
        self._init_gaia()
        self._init_crossref()

    def _init_gaia(self) -> None:
        """Verifica disponibilità gaia_lookup binario."""
        if not self.gaia_exe:
            print("⚠️  gaia_lookup binario non trovato. Ricerche Gaia disabilitate.")
            print(f"   Cercato in: {', '.join(GAIA_LOOKUP_CANDIDATES)}")
            return
        print(f"✓ gaia_lookup binario trovato: {self.gaia_exe}")

    def _init_crossref(self) -> None:
        """Inizializza Crossreference database (SQLite)."""
        if not CROSSREF_DIR.exists():
            print(f"⚠️  Crossreference dir non trovato: {CROSSREF_DIR}")
            return
        
        # Preferisci gaia_sao_xmatch.db
        db_candidates = [
            CROSSREF_DIR / "gaia_sao_xmatch.db",
            CROSSREF_DIR / "stellar_crossref_complete.db",
        ]
        
        db_file = None
        for candidate in db_candidates:
            if candidate.exists():
                db_file = candidate
                break
        
        if not db_file:
            print(f"⚠️  Nessun DB crossref trovato in {CROSSREF_DIR}")
            return
        
        try:
            self.crossref_conn = sqlite3.connect(str(db_file))
            self.crossref_conn.row_factory = sqlite3.Row
            print(f"✓ Crossreference catalog caricato da {db_file}")
        except Exception as e:
            print(f"⚠️  Errore loading Crossreference: {e}")

    def search_gaia(self, ra_deg: float, dec_deg: float, radius_deg: float = 2.0, 
                   maxmag: float = 5.0, limit: int = 50) -> List[Dict[str, Any]]:
        """Ricerca cone in Gaia Unified Catalog (se gaia_lookup disponibile con supporto --cone)."""
        # Nota: il binario compilato da IOC_GaiaLib è un demo, non supporta interfaccia CLI.
        # Per ricerche cone, usare direttamente _gaia_lookup_cone() da app.py.
        # Qui ritorniamo lista vuota per fallback a crossref/bright_stars.
        return []

    def search_by_name(self, name: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Ricerca per nome: crossreference (SAO/HD/HIP) principalmente."""
        results = []
        
        # Prova crossreference per SAO/HD/HIP - sono i cataloghi locali disponibili
        if self.crossref_conn:
            try:
                # Formati comuni: SAO 1234, HD 5678, HIP 9999
                name_upper = name.upper().strip()
                patterns = []
                
                if name_upper.startswith("SAO"):
                    sao_num = name_upper.replace("SAO", "").strip()
                    try:
                        patterns.append(("sao", int(sao_num)))
                    except:
                        pass
                elif name_upper.startswith("HD"):
                    hd_num = name_upper.replace("HD", "").strip()
                    try:
                        patterns.append(("hd", int(hd_num)))
                    except:
                        pass
                elif name_upper.startswith("HIP"):
                    hip_num = name_upper.replace("HIP", "").strip()
                    try:
                        patterns.append(("hip", int(hip_num)))
                    except:
                        pass
                
                cursor = self.crossref_conn.cursor()
                for catalog_type, query_val in patterns:
                    try:
                        # Query la tabella 'stars'
                        if catalog_type == "sao":
                            cursor.execute(
                                "SELECT gaia_dr3, hip, sao, hd, ra_deg, dec_deg, magnitude FROM stars WHERE sao = ? LIMIT ?",
                                (query_val, limit)
                            )
                        elif catalog_type == "hd":
                            cursor.execute(
                                "SELECT gaia_dr3, hip, sao, hd, ra_deg, dec_deg, magnitude FROM stars WHERE hd = ? LIMIT ?",
                                (query_val, limit)
                            )
                        elif catalog_type == "hip":
                            cursor.execute(
                                "SELECT gaia_dr3, hip, sao, hd, ra_deg, dec_deg, magnitude FROM stars WHERE hip = ? LIMIT ?",
                                (query_val, limit)
                            )
                        
                        for row in cursor.fetchall():
                            results.append({
                                "name": f"{catalog_type.upper()} {query_val}",
                                "ra_deg": float(row[4]),
                                "dec_deg": float(row[5]),
                                "mag": row[6],
                                "source_id": row[0],
                                "catalog": "Crossreference",
                            })
                    except Exception as e:
                        pass
                    
                    if results:
                        break
            except Exception as e:
                print(f"⚠️  Errore ricerca crossref: {e}")
        
        return results[:limit]

    def lookup_sao(self, sao_id: str) -> Optional[Dict[str, Any]]:
        """Lookup via SAO ID."""
        if not self.crossref_conn:
            return None
        try:
            cursor = self.crossref_conn.cursor()
            cursor.execute(
                "SELECT gaia_dr3, hip, sao, hd, ra_deg, dec_deg, magnitude FROM stars WHERE sao = ? LIMIT 1",
                (int(sao_id),)
            )
            row = cursor.fetchone()
            if row:
                return {
                    "name": f"SAO {sao_id}",
                    "ra_deg": float(row[4]),
                    "dec_deg": float(row[5]),
                    "mag": row[6],
                    "source_id": row[0],
                    "sao_id": row[2],
                    "hd_id": row[3],
                    "hip_id": row[1],
                    "catalog": "Crossreference",
                }
        except Exception as e:
            print(f"⚠️  Errore lookup SAO: {e}")
        return None

    def lookup_hd(self, hd_id: str) -> Optional[Dict[str, Any]]:
        """Lookup via HD ID."""
        if not self.crossref_conn:
            return None
        try:
            cursor = self.crossref_conn.cursor()
            cursor.execute(
                "SELECT gaia_dr3, hip, sao, hd, ra_deg, dec_deg, magnitude FROM stars WHERE hd = ? LIMIT 1",
                (int(hd_id),)
            )
            row = cursor.fetchone()
            if row:
                return {
                    "name": f"HD {hd_id}",
                    "ra_deg": float(row[4]),
                    "dec_deg": float(row[5]),
                    "mag": row[6],
                    "source_id": row[0],
                    "sao_id": row[2],
                    "hd_id": row[3],
                    "hip_id": row[1],
                    "catalog": "Crossreference",
                }
        except Exception as e:
            print(f"⚠️  Errore lookup HD: {e}")
        return None

    def lookup_hip(self, hip_id: str) -> Optional[Dict[str, Any]]:
        """Lookup via HIP ID."""
        if not self.crossref_conn:
            return None
        try:
            cursor = self.crossref_conn.cursor()
            cursor.execute(
                "SELECT gaia_dr3, hip, sao, hd, ra_deg, dec_deg, magnitude FROM stars WHERE hip = ? LIMIT 1",
                (int(hip_id),)
            )
            row = cursor.fetchone()
            if row:
                return {
                    "name": f"HIP {hip_id}",
                    "ra_deg": float(row[4]),
                    "dec_deg": float(row[5]),
                    "mag": row[6],
                    "source_id": row[0],
                    "sao_id": row[2],
                    "hd_id": row[3],
                    "hip_id": row[1],
                    "catalog": "Crossreference",
                }
        except Exception as e:
            print(f"⚠️  Errore lookup HIP: {e}")
        return None

    def close(self) -> None:
        """Chiudi connessioni."""
        if self.crossref_conn:
            self.crossref_conn.close()


# Istanza globale
local_catalog = LocalCatalogManager()
