# Guida Watec 910BD con ObservationManager

## Panoramica Sistema

La **Watec 910BD** è una telecamera astronomica analogica (PAL/NTSC) professionale con sensore CCD ad alta sensibilità, ideale per:
- 🌙 **Imaging lunare/planetario** ad alta risoluzione
- ⭐ **Occultazioni stellari** con timing preciso
- 🌌 **Deep sky** con integrazione lunga
- 📹 **Video astronomia** in tempo reale

ObservationManager supporta il sistema **TACOS** (The Australian Contributors for Occultation Science) per il controllo completo via USB.

## Architettura Sistema

```
┌──────────────────┐
│  Watec 910BD     │
│  (Video CCD)     │
└────┬─────────┬───┘
     │         │
     │ BNC     │ RS-232 (8-pin)
     │ (PAL)   │
     ▼         ▼
┌─────────┐  ┌──────────────────┐
│ Video   │  │ Arduino Nano/Uno │
│ Grabber │  │ + TACOS Firmware │
│ USB     │  └────────┬─────────┘
└────┬────┘           │ USB
     │                │
     ▼                ▼
┌────────────────────────────────┐
│  Mac/PC con ObservationManager │
│  - OpenCV: video via grabber   │
│  - pyserial: controllo via USB │
└────────────────────────────────┘
```

### Componenti Necessari

1. **Watec 910BD** (o varianti: 910HX, 902H2)
2. **Video Grabber USB PAL/NTSC** (es: Elgato, StarTech, Magewell)
3. **Arduino Nano/Uno** con firmware TACOS
4. **Cavo RS-232** (8-pin Watec → Arduino)
5. **Alimentazione 12V DC** per Watec

## Installazione Hardware

### 1. Preparazione Arduino TACOS

**Firmware**: Scarica da [http://www.hristopavlov.net/WAT910BD/](http://www.hristopavlov.net/WAT910BD/)

```bash
# Installa Arduino IDE
brew install --cask arduino  # macOS

# Carica firmware TACOS su Arduino Nano:
# 1. Apri Arduino IDE
# 2. File → Open → TACOS_WAT910BD.ino
# 3. Tools → Board → Arduino Nano
# 4. Tools → Port → /dev/cu.usbserial-XXX
# 5. Upload (⬆️)
```

**Connessioni Arduino ↔ Watec** (cavo RS-232 8-pin):
- Pin 2 (Arduino) → Pin 5 Watec (TX)
- Pin 3 (Arduino) → Pin 3 Watec (RX)
- GND → Pin 1 Watec (GND)

### 2. Setup Video Grabber

1. Collega BNC Watec → Video Grabber (adapter composito se necessario)
2. Collega Video Grabber USB → Mac
3. Verifica rilevamento:

```bash
python3 -c "import cv2; cap = cv2.VideoCapture(0); print(f'Device 0: {cap.isOpened()}')"
```

### 3. Test Connessioni

```bash
# Verifica porta seriale Arduino
ls -la /dev/tty.usbserial* /dev/cu.usbserial*

# Test comunicazione TACOS
python3 << EOF
from server.watec_controller import WatecController
watec = WatecController()
if watec.connect():
    print("✓ Watec connessa!")
    print(watec.get_status())
else:
    print("✗ Connessione fallita")
EOF
```

## Utilizzo Software

### 1. Avvio Server

```bash
cd /path/to/ObservationManager
uvicorn server.app:app --host 0.0.0.0 --port 8000
```

### 2. Interfaccia Web

1. Apri browser: `http://localhost:8000/camera.html`
2. Clicca link **"🎥 Watec 910BD"** in alto
3. Pannello Watec appare → **Connetti**
4. Scansiona e apri device video (video grabber)
5. Configura parametri Watec

### 3. Controlli Watec

#### Gamma
- **0.45**: Curva standard (consigliata per Luna/Pianeti)
- **0.50**: Curva alta (maggior contrasto)
- **OFF**: Lineare (raw, per plate solving)

#### Shutter Speed
- **1/50 - 1/100**: Deep sky, integrazione lunga
- **1/200 - 1/800**: Pianeti brillanti
- **1/1600 - 1/6400**: Luna, occultazioni
- **1/12800**: Luna piena, timing precisissimo

#### AGC (Automatic Gain Control)
- **ON**: Gain automatico (deep sky variabile)
- **OFF**: Gain manuale 0-255 (occultazioni, riprese calibrate)

#### AWB (Auto White Balance)
- **ON**: Bilanciamento automatico
- **OFF**: Bilanciamento manuale (raw per scientifica)

#### BLC (Back Light Compensation)
- **ON**: Compensazione controluce (raramente usato)
- **OFF**: Standard

### 4. Preset Ottimizzati

| Preset | Gamma | Shutter | AGC | Gain | Uso |
|--------|-------|---------|-----|------|-----|
| **Lunar** | 0.45 | 1/3200 | OFF | 50 | Luna ad alto contrasto |
| **Planetary** | 0.45 | 1/1600 | OFF | 100 | Giove, Saturno, Marte |
| **Deep Sky** | OFF | 1/50 | ON | Auto | Nebulose, galassie |
| **Occultation** | OFF | 1/100 | OFF | 200 | Timing stellare preciso |

## API REST

### Connessione

```bash
# Connetti (auto-detect porta)
curl -X POST http://localhost:8000/api/camera/watec/connect \
  -H "Content-Type: application/json" \
  -d '{}'

# Connetti a porta specifica
curl -X POST http://localhost:8000/api/camera/watec/connect \
  -H "Content-Type: application/json" \
  -d '{"port": "/dev/cu.usbserial-A50285BI"}'

# Stato
curl http://localhost:8000/api/camera/watec/status

# Disconnetti
curl -X POST http://localhost:8000/api/camera/watec/disconnect
```

### Controlli

```bash
# Gamma
curl -X POST http://localhost:8000/api/camera/watec/gamma \
  -H "Content-Type: application/json" \
  -d '{"gamma": "0.45"}'

# Shutter (multiplier: 1, 2, 4, 8, 16, 32, 64, 128, 256)
curl -X POST http://localhost:8000/api/camera/watec/shutter \
  -H "Content-Type: application/json" \
  -d '{"multiplier": 64}'

# AGC
curl -X POST http://localhost:8000/api/camera/watec/agc \
  -H "Content-Type: application/json" \
  -d '{"enabled": false}'

# Gain manuale (solo se AGC OFF)
curl -X POST http://localhost:8000/api/camera/watec/gain \
  -H "Content-Type: application/json" \
  -d '{"gain": 150}'

# Preset
curl -X POST http://localhost:8000/api/camera/watec/preset \
  -H "Content-Type: application/json" \
  -d '{"preset": "lunar"}'
```

## Scripting Python

```python
from server.watec_controller import WatecController

# Connetti
watec = WatecController()
watec.connect()

# Configura per Luna
watec.set_gamma("0.45")
watec.set_shutter(64)  # 1/3200
watec.set_agc(False)
watec.set_gain(50)
watec.set_awb(False)

# Oppure usa preset
watec.apply_preset("lunar")

# Stato
status = watec.get_status()
print(f"Gamma: {status['gamma']}")
print(f"Shutter: {status['shutter_speed']}")
print(f"Gain: {status['gain']}")

# Disconnetti
watec.disconnect()
```

## Troubleshooting

### Problema: "Watec 910BD non trovata"

**Soluzioni**:
1. Verifica Arduino collegato: `ls /dev/tty.usb* /dev/cu.usb*`
2. Controlla firmware TACOS caricato su Arduino
3. Test seriale manuale:
   ```python
   import serial
   ser = serial.Serial('/dev/cu.usbserial-XXX', 9600, timeout=1)
   ser.write(b"?\r\n")  # Comando status
   print(ser.readline())  # Dovrebbe rispondere "OK"
   ```

### Problema: "Video grabber non rilevato"

**Soluzioni**:
1. Verifica driver grabber installati
2. Test OpenCV:
   ```python
   import cv2
   for i in range(5):
       cap = cv2.VideoCapture(i)
       if cap.isOpened():
           print(f"Device {i}: OK")
   ```
3. Prova backend diverso:
   ```python
   cap = cv2.VideoCapture(0, cv2.CAP_AVFOUNDATION)  # macOS
   ```

### Problema: "Comando fallito" su gamma/shutter

**Soluzioni**:
1. Verifica firmware TACOS versione compatibile
2. Check baudrate: deve essere 9600
3. Log debug:
   ```python
   import logging
   logging.basicConfig(level=logging.DEBUG)
   watec.set_gamma("0.45")  # Vedi messaggi TX/RX
   ```

### Problema: Immagine nera o rumore

**Soluzioni**:
1. Verifica alimentazione 12V Watec (LED rosso acceso)
2. Controlla standard video: PAL vs NTSC sul grabber
3. Aumenta gain: `watec.set_gain(200)`
4. Shutter più lento: `watec.set_shutter(1)`  # 1/50

## Specifiche Tecniche Watec 910BD

- **Sensore**: Sony EXview HAD CCD 1/2"
- **Risoluzione**: 768×494 (PAL) / 768×480 (NTSC)
- **Sensibilità**: 0.0003 lux (F1.2)
- **Range dinamico**: >600x con gamma OFF
- **Shutter**: 1/50 - 1/100000 sec
- **Gamma**: 0.45, 0.50, OFF
- **AGC**: 0-48 dB
- **Alimentazione**: 12V DC, 1.9W
- **Uscita video**: 1.0Vp-p, 75Ω (BNC)
- **Controllo**: RS-232C (8-pin)

## Riferimenti

- **Sistema TACOS**: http://www.hristopavlov.net/WAT910BD/
- **Watec 910BD Manual**: https://www.watec.co.jp/en/product/camera/wat-910bd/
- **Arduino Firmware**: http://www.hristopavlov.net/WAT910BD/firmware/TACOS_WAT910BD.zip
- **ObservationManager Docs**: [ARCHITECTURE.md](ARCHITECTURE.md)

---

**Nota**: Il sistema TACOS è fornito AS-IS senza garanzie da TACOS contributors. ObservationManager implementa il protocollo TACOS ma non fornisce supporto hardware. Per problemi elettronici/meccanici, consulta la comunità TACOS.
