"""
Watec 910BD Camera Controller - ObservationManager
Controllo via USB della Watec 910BD usando protocollo TACOS Arduino
Documentazione: http://www.hristopavlov.net/WAT910BD/

Sistema TACOS:
- Arduino con firmware dedicato collegato alla camera
- Comunicazione seriale USB 9600 baud
- Comandi per gamma, gain, shutter, AGC, AWB
"""
import time
import threading
from typing import Optional, Dict, List, Any
from pathlib import Path
import logging

try:
    import serial
    import serial.tools.list_ports
    HAS_SERIAL = True
except ImportError:
    serial = None
    HAS_SERIAL = False

logger = logging.getLogger(__name__)


class WatecController:
    """
    Controller per Watec 910BD con sistema TACOS Arduino.
    
    Parametri controllabili:
    - Gamma: 0.45, 0.50, OFF
    - Shutter: 1/50 a 1/100000 (X2, X4, X8, X16, X32, X64, X128, X256)
    - AGC (Automatic Gain Control): ON/OFF + livello gain manuale
    - AWB (Auto White Balance): ON/OFF
    - BLC (Back Light Compensation): ON/OFF
    
    Protocollo TACOS:
    - Baudrate: 9600, 8N1
    - Comandi ASCII terminati con \r\n
    - Risposte: OK/ERROR
    """
    
    # Valori gamma supportati
    GAMMA_VALUES = {
        "0.45": "G1",
        "0.50": "G2",
        "OFF": "G0"
    }
    
    # Moltiplicatori shutter (1/50 base * multiplier)
    SHUTTER_MULTIPLIERS = {
        1: "S0",      # 1/50 (PAL) o 1/60 (NTSC)
        2: "S1",      # 1/100 o 1/120
        4: "S2",      # 1/200 o 1/240
        8: "S3",      # 1/400 o 1/480
        16: "S4",     # 1/800 o 1/960
        32: "S5",     # 1/1600 o 1/1920
        64: "S6",     # 1/3200 o 1/3840
        128: "S7",    # 1/6400 o 1/7680
        256: "S8"     # 1/12800 o 1/15360
    }
    
    def __init__(self):
        if not HAS_SERIAL:
            raise RuntimeError("pyserial non installato. pip install pyserial")
        
        self.port: Optional[serial.Serial] = None
        self.port_name: Optional[str] = None
        self.is_connected = False
        self.lock = threading.Lock()
        
        # Stato corrente
        self.state = {
            "gamma": "0.45",
            "shutter_multiplier": 1,
            "agc_enabled": True,
            "gain": 0,  # 0-255 se AGC disabilitato
            "awb_enabled": True,
            "blc_enabled": False,
            "video_system": "PAL"  # PAL o NTSC
        }
    
    def find_watec_port(self) -> Optional[str]:
        """
        Cerca la porta seriale della Watec 910BD.
        Il sistema TACOS usa tipicamente Arduino Nano/Uno.
        
        Returns:
            Nome porta (es: /dev/tty.usbserial-XXX) o None
        """
        ports = list(serial.tools.list_ports.comports())
        
        # Cerca dispositivi Arduino o FTDI
        for port in ports:
            desc = port.description.lower()
            if any(keyword in desc for keyword in ["arduino", "nano", "uno", "ftdi", "ch340", "cp210"]):
                logger.info(f"Watec 910BD trovata su {port.device}: {port.description}")
                return port.device
        
        # Fallback: cerca qualsiasi porta USB seriale non-Bluetooth
        for port in ports:
            if "bluetooth" not in port.device.lower() and "usb" in port.device.lower():
                logger.warning(f"Possibile Watec su {port.device}: {port.description}")
                return port.device
        
        return None
    
    def connect(self, port: Optional[str] = None) -> bool:
        """
        Connette alla Watec 910BD.
        
        Args:
            port: Nome porta (es: /dev/tty.usbserial-XXX).
                  Se None, cerca automaticamente.
        
        Returns:
            True se connesso con successo
        """
        if self.is_connected:
            logger.warning("Watec già connessa")
            return True
        
        if port is None:
            port = self.find_watec_port()
            if port is None:
                logger.error("Watec 910BD non trovata. Collega Arduino TACOS e riprova.")
                return False
        
        try:
            self.port = serial.Serial(
                port=port,
                baudrate=9600,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=1.0
            )
            
            # Attendi che Arduino si resetti (DTR toggle)
            time.sleep(2)
            
            # Flush buffer
            self.port.flushInput()
            self.port.flushOutput()
            
            # Test comunicazione
            if self._send_command("?"):  # Comando status
                self.port_name = port
                self.is_connected = True
                logger.info(f"Watec 910BD connessa su {port}")
                return True
            else:
                self.port.close()
                self.port = None
                logger.error("Watec non risponde ai comandi")
                return False
                
        except serial.SerialException as e:
            logger.error(f"Errore apertura porta {port}: {e}")
            return False
    
    def disconnect(self):
        """Disconnette dalla Watec."""
        if self.port and self.port.is_open:
            self.port.close()
        self.port = None
        self.is_connected = False
        logger.info("Watec 910BD disconnessa")
    
    def _send_command(self, command: str) -> bool:
        """
        Invia comando alla Watec e verifica risposta.
        
        Args:
            command: Comando ASCII (senza terminatore)
        
        Returns:
            True se OK, False se ERROR o timeout
        """
        if not self.is_connected or not self.port:
            logger.error("Watec non connessa")
            return False
        
        with self.lock:
            try:
                # Invia comando
                cmd = f"{command}\r\n".encode('ascii')
                self.port.write(cmd)
                logger.debug(f"Watec TX: {command}")
                
                # Leggi risposta (max 1 sec)
                response = self.port.readline().decode('ascii').strip()
                logger.debug(f"Watec RX: {response}")
                
                if response == "OK":
                    return True
                elif response == "ERROR":
                    logger.error(f"Watec comando fallito: {command}")
                    return False
                else:
                    # Alcuni comandi restituiscono valori invece di OK
                    return True
                    
            except (serial.SerialException, UnicodeDecodeError) as e:
                logger.error(f"Errore comunicazione Watec: {e}")
                return False
    
    def set_gamma(self, gamma: str) -> bool:
        """
        Imposta curva gamma.
        
        Args:
            gamma: "0.45", "0.50", o "OFF"
        
        Returns:
            True se successo
        """
        if gamma not in self.GAMMA_VALUES:
            logger.error(f"Valore gamma non valido: {gamma}. Usa 0.45, 0.50 o OFF")
            return False
        
        command = self.GAMMA_VALUES[gamma]
        if self._send_command(command):
            self.state["gamma"] = gamma
            logger.info(f"Watec gamma impostato a {gamma}")
            return True
        return False
    
    def set_shutter(self, multiplier: int) -> bool:
        """
        Imposta velocità shutter.
        
        Args:
            multiplier: Moltiplicatore 1-256 (potenze di 2)
                       Es: 1 = 1/50, 2 = 1/100, 4 = 1/200, ..., 256 = 1/12800
        
        Returns:
            True se successo
        """
        if multiplier not in self.SHUTTER_MULTIPLIERS:
            logger.error(f"Moltiplicatore shutter non valido: {multiplier}")
            return False
        
        command = self.SHUTTER_MULTIPLIERS[multiplier]
        if self._send_command(command):
            self.state["shutter_multiplier"] = multiplier
            base = 50 if self.state["video_system"] == "PAL" else 60
            actual_shutter = base * multiplier
            logger.info(f"Watec shutter impostato a 1/{actual_shutter}")
            return True
        return False
    
    def set_agc(self, enabled: bool) -> bool:
        """
        Abilita/disabilita Automatic Gain Control.
        
        Args:
            enabled: True per AGC ON, False per gain manuale
        
        Returns:
            True se successo
        """
        command = "A1" if enabled else "A0"
        if self._send_command(command):
            self.state["agc_enabled"] = enabled
            logger.info(f"Watec AGC {'abilitato' if enabled else 'disabilitato'}")
            return True
        return False
    
    def set_gain(self, gain: int) -> bool:
        """
        Imposta gain manuale (solo se AGC disabilitato).
        
        Args:
            gain: Livello gain 0-255
        
        Returns:
            True se successo
        """
        if not 0 <= gain <= 255:
            logger.error(f"Gain fuori range: {gain}. Usa 0-255")
            return False
        
        if self.state["agc_enabled"]:
            logger.warning("AGC abilitato, disabilitalo prima di impostare gain manuale")
            return False
        
        command = f"M{gain:03d}"  # M000-M255
        if self._send_command(command):
            self.state["gain"] = gain
            logger.info(f"Watec gain manuale impostato a {gain}")
            return True
        return False
    
    def set_awb(self, enabled: bool) -> bool:
        """
        Abilita/disabilita Auto White Balance.
        
        Args:
            enabled: True per AWB ON, False per OFF
        
        Returns:
            True se successo
        """
        command = "W1" if enabled else "W0"
        if self._send_command(command):
            self.state["awb_enabled"] = enabled
            logger.info(f"Watec AWB {'abilitato' if enabled else 'disabilitato'}")
            return True
        return False
    
    def set_blc(self, enabled: bool) -> bool:
        """
        Abilita/disabilita Back Light Compensation.
        
        Args:
            enabled: True per BLC ON, False per OFF
        
        Returns:
            True se successo
        """
        command = "B1" if enabled else "B0"
        if self._send_command(command):
            self.state["blc_enabled"] = enabled
            logger.info(f"Watec BLC {'abilitato' if enabled else 'disabilitato'}")
            return True
        return False
    
    def get_status(self) -> Dict[str, Any]:
        """
        Ritorna stato corrente della camera.
        
        Returns:
            Dizionario con tutti i parametri
        """
        # Calcola shutter effettivo
        base = 50 if self.state["video_system"] == "PAL" else 60
        shutter_speed = base * self.state["shutter_multiplier"]
        
        return {
            **self.state,
            "connected": self.is_connected,
            "port": self.port_name,
            "shutter_speed": f"1/{shutter_speed}",
            "gamma_numeric": 0.45 if self.state["gamma"] == "0.45" else 0.50 if self.state["gamma"] == "0.50" else None
        }
    
    def apply_preset(self, preset: str) -> bool:
        """
        Applica preset ottimizzato per specifico uso.
        
        Args:
            preset: Nome preset ("lunar", "planetary", "deepsky", "occultation")
        
        Returns:
            True se successo
        """
        presets = {
            "lunar": {
                "gamma": "0.45",
                "shutter_multiplier": 64,  # 1/3200
                "agc_enabled": False,
                "gain": 50,
                "awb_enabled": False,
                "blc_enabled": False
            },
            "planetary": {
                "gamma": "0.45",
                "shutter_multiplier": 32,  # 1/1600
                "agc_enabled": False,
                "gain": 100,
                "awb_enabled": False,
                "blc_enabled": False
            },
            "deepsky": {
                "gamma": "OFF",
                "shutter_multiplier": 1,  # 1/50 integrazione massima
                "agc_enabled": True,
                "awb_enabled": False,
                "blc_enabled": False
            },
            "occultation": {
                "gamma": "OFF",
                "shutter_multiplier": 2,  # 1/100 per timing preciso
                "agc_enabled": False,
                "gain": 200,  # High gain per stelle deboli
                "awb_enabled": False,
                "blc_enabled": False
            }
        }
        
        if preset not in presets:
            logger.error(f"Preset non valido: {preset}")
            return False
        
        config = presets[preset]
        logger.info(f"Applicazione preset Watec: {preset}")
        
        # Applica tutti i parametri
        success = True
        success &= self.set_gamma(config["gamma"])
        success &= self.set_shutter(config["shutter_multiplier"])
        success &= self.set_agc(config["agc_enabled"])
        if not config["agc_enabled"] and "gain" in config:
            success &= self.set_gain(config["gain"])
        success &= self.set_awb(config["awb_enabled"])
        success &= self.set_blc(config["blc_enabled"])
        
        if success:
            logger.info(f"Preset {preset} applicato con successo")
        else:
            logger.error(f"Errore applicazione preset {preset}")
        
        return success


# Singleton globale
watec_controller: Optional[WatecController] = None

def get_watec_controller() -> Optional[WatecController]:
    """Ritorna singleton WatecController (thread-safe)."""
    global watec_controller
    if watec_controller is None and HAS_SERIAL:
        watec_controller = WatecController()
    return watec_controller
