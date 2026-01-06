"""
Sequence Management Module - ObservationManager
Gestisce sequenze osservative automatizzate con step multipli
"""
import time
import json
import threading
from typing import Optional, Dict, List, Any
from pathlib import Path
from datetime import datetime
from enum import Enum

# Storage directory
SEQUENCES_DIR = Path("data/sequences")
SEQUENCES_DIR.mkdir(parents=True, exist_ok=True)


class StepType(str, Enum):
    """Tipi di step supportati nelle sequenze."""
    GOTO = "goto"           # Slew to target coordinates
    SYNC = "sync"           # Sync mount to coordinates
    IMAGE = "image"         # Capture image(s)
    WAIT = "wait"           # Wait for duration or condition
    FILTER = "filter"       # Change filter wheel position
    FOCUS = "focus"         # Auto-focus routine
    CUSTOM = "custom"       # Custom command


class StepStatus(str, Enum):
    """Stati di esecuzione step."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class SequenceStep:
    """
    Singolo step in una sequenza osservativa.
    """
    
    def __init__(
        self,
        step_type: StepType,
        params: Dict[str, Any],
        name: Optional[str] = None
    ):
        self.id = f"step_{int(time.time() * 1000)}"
        self.step_type = step_type
        self.params = params
        self.name = name or f"{step_type.value}_{self.id[-6:]}"
        self.status = StepStatus.PENDING
        self.result: Optional[Dict[str, Any]] = None
        self.error: Optional[str] = None
        self.start_time: Optional[float] = None
        self.end_time: Optional[float] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Serializza step a dict."""
        return {
            "id": self.id,
            "type": self.step_type.value,
            "name": self.name,
            "params": self.params,
            "status": self.status.value,
            "result": self.result,
            "error": self.error,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration": (self.end_time - self.start_time) if (self.start_time and self.end_time) else None
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SequenceStep':
        """Deserializza step da dict."""
        step = cls(
            step_type=StepType(data["type"]),
            params=data["params"],
            name=data.get("name")
        )
        step.id = data["id"]
        step.status = StepStatus(data.get("status", "pending"))
        step.result = data.get("result")
        step.error = data.get("error")
        step.start_time = data.get("start_time")
        step.end_time = data.get("end_time")
        return step


class ObservingSequence:
    """
    Sequenza osservativa completa con metadata e steps.
    """
    
    def __init__(
        self,
        name: str,
        description: str = "",
        target: Optional[str] = None
    ):
        self.id = f"seq_{int(time.time() * 1000)}"
        self.name = name
        self.description = description
        self.target = target
        self.steps: List[SequenceStep] = []
        self.created_at = time.time()
        self.modified_at = time.time()
        self.executed_count = 0
        self.last_execution: Optional[float] = None
    
    def add_step(self, step: SequenceStep):
        """Aggiunge step alla sequenza."""
        self.steps.append(step)
        self.modified_at = time.time()
    
    def remove_step(self, step_id: str):
        """Rimuove step dalla sequenza."""
        self.steps = [s for s in self.steps if s.id != step_id]
        self.modified_at = time.time()
    
    def get_step(self, step_id: str) -> Optional[SequenceStep]:
        """Trova step per ID."""
        return next((s for s in self.steps if s.id == step_id), None)
    
    def reset_status(self):
        """Reset tutti gli step a pending."""
        for step in self.steps:
            step.status = StepStatus.PENDING
            step.result = None
            step.error = None
            step.start_time = None
            step.end_time = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Serializza sequenza a dict."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "target": self.target,
            "steps": [s.to_dict() for s in self.steps],
            "created_at": self.created_at,
            "modified_at": self.modified_at,
            "executed_count": self.executed_count,
            "last_execution": self.last_execution,
            "step_count": len(self.steps),
            "duration_estimate": self._estimate_duration()
        }
    
    def _estimate_duration(self) -> float:
        """Stima durata totale sequenza (secondi)."""
        total = 0.0
        for step in self.steps:
            if step.step_type == StepType.GOTO:
                total += 30.0  # Average slew time
            elif step.step_type == StepType.IMAGE:
                exp = step.params.get("exposure", 1.0)
                count = step.params.get("count", 1)
                total += exp * count
            elif step.step_type == StepType.WAIT:
                total += step.params.get("duration", 0.0)
            elif step.step_type == StepType.FOCUS:
                total += 60.0  # Focus routine estimate
            else:
                total += 5.0  # Generic step overhead
        return total
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ObservingSequence':
        """Deserializza sequenza da dict."""
        seq = cls(
            name=data["name"],
            description=data.get("description", ""),
            target=data.get("target")
        )
        seq.id = data["id"]
        seq.created_at = data.get("created_at", time.time())
        seq.modified_at = data.get("modified_at", time.time())
        seq.executed_count = data.get("executed_count", 0)
        seq.last_execution = data.get("last_execution")
        
        for step_data in data.get("steps", []):
            seq.steps.append(SequenceStep.from_dict(step_data))
        
        return seq
    
    def save(self):
        """Salva sequenza su disco."""
        filepath = SEQUENCES_DIR / f"{self.id}.json"
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2)
    
    @classmethod
    def load(cls, sequence_id: str) -> Optional['ObservingSequence']:
        """Carica sequenza da disco."""
        filepath = SEQUENCES_DIR / f"{sequence_id}.json"
        if not filepath.exists():
            return None
        
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        return cls.from_dict(data)
    
    @classmethod
    def list_all(cls) -> List[Dict[str, Any]]:
        """Lista tutte le sequenze salvate (metadata only)."""
        sequences = []
        for filepath in SEQUENCES_DIR.glob("seq_*.json"):
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                
                # Return metadata only (no steps)
                sequences.append({
                    "id": data["id"],
                    "name": data["name"],
                    "description": data.get("description", ""),
                    "target": data.get("target"),
                    "step_count": len(data.get("steps", [])),
                    "created_at": data.get("created_at"),
                    "modified_at": data.get("modified_at"),
                    "executed_count": data.get("executed_count", 0),
                    "last_execution": data.get("last_execution"),
                    "duration_estimate": data.get("duration_estimate", 0)
                })
            except Exception:
                continue
        
        # Sort by modified_at descending
        sequences.sort(key=lambda x: x.get("modified_at", 0), reverse=True)
        return sequences
    
    def delete(self):
        """Elimina sequenza da disco."""
        filepath = SEQUENCES_DIR / f"{self.id}.json"
        if filepath.exists():
            filepath.unlink()


class SequenceExecutor:
    """
    Execution engine per sequenze osservative.
    Esegue steps in sequenza con supporto pause/resume/abort.
    """
    
    def __init__(self, sequence: ObservingSequence, lx200_getter, camera_controller):
        self.sequence = sequence
        self.lx200_getter = lx200_getter  # Callable that returns LX200 instance
        self.camera_controller = camera_controller
        
        self.is_running = False
        self.is_paused = False
        self.should_abort = False
        self.current_step_index = 0
        self.execution_thread: Optional[threading.Thread] = None
        
        self.progress = {
            "total_steps": len(sequence.steps),
            "completed_steps": 0,
            "current_step": None,
            "elapsed_time": 0.0,
            "start_time": None
        }
    
    def start(self):
        """Avvia esecuzione sequenza in thread separato."""
        if self.is_running:
            raise RuntimeError("Sequence already running")
        
        self.is_running = True
        self.should_abort = False
        self.progress["start_time"] = time.time()
        
        self.execution_thread = threading.Thread(target=self._execute_loop, daemon=True)
        self.execution_thread.start()
    
    def pause(self):
        """Mette in pausa esecuzione."""
        self.is_paused = True
    
    def resume(self):
        """Riprende esecuzione."""
        self.is_paused = False
    
    def abort(self):
        """Interrompe esecuzione."""
        self.should_abort = True
        self.is_paused = False
    
    def get_status(self) -> Dict[str, Any]:
        """Ritorna stato esecuzione corrente."""
        if self.progress["start_time"]:
            self.progress["elapsed_time"] = time.time() - self.progress["start_time"]
        
        return {
            "is_running": self.is_running,
            "is_paused": self.is_paused,
            "progress": self.progress,
            "sequence_id": self.sequence.id,
            "sequence_name": self.sequence.name
        }
    
    def _execute_loop(self):
        """Loop principale esecuzione (runs in thread)."""
        try:
            for i, step in enumerate(self.sequence.steps):
                # Check abort
                if self.should_abort:
                    step.status = StepStatus.SKIPPED
                    continue
                
                # Wait if paused
                while self.is_paused and not self.should_abort:
                    time.sleep(0.5)
                
                if self.should_abort:
                    step.status = StepStatus.SKIPPED
                    continue
                
                # Execute step
                self.current_step_index = i
                self.progress["current_step"] = step.to_dict()
                
                try:
                    self._execute_step(step)
                    step.status = StepStatus.COMPLETED
                    self.progress["completed_steps"] += 1
                except Exception as e:
                    step.status = StepStatus.FAILED
                    step.error = str(e)
                    # Continue to next step (no break)
            
            # Sequence complete
            self.sequence.executed_count += 1
            self.sequence.last_execution = time.time()
            self.sequence.save()
            
        finally:
            self.is_running = False
            self.progress["current_step"] = None
    
    def _execute_step(self, step: SequenceStep):
        """Esegue singolo step."""
        step.start_time = time.time()
        step.status = StepStatus.RUNNING
        
        try:
            if step.step_type == StepType.GOTO:
                self._execute_goto(step)
            elif step.step_type == StepType.SYNC:
                self._execute_sync(step)
            elif step.step_type == StepType.IMAGE:
                self._execute_image(step)
            elif step.step_type == StepType.WAIT:
                self._execute_wait(step)
            elif step.step_type == StepType.FILTER:
                self._execute_filter(step)
            elif step.step_type == StepType.FOCUS:
                self._execute_focus(step)
            else:
                step.result = {"message": "Step type not implemented"}
        
        finally:
            step.end_time = time.time()
    
    def _execute_goto(self, step: SequenceStep):
        """Execute GOTO step."""
        ra_deg = step.params.get("ra_deg")
        dec_deg = step.params.get("dec_deg")
        
        if ra_deg is None or dec_deg is None:
            raise ValueError("GOTO requires ra_deg and dec_deg")
        
        lx = self.lx200_getter()
        
        # Convert to HMS/DMS
        from lx200.protocol import parse_ra, parse_dec
        ra_str = parse_ra(ra_deg / 15.0)
        dec_str = parse_dec(dec_deg)
        
        lx.set_target_ra_dec(ra_str, dec_str)
        response = lx.goto()
        
        step.result = {
            "ra": ra_str,
            "dec": dec_str,
            "response": response
        }
    
    def _execute_sync(self, step: SequenceStep):
        """Execute SYNC step."""
        ra_deg = step.params.get("ra_deg")
        dec_deg = step.params.get("dec_deg")
        
        if ra_deg is None or dec_deg is None:
            raise ValueError("SYNC requires ra_deg and dec_deg")
        
        lx = self.lx200_getter()
        
        from lx200.protocol import parse_ra, parse_dec
        ra_str = parse_ra(ra_deg / 15.0)
        dec_str = parse_dec(dec_deg)
        
        response = lx.sync_to(ra_str, dec_str)
        
        step.result = {
            "ra": ra_str,
            "dec": dec_str,
            "response": response
        }
    
    def _execute_image(self, step: SequenceStep):
        """Execute IMAGE step."""
        exposure = step.params.get("exposure", 1.0)
        count = step.params.get("count", 1)
        save_fits = step.params.get("save_fits", True)
        target_name = step.params.get("target", self.sequence.target)
        
        captured = []
        
        for i in range(count):
            # Check abort between frames
            if self.should_abort:
                break
            
            # Capture frame
            frame = self.camera_controller.capture_single(timeout=exposure + 5.0)
            
            if save_fits:
                filename = f"{target_name}_{i+1:03d}.fits" if target_name else None
                metadata = {"OBJECT": target_name} if target_name else {}
                filepath = self.camera_controller.save_fits(frame, filename or "", metadata)
                captured.append(filepath)
            
            # Wait between frames (if specified)
            delay = step.params.get("delay", 0.0)
            if delay > 0 and i < count - 1:
                time.sleep(delay)
        
        step.result = {
            "captured_count": len(captured),
            "files": captured
        }
    
    def _execute_wait(self, step: SequenceStep):
        """Execute WAIT step."""
        duration = step.params.get("duration", 0.0)
        
        # Sleep with abort checking
        start = time.time()
        while time.time() - start < duration:
            if self.should_abort:
                break
            time.sleep(min(1.0, duration - (time.time() - start)))
        
        step.result = {
            "waited": time.time() - start
        }
    
    def _execute_filter(self, step: SequenceStep):
        """Execute FILTER step (placeholder)."""
        position = step.params.get("position", 1)
        
        # TODO: Integrate with filter wheel controller
        step.result = {
            "message": "Filter wheel not implemented",
            "position": position
        }
    
    def _execute_focus(self, step: SequenceStep):
        """Execute FOCUS step (placeholder)."""
        # TODO: Implement auto-focus routine using FWHM
        step.result = {
            "message": "Auto-focus not implemented"
        }


# Global executor registry
_active_executors: Dict[str, SequenceExecutor] = {}


def get_executor(sequence_id: str) -> Optional[SequenceExecutor]:
    """Retrieve active executor for sequence."""
    return _active_executors.get(sequence_id)


def register_executor(sequence_id: str, executor: SequenceExecutor):
    """Register active executor."""
    _active_executors[sequence_id] = executor


def unregister_executor(sequence_id: str):
    """Unregister executor."""
    _active_executors.pop(sequence_id, None)
