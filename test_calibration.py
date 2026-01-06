#!/usr/bin/env python3
"""
Smoke test per CalibrationManager (Milestone 5B)
- Verifica flusso dark/flat/bias con camera_controller mockato
"""
import sys
import time
from pathlib import Path

import numpy as np

from server.calibration import calibration_manager
from server import camera as camera_module


def main():
    print("=" * 60)
    print("CalibrationManager Smoke Test")
    print("=" * 60)

    cam = camera_module.camera_controller

    # Backup metodi reali
    original = {
        "update_settings": cam.update_settings,
        "start_capture": cam.start_capture,
        "stop_capture": cam.stop_capture,
        "capture_single": cam.capture_single,
        "save_fits": cam.save_fits,
        "get_settings": cam.get_settings,
        "settings": cam.settings.copy(),
    }

    records = {
        "update_calls": [],
        "started": False,
        "stopped": False,
        "save_calls": [],
    }

    dummy_frame = np.ones((8, 8), dtype=np.uint8) * 100

    def fake_update_settings(**kwargs):
        records["update_calls"].append(kwargs)
        cam.settings.update(kwargs)
        return cam.settings

    def fake_start_capture():
        records["started"] = True

    def fake_stop_capture():
        records["stopped"] = True

    def fake_capture_single(timeout: float = 5.0):
        return dummy_frame

    def fake_save_fits(frame, filename, metadata=None, output_dir="data/images", wcs_info=None):
        out_dir = Path(output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / f"{filename}.fits"
        path.write_bytes(b"test")
        records["save_calls"].append((filename, metadata))
        return str(path)

    def fake_get_settings():
        return cam.settings.copy()

    try:
        cam.update_settings = fake_update_settings
        cam.start_capture = fake_start_capture
        cam.stop_capture = fake_stop_capture
        cam.capture_single = fake_capture_single
        cam.save_fits = fake_save_fits
        cam.get_settings = fake_get_settings

        status = calibration_manager.start(
            calib_type="dark",
            count=2,
            interval=0.0,
            exposure=5,
            gain=10,
            output_dir="data/calibration_test",
            metadata={"TEST": 1},
        )
        print(f"Avviato: {status}")

        # Attendi completamento
        timeout = time.time() + 5
        while calibration_manager.is_running and time.time() < timeout:
            time.sleep(0.05)

        final_status = calibration_manager.get_status()
        print(f"Finale: {final_status}")

        assert final_status["captured"] == 2, "Devono essere catturati 2 frame"
        assert final_status["error"] is None, f"Errore inatteso: {final_status['error']}"
        assert records["started"], "start_capture non chiamato"
        assert records["stopped"], "stop_capture non chiamato"
        assert len(records["save_calls"]) == 2, "save_fits deve essere chiamato 2 volte"

        print("\n✅ CalibrationManager test completato")
        return 0
    except AssertionError as exc:
        print(f"❌ Test fallito: {exc}")
        return 1
    finally:
        # Ripristina metodi originali
        cam.update_settings = original["update_settings"]
        cam.start_capture = original["start_capture"]
        cam.stop_capture = original["stop_capture"]
        cam.capture_single = original["capture_single"]
        cam.save_fits = original["save_fits"]
        cam.get_settings = original["get_settings"]
        cam.settings = original["settings"].copy()

        # Cleanup file
        try:
            out_dir = Path("data/calibration_test")
            for f in out_dir.glob("*.fits"):
                f.unlink()
            if out_dir.exists() and not any(out_dir.iterdir()):
                out_dir.rmdir()
        except Exception:
            pass


if __name__ == "__main__":
    sys.exit(main())
