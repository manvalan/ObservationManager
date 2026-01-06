"""
Frame Capture - ObservationManager
Classe dedicata per cattura singoli frame da telecamera
"""
import time
import threading
from typing import Optional, Dict, Any, Tuple
from pathlib import Path
from datetime import datetime
import logging

try:
    import cv2
    import numpy as np
    HAS_CV2 = True
except ImportError:
    cv2 = None
    np = None
    HAS_CV2 = False

try:
    from astropy.io import fits
    from astropy.time import Time
    HAS_ASTROPY = True
except ImportError:
    fits = None
    Time = None
    HAS_ASTROPY = False

logger = logging.getLogger(__name__)


class FrameCapture:
    """
    Cattura frame singoli da telecamera.
    
    Features:
    - Cattura singola o continua
    - Buffer circolare per frame recenti
    - Salvataggio in multiple formati (PNG, JPG, FITS)
    - Statistiche immagine (mean, std, histogram)
    - Metadata FITS per astronomia
    - Thread-safe
    """
    
    def __init__(self, video_capture: cv2.VideoCapture, buffer_size: int = 10):
        """
        Inizializza frame capture.
        
        Args:
            video_capture: Oggetto cv2.VideoCapture già aperto
            buffer_size: Dimensione buffer frame recenti
        """
        if not HAS_CV2:
            raise RuntimeError("OpenCV non installato")
        
        if video_capture is None or not video_capture.isOpened():
            raise ValueError("VideoCapture deve essere aperto")
        
        self.capture = video_capture
        self.buffer_size = buffer_size
        
        # Buffer circolare
        self.frame_buffer = []
        self.buffer_lock = threading.Lock()
        
        # Cattura continua (opzionale)
        self.is_capturing = False
        self.capture_thread: Optional[threading.Thread] = None
        
        # Ultimo frame
        self.last_frame: Optional[np.ndarray] = None
        self.last_capture_time: Optional[float] = None
        
        logger.info("FrameCapture inizializzato")
    
    def capture_single(self, timeout: float = 5.0) -> np.ndarray:
        """
        Cattura singolo frame.
        
        Args:
            timeout: Timeout in secondi
        
        Returns:
            Frame numpy array (BGR)
        
        Raises:
            RuntimeError: Se cattura fallisce entro timeout
        """
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            ret, frame = self.capture.read()
            
            if ret and frame is not None:
                with self.buffer_lock:
                    self.last_frame = frame.copy()
                    self.last_capture_time = time.time()
                    
                    # Aggiungi a buffer
                    self.frame_buffer.append(frame.copy())
                    if len(self.frame_buffer) > self.buffer_size:
                        self.frame_buffer.pop(0)
                
                logger.debug("Frame catturato")
                return frame
            
            time.sleep(0.05)
        
        raise RuntimeError(f"Impossibile catturare frame entro {timeout}s")
    
    def get_last_frame(self) -> Optional[np.ndarray]:
        """
        Ritorna ultimo frame catturato.
        
        Returns:
            Frame numpy array o None
        """
        with self.buffer_lock:
            return self.last_frame.copy() if self.last_frame is not None else None
    
    def get_frame_buffer(self) -> list[np.ndarray]:
        """
        Ritorna tutti i frame nel buffer.
        
        Returns:
            Lista di frame numpy array
        """
        with self.buffer_lock:
            return [f.copy() for f in self.frame_buffer]
    
    def start_continuous(self, fps: float = 30.0):
        """
        Avvia cattura continua in background.
        
        Args:
            fps: Frame rate target
        """
        if self.is_capturing:
            logger.warning("Cattura continua già attiva")
            return
        
        self.is_capturing = True
        self.capture_thread = threading.Thread(
            target=self._capture_loop,
            args=(fps,),
            daemon=True,
            name="FrameCapture"
        )
        self.capture_thread.start()
        
        logger.info(f"Cattura continua avviata ({fps} fps)")
    
    def stop_continuous(self):
        """Ferma cattura continua."""
        if not self.is_capturing:
            return
        
        self.is_capturing = False
        if self.capture_thread:
            self.capture_thread.join(timeout=2.0)
            self.capture_thread = None
        
        logger.info("Cattura continua fermata")
    
    def _capture_loop(self, fps: float):
        """Loop cattura continua (esegue in thread separato)."""
        frame_interval = 1.0 / fps
        
        while self.is_capturing:
            loop_start = time.time()
            
            try:
                ret, frame = self.capture.read()
                
                if ret and frame is not None:
                    with self.buffer_lock:
                        self.last_frame = frame.copy()
                        self.last_capture_time = time.time()
                        
                        # Aggiungi a buffer circolare
                        self.frame_buffer.append(frame.copy())
                        if len(self.frame_buffer) > self.buffer_size:
                            self.frame_buffer.pop(0)
            
            except Exception as e:
                logger.error(f"Errore cattura frame: {e}")
            
            # Mantieni fps target
            elapsed = time.time() - loop_start
            sleep_time = max(0, frame_interval - elapsed)
            if sleep_time > 0:
                time.sleep(sleep_time)
    
    # ========== Salvataggio Frame ==========
    
    def save_png(
        self,
        frame: Optional[np.ndarray] = None,
        filename: Optional[str] = None,
        output_dir: str = "data/frames"
    ) -> str:
        """
        Salva frame come PNG lossless.
        
        Args:
            frame: Frame da salvare. Se None, usa ultimo frame catturato.
            filename: Nome file (senza estensione). Se None, usa timestamp.
            output_dir: Directory output
        
        Returns:
            Path completo file salvato
        """
        if frame is None:
            frame = self.get_last_frame()
            if frame is None:
                raise RuntimeError("Nessun frame disponibile")
        
        # Crea directory
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        # Nome file
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
            filename = f"frame_{timestamp}"
        
        filepath = output_path / f"{filename}.png"
        
        # Salva PNG
        cv2.imwrite(str(filepath), frame)
        
        logger.info(f"Frame salvato: {filepath}")
        return str(filepath)
    
    def save_jpg(
        self,
        frame: Optional[np.ndarray] = None,
        filename: Optional[str] = None,
        quality: int = 95,
        output_dir: str = "data/frames"
    ) -> str:
        """
        Salva frame come JPEG.
        
        Args:
            frame: Frame da salvare. Se None, usa ultimo frame.
            filename: Nome file (senza estensione). Se None, usa timestamp.
            quality: Qualità JPEG 0-100
            output_dir: Directory output
        
        Returns:
            Path completo file salvato
        """
        if frame is None:
            frame = self.get_last_frame()
            if frame is None:
                raise RuntimeError("Nessun frame disponibile")
        
        # Crea directory
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        # Nome file
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
            filename = f"frame_{timestamp}"
        
        filepath = output_path / f"{filename}.jpg"
        
        # Salva JPEG
        cv2.imwrite(str(filepath), frame, [cv2.IMWRITE_JPEG_QUALITY, quality])
        
        logger.info(f"Frame salvato: {filepath}")
        return str(filepath)
    
    def save_fits(
        self,
        frame: Optional[np.ndarray] = None,
        filename: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        output_dir: str = "data/frames"
    ) -> str:
        """
        Salva frame come FITS astronomico.
        
        Args:
            frame: Frame da salvare. Se None, usa ultimo frame.
            filename: Nome file (senza estensione). Se None, usa timestamp.
            metadata: Metadata FITS (OBJECT, RA, DEC, etc.)
            output_dir: Directory output
        
        Returns:
            Path completo file salvato
        """
        if not HAS_ASTROPY:
            raise RuntimeError("Astropy non installato. pip install astropy")
        
        if frame is None:
            frame = self.get_last_frame()
            if frame is None:
                raise RuntimeError("Nessun frame disponibile")
        
        # Converti a grayscale per FITS
        if len(frame.shape) == 3:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        else:
            gray = frame
        
        # Crea directory
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        # Nome file
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"frame_{timestamp}"
        
        filepath = output_path / f"{filename}.fits"
        
        # Crea FITS HDU
        hdu = fits.PrimaryHDU(gray)
        
        # Metadata base
        hdu.header['DATE-OBS'] = Time.now().isot
        hdu.header['ORIGIN'] = 'ObservationManager'
        
        # Aggiungi metadata personalizzati
        if metadata:
            for key, value in metadata.items():
                try:
                    hdu.header[key] = value
                except Exception as e:
                    logger.warning(f"Impossibile aggiungere metadata {key}: {e}")
        
        # Salva FITS
        hdu.writeto(filepath, overwrite=True)
        
        logger.info(f"FITS salvato: {filepath}")
        return str(filepath)
    
    # ========== Statistiche Frame ==========
    
    def compute_statistics(self, frame: Optional[np.ndarray] = None) -> Dict[str, Any]:
        """
        Calcola statistiche frame.
        
        Args:
            frame: Frame da analizzare. Se None, usa ultimo frame.
        
        Returns:
            Dict con mean, std, min, max, histogram
        """
        if frame is None:
            frame = self.get_last_frame()
            if frame is None:
                raise RuntimeError("Nessun frame disponibile")
        
        # Converti a grayscale
        if len(frame.shape) == 3:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        else:
            gray = frame
        
        # Statistiche base
        mean_val = float(np.mean(gray))
        std_val = float(np.std(gray))
        min_val = int(np.min(gray))
        max_val = int(np.max(gray))
        
        # Histogram
        hist, _ = np.histogram(gray, bins=256, range=(0, 256))
        histogram = hist.tolist()
        
        # SNR approssimato
        snr = mean_val / std_val if std_val > 0 else 0
        
        return {
            "mean": mean_val,
            "std": std_val,
            "min": min_val,
            "max": max_val,
            "snr": snr,
            "histogram": histogram,
            "shape": gray.shape
        }
    
    def __del__(self):
        """Cleanup."""
        self.stop_continuous()


# Esempio di utilizzo
if __name__ == "__main__":
    import sys
    
    # Apri webcam
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("Errore: impossibile aprire webcam")
        sys.exit(1)
    
    # Crea frame capture
    fc = FrameCapture(cap, buffer_size=5)
    
    # Cattura singola
    print("Cattura frame singolo...")
    frame = fc.capture_single()
    print(f"Frame catturato: shape={frame.shape}")
    
    # Salva in vari formati
    png_path = fc.save_png(frame, "test_frame")
    print(f"PNG salvato: {png_path}")
    
    jpg_path = fc.save_jpg(frame, "test_frame", quality=95)
    print(f"JPG salvato: {jpg_path}")
    
    if HAS_ASTROPY:
        fits_path = fc.save_fits(frame, "test_frame", metadata={"OBJECT": "Test"})
        print(f"FITS salvato: {fits_path}")
    
    # Statistiche
    stats = fc.compute_statistics(frame)
    print(f"\nStatistiche:")
    print(f"  Mean: {stats['mean']:.1f}")
    print(f"  Std:  {stats['std']:.1f}")
    print(f"  SNR:  {stats['snr']:.2f}")
    print(f"  Min:  {stats['min']}")
    print(f"  Max:  {stats['max']}")
    
    # Cattura continua per 3 secondi
    print("\nCattura continua per 3 secondi...")
    fc.start_continuous(fps=30.0)
    time.sleep(3)
    fc.stop_continuous()
    
    # Buffer frames
    buffer = fc.get_frame_buffer()
    print(f"Frames in buffer: {len(buffer)}")
    
    # Cleanup
    cap.release()
    print("\nCompletato!")
