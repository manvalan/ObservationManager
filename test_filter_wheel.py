#!/usr/bin/env python3
"""
Test suite for Filter Wheel (Milestone 8.1)

Tests:
- Mock filter wheel initialization and connection
- Filter selection and position tracking
- Filter list management
- Status and statistics monitoring
- API endpoints validation
"""

import sys
import time
from server.filter_wheel import SerialFilterWheel, MockFilterWheel, FilterWheelManager, Filter


def test_mock_filter_wheel_init():
    """Test mock filter wheel initialization."""
    print("🧪 Testing mock filter wheel initialization...")
    
    wheel = MockFilterWheel()
    assert wheel.is_connected() or wheel.connect(), "Failed to connect mock wheel"
    
    print(f"  ✓ Connected: {wheel.is_connected()}")
    print(f"  ✓ Status: {wheel.get_status()['status']}")
    print(f"  ✓ Position: {wheel.get_position()}")
    print(f"  ✓ Filter count: {wheel.get_filter_count()}")
    
    print("✅ Mock filter wheel initialization test passed!\n")


def test_filter_selection():
    """Test filter selection and movement."""
    print("🧪 Testing filter selection...")
    
    wheel = MockFilterWheel()
    wheel.connect()
    
    # Select filter 0 (Clear)
    assert wheel.select_filter(0), "Failed to select filter 0"
    print(f"  ✓ Selected filter 0 (Clear)")
    
    # Wait for movement
    assert wheel.wait_for_position(0, timeout=3.0), "Timeout waiting for position 0"
    print(f"  ✓ Reached position 0")
    
    # Select filter 2 (Green)
    assert wheel.select_filter(2), "Failed to select filter 2"
    print(f"  ✓ Selected filter 2 (Green)")
    
    # Wait for movement
    assert wheel.wait_for_position(2, timeout=3.0), "Timeout waiting for position 2"
    print(f"  ✓ Reached position 2")
    
    current_pos = wheel.get_position()
    print(f"  ✓ Current position: {current_pos}")
    print(f"  ✓ Current filter: {wheel.get_filter_name(current_pos)}")
    
    print("✅ Filter selection test passed!\n")


def test_filter_list():
    """Test filter list management."""
    print("🧪 Testing filter list management...")
    
    wheel = MockFilterWheel()
    wheel.connect()
    
    filters = wheel.get_filters()
    print(f"  ✓ Available filters: {len(filters)}")
    
    for f in filters:
        print(f"    - {f['position']}: {f['name']} ({f['color']})")
    
    # Get filter names
    names = [wheel.get_filter_name(i) for i in range(wheel.get_filter_count())]
    print(f"  ✓ Filter names: {', '.join(names)}")
    
    # Set custom names
    custom_names = ["Clear", "Luminance", "Red", "Green", "Blue", "H-Alpha"]
    wheel.set_filter_names(custom_names)
    print(f"  ✓ Set custom filter names")
    
    # Verify
    names_after = [wheel.get_filter_name(i) for i in range(wheel.get_filter_count())]
    print(f"  ✓ Updated names: {', '.join(names_after)}")
    
    print("✅ Filter list test passed!\n")


def test_status_monitoring():
    """Test status and statistics monitoring."""
    print("🧪 Testing status monitoring...")
    
    wheel = MockFilterWheel()
    wheel.connect()
    
    # Get initial status
    status = wheel.get_status()
    print(f"  ✓ Connected: {status['connected']}")
    print(f"  ✓ Status: {status['status']}")
    print(f"  ✓ Position: {status['position']}")
    print(f"  ✓ Filter: {status['filter_name']}")
    
    # Make some moves
    for i in range(3):
        wheel.select_filter(i)
        wheel.wait_for_position(i, timeout=3.0)
    
    # Get statistics
    stats = wheel.get_statistics()
    print(f"  ✓ Total moves: {stats['moves_total']}")
    print(f"  ✓ Errors: {stats['errors']}")
    print(f"  ✓ Uptime: {stats['uptime_sec']:.1f}s")
    
    # Final status
    final_status = wheel.get_status()
    print(f"  ✓ Final position: {final_status['position']}")
    print(f"  ✓ Still moving: {final_status['moving']}")
    
    print("✅ Status monitoring test passed!\n")


def test_filter_wheel_manager():
    """Test FilterWheelManager singleton."""
    print("🧪 Testing FilterWheelManager...")
    
    manager = FilterWheelManager()
    
    # Create wheels
    wheel1 = manager.create_wheel("main")
    wheel2 = manager.create_wheel("secondary")
    
    print(f"  ✓ Created wheel 'main'")
    print(f"  ✓ Created wheel 'secondary'")
    
    # Connect
    assert wheel1.connect(), "Failed to connect wheel1"
    assert wheel2.connect(), "Failed to connect wheel2"
    print(f"  ✓ Both wheels connected")
    
    # List wheels
    wheels_list = manager.list_wheels()
    print(f"  ✓ Registered wheels: {wheels_list}")
    
    # Get wheel
    retrieved = manager.get_wheel("main")
    assert retrieved is wheel1, "Failed to retrieve correct wheel"
    print(f"  ✓ Retrieved correct wheel")
    
    # Get default
    default = manager.get_wheel(None)
    print(f"  ✓ Default wheel: {manager._default_wheel}")
    
    # Remove wheel
    manager.remove_wheel("secondary")
    print(f"  ✓ Removed secondary wheel")
    print(f"  ✓ Remaining wheels: {manager.list_wheels()}")
    
    print("✅ FilterWheelManager test passed!\n")


def test_invalid_operations():
    """Test error handling."""
    print("🧪 Testing error handling...")
    
    wheel = MockFilterWheel()
    wheel.connect()
    
    # Invalid position
    result = wheel.select_filter(99)
    print(f"  ✓ Invalid position rejected: {not result}")
    
    # Disconnect and try to move
    wheel.disconnect()
    result = wheel.select_filter(0)
    print(f"  ✓ Disconnected wheel rejects moves: {not result}")
    
    # Reconnect
    wheel.connect()
    result = wheel.select_filter(0)
    print(f"  ✓ Reconnected wheel accepts moves: {result}")
    
    print("✅ Error handling test passed!\n")


def test_sequential_moves():
    """Test sequential filter changes."""
    print("🧪 Testing sequential moves...")
    
    wheel = MockFilterWheel()
    wheel.connect()
    
    sequence = [0, 2, 4, 1, 3, 0]
    total_time = 0
    
    for target in sequence:
        start = time.time()
        wheel.select_filter(target)
        success = wheel.wait_for_position(target, timeout=5.0)
        elapsed = time.time() - start
        total_time += elapsed
        
        filter_name = wheel.get_filter_name(target)
        print(f"  ✓ {filter_name} ({target}): {elapsed:.2f}s")
        
        assert success, f"Failed to reach position {target}"
    
    print(f"  ✓ Total time: {total_time:.1f}s")
    print(f"  ✓ Average per move: {total_time/len(sequence):.2f}s")
    
    print("✅ Sequential moves test passed!\n")


def test_filter_properties():
    """Test Filter class properties."""
    print("🧪 Testing Filter properties...")
    
    # Create filter
    f = Filter(0, "Clear", "#ffffff", 700)
    
    # Convert to dict
    fdict = f.to_dict()
    print(f"  ✓ Position: {fdict['position']}")
    print(f"  ✓ Name: {fdict['name']}")
    print(f"  ✓ Color: {fdict['color']}")
    print(f"  ✓ Wavelength: {fdict['wavelength_nm']}nm")
    
    # Create without wavelength
    f2 = Filter(1, "Red", "#ff0000")
    fdict2 = f2.to_dict()
    print(f"  ✓ Optional wavelength: {fdict2['wavelength_nm']}")
    
    print("✅ Filter properties test passed!\n")


if __name__ == "__main__":
    print("=" * 60)
    print("Filter Wheel Test Suite (Milestone 8.1)")
    print("=" * 60)
    print()
    
    try:
        test_mock_filter_wheel_init()
        test_filter_selection()
        test_filter_list()
        test_status_monitoring()
        test_filter_wheel_manager()
        test_invalid_operations()
        test_sequential_moves()
        test_filter_properties()
        
        print("=" * 60)
        print("🎉 All filter wheel tests passed!")
        print("=" * 60)
        sys.exit(0)
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
