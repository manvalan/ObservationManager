#!/usr/bin/env python3
"""
Quick test script for MockConnection virtual driver.
Run this to verify mock driver works without hardware.
"""

from lx200.connection import MockConnection
from lx200.protocol import LX200


def test_mock_basic():
    """Test basic mock connection operations"""
    print("🧪 Testing MockConnection basic operations...")
    
    conn = MockConnection()
    lx = LX200(conn)
    
    # Test version query
    version = lx.get_version()
    print(f"✓ Version: {version}")
    assert "LX200GPS" in version
    
    # Test initial position
    ra = lx.get_ra()
    dec = lx.get_dec()
    print(f"✓ Initial position: RA={ra}, Dec={dec}")
    
    # Test GOTO
    print("\n🎯 Testing GOTO...")
    lx.set_target_ra_dec("10:30:00", "+45*30:00")
    result = lx.goto()
    print(f"✓ Slew result: {result}")
    
    # Verify position changed
    new_ra = lx.get_ra()
    new_dec = lx.get_dec()
    print(f"✓ New position: RA={new_ra}, Dec={new_dec}")
    # Note: Mock returns with # terminator
    assert "10:30:00" in new_ra
    assert "45*30:00" in new_dec
    
    # Test sync
    print("\n🔄 Testing SYNC...")
    sync_msg = lx.sync_to("12:00:00", "+60*00:00")
    print(f"✓ Sync message: {sync_msg}")
    assert "matched" in sync_msg.lower() or "Coordinates" in sync_msg
    
    # Test movement
    print("\n↗️  Testing MOVE...")
    lx.move_dir("n")
    lx.move_dir("e")
    lx.stop_all()
    print("✓ Movement commands sent")
    
    # Test command history
    print(f"\n📜 Command history ({len(conn.history)} commands):")
    for i, cmd in enumerate(conn.history[-5:], 1):
        print(f"  {i}. {cmd}")
    
    print("\n✅ All tests passed! MockConnection works correctly.")
    print("\n💡 You can now use the web UI with mock driver:")
    print("   1. Start server: python -m uvicorn server.app:app --reload")
    print("   2. Open browser: http://127.0.0.1:8000/ui/")
    print("   3. Connect using 'mock' or leave port empty")


def test_mock_state_tracking():
    """Test that mock tracks state correctly"""
    print("\n🔬 Testing state tracking...")
    
    conn = MockConnection()
    lx = LX200(conn)
    
    # Initial state should be unaligned
    initial_ra = lx.get_ra()
    print(f"✓ Initial RA: {initial_ra}")
    
    # After slew, position should update
    lx.set_target_ra_dec("15:30:45", "+30*15:30")
    lx.goto()
    slew_ra = lx.get_ra()
    slew_dec = lx.get_dec()
    print(f"✓ After slew: RA={slew_ra}, Dec={slew_dec}")
    assert "15:30:45" in slew_ra
    assert "30*15:30" in slew_dec
    
    # Sync should update position and set aligned flag
    sync_msg = lx.sync_to("16:00:00", "+45*00:00")
    sync_ra = lx.get_ra()
    sync_dec = lx.get_dec()
    print(f"✓ After sync: RA={sync_ra}, Dec={sync_dec}")
    assert "16:00:00" in sync_ra
    assert "45*00:00" in sync_dec
    
    print("✅ State tracking works correctly!")


if __name__ == "__main__":
    print("=" * 60)
    print("MockConnection Virtual Driver Test Suite")
    print("=" * 60)
    print()
    
    try:
        test_mock_basic()
        test_mock_state_tracking()
        print("\n" + "=" * 60)
        print("🎉 All tests passed! Mock driver is ready.")
        print("=" * 60)
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
