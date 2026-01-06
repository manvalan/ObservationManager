"""
Camera Control Module - ObservationManager
Gestisce device video, controlli esposizione/gain/binning, cattura immagini, plate solving
Supporto Watec 910BD con sistema TACOS Arduino
"""
import time
import threading
from typing import Optional, Dict, List, Any, Tuple
from pathlib import Path
from datetime import datetime
import json
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

try:
    from server.watec_controller import get_watec_controller
    HAS_WATEC = True
except ImportError:
    HAS_WATEC = False

logger = logging.getLogger(__name__)


class CameraController:
    """
    Controller per camera astronomica/webcam con supporto:
    - Multiple device (USB/UVC)
    - Controlli esposizione, gain, binning
    - Cattura singola/continua
    - Salvataggio FITS con metadata
    - Statistiche immagine (istogramma, FWHM, SNR)
    """
    
    def __init__(self):
        if not HAS_CV2:
            raise RuntimeError("OpenCV non installato. pip install opencv-python")
        
        self.device: Optional[cv2.VideoCapture] = None
        self.device_index: Optional[int] = None
        self.is_capturing = False
        self.capture_thread: Optional[threading.Thread] = None
        self.last_frame: Optional[np.ndarray] = None
        self.frame_lock = threading.Lock()
        
        # Camera settings
        self.settings = {
            "exposure": -1,  # Auto exposure (-1) o ms
            "gain": -1,      # Auto gain (-1) o valore 0-100
            "binning": 1,    # 1=no binning, 2=2x2, 4=4x4
            "fps": 30.0,
            "width": 640,
            "height": 480,
        }
        
        # Watec 910BD controller (se disponibile)
        self.watec = None
        self.is_watec_camera = False
        if HAS_WATEC:
            self.watec = get_watec_controller()
            logger.info("Supporto Watec 910BD abilitato")
        
        # Statistics cache
        self.stats_cache: Dict[str, Any] = {}
        
    def list_devices(self, max_check: int = 10) -> List[Dict[str, Any]]:
        """
        Scansiona dispositivi video disponibili.
        
        Returns:
            Lista di device con index, name, resolutions
        """
        devices = []
        for i in range(max_check):
            cap = cv2.VideoCapture(i)
            if cap.isOpened():
                width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                fps = cap.get(cv2.CAP_PROP_FPS)
                
                devices.append({
                    "index": i,
                    "name": f"Camera {i}",
                    "backend": cap.getBackendName(),
                    "width": width,
                    "height": height,
                    "fps": fps,
                    "available": True
                })
                cap.release()
        return devices
    
    def open_device(self, device_index: int = 0) -> Dict[str, Any]:
        """
        Apre device video e applica settings.
        
        Args:
            device_index: Indice device video (0 = default)
            
        Returns:
            Device info con capabilities
        """
        if self.device is not None and self.device_index == device_index:
            return {"status": "already_open", "index": device_index}
        
        self.close_device()
        
        self.device = cv2.VideoCapture(device_index)
        if not self.device.isOpened():
            raise RuntimeError(f"Impossibile aprire camera index {device_index}")
        
        self.device_index = device_index
        
        # Applica settings iniziali
        self._apply_settings()
        
        # Leggi capabilities
        caps = self._get_capabilities()
        
        return {
            "status": "opened",
            "index": device_index,
            "capabilities": caps,
            "settings": self.settings.copy()
        }
    
    def close_device(self):
        """Chiude device e ferma capture."""
        self.stop_capture()
        if self.device is not None:
            self.device.release()
            self.device = None
            self.device_index = None
    
    def _get_capabilities(self) -> Dict[str, Any]:
        """Legge capabilities device corrente."""
        if self.device is None:
            return {}
        
        return {
            "width": int(self.device.get(cv2.CAP_PROP_FRAME_WIDTH)),
            "height": int(self.device.get(cv2.CAP_PROP_FRAME_HEIGHT)),
            "fps": self.device.get(cv2.CAP_PROP_FPS),
            "brightness": self.device.get(cv2.CAP_PROP_BRIGHTNESS),
            "contrast": self.device.get(cv2.CAP_PROP_CONTRAST),
            "saturation": self.device.get(cv2.CAP_PROP_SATURATION),
            "exposure": self.device.get(cv2.CAP_PROP_EXPOSURE),
            "gain": self.device.get(cv2.CAP_PROP_GAIN),
            "backend": self.device.getBackendName() if hasattr(self.device, 'getBackendName') else "unknown"
        }
    
    def _apply_settings(self):
        """Applica settings al device corrente."""
        if self.device is None:
            return
        
        # Resolution
        self.device.set(cv2.CAP_PROP_FRAME_WIDTH, self.settings["width"])
        self.device.set(cv2.CAP_PROP_FRAME_HEIGHT, self.settings["height"])
        
        # FPS
        self.device.set(cv2.CAP_PROP_FPS, self.settings["fps"])
        
        # Exposure (se supportato)
        if self.settings["exposure"] >= 0:
            # Disabilita auto-exposure
            self.device.set(cv2.CAP_PROP_AUTO_EXPOSURE, 0.25)  # 0.25 = manual mode
            # Imposta esposizione (valore dipende da driver)
            self.device.set(cv2.CAP_PROP_EXPOSURE, self.settings["exposure"])
        else:
            # Auto-exposure
            self.device.set(cv2.CAP_PROP_AUTO_EXPOSURE, 0.75)  # 0.75 = auto mode
        
        # Gain (se supportato)
        if self.settings["gain"] >= 0:
            self.device.set(cv2.CAP_PROP_GAIN, self.settings["gain"])
    
    def update_settings(self, **kwargs) -> Dict[str, Any]:
        """
        Aggiorna camera settings.
        
        Args:
            exposure: Esposizione in ms (-1 = auto)
            gain: Gain 0-100 (-1 = auto)
            binning: Binning 1/2/4
            width: Larghezza frame
            height: Altezza frame
            fps: Frame rate
            
        Returns:
            Settings aggiornati
        """
        for key in ["exposure", "gain", "binning", "width", "height", "fps"]:
            if key in kwargs:
                self.settings[key] = kwargs[key]
        
        if self.device is not None:
            self._apply_settings()
        
        return self.settings.copy()
    
    def get_settings(self) -> Dict[str, Any]:
        """Ritorna settings correnti."""
        return self.settings.copy()
    
    def start_capture(self):
        """Avvia capture continua in thread separato."""
        if self.is_capturing:
            return
        
        if self.device is None:
            raise RuntimeError("Device non aperto. Usa open_device() prima.")
        
        self.is_capturing = True
        self.capture_thread = threading.Thread(target=self._capture_loop, daemon=True)
        self.capture_thread.start()
    
    def stop_capture(self):
        """Ferma capture continua."""
        self.is_capturing = False
        if self.capture_thread is not None:
            self.capture_thread.join(timeout=2.0)
            self.capture_thread = None
    
    def _capture_loop(self):
        """Loop capture continua (esegue in thread separato)."""
        while self.is_capturing and self.device is not None:
            ok, frame = self.device.read()
            if ok:
                # Applica binning software se necessario
                binned = self._apply_binning(frame, self.settings["binning"])
                
                with self.frame_lock:
                    self.last_frame = binned
                    
            time.sleep(1.0 / self.settings["fps"])
    
    def _apply_binning(self, frame: np.ndarray, binning: int) -> np.ndarray:
        """Applica binning software."""
        if binning <= 1:
            return frame
        
        h, w = frame.shape[:2]
        new_h, new_w = h // binning, w // binning
        
        # Ridimensiona con INTER_AREA per media pixel
        return cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_AREA)
    
    def get_frame(self) -> Optional[np.ndarray]:
        """
        Ritorna ultimo frame catturato.
        
        Returns:
            Frame numpy array (BGR) o None
        """
        with self.frame_lock:
            return self.last_frame.copy() if self.last_frame is not None else None
    
    def capture_single(self, timeout: float = 5.0) -> np.ndarray:
        """
        Cattura singolo frame.
        
        Args:
            timeout: Timeout in secondi
            
        Returns:
            Frame numpy array (BGR)
        """
        if self.device is None:
            raise RuntimeError("Device non aperto")
        
        start = time.time()
        while time.time() - start < timeout:
            ok, frame = self.device.read()
            if ok:
                return self._apply_binning(frame, self.settings["binning"])
            time.sleep(0.01)
        
        raise TimeoutError("Capture timeout")
    
    def compute_statistics(self, frame: Optional[np.ndarray] = None) -> Dict[str, Any]:
        """
        Calcola statistiche frame (istogramma, mean, std, SNR stimato).
        
        Args:
            frame: Frame numpy (BGR). Se None usa last_frame.
            
        Returns:
            Dict con histogram, mean, std, min, max, snr
        """
        if frame is None:
            frame = self.get_frame()
        
        if frame is None:
            return {}
        
        # Converti a grayscale
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if len(frame.shape) == 3 else frame
        
        # Statistiche base
        mean_val = float(np.mean(gray))
        std_val = float(np.std(gray))
        min_val = int(np.min(gray))
        max_val = int(np.max(gray))
        
        # SNR stimato (signal-to-noise ratio)
        snr = mean_val / std_val if std_val > 0 else 0
        
        # Istogramma (256 bins)
        hist, _ = np.histogram(gray, bins=256, range=(0, 256))
        
        stats = {
            "mean": mean_val,
            "std": std_val,
            "min": min_val,
            "max": max_val,
            "snr": snr,
            "histogram": hist.tolist(),
            "width": gray.shape[1],
            "height": gray.shape[0]
        }
        
        # Cache per riutilizzo
        self.stats_cache = stats
        
        return stats
    
    def save_fits(
        self,
        frame: np.ndarray,
        filename: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Salva frame come FITS con metadata.
        
        Args:
            frame: Frame numpy array
            filename: Nome file (senza path, verrà salvato in data/)
            metadata: Dict con metadata aggiuntivi (target, ra, dec, telescope, etc)
            
        Returns:
            Path completo file salvato
        """
        if not HAS_ASTROPY:
            raise RuntimeError("Astropy non installato. pip install astropy")
        
        # Prepara directory
        save_dir = Path("data/images")
        save_dir.mkdir(parents=True, exist_ok=True)
        
        # Nome file con timestamp se non specificato
        if not filename:
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            filename = f"capture_{timestamp}.fits"
        
        if not filename.endswith('.fits'):
            filename += '.fits'
        
        filepath = save_dir / filename
        
        # Converti BGR -> grayscale per astronomia
        if len(frame.shape) == 3:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        else:
            gray = frame
        
        # Crea HDU primario
        hdu = fits.PrimaryHDU(gray)
        
        # Aggiungi header standard
        hdu.header['IMAGETYP'] = ('Light Frame', 'Type of image')
        hdu.header['INSTRUME'] = ('ObservationManager Camera', 'Camera instrument')
        hdu.header['DATE-OBS'] = (datetime.utcnow().isoformat(), 'UTC observation start')
        hdu.header['EXPTIME'] = (self.settings.get('exposure', -1), 'Exposure time (ms)')
        hdu.header['GAIN'] = (self.settings.get('gain', -1), 'Camera gain')
        hdu.header['BINNING'] = (self.settings.get('binning', 1), 'Binning factor')
        hdu.header['XBINNING'] = (self.settings.get('binning', 1), 'X binning')
        hdu.header['YBINNING'] = (self.settings.get('binning', 1), 'Y binning')
        
        # Aggiungi metadata custom
        if metadata:
            for key, value in metadata.items():
                if key.upper() not in hdu.header:
                    # FITS keywords max 8 chars
                    fits_key = key.upper()[:8]
                    try:
                        hdu.header[fits_key] = (value, key)
                    except:
                        pass  # Skip se valore non valido
        
        # Salva
        hdu.writeto(str(filepath), overwrite=True)
        
        return str(filepath)
    
    def estimate_fwhm(self, frame: Optional[np.ndarray] = None) -> float:
        """
        Stima FWHM (Full Width Half Maximum) per valutazione focus.
        Trova stelle e calcola media FWHM.
        
        Args:
            frame: Frame numpy. Se None usa last_frame.
            
        Returns:
            FWHM in pixel (0 se nessuna stella trovata)
        """
        if frame is None:
            frame = self.get_frame()
        
        if frame is None:
            return 0.0
        
        # Converti a grayscale
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if len(frame.shape) == 3 else frame
        
        # Trova stelle candidate (blob detection)
        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        
        # Trova contorni
        contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        fwhm_values = []
        
        for contour in contours:
            area = cv2.contourArea(contour)
            
            # Filtra: stelle tipicamente 10-1000 pixel^2
            if 10 < area < 1000:
                # Approssima FWHM da area (assumendo gaussiana)
                # FWHM ≈ 2 * sqrt(area / π)
                fwhm = 2.0 * np.sqrt(area / np.pi)
                fwhm_values.append(fwhm)
        
        # Media FWHM
        if fwhm_values:
            return float(np.median(fwhm_values))
        
        return 0.0
    
    def __del__(self):
        """Cleanup on delete."""
        self.close_device()


# Singleton globale
camera_controller = CameraController()
