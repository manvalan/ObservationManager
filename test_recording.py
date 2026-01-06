#!/usr/bin/env python3
"""
Test script per Video Recording e Image Sequences
Verifica funzionalità di registrazione e acquisizione
"""
import sys
import time
from pathlib import Path
from server.camera import camera_controller

def test_recording():
    """Test registrazione video."""
    print("\n[TEST 1] Registrazione Video")
    print("="*50)
    
    # Apri device mock (device 0 se disponibile)
    try:
        devices = camera_controller.list_devices()
        if not devices:
            print("✗ Nessun device disponibile")
            return False
        
        camera_controller.open_device(devices[0]['index'])
        camera_controller.start_capture()
        print(f"✓ Device aperto: {devices[0]['name']}")
        time.sleep(1)
        
    except Exception as e:
        print(f"✗ Errore apertura device: {e}")
        return False
    
    # Start recording
    try:
        info = camera_controller.start_recording(
            filename="test_video",
            codec="mp4v"
        )
        print(f"✓ Recording avviato: {info['filename']}")
        print(f"  FPS: {info['fps']}, Resolution: {info['resolution']}")
        
        # Registra per 3 secondi
        for i in range(3):
            status = camera_controller.get_recording_status()
            print(f"  [{i+1}s] Frames: {status['frames']}, FPS: {status['fps']:.1f}")
            time.sleep(1)
        
        # Stop
        result = camera_controller.stop_recording()
        print(f"✓ Recording fermato")
        print(f"  Frames totali: {result['frames']}")
        print(f"  Durata: {result['duration']:.1f}s")
        print(f"  File: {result['filepath']}")
        
        # Verifica file
        if Path(result['filepath']).exists():
            size = Path(result['filepath']).stat().st_size
            print(f"  Dimensione: {size / 1024:.1f} KB")
            return True
        else:
            print(f"✗ File non trovato: {result['filepath']}")
            return False
            
    except Exception as e:
        print(f"✗ Errore recording: {e}")
        return False
    finally:
        if camera_controller.is_recording:
            camera_controller.stop_recording()


def test_image_sequence():
    """Test sequenza immagini."""
    print("\n[TEST 2] Sequenza Immagini")
    print("="*50)
    
    # Device già aperto dal test precedente
    try:
        info = camera_controller.start_image_sequence(
            count=5,
            interval=0.5,
            filename_prefix="test_seq",
            save_format="png"
        )
        print(f"✓ Sequenza avviata: {info['count']} immagini")
        print(f"  Intervallo: {info['interval']}s")
        print(f"  Formato: {info['format']}")
        print(f"  Output: {info['output_dir']}")
        
        # Monitor progress
        while camera_controller.is_sequencing:
            status = camera_controller.get_sequence_status()
            print(f"  Progress: {status['captured']}/{status['total']} ({status['progress']:.0f}%)")
            time.sleep(0.3)
        
        # Risultato finale
        status = camera_controller.get_sequence_status()
        print(f"✓ Sequenza completata: {status['captured']} immagini")
        
        # Verifica file
        output_dir = Path(info['output_dir'])
        files = list(output_dir.glob("test_seq_*.png"))
        print(f"  File trovati: {len(files)}")
        
        if len(files) >= 5:
            total_size = sum(f.stat().st_size for f in files)
            print(f"  Dimensione totale: {total_size / 1024:.1f} KB")
            return True
        else:
            print(f"✗ File insufficienti: attesi 5, trovati {len(files)}")
            return False
            
    except Exception as e:
        print(f"✗ Errore sequenza: {e}")
        return False
    finally:
        if camera_controller.is_sequencing:
            camera_controller.stop_image_sequence()


def test_fits_sequence():
    """Test sequenza FITS con metadata."""
    print("\n[TEST 3] Sequenza FITS con Metadata")
    print("="*50)
    
    try:
        metadata = {
            'OBJECT': 'Test Target',
            'RA': 12.5,
            'DEC': 45.3
        }
        
        info = camera_controller.start_image_sequence(
            count=3,
            interval=0.2,
            filename_prefix="test_fits",
            save_format="fits",
            metadata=metadata
        )
        print(f"✓ Sequenza FITS avviata: {info['count']} immagini")
        
        # Attendi completamento
        while camera_controller.is_sequencing:
            status = camera_controller.get_sequence_status()
            time.sleep(0.2)
        
        status = camera_controller.get_sequence_status()
        print(f"✓ Sequenza FITS completata: {status['captured']} immagini")
        
        # Verifica file FITS
        output_dir = Path(info['output_dir'])
        fits_files = list(output_dir.glob("test_fits_*.fits"))
        print(f"  File FITS trovati: {len(fits_files)}")
        
        if len(fits_files) >= 3:
            # Verifica header FITS (richiede astropy)
            try:
                from astropy.io import fits as astropy_fits
                with astropy_fits.open(fits_files[0]) as hdul:
                    header = hdul[0].header
                    print(f"  Header FITS OK")
                    if 'OBJECT' in header:
                        print(f"    OBJECT: {header['OBJECT']}")
                    if 'RA' in header:
                        print(f"    RA: {header['RA']}")
            except ImportError:
                print("  (Astropy non disponibile per verifica header)")
            
            return True
        else:
            print(f"✗ File insufficienti: attesi 3, trovati {len(fits_files)}")
            return False
            
    except Exception as e:
        print(f"✗ Errore sequenza FITS: {e}")
        return False


def main():
    print("="*50)
    print("VIDEO RECORDING & IMAGE SEQUENCES TEST")
    print("ObservationManager")
    print("="*50)
    
    results = []
    
    # Test 1: Video Recording
    try:
        result = test_recording()
        results.append(("Video Recording", result))
    except Exception as e:
        print(f"\n✗ Test recording fallito: {e}")
        results.append(("Video Recording", False))
    
    # Test 2: Image Sequence PNG
    try:
        result = test_image_sequence()
        results.append(("Image Sequence (PNG)", result))
    except Exception as e:
        print(f"\n✗ Test sequence fallito: {e}")
        results.append(("Image Sequence (PNG)", False))
    
    # Test 3: Image Sequence FITS
    try:
        result = test_fits_sequence()
        results.append(("Image Sequence (FITS)", result))
    except Exception as e:
        print(f"\n✗ Test FITS sequence fallito: {e}")
        results.append(("Image Sequence (FITS)", False))
    
    # Cleanup
    camera_controller.stop_capture()
    camera_controller.close_device()
    
    # Summary
    print("\n" + "="*50)
    print("RIEPILOGO TEST")
    print("="*50)
    
    all_passed = True
    for name, passed in results:
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{name:25} {status}")
        if not passed:
            all_passed = False
    
    print("="*50)
    
    if all_passed:
        print("\n✅ TUTTI I TEST SUPERATI")
        print("\nFile salvati in:")
        print("  - data/recordings/test_video.mp4")
        print("  - data/sequences/test_seq_*.png")
        print("  - data/sequences/test_fits_*.fits")
        return 0
    else:
        print("\n⚠️ ALCUNI TEST FALLITI")
        return 1


if __name__ == "__main__":
    sys.exit(main())
