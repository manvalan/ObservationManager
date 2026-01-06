"""
Live stacking utility for ObservationManager.
Accumulates frames with simple translation alignment for real-time SNR improvement.
"""
import threading
import time
from typing import Callable, Dict, Optional, Tuple, Any
from pathlib import Path
from datetime import datetime
import logging

try:
    import cv2
    import numpy as np
    HAS_CV2 = True
except ImportError:  # pragma: no cover - cv2 optional in some environments
    cv2 = None
    np = None
    HAS_CV2 = False

try:
    from astropy.io import fits
    from astropy.time import Time
    HAS_ASTROPY = True
except ImportError:  # pragma: no cover - astropy optional
    fits = None
    Time = None
    HAS_ASTROPY = False

logger = logging.getLogger(__name__)


class LiveStacker:
    """Simple translation-based live stacking with optional polling loop."""

    def __init__(
        self,
        frame_provider: Callable[[], Optional["np.ndarray"]],
        save_fits_callable: Optional[Callable[..., str]] = None,
    ):
        if not HAS_CV2:
            raise RuntimeError("OpenCV non installato. pip install opencv-python")

        self.frame_provider = frame_provider
        self.save_fits_callable = save_fits_callable
        self.lock = threading.Lock()
        self.reset()

    def reset(self):
        """Reset internal accumulators."""
        with self.lock:
            self.reference_gray: Optional["np.ndarray"] = None
            self.accumulator: Optional["np.ndarray"] = None
            self.stack_count = 0
            self.last_offset: Tuple[float, float] = (0.0, 0.0)
            self.last_response: float = 0.0
            self.start_time: Optional[float] = None
            self.normalize = True
            self.max_frames: int = 0
            self.is_running = False
            self.poll_interval = 0.5
            self.last_frame_shape: Optional[Tuple[int, int, int]] = None

    def start(self, interval: float = 0.5, max_frames: int = 0, normalize: bool = True):
        """Start background stacking loop."""
        if self.is_running:
            return self.get_status()

        self.reset()
        self.normalize = normalize
        self.max_frames = max_frames
        self.start_time = time.time()
        self.poll_interval = max(interval, 0.01)
        self.is_running = True

        thread = threading.Thread(target=self._stack_loop, daemon=True, name="LiveStacker")
        thread.start()
        return self.get_status()

    def stop(self) -> Dict[str, Any]:
        """Stop stacking and return final status."""
        self.is_running = False
        return self.get_status()

    def _stack_loop(self):
        while self.is_running:
            frame = None
            try:
                frame = self.frame_provider()
            except Exception as exc:  # pragma: no cover - defensive
                logger.error(f"Errore lettura frame live stack: {exc}")

            if frame is not None:
                try:
                    self._accumulate(frame)
                except Exception as exc:
                    logger.error(f"Errore accumulo live stack: {exc}")

            if self.max_frames and self.stack_count >= self.max_frames:
                self.is_running = False
                break

            time.sleep(self.poll_interval)

    def _accumulate(self, frame: "np.ndarray"):
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if len(frame.shape) == 3 else frame
        gray_f32 = gray.astype("float32")

        with self.lock:
            if self.reference_gray is None:
                self.reference_gray = gray_f32
                self.last_frame_shape = frame.shape
                aligned = frame.astype("float32")
            else:
                if frame.shape[:2] != self.reference_gray.shape[:2]:
                    logger.warning("Frame size changed durante stacking; rescale to reference")
                    frame = cv2.resize(frame, (self.reference_gray.shape[1], self.reference_gray.shape[0]))
                    gray_f32 = cv2.resize(gray_f32, (self.reference_gray.shape[1], self.reference_gray.shape[0]))

                shift, response = cv2.phaseCorrelate(self.reference_gray, gray_f32)
                dx, dy = shift  # phaseCorrelate returns (dx, dy)
                self.last_offset = (dx, dy)
                self.last_response = float(response)

                transform = np.float32([[1, 0, dx], [0, 1, dy]])
                aligned = cv2.warpAffine(frame, transform, (frame.shape[1], frame.shape[0]), borderMode=cv2.BORDER_REFLECT)
                aligned = aligned.astype("float32")

            if self.accumulator is None:
                self.accumulator = aligned
            else:
                self.accumulator += aligned

            self.stack_count += 1
            if self.last_frame_shape is None:
                self.last_frame_shape = frame.shape

    def get_stack_image(self) -> Optional["np.ndarray"]:
        """Return stacked frame (float32)."""
        with self.lock:
            if self.accumulator is None or self.stack_count == 0:
                return None
            avg = self.accumulator / float(self.stack_count)
            return avg.copy()

    def get_preview(self) -> Optional["np.ndarray"]:
        """Return uint8 preview of the stacked image."""
        stacked = self.get_stack_image()
        if stacked is None:
            return None

        if self.normalize:
            min_val = stacked.min()
            max_val = stacked.max()
            if max_val > min_val:
                scaled = (stacked - min_val) / (max_val - min_val)
                stacked = (scaled * 255.0).clip(0, 255)
        return stacked.astype("uint8")

    def save_stack(
        self,
        filename: Optional[str] = None,
        fmt: str = "fits",
        metadata: Optional[Dict[str, Any]] = None,
        wcs_info: Optional[Dict[str, Any]] = None,
        output_dir: str = "data/stacking",
    ) -> str:
        stacked = self.get_stack_image()
        if stacked is None:
            raise RuntimeError("Nessun frame accumulato per il live stacking")

        Path(output_dir).mkdir(parents=True, exist_ok=True)
        if not filename:
            ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            filename = f"stack_{ts}"

        if fmt.lower() == "png":
            filepath = Path(output_dir) / f"{filename}.png"
            preview = self.get_preview()
            if preview is None:
                raise RuntimeError("Preview non disponibile per salvataggio")
            cv2.imwrite(str(filepath), preview)
            return str(filepath)

        if fmt.lower() != "fits":
            raise ValueError("Formato non supportato: usare 'fits' o 'png'")

        if self.save_fits_callable:
            # Reuse camera's FITS writer for consistent metadata
            return self.save_fits_callable(stacked.astype("float32"), filename, metadata, output_dir=output_dir, wcs_info=wcs_info)

        if not HAS_ASTROPY:
            raise RuntimeError("Astropy non installato per salvataggio FITS")

        filepath = Path(output_dir) / f"{filename}.fits"
        hdu = fits.PrimaryHDU(stacked.astype("float32"))
        hdu.header['DATE-OBS'] = Time.now().isot
        hdu.header['ORIGIN'] = 'ObservationManager'
        hdu.header['IMAGETYP'] = ('Light Frame', 'Live stack')

        if metadata:
            for key, value in metadata.items():
                fits_key = key.upper()[:8]
                try:
                    hdu.header[fits_key] = value
                except Exception as exc:
                    logger.debug(f"Skip metadata {key}: {exc}")

        if wcs_info:
            self._apply_wcs(hdu, stacked, wcs_info)

        hdu.writeto(filepath, overwrite=True)
        return str(filepath)

    def _apply_wcs(self, hdu: "fits.PrimaryHDU", data: "np.ndarray", wcs_info: Dict[str, Any]):
        try:
            ra = float(wcs_info.get("ra_deg")) if "ra_deg" in wcs_info else None
            dec = float(wcs_info.get("dec_deg")) if "dec_deg" in wcs_info else None
            pixel_scale = float(wcs_info.get("pixel_scale_arcsec", 0))
            rotation = float(wcs_info.get("rotation_deg", 0))
            if ra is None or dec is None or pixel_scale <= 0:
                return

            height, width = data.shape[:2]
            crpix1 = width / 2.0
            crpix2 = height / 2.0
            cdelt = pixel_scale / 3600.0

            hdu.header['CRVAL1'] = ra
            hdu.header['CRVAL2'] = dec
            hdu.header['CRPIX1'] = crpix1
            hdu.header['CRPIX2'] = crpix2
            hdu.header['CDELT1'] = -cdelt  # RA axis flipped
            hdu.header['CDELT2'] = cdelt
            hdu.header['CROTA2'] = rotation
        except Exception as exc:
            logger.debug(f"Skip WCS metadata: {exc}")

    def get_status(self) -> Dict[str, Any]:
        duration = time.time() - self.start_time if self.start_time else 0.0
        with self.lock:
            return {
                "is_running": self.is_running,
                "frames": self.stack_count,
                "duration": duration,
                "fps": (self.stack_count / duration) if duration > 0 else 0,
                "last_offset": self.last_offset,
                "last_response": self.last_response,
                "normalize": self.normalize,
                "max_frames": self.max_frames,
            }

