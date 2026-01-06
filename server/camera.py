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

from server.live_stacker import LiveStacker

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
        
        # Video recording
        self.is_recording = False
        self.video_writer: Optional[cv2.VideoWriter] = None
        self.recording_thread: Optional[threading.Thread] = None
        self.recording_path: Optional[str] = None
        self.recording_start_time: Optional[float] = None
        self.recorded_frames = 0
        
        # Image sequence capture
        self.is_sequencing = False
        self.sequence_thread: Optional[threading.Thread] = None
        self.sequence_params: Dict[str, Any] = {}
        self.captured_sequence_count = 0

        # Live stacking helper
        self.live_stacker = LiveStacker(self.get_frame, save_fits_callable=self.save_fits)
        
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
        metadata: Optional[Dict[str, Any]] = None,
        output_dir: str = "data/images",
        wcs_info: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Salva frame come FITS con metadata.
        
        Args:
            frame: Frame numpy array
            filename: Nome file (senza path, verrà salvato in data/)
            metadata: Dict con metadata aggiuntivi (target, ra, dec, telescope, etc)
            output_dir: Directory di output (default data/images)
            wcs_info: Dict opzionale con RA/DEC centro, pixel_scale_arcsec, rotation_deg
            
        Returns:
            Path completo file salvato
        """
        if not HAS_ASTROPY:
            raise RuntimeError("Astropy non installato. pip install astropy")
        
        # Prepara directory
        save_dir = Path(output_dir)
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
                    fits_key = key.upper()[:8]
                    try:
                        hdu.header[fits_key] = (value, key)
                    except Exception as exc:
                        logger.debug(f"Skip metadata {key}: {exc}")

        if wcs_info:
            try:
                ra = float(wcs_info.get("ra_deg")) if wcs_info.get("ra_deg") is not None else None
                dec = float(wcs_info.get("dec_deg")) if wcs_info.get("dec_deg") is not None else None
                pixel_scale = float(wcs_info.get("pixel_scale_arcsec", 0))
                rotation = float(wcs_info.get("rotation_deg", 0))
                if ra is not None and dec is not None and pixel_scale > 0:
                    height, width = gray.shape[:2]
                    crpix1 = width / 2.0
                    crpix2 = height / 2.0
                    cdelt = pixel_scale / 3600.0
                    hdu.header['CRVAL1'] = ra
                    hdu.header['CRVAL2'] = dec
                    hdu.header['CRPIX1'] = crpix1
                    hdu.header['CRPIX2'] = crpix2
                    hdu.header['CDELT1'] = -cdelt
                    hdu.header['CDELT2'] = cdelt
                    hdu.header['CROTA2'] = rotation
            except Exception as exc:
                logger.debug(f"Skip WCS metadata: {exc}")
        
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
    
    # ========== Video Recording ==========
    
    def start_recording(
        self,
        filename: Optional[str] = None,
        codec: str = "mp4v",
        output_dir: str = "data/recordings"
    ) -> Dict[str, Any]:
        """
        Avvia registrazione video.
        
        Args:
            filename: Nome file (senza estensione). Se None, usa timestamp.
            codec: Codec video ('mp4v', 'XVID', 'MJPEG', 'H264')
            output_dir: Directory output
        
        Returns:
            Info registrazione (filepath, fps, resolution)
        """
        if self.is_recording:
            raise RuntimeError("Registrazione già in corso")
        
        if self.device is None:
            raise RuntimeError("Device non aperto")
        
        # Assicura che capture sia attiva
        if not self.is_capturing:
            self.start_capture()
        
        # Crea directory
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        # Nome file
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"video_{timestamp}"
        
        # Estensione basata su codec
        ext = ".mp4" if codec in ["mp4v", "H264", "avc1"] else ".avi"
        filepath = output_path / f"{filename}{ext}"
        
        # Configurazione video writer
        fourcc = cv2.VideoWriter_fourcc(*codec)
        fps = self.settings["fps"]
        frame_size = (self.settings["width"], self.settings["height"])
        
        self.video_writer = cv2.VideoWriter(
            str(filepath),
            fourcc,
            fps,
            frame_size
        )
        
        if not self.video_writer.isOpened():
            raise RuntimeError(f"Impossibile aprire video writer con codec {codec}")
        
        # Stato
        self.is_recording = True
        self.recording_path = str(filepath)
        self.recording_start_time = time.time()
        self.recorded_frames = 0
        
        # Thread recording
        self.recording_thread = threading.Thread(target=self._recording_loop, daemon=True)
        self.recording_thread.start()
        
        logger.info(f"Registrazione avviata: {filepath} ({fps} fps, {frame_size})")
        
        return {
            "status": "recording",
            "filepath": str(filepath),
            "filename": filepath.name,
            "fps": fps,
            "resolution": f"{frame_size[0]}x{frame_size[1]}",
            "codec": codec
        }
    
    def _recording_loop(self):
        """Loop registrazione video (esegue in thread separato)."""
        while self.is_recording and self.video_writer is not None:
            frame = self.get_frame()
            
            if frame is not None:
                # Assicura dimensioni corrette
                h, w = frame.shape[:2]
                target_w, target_h = self.settings["width"], self.settings["height"]
                
                if (w, h) != (target_w, target_h):
                    frame = cv2.resize(frame, (target_w, target_h))
                
                self.video_writer.write(frame)
                self.recorded_frames += 1
            
            time.sleep(1.0 / self.settings["fps"])
    
    def stop_recording(self) -> Dict[str, Any]:
        """
        Ferma registrazione video.
        
        Returns:
            Statistiche registrazione (frames, durata, filepath)
        """
        if not self.is_recording:
            raise RuntimeError("Nessuna registrazione in corso")
        
        self.is_recording = False
        
        # Attendi thread
        if self.recording_thread is not None:
            self.recording_thread.join(timeout=2.0)
            self.recording_thread = None
        
        # Chiudi writer
        if self.video_writer is not None:
            self.video_writer.release()
            self.video_writer = None
        
        # Statistiche
        duration = time.time() - self.recording_start_time if self.recording_start_time else 0
        filepath = self.recording_path
        frames = self.recorded_frames
        
        # Reset
        self.recording_path = None
        self.recording_start_time = None
        self.recorded_frames = 0
        
        logger.info(f"Registrazione fermata: {frames} frames in {duration:.1f}s")
        
        return {
            "status": "stopped",
            "filepath": filepath,
            "frames": frames,
            "duration": duration,
            "fps": frames / duration if duration > 0 else 0
        }
    
    def get_recording_status(self) -> Dict[str, Any]:
        """
        Ritorna stato registrazione corrente.
        
        Returns:
            Status dict (is_recording, frames, duration, filepath)
        """
        if not self.is_recording:
            return {
                "is_recording": False,
                "frames": 0,
                "duration": 0,
                "filepath": None
            }
        
        duration = time.time() - self.recording_start_time if self.recording_start_time else 0
        
        return {
            "is_recording": True,
            "frames": self.recorded_frames,
            "duration": duration,
            "fps": self.recorded_frames / duration if duration > 0 else 0,
            "filepath": self.recording_path
        }
    
    # ========== Image Sequence Capture ==========
    
    def start_image_sequence(
        self,
        count: int,
        interval: float = 0.0,
        filename_prefix: Optional[str] = None,
        save_format: str = "fits",
        output_dir: str = "data/sequences",
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Avvia acquisizione sequenza immagini.
        
        Args:
            count: Numero immagini da catturare
            interval: Intervallo tra catture in secondi (0 = massima velocità)
            filename_prefix: Prefisso nome file. Se None, usa timestamp.
            save_format: Formato salvataggio ('fits', 'png', 'jpg')
            output_dir: Directory output
            metadata: Metadata opzionali per FITS
        
        Returns:
            Info sequenza (count, interval, output_dir)
        """
        if self.is_sequencing:
            raise RuntimeError("Sequenza già in corso")
        
        if self.device is None:
            raise RuntimeError("Device non aperto")
        
        # Assicura che capture sia attiva
        if not self.is_capturing:
            self.start_capture()
        
        # Crea directory
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        # Prefisso
        if filename_prefix is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename_prefix = f"seq_{timestamp}"
        
        # Parametri sequenza
        self.sequence_params = {
            "count": count,
            "interval": interval,
            "prefix": filename_prefix,
            "format": save_format,
            "output_dir": str(output_path),
            "metadata": metadata or {}
        }
        
        self.is_sequencing = True
        self.captured_sequence_count = 0
        
        # Thread sequenza
        self.sequence_thread = threading.Thread(target=self._sequence_loop, daemon=True)
        self.sequence_thread.start()
        
        logger.info(f"Sequenza avviata: {count} immagini, interval={interval}s, formato={save_format}")
        
        return {
            "status": "sequencing",
            "count": count,
            "interval": interval,
            "format": save_format,
            "output_dir": str(output_path),
            "prefix": filename_prefix
        }
    
    def _sequence_loop(self):
        """Loop acquisizione sequenza (esegue in thread separato)."""
        params = self.sequence_params
        
        for i in range(params["count"]):
            if not self.is_sequencing:
                break
            
            try:
                # Cattura frame
                frame = self.capture_single(timeout=5.0)
                
                # Nome file
                filename = f"{params['prefix']}_{i+1:04d}"
                
                # Salva in base al formato
                if params["format"] == "fits":
                    filepath = self.save_fits(
                        frame,
                        filename,
                        params["metadata"],
                        output_dir=params["output_dir"]
                    )
                elif params["format"] == "png":
                    filepath = Path(params["output_dir"]) / f"{filename}.png"
                    cv2.imwrite(str(filepath), frame)
                elif params["format"] == "jpg":
                    filepath = Path(params["output_dir"]) / f"{filename}.jpg"
                    cv2.imwrite(str(filepath), frame, [cv2.IMWRITE_JPEG_QUALITY, 95])
                else:
                    raise ValueError(f"Formato non supportato: {params['format']}")
                
                self.captured_sequence_count += 1
                logger.debug(f"Sequenza: catturata immagine {i+1}/{params['count']}")
                
                # Attendi intervallo
                if i < params["count"] - 1 and params["interval"] > 0:
                    time.sleep(params["interval"])
                    
            except Exception as e:
                logger.error(f"Errore cattura sequenza frame {i+1}: {e}")
                break
        
        # Auto-stop
        if self.is_sequencing:
            self.is_sequencing = False
            logger.info(f"Sequenza completata: {self.captured_sequence_count} immagini")
    
    def stop_image_sequence(self) -> Dict[str, Any]:
        """
        Ferma acquisizione sequenza.
        
        Returns:
            Statistiche sequenza (captured, total, output_dir)
        """
        if not self.is_sequencing:
            raise RuntimeError("Nessuna sequenza in corso")
        
        self.is_sequencing = False
        
        # Attendi thread
        if self.sequence_thread is not None:
            self.sequence_thread.join(timeout=5.0)
            self.sequence_thread = None
        
        captured = self.captured_sequence_count
        total = self.sequence_params.get("count", 0)
        output_dir = self.sequence_params.get("output_dir", "")
        
        logger.info(f"Sequenza fermata: {captured}/{total} immagini salvate")
        
        return {
            "status": "stopped",
            "captured": captured,
            "total": total,
            "output_dir": output_dir,
            "completed": captured >= total
        }
    
    def get_sequence_status(self) -> Dict[str, Any]:
        """
        Ritorna stato sequenza corrente.
        
        Returns:
            Status dict (is_sequencing, captured, total, progress)
        """
        if not self.is_sequencing:
            return {
                "is_sequencing": False,
                "captured": 0,
                "total": 0,
                "progress": 0
            }
        
        captured = self.captured_sequence_count
        total = self.sequence_params.get("count", 0)
        
        return {
            "is_sequencing": True,
            "captured": captured,
            "total": total,
            "progress": (captured / total * 100) if total > 0 else 0,
            "output_dir": self.sequence_params.get("output_dir", "")
        }

    # ========== Live Stacking ==========

    def start_live_stack(self, interval: float = 0.5, max_frames: int = 0, normalize: bool = True) -> Dict[str, Any]:
        """Avvia live stacking in background (polling get_frame)."""
        if not self.is_capturing:
            self.start_capture()
        return self.live_stacker.start(interval=interval, max_frames=max_frames, normalize=normalize)

    def stop_live_stack(self) -> Dict[str, Any]:
        """Ferma live stacking e ritorna stato finale."""
        return self.live_stacker.stop()

    def get_live_stack_status(self) -> Dict[str, Any]:
        """Ritorna stato live stacking."""
        return self.live_stacker.get_status()

    def save_live_stack(
        self,
        filename: Optional[str] = None,
        fmt: str = "fits",
        metadata: Optional[Dict[str, Any]] = None,
        wcs_info: Optional[Dict[str, Any]] = None,
        output_dir: str = "data/stacking"
    ) -> str:
        """Salva stack corrente come FITS/PNG."""
        return self.live_stacker.save_stack(
            filename=filename,
            fmt=fmt,
            metadata=metadata,
            wcs_info=wcs_info,
            output_dir=output_dir,
        )
    
    def __del__(self):
        """Cleanup on delete."""
        # Stop recording se attivo
        if self.is_recording:
            try:
                self.stop_recording()
            except:
                pass
        
        # Stop sequenza se attiva
        if self.is_sequencing:
            try:
                self.stop_image_sequence()
            except:
                pass
        
        self.close_device()


# Singleton globale
camera_controller = CameraController()
