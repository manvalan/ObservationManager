"""
AVI Recorder - ObservationManager
Classe dedicata per registrazione video AVI da telecamera
"""
import time
import threading
from typing import Optional, Dict, Any, Callable
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

logger = logging.getLogger(__name__)


class AVIRecorder:
    """
    Registratore video AVI dedicato.
    
    Features:
    - Registrazione continua da VideoCapture
    - Codec configurabili (MJPEG, XVID, etc.)
    - Threading per prestazioni ottimali
    - Statistiche real-time (fps, frames, durata)
    - Callback per eventi (start, stop, frame)
    """
    
    def __init__(self, video_capture: cv2.VideoCapture):
        """
        Inizializza recorder.
        
        Args:
            video_capture: Oggetto cv2.VideoCapture già aperto
        """
        if not HAS_CV2:
            raise RuntimeError("OpenCV non installato")
        
        if video_capture is None or not video_capture.isOpened():
            raise ValueError("VideoCapture deve essere aperto")
        
        self.capture = video_capture
        self.writer: Optional[cv2.VideoWriter] = None
        self.is_recording = False
        self.recording_thread: Optional[threading.Thread] = None
        
        # Stato recording
        self.output_path: Optional[str] = None
        self.start_time: Optional[float] = None
        self.frame_count = 0
        self.dropped_frames = 0
        
        # Configurazione
        self.fps = 30.0
        self.frame_width = 640
        self.frame_height = 480
        self.codec = "MJPG"
        
        # Callbacks opzionali
        self.on_start_callback: Optional[Callable] = None
        self.on_stop_callback: Optional[Callable] = None
        self.on_frame_callback: Optional[Callable[[np.ndarray], None]] = None
        
        logger.info("AVIRecorder inizializzato")
    
    def configure(
        self,
        fps: float = 30.0,
        width: int = 640,
        height: int = 480,
        codec: str = "MJPG"
    ):
        """
        Configura parametri recording.
        
        Args:
            fps: Frame rate target
            width: Larghezza frame
            height: Altezza frame
            codec: Codec video (MJPG, XVID, MP4V, etc.)
        """
        if self.is_recording:
            raise RuntimeError("Impossibile configurare durante recording")
        
        self.fps = fps
        self.frame_width = width
        self.frame_height = height
        self.codec = codec
        
        logger.info(f"AVIRecorder configurato: {width}x{height} @ {fps} fps, codec={codec}")
    
    def start(
        self,
        output_path: Optional[str] = None,
        output_dir: str = "data/recordings"
    ) -> Dict[str, Any]:
        """
        Avvia registrazione AVI.
        
        Args:
            output_path: Path completo file output. Se None, genera automaticamente.
            output_dir: Directory output (usata se output_path è None)
        
        Returns:
            Info dict con filepath, fps, resolution, codec
        """
        if self.is_recording:
            raise RuntimeError("Recording già in corso")
        
        # Genera path se necessario
        if output_path is None:
            output_dir_path = Path(output_dir)
            output_dir_path.mkdir(parents=True, exist_ok=True)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"video_{timestamp}.avi"
            output_path = str(output_dir_path / filename)
        else:
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        
        # Crea VideoWriter
        fourcc = cv2.VideoWriter_fourcc(*self.codec)
        self.writer = cv2.VideoWriter(
            output_path,
            fourcc,
            self.fps,
            (self.frame_width, self.frame_height)
        )
        
        if not self.writer.isOpened():
            raise RuntimeError(f"Impossibile creare VideoWriter: {output_path}")
        
        # Inizializza stato
        self.output_path = output_path
        self.start_time = time.time()
        self.frame_count = 0
        self.dropped_frames = 0
        self.is_recording = True
        
        # Avvia thread recording
        self.recording_thread = threading.Thread(
            target=self._recording_loop,
            daemon=True,
            name="AVIRecorder"
        )
        self.recording_thread.start()
        
        logger.info(f"Recording avviato: {output_path}")
        
        # Callback
        if self.on_start_callback:
            try:
                self.on_start_callback(output_path)
            except Exception as e:
                logger.error(f"Errore on_start callback: {e}")
        
        return {
            "filepath": output_path,
            "filename": Path(output_path).name,
            "fps": self.fps,
            "resolution": f"{self.frame_width}x{self.frame_height}",
            "codec": self.codec
        }
    
    def _recording_loop(self):
        """Loop principale recording (esegue in thread separato)."""
        frame_interval = 1.0 / self.fps
        
        while self.is_recording:
            loop_start = time.time()
            
            # Cattura frame
            ret, frame = self.capture.read()
            
            if not ret:
                logger.warning("Errore lettura frame")
                self.dropped_frames += 1
                time.sleep(frame_interval)
                continue
            
            # Resize se necessario
            h, w = frame.shape[:2]
            if (w, h) != (self.frame_width, self.frame_height):
                frame = cv2.resize(frame, (self.frame_width, self.frame_height))
            
            # Scrivi frame
            try:
                self.writer.write(frame)
                self.frame_count += 1
                
                # Callback frame
                if self.on_frame_callback:
                    try:
                        self.on_frame_callback(frame)
                    except Exception as e:
                        logger.error(f"Errore on_frame callback: {e}")
                
            except Exception as e:
                logger.error(f"Errore scrittura frame: {e}")
                self.dropped_frames += 1
            
            # Timing per mantenere fps target
            elapsed = time.time() - loop_start
            sleep_time = max(0, frame_interval - elapsed)
            if sleep_time > 0:
                time.sleep(sleep_time)
        
        logger.debug("Recording loop terminato")
    
    def stop(self) -> Dict[str, Any]:
        """
        Ferma registrazione.
        
        Returns:
            Statistiche recording (frames, duration, fps, filepath, dropped_frames)
        """
        if not self.is_recording:
            raise RuntimeError("Nessun recording in corso")
        
        # Ferma thread
        self.is_recording = False
        if self.recording_thread:
            self.recording_thread.join(timeout=3.0)
            self.recording_thread = None
        
        # Chiudi writer
        if self.writer:
            self.writer.release()
            self.writer = None
        
        # Calcola statistiche
        duration = time.time() - self.start_time if self.start_time else 0
        actual_fps = self.frame_count / duration if duration > 0 else 0
        
        result = {
            "filepath": self.output_path,
            "filename": Path(self.output_path).name if self.output_path else None,
            "frames": self.frame_count,
            "dropped_frames": self.dropped_frames,
            "duration": duration,
            "fps": actual_fps,
            "filesize": Path(self.output_path).stat().st_size if self.output_path and Path(self.output_path).exists() else 0
        }
        
        logger.info(f"Recording fermato: {result['frames']} frames in {duration:.1f}s ({actual_fps:.1f} fps)")
        
        # Callback
        if self.on_stop_callback:
            try:
                self.on_stop_callback(result)
            except Exception as e:
                logger.error(f"Errore on_stop callback: {e}")
        
        # Reset stato
        self.output_path = None
        self.start_time = None
        self.frame_count = 0
        self.dropped_frames = 0
        
        return result
    
    def get_status(self) -> Dict[str, Any]:
        """
        Ritorna stato corrente recording.
        
        Returns:
            Status dict con is_recording, frames, duration, fps
        """
        if not self.is_recording:
            return {
                "is_recording": False,
                "frames": 0,
                "dropped_frames": 0,
                "duration": 0,
                "fps": 0,
                "filepath": None
            }
        
        duration = time.time() - self.start_time if self.start_time else 0
        fps = self.frame_count / duration if duration > 0 else 0
        
        return {
            "is_recording": True,
            "frames": self.frame_count,
            "dropped_frames": self.dropped_frames,
            "duration": duration,
            "fps": fps,
            "filepath": self.output_path
        }
    
    def set_callbacks(
        self,
        on_start: Optional[Callable] = None,
        on_stop: Optional[Callable] = None,
        on_frame: Optional[Callable[[np.ndarray], None]] = None
    ):
        """
        Imposta callback per eventi.
        
        Args:
            on_start: Chiamato all'avvio (args: filepath)
            on_stop: Chiamato allo stop (args: result dict)
            on_frame: Chiamato per ogni frame (args: frame numpy array)
        """
        self.on_start_callback = on_start
        self.on_stop_callback = on_stop
        self.on_frame_callback = on_frame
    
    def __del__(self):
        """Cleanup."""
        if self.is_recording:
            try:
                self.stop()
            except:
                pass


# Esempio di utilizzo
if __name__ == "__main__":
    import sys
    
    # Apri webcam
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("Errore: impossibile aprire webcam")
        sys.exit(1)
    
    # Crea recorder
    recorder = AVIRecorder(cap)
    
    # Configura
    recorder.configure(fps=30.0, width=640, height=480, codec="MJPG")
    
    # Callback esempio
    def on_frame(frame):
        # Puoi processare ogni frame qui
        pass
    
    recorder.set_callbacks(
        on_start=lambda path: print(f"Recording avviato: {path}"),
        on_stop=lambda result: print(f"Recording fermato: {result['frames']} frames"),
        on_frame=on_frame
    )
    
    # Start recording
    info = recorder.start()
    print(f"Recording: {info['filename']}")
    
    # Registra per 5 secondi
    try:
        for i in range(5):
            status = recorder.get_status()
            print(f"[{i+1}s] Frames: {status['frames']}, FPS: {status['fps']:.1f}")
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nInterrotto")
    
    # Stop
    result = recorder.stop()
    print(f"\nCompletato:")
    print(f"  File: {result['filename']}")
    print(f"  Frames: {result['frames']}")
    print(f"  Durata: {result['duration']:.1f}s")
    print(f"  FPS: {result['fps']:.1f}")
    print(f"  Dimensione: {result['filesize'] / 1024:.1f} KB")
    
    # Cleanup
    cap.release()
