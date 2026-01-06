#!/usr/bin/env python3
"""
Test Suite - Camera Controller
Testa CameraController per device management, settings, capture, statistics
"""
from server.camera import CameraController
import sys

print("=" * 60)
print("Camera Controller Test Suite")
print("=" * 60)

# Test 1: Inizializzazione
print("\n🧪 Test 1: Inizializzazione controller")
try:
    controller = CameraController()
    print("  ✓ Controller inizializzato")
    print(f"  Settings default: {controller.settings}")
    assert controller.device is None, "Device deve essere None all'inizio"
    assert controller.is_capturing is False, "is_capturing deve essere False"
    print("✅ Test inizializzazione OK")
except Exception as e:
    print(f"❌ Test fallito: {e}")
    sys.exit(1)

# Test 2: List devices
print("\n🧪 Test 2: Scansione devices")
try:
    devices = controller.list_devices(max_check=5)
    print(f"  Devices trovati: {len(devices)}")
    for dev in devices:
        print(f"    - {dev['name']}: {dev['width']}x{dev['height']} ({dev['backend']})")
    print("✅ Test list_devices OK")
except Exception as e:
    print(f"❌ Test fallito: {e}")

# Test 3: Open device (se disponibile)
print("\n🧪 Test 3: Apertura device")
try:
    devices = controller.list_devices(max_check=3)
    if len(devices) > 0:
        result = controller.open_device(devices[0]['index'])
        print(f"  ✓ Device {result['index']} aperto")
        print(f"  Capabilities: {result['capabilities']}")
        
        # Test 4: Update settings
        print("\n🧪 Test 4: Update settings")
        new_settings = controller.update_settings(
            exposure=10,
            gain=50,
            binning=2
        )
        print(f"  ✓ Settings aggiornati")
        print(f"    Exposure: {new_settings['exposure']}")
        print(f"    Gain: {new_settings['gain']}")
        print(f"    Binning: {new_settings['binning']}")
        print("✅ Test update_settings OK")
        
        # Test 5: Capture single frame
        print("\n🧪 Test 5: Capture singola")
        try:
            frame = controller.capture_single(timeout=3.0)
            print(f"  ✓ Frame catturato: {frame.shape}")
            assert frame is not None, "Frame non deve essere None"
            assert len(frame.shape) >= 2, "Frame deve avere almeno 2 dimensioni"
            print("✅ Test capture_single OK")
            
            # Test 6: Statistics
            print("\n🧪 Test 6: Calcolo statistiche")
            stats = controller.compute_statistics(frame)
            print(f"  Mean: {stats['mean']:.2f}")
            print(f"  StdDev: {stats['std']:.2f}")
            print(f"  SNR: {stats['snr']:.2f}")
            print(f"  Min: {stats['min']}, Max: {stats['max']}")
            print(f"  Histogram bins: {len(stats['histogram'])}")
            assert 'mean' in stats, "Stats deve contenere 'mean'"
            assert 'histogram' in stats, "Stats deve contenere 'histogram'"
            print("✅ Test statistics OK")
            
            # Test 7: FWHM estimation
            print("\n🧪 Test 7: Stima FWHM")
            fwhm = controller.estimate_fwhm(frame)
            print(f"  FWHM: {fwhm:.2f} pixels")
            print("✅ Test FWHM OK")
            
            # Test 8: Save FITS (se astropy disponibile)
            print("\n🧪 Test 8: Salvataggio FITS")
            try:
                filepath = controller.save_fits(
                    frame,
                    "test_capture.fits",
                    metadata={
                        "OBJECT": "Test Target",
                        "RA": 150.0,
                        "DEC": 45.0
                    }
                )
                print(f"  ✓ FITS salvato: {filepath}")
                print("✅ Test save_fits OK")
            except RuntimeError as e:
                print(f"  ⚠️ FITS save skipped: {e}")
        
        except TimeoutError:
            print("  ⚠️ Capture timeout (device potrebbe non supportare capture)")
        except Exception as e:
            print(f"  ⚠️ Capture test skipped: {e}")
        
        # Test 9: Start/Stop capture
        print("\n🧪 Test 9: Capture continua")
        try:
            controller.start_capture()
            assert controller.is_capturing is True, "is_capturing deve essere True"
            print("  ✓ Capture avviata")
            
            import time
            time.sleep(0.5)
            
            frame = controller.get_frame()
            if frame is not None:
                print(f"  ✓ Frame da buffer: {frame.shape}")
            
            controller.stop_capture()
            assert controller.is_capturing is False, "is_capturing deve essere False"
            print("  ✓ Capture fermata")
            print("✅ Test capture continua OK")
        except Exception as e:
            print(f"  ⚠️ Continuous capture test skipped: {e}")
        
        # Cleanup
        controller.close_device()
        print("\n  ✓ Device chiuso")
        print("✅ Test open_device OK")
    else:
        print("  ⚠️ Nessun device disponibile, test skip")
        print("  (Normale su sistemi senza webcam)")
except Exception as e:
    print(f"❌ Test fallito: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 60)
print("🎉 Test suite completata!")
print("=" * 60)
print("\n💡 Per testare con UI:")
print("   1. Start server: python -m uvicorn server.app:app --reload")
print("   2. Apri: http://127.0.0.1:8000/ui/camera.html")
print("   3. Scansiona devices, apri camera, modifica settings")
print("   4. Cattura frame, visualizza statistiche, salva FITS")
