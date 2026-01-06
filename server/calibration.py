"""
Calibration automation for dark/flat/bias frame capture.
"""
import threading
import time
from pathlib import Path
from typing import Dict, Optional, Any
import logging

from server.camera import camera_controller

logger = logging.getLogger(__name__)


class CalibrationManager:
    """Manage automated calibration frame capture."""

    def __init__(self):
        self.is_running = False
        self.thread: Optional[threading.Thread] = None
        self._stop = False
        self.status: Dict[str, Any] = {
            "is_running": False,
            "type": None,
            "captured": 0,
            "total": 0,
            "last_file": None,
            "output_dir": None,
            "error": None,
        }

    def start(
        self,
        calib_type: str,
        count: int = 10,
        interval: float = 0.0,
        exposure: Optional[float] = None,
        gain: Optional[int] = None,
        output_dir: str = "data/calibration",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        if self.is_running:
            raise RuntimeError("Una sequenza di calibrazione è già in esecuzione")

        calib_type = calib_type.lower()
        if calib_type not in {"dark", "flat", "bias"}:
            raise ValueError("Tipo calibrazione non valido (dark/flat/bias)")

        self.is_running = True
        self._stop = False
        self.status = {
            "is_running": True,
            "type": calib_type,
            "captured": 0,
            "total": count,
            "last_file": None,
            "output_dir": str(Path(output_dir) / calib_type),
            "error": None,
            "exposure": exposure,
            "gain": gain,
        }

        self.thread = threading.Thread(
            target=self._run,
            args=(calib_type, count, interval, exposure, gain, metadata or {}),
            daemon=True,
            name="CalibrationCapture",
        )
        self.thread.start()
        return self.status.copy()

    def stop(self) -> Dict[str, Any]:
        self._stop = True
        return self.get_status()

    def _run(
        self,
        calib_type: str,
        count: int,
        interval: float,
        exposure: Optional[float],
        gain: Optional[int],
        metadata: Dict[str, Any],
    ):
        output_dir = Path(self.status["output_dir"])
        output_dir.mkdir(parents=True, exist_ok=True)

        original_settings = camera_controller.get_settings()
        restore_needed = False
        started_capture = False
        try:
            # Apply calibration settings if provided
            update_kwargs = {}
            if exposure is not None:
                update_kwargs["exposure"] = exposure
            if gain is not None:
                update_kwargs["gain"] = gain
            if update_kwargs:
                camera_controller.update_settings(**update_kwargs)
                restore_needed = True

            if not camera_controller.is_capturing:
                camera_controller.start_capture()
                started_capture = True

            for idx in range(count):
                if self._stop:
                    break

                frame = camera_controller.capture_single(timeout=5.0)
                filename = f"{calib_type}_{time.strftime('%Y%m%d_%H%M%S')}_{idx+1:03d}"

                calib_metadata = {
                    "IMAGETYP": f"{calib_type.capitalize()} Frame",
                    "CALTYPE": calib_type,
                    "EXPTIME": camera_controller.settings.get("exposure", -1),
                    "GAIN": camera_controller.settings.get("gain", -1),
                }
                calib_metadata.update(metadata)

                filepath = camera_controller.save_fits(
                    frame,
                    filename,
                    metadata=calib_metadata,
                    output_dir=str(output_dir),
                )

                self.status["captured"] = idx + 1
                self.status["last_file"] = filepath
                time.sleep(max(interval, 0.0))

        except Exception as exc:
            logger.error(f"Errore cattura calibrazione: {exc}")
            self.status["error"] = str(exc)
        finally:
            if started_capture:
                try:
                    camera_controller.stop_capture()
                except Exception:
                    pass
            if restore_needed:
                try:
                    camera_controller.update_settings(
                        exposure=original_settings.get("exposure"),
                        gain=original_settings.get("gain"),
                    )
                except Exception:
                    pass
            self.is_running = False
            self.status["is_running"] = False

    def get_status(self) -> Dict[str, Any]:
        return self.status.copy()


calibration_manager = CalibrationManager()
