"""Filter wheel controller (serial + mock).

Supports:
- Serial/USB wheels (generic commands placeholder)
- MockFilterWheel for testing without hardware

Thread-safe operations, simple stats, and default 6-slot filter set.
"""

import threading
import time
from enum import Enum
from typing import Dict, List, Optional


class FilterWheelStatus(Enum):
    IDLE = "idle"
    MOVING = "moving"
    ERROR = "error"
    DISCONNECTED = "disconnected"


class Filter:
    def __init__(self, position: int, name: str, color: str = "#888888", wavelength_nm: Optional[int] = None):
        self.position = position
        self.name = name
        self.color = color
        self.wavelength_nm = wavelength_nm

    def to_dict(self) -> Dict:
        return {
            "position": self.position,
            "name": self.name,
            "color": self.color,
            "wavelength_nm": self.wavelength_nm,
        }


class SerialFilterWheel:
    """Filter wheel controller. If port is None, works in mock mode."""

    def __init__(self, port: Optional[str] = None, baudrate: int = 9600, timeout: float = 2.0):
        self._port = port
        self._baudrate = baudrate
        self._timeout = timeout
        self._lock = threading.RLock()
        self._connected = False
        self._position = 0
        self._status = FilterWheelStatus.DISCONNECTED

        # Default filters (6-slot)
        self._filters: List[Filter] = [
            Filter(0, "Clear", "#ffffff"),
            Filter(1, "Red", "#ff4d4d", 650),
            Filter(2, "Green", "#00ff99", 550),
            Filter(3, "Blue", "#3399ff", 450),
            Filter(4, "H-Alpha", "#ff66b2", 656),
            Filter(5, "OIII", "#33ffff", 500),
        ]

        # Mock parameters
        self._mock_move_time = 1.0
        self._mock_target_position = 0
        self._mock_moving_start = 0.0

        # Stats
        self._stats = {"moves_total": 0, "errors": 0, "uptime_sec": 0}
        self._start_time = time.time()

    # --------------------------------------------------------------
    # Connection
    # --------------------------------------------------------------
    def connect(self) -> bool:
        with self._lock:
            if self._port is None:
                self._connected = True
                self._status = FilterWheelStatus.IDLE
                return True
            try:  # pragma: no cover (hardware)
                import serial  # type: ignore

                self._serial = serial.Serial(self._port, self._baudrate, timeout=self._timeout)
                self._connected = True
                self._status = FilterWheelStatus.IDLE
                self._query_position()
                return True
            except Exception:
                self._status = FilterWheelStatus.ERROR
                return False

    def disconnect(self) -> bool:
        with self._lock:
            if self._port is None:
                self._connected = False
                self._status = FilterWheelStatus.DISCONNECTED
                return True
            try:  # pragma: no cover
                if hasattr(self, "_serial"):
                    self._serial.close()
                self._connected = False
                self._status = FilterWheelStatus.DISCONNECTED
                return True
            except Exception:
                return False

    def is_connected(self) -> bool:
        return self._connected

    # --------------------------------------------------------------
    # Movement
    # --------------------------------------------------------------
    def select_filter(self, position: int) -> bool:
        with self._lock:
            if not self._connected:
                return False
            if position < 0 or position >= len(self._filters):
                self._stats["errors"] += 1
                return False

            try:
                if self._port is None:
                    self._status = FilterWheelStatus.MOVING
                    self._mock_target_position = position
                    self._mock_moving_start = time.time()
                else:  # pragma: no cover
                    cmd = f"$MOVE{position}\r"
                    self._serial.write(cmd.encode())
                    self._status = FilterWheelStatus.MOVING
                    self._mock_target_position = position
                self._stats["moves_total"] += 1
                return True
            except Exception:
                self._status = FilterWheelStatus.ERROR
                self._stats["errors"] += 1
                return False

    def wait_for_position(self, position: int, timeout: float = 10.0) -> bool:
        start = time.time()
        while time.time() - start < timeout:
            status = self.get_status()  # updates mock state
            if status["position"] == position and not status["moving"]:
                return True
            time.sleep(0.1)
        return False

    # --------------------------------------------------------------
    # Filters
    # --------------------------------------------------------------
    def get_filters(self) -> List[Dict]:
        with self._lock:
            return [f.to_dict() for f in self._filters]

    def get_filter_count(self) -> int:
        return len(self._filters)

    def get_filter_name(self, position: int) -> str:
        if 0 <= position < len(self._filters):
            return self._filters[position].name
        return "Unknown"

    def get_position(self) -> int:
        """Return current filter position."""
        return self._position

    def set_filter_names(self, names: List[str]) -> bool:
        with self._lock:
            if len(names) != len(self._filters):
                return False
            for i, name in enumerate(names):
                self._filters[i].name = name
            return True

    # --------------------------------------------------------------
    # Status & stats
    # --------------------------------------------------------------
    def get_status(self) -> Dict:
        with self._lock:
            if self._port is None and self._status == FilterWheelStatus.MOVING:
                elapsed = time.time() - self._mock_moving_start
                if elapsed >= self._mock_move_time:
                    self._position = self._mock_target_position
                    self._status = FilterWheelStatus.IDLE

            return {
                "connected": self._connected,
                "status": self._status.value,
                "position": self._position,
                "filter_name": self.get_filter_name(self._position),
                "filter_count": len(self._filters),
                "moving": self._status == FilterWheelStatus.MOVING,
                "uptime_sec": time.time() - self._start_time,
            }

    def get_statistics(self) -> Dict:
        with self._lock:
            stats = dict(self._stats)
            stats["uptime_sec"] = time.time() - self._start_time
            return stats

    # --------------------------------------------------------------
    # Internal
    # --------------------------------------------------------------
    def _query_position(self) -> bool:
        if self._port is None:
            return True
        try:  # pragma: no cover
            self._serial.write(b"$POS?\r")
            resp = self._serial.readline().decode().strip()
            if resp.startswith("$"):
                self._position = int(resp[1:])
                self._status = FilterWheelStatus.IDLE
                return True
        except Exception:
            pass
        return False


class MockFilterWheel(SerialFilterWheel):
    def __init__(self):
        super().__init__(port=None, timeout=2.0)
        self._connected = True
        self._status = FilterWheelStatus.IDLE


class FilterWheelManager:
    _instance: Optional["FilterWheelManager"] = None
    _lock = threading.RLock()

    def __new__(cls) -> "FilterWheelManager":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not hasattr(self, "_initialized"):
            self._wheels: Dict[str, SerialFilterWheel] = {}
            self._default_wheel: Optional[str] = None
            self._initialized = True

    def create_wheel(self, name: str, port: Optional[str] = None, baudrate: int = 9600) -> SerialFilterWheel:
        wheel = SerialFilterWheel(port=port, baudrate=baudrate)
        self._wheels[name] = wheel
        if self._default_wheel is None:
            self._default_wheel = name
        return wheel

    def get_wheel(self, name: Optional[str] = None) -> Optional[SerialFilterWheel]:
        if name is None:
            name = self._default_wheel
        return self._wheels.get(name)

    def list_wheels(self) -> List[str]:
        return list(self._wheels.keys())

    def remove_wheel(self, name: str) -> bool:
        if name in self._wheels:
            self._wheels[name].disconnect()
            del self._wheels[name]
            if self._default_wheel == name:
                self._default_wheel = next(iter(self._wheels)) if self._wheels else None
            return True
        return False


filter_wheel_manager = FilterWheelManager()
