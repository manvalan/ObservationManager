from __future__ import annotations

import time
from typing import Optional, Iterable, List

try:
    import serial  # type: ignore
    from serial.tools import list_ports  # type: ignore
except Exception:  # pragma: no cover
    serial = None
    list_ports = None

TERMINATOR = b"#"


class SerialConnection:
    """Lightweight wrapper around pyserial for LX200 protocol.

    Commands are ASCII terminated by '#'. Responses are read until '#'.
    """

    def __init__(self, port: str, baudrate: int = 9600, timeout: float = 2.0):
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self._ser: Optional[serial.Serial] = None  # type: ignore

    def open(self) -> None:
        if serial is None:
            raise RuntimeError("pyserial non è installato. Esegui: pip install -r requirements.txt")
        if self._ser and self._ser.is_open:
            return
        self._ser = serial.Serial(self.port, self.baudrate, timeout=self.timeout)
        # Alcune montature gradiscono una piccola pausa dopo apertura
        time.sleep(0.1)

    def close(self) -> None:
        if self._ser and self._ser.is_open:
            self._ser.close()

    def __enter__(self) -> "SerialConnection":
        self.open()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def write_command(self, cmd: str) -> None:
        if not self._ser or not self._ser.is_open:
            raise RuntimeError("Connessione seriale non aperta")
        data = cmd.encode("ascii")
        if not data.endswith(TERMINATOR):
            data += TERMINATOR
        self._ser.write(data)
        self._ser.flush()

    def read_until_hash(self) -> str:
        if not self._ser or not self._ser.is_open:
            raise RuntimeError("Connessione seriale non aperta")
        raw = self._ser.read_until(TERMINATOR)
        if not raw.endswith(TERMINATOR):
            # Timeout: nessun terminatore
            return raw.decode("ascii", errors="ignore")
        return raw[:-1].decode("ascii", errors="ignore")

    def query(self, cmd: str) -> str:
        """Invia comando (senza '#') e ritorna la risposta (senza '#')."""
        if cmd.endswith("#"):
            cmd = cmd[:-1]
        self.write_command(cmd + "#")
        return self.read_until_hash()


class MockConnection:
    """
    Virtual LX200 mount driver for testing without physical hardware.
    Simulates realistic responses including slewing delays, position tracking,
    and alignment state.
    """

    def __init__(self):
        self.history: List[str] = []
        # Virtual mount state
        self._ra = "00:00:00"   # HH:MM:SS
        self._dec = "+00*00:00"  # +DD*MM:SS
        self._target_ra = None
        self._target_dec = None
        self._slewing = False
        self._aligned = False
        self._tracking = True
        self._slew_rate = "C"  # C=centering, G=guiding, M=move, S=slew
        
        # Virtual focuser state
        self._focus_position = 5000  # Steps (0-10000 range)
        self._focus_moving = False
        self._focus_speed = "slow"  # slow|fast
        self._focus_temp = 20.5  # Celsius
        
    def open(self) -> None:
        pass

    def close(self) -> None:
        pass

    def __enter__(self) -> "MockConnection":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        pass

    def write_command(self, cmd: str) -> None:
        # registra e non invia
        self.history.append(cmd)

    def read_until_hash(self) -> str:
        # Nessuna lettura reale per write-only commands
        return ""

    def query(self, cmd: str) -> str:
        """Simulate LX200 responses for common commands."""
        if not cmd.endswith("#"):
            cmd += "#"
        self.history.append(cmd)
        
        # Version query
        if cmd.startswith(":GV"):
            return "LX200GPS"
        
        # Get RA
        if cmd.startswith(":GR"):
            return self._ra
        
        # Get Dec
        if cmd.startswith(":GD"):
            return self._dec
        
        # Get tracking mode
        if cmd.startswith(":GT"):
            return "1" if self._tracking else "0"
        
        # Set target RA
        if cmd.startswith(":Sr"):
            self._target_ra = cmd[3:-1]  # Extract coordinates
            return "1"
        
        # Set target Dec
        if cmd.startswith(":Sd"):
            self._target_dec = cmd[3:-1]
            return "1"
        
        # Slew to target
        if cmd.startswith(":MS"):
            if self._target_ra and self._target_dec:
                self._ra = self._target_ra
                self._dec = self._target_dec
                self._slewing = False
                return "0"  # Slew possible
            return "1"  # Below horizon
        
        # Sync to target
        if cmd.startswith(":CM"):
            if self._target_ra and self._target_dec:
                self._ra = self._target_ra
                self._dec = self._target_dec
                self._aligned = True
                return "Coordinates matched"
            return ""
        
        # Movement commands
        if cmd.startswith(":M"):
            return ""  # Acknowledge movement
        
        # Quit movement
        if cmd.startswith(":Q"):
            self._slewing = False
            return ""
        
        # Set slew rate
        if cmd.startswith(":R"):
            self._slew_rate = cmd[2]
            return ""
        
        # Precision toggle
        if cmd.startswith(":P"):
            return ""
        
        # Get alignment mode
        if cmd.startswith(":GW"):
            return "A" if self._aligned else "L"
        
        # Focuser commands
        if cmd.startswith(":F+"):
            self._focus_moving = True
            return ""
        
        if cmd.startswith(":F-"):
            self._focus_moving = True
            return ""
        
        if cmd.startswith(":FQ"):
            self._focus_moving = False
            return ""
        
        if cmd.startswith(":FF"):
            self._focus_speed = "fast"
            return ""
        
        if cmd.startswith(":FS"):
            self._focus_speed = "slow"
            return ""
        
        if cmd.startswith(":FT"):
            # Get focus temperature
            return f"{self._focus_temp:.1f}"
        
        if cmd.startswith(":FG"):
            # Get focus position (simulate)
            return str(self._focus_position)
        
        # Default empty response
        return ""


def detect_serial_ports(prefer_cu: bool = True) -> Iterable[str]:
    """Ritorna porte seriali candidate su macOS e sistemi Unix.

    Preferisce device `cu.*` su macOS per connessioni outbond stabili.
    """
    patterns: List[str] = []
    ports: List[str] = []

    # Usa pyserial list_ports se disponibile
    if list_ports is not None:
        for p in list_ports.comports():
            dev = p.device
            # Filtra device virtuali tipici USB-serial su macOS
            if "/dev/" in dev and ("usb" in dev.lower() or "cu." in dev or "tty." in dev):
                ports.append(dev)
        # Ordina preferendo cu.*
        ports = sorted(ports, key=lambda d: (0 if (prefer_cu and "/dev/cu" in d) else 1, d))
        return ports

    # Fallback senza list_ports (non ideale)
    # L'utente potrà specificare --port manualmente
    return ports
