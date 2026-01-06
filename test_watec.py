#!/usr/bin/env python3
"""
Test script per Watec 910BD - ObservationManager
Verifica funzionalità hardware e protocollo TACOS
"""
import sys
import time
from server.watec_controller import WatecController

def print_status(watec):
    """Stampa stato formattato."""
    status = watec.get_status()
    print("\n" + "="*50)
    print("STATO WATEC 910BD")
    print("="*50)
    print(f"Connessa:      {status['connected']}")
    print(f"Porta:         {status['port']}")
    print(f"Gamma:         {status['gamma']}")
    print(f"Shutter:       {status['shutter_speed']} (x{status['shutter_multiplier']})")
    print(f"AGC:           {'ON' if status['agc_enabled'] else 'OFF'}")
    if not status['agc_enabled']:
        print(f"Gain manuale:  {status['gain']}/255")
    print(f"AWB:           {'ON' if status['awb_enabled'] else 'OFF'}")
    print(f"BLC:           {'ON' if status['blc_enabled'] else 'OFF'}")
    print(f"Sistema video: {status['video_system']}")
    print("="*50 + "\n")


def test_connection():
    """Test 1: Connessione base."""
    print("\n[TEST 1] Connessione Watec 910BD...")
    watec = WatecController()
    
    # Cerca porta
    port = watec.find_watec_port()
    if port:
        print(f"✓ Porta trovata: {port}")
    else:
        print("✗ Nessuna porta Arduino/FTDI trovata")
        print("\nAssicurati che:")
        print("  1. Arduino con firmware TACOS sia collegato")
        print("  2. Driver USB installati")
        print("  3. pyserial installato: pip install pyserial")
        return None
    
    # Connetti
    if watec.connect(port):
        print("✓ Connessione OK")
        print_status(watec)
        return watec
    else:
        print("✗ Connessione fallita")
        print("\nVerifica:")
        print("  1. Firmware TACOS caricato su Arduino")
        print("  2. Baudrate 9600")
        print("  3. Cavo RS-232 collegato a Watec")
        return None


def test_gamma(watec):
    """Test 2: Controllo gamma."""
    print("\n[TEST 2] Test controllo gamma...")
    
    for gamma in ["0.45", "0.50", "OFF"]:
        print(f"  Impostando gamma {gamma}...", end=" ")
        if watec.set_gamma(gamma):
            print("✓")
            time.sleep(0.5)
        else:
            print("✗ FALLITO")
            return False
    
    print("✓ Gamma OK")
    return True


def test_shutter(watec):
    """Test 3: Controllo shutter."""
    print("\n[TEST 3] Test controllo shutter...")
    
    # Test alcuni valori chiave
    multipliers = [1, 8, 64, 256]
    
    for mult in multipliers:
        print(f"  Shutter x{mult}...", end=" ")
        if watec.set_shutter(mult):
            status = watec.get_status()
            print(f"✓ ({status['shutter_speed']})")
            time.sleep(0.5)
        else:
            print("✗ FALLITO")
            return False
    
    print("✓ Shutter OK")
    return True


def test_agc_gain(watec):
    """Test 4: AGC e gain manuale."""
    print("\n[TEST 4] Test AGC e gain manuale...")
    
    # Disabilita AGC
    print("  AGC OFF...", end=" ")
    if not watec.set_agc(False):
        print("✗ FALLITO")
        return False
    print("✓")
    time.sleep(0.5)
    
    # Test gain manuale
    for gain in [50, 128, 200]:
        print(f"  Gain {gain}...", end=" ")
        if watec.set_gain(gain):
            print("✓")
            time.sleep(0.5)
        else:
            print("✗ FALLITO")
            return False
    
    # Riabilita AGC
    print("  AGC ON...", end=" ")
    if not watec.set_agc(True):
        print("✗ FALLITO")
        return False
    print("✓")
    
    print("✓ AGC/Gain OK")
    return True


def test_awb_blc(watec):
    """Test 5: AWB e BLC."""
    print("\n[TEST 5] Test AWB e BLC...")
    
    print("  AWB OFF...", end=" ")
    if not watec.set_awb(False):
        print("✗ FALLITO")
        return False
    print("✓")
    time.sleep(0.5)
    
    print("  AWB ON...", end=" ")
    if not watec.set_awb(True):
        print("✗ FALLITO")
        return False
    print("✓")
    time.sleep(0.5)
    
    print("  BLC ON...", end=" ")
    if not watec.set_blc(True):
        print("✗ FALLITO")
        return False
    print("✓")
    time.sleep(0.5)
    
    print("  BLC OFF...", end=" ")
    if not watec.set_blc(False):
        print("✗ FALLITO")
        return False
    print("✓")
    
    print("✓ AWB/BLC OK")
    return True


def test_presets(watec):
    """Test 6: Preset ottimizzati."""
    print("\n[TEST 6] Test preset ottimizzati...")
    
    presets = ["lunar", "planetary", "deepsky", "occultation"]
    
    for preset in presets:
        print(f"  Preset '{preset}'...", end=" ")
        if watec.apply_preset(preset):
            print("✓")
            time.sleep(1)
        else:
            print("✗ FALLITO")
            return False
    
    print("✓ Preset OK")
    return True


def main():
    print("="*50)
    print("WATEC 910BD TEST SUITE")
    print("ObservationManager - TACOS Protocol")
    print("="*50)
    
    # Test 1: Connessione
    watec = test_connection()
    if not watec:
        print("\n❌ Test fallito: impossibile connettersi")
        return 1
    
    try:
        # Test 2-6: Controlli
        tests = [
            ("Gamma", test_gamma),
            ("Shutter", test_shutter),
            ("AGC/Gain", test_agc_gain),
            ("AWB/BLC", test_awb_blc),
            ("Presets", test_presets)
        ]
        
        results = []
        for name, test_func in tests:
            try:
                result = test_func(watec)
                results.append((name, result))
            except Exception as e:
                print(f"\n✗ Errore durante test {name}: {e}")
                results.append((name, False))
        
        # Stato finale
        print_status(watec)
        
        # Summary
        print("\n" + "="*50)
        print("RIEPILOGO TEST")
        print("="*50)
        
        all_passed = True
        for name, passed in results:
            status = "✓ PASS" if passed else "✗ FAIL"
            print(f"{name:15} {status}")
            if not passed:
                all_passed = False
        
        print("="*50)
        
        if all_passed:
            print("\n✅ TUTTI I TEST SUPERATI")
            print("\nLa tua Watec 910BD è completamente funzionante!")
            print("Puoi ora usare l'interfaccia web: http://localhost:8000/camera.html")
            return 0
        else:
            print("\n⚠️ ALCUNI TEST FALLITI")
            print("\nVerifica:")
            print("  1. Firmware TACOS corretto su Arduino")
            print("  2. Watec 910BD alimentata (12V DC)")
            print("  3. Connessioni RS-232 corrette")
            print("  4. Log debug per dettagli")
            return 1
            
    finally:
        # Cleanup
        watec.disconnect()
        print("\nWatec disconnessa.")


if __name__ == "__main__":
    sys.exit(main())
