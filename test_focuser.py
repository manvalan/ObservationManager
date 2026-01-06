#!/usr/bin/env python3
"""
Test smoke per il controllo del focheggiatore LX200.

Verifica:
- Comandi di movimento (in/out/stop)
- Cambio velocità (slow/fast)
- Query stato (posizione/temperatura)
- MockConnection simula risposte realistiche
"""

from lx200.connection import MockConnection
from lx200.protocol import LX200


def test_focuser_smoke():
    """Test basico del focheggiatore con MockConnection."""
    
    print("=" * 60)
    print("Test Focheggiatore LX200")
    print("=" * 60)
    
    # Setup
    conn = MockConnection()
    conn.open()
    lx = LX200(conn)
    
    # Test 1: Movimento IN
    print("\n1. Test movimento IN")
    try:
        lx.focus_in()
        assert ":F+#" in conn.history
        print("   ✓ Comando :F+ inviato")
    except Exception as e:
        print(f"   ✗ Errore: {e}")
        raise
    
    # Test 2: Movimento OUT
    print("\n2. Test movimento OUT")
    try:
        lx.focus_out()
        assert ":F-#" in conn.history
        print("   ✓ Comando :F- inviato")
    except Exception as e:
        print(f"   ✗ Errore: {e}")
        raise
    
    # Test 3: Stop
    print("\n3. Test stop movimento")
    try:
        lx.focus_stop()
        assert ":FQ#" in conn.history
        print("   ✓ Comando :FQ inviato")
    except Exception as e:
        print(f"   ✗ Errore: {e}")
        raise
    
    # Test 4: Velocità slow
    print("\n4. Test velocità SLOW")
    try:
        lx.set_focus_speed("slow")
        assert ":FS#" in conn.history
        print("   ✓ Comando :FS inviato")
    except Exception as e:
        print(f"   ✗ Errore: {e}")
        raise
    
    # Test 5: Velocità fast
    print("\n5. Test velocità FAST")
    try:
        lx.set_focus_speed("fast")
        assert ":FF#" in conn.history
        print("   ✓ Comando :FF inviato")
    except Exception as e:
        print(f"   ✗ Errore: {e}")
        raise
    
    # Test 6: Query temperatura
    print("\n6. Test query temperatura")
    try:
        temp = conn.query(":FT")
        print(f"   ✓ Temperatura: {temp}°C")
        assert temp is not None
        assert float(temp) > 0  # Mock returns 20.5
    except Exception as e:
        print(f"   ✗ Errore: {e}")
        raise
    
    # Test 7: Query posizione
    print("\n7. Test query posizione")
    try:
        pos = conn.query(":FG")
        print(f"   ✓ Posizione: {pos} steps")
        assert pos is not None
        assert int(pos) > 0  # Mock returns 5000
    except Exception as e:
        print(f"   ✗ Errore: {e}")
        raise
    
    # Test 8: Velocità invalida
    print("\n8. Test velocità invalida")
    try:
        lx.set_focus_speed("invalid")
        print("   ✗ Doveva sollevare ValueError")
        raise AssertionError("Expected ValueError")
    except ValueError as e:
        print(f"   ✓ ValueError correttamente sollevato: {e}")
    
    # Test 9: Sequenza realistica
    print("\n9. Test sequenza realistica")
    try:
        conn.history.clear()
        
        # Imposta velocità lenta
        lx.set_focus_speed("slow")
        
        # Muovi IN per messa a fuoco
        lx.focus_in()
        
        # Ferma
        lx.focus_stop()
        
        # Controlla posizione
        pos = conn.query(":FG")
        
        # Verifica storia comandi
        assert ":FS#" in conn.history
        assert ":F+#" in conn.history
        assert ":FQ#" in conn.history
        assert ":FG#" in conn.history
        
        print("   ✓ Sequenza completata correttamente")
        print(f"   Storia comandi: {len(conn.history)} comandi")
        
    except Exception as e:
        print(f"   ✗ Errore: {e}")
        raise
    
    # Cleanup
    conn.close()
    
    # Summary
    print("\n" + "=" * 60)
    print("✅ TUTTI I TEST PASSATI")
    print("=" * 60)
    print(f"\nTotale comandi testati: {len(conn.history)}")
    print("Comandi inviati:")
    for i, cmd in enumerate(set(conn.history), 1):
        print(f"  {i}. {cmd}")
    print()


if __name__ == "__main__":
    test_focuser_smoke()
