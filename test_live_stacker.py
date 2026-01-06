#!/usr/bin/env python3
"""
Smoke test per LiveStacker (Milestone 5B)
- Verifica accumulo con allineamento
- Verifica salvataggio PNG senza dipendere da astropy
"""
import sys
import time
from pathlib import Path

try:
    import numpy as np
    import cv2
except ImportError:
    print("⚠️ OpenCV o numpy non disponibili: skip live stacking test")
    sys.exit(0)

from server.live_stacker import LiveStacker


def make_shifted_frame(shift_x: int = 0, shift_y: int = 0) -> "np.ndarray":
    base = np.zeros((64, 64), dtype=np.uint8)
    cv2.circle(base, (32, 32), 5, 255, -1)
    M = np.float32([[1, 0, shift_x], [0, 1, shift_y]])
    shifted = cv2.warpAffine(base, M, (64, 64), borderMode=cv2.BORDER_REFLECT)
    return shifted


def main():
    print("=" * 60)
    print("LiveStacker Smoke Test")
    print("=" * 60)

    # Prepara frames
    f1 = cv2.cvtColor(make_shifted_frame(0, 0), cv2.COLOR_GRAY2BGR)
    f2 = cv2.cvtColor(make_shifted_frame(2, 1), cv2.COLOR_GRAY2BGR)

    # Usa provider dummy (non serve nel test diretto)
    stacker = LiveStacker(lambda: None)

    # Accumulo manuale (evita thread)
    stacker._accumulate(f1)
    stacker._accumulate(f2)

    status = stacker.get_status()
    print(f"Frames accumulati: {status['frames']}")
    print(f"Ultimo offset stimato: {status['last_offset']}")
    assert status['frames'] == 2, "Deve accumulare due frame"

    stacked = stacker.get_stack_image()
    assert stacked is not None, "Stacked frame non deve essere None"
    assert stacked.shape[:2] == f1.shape[:2], "Dimensioni inattese"
    print("✓ Stack image generato")

    # Preview e salvataggio PNG
    preview = stacker.get_preview()
    assert preview is not None, "Preview non generata"
    print("✓ Preview generata")

    out_dir = Path("data/stacking_test")
    path = stacker.save_stack(fmt="png", output_dir=str(out_dir))
    print(f"✓ Stack salvato: {path}")
    assert Path(path).exists(), "File PNG non creato"

    # Cleanup leggero
    try:
        for f in out_dir.glob("*.png"):
            f.unlink()
        if not any(out_dir.iterdir()):
            out_dir.rmdir()
    except Exception:
        pass

    print("\n✅ LiveStacker test completato")


if __name__ == "__main__":
    sys.exit(main())
