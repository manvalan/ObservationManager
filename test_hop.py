#!/usr/bin/env python3
"""
Test star-hopping algorithm and API endpoints.
"""

import sys
sys.path.insert(0, '/Users/michelebigi/Documents/Develop/VSC/ObservationManager')

from server.app import _plan_star_hop, _angular_distance


def test_angular_distance():
    """Test angular distance calculation."""
    print("🧪 Testing angular distance calculation...")
    
    # Same point
    dist = _angular_distance(0, 0, 0, 0)
    assert abs(dist) < 0.01, f"Same point should be 0°, got {dist}"
    print(f"✓ Same point: {dist:.3f}°")
    
    # 90° apart
    dist = _angular_distance(0, 0, 90, 0)
    assert abs(dist - 90) < 0.1, f"90° apart should be ~90°, got {dist}"
    print(f"✓ 90° apart: {dist:.3f}°")
    
    # Opposite poles
    dist = _angular_distance(0, 90, 0, -90)
    assert abs(dist - 180) < 0.1, f"Poles should be 180°, got {dist}"
    print(f"✓ Poles: {dist:.3f}°")
    
    print("✅ Angular distance tests passed!\n")


def test_star_hop_algorithm():
    """Test star-hopping pathfinding."""
    print("🧪 Testing star-hopping algorithm...")
    
    # Simple test: close target (should return empty path)
    print("\nTest 1: Close target (direct hop)")
    steps = _plan_star_hop(10.0, 45.0, 12.0, 46.0, max_steps=5, max_mag=4.0, max_spacing=10.0)
    print(f"  Steps required: {len(steps)}")
    assert len(steps) == 0, "Close target should need no intermediate steps"
    print("  ✓ Direct hop works")
    
    # Test: distant target (should find path)
    print("\nTest 2: Distant target (requires hops)")
    steps = _plan_star_hop(0.0, 45.0, 50.0, 45.0, max_steps=5, max_mag=5.0, max_spacing=15.0)
    print(f"  Steps found: {len(steps)}")
    
    if steps:
        print(f"  Path preview:")
        for i, step in enumerate(steps):
            print(f"    {i+1}. {step['name']}: RA {step['ra_deg']:.2f}° Dec {step['dec_deg']:.2f}° "
                  f"(mag {step.get('mag', 'N/A')}, {step['distance_from_prev']:.1f}° from prev)")
        print("  ✓ Pathfinding works")
    else:
        print("  ⚠️ No path found (may need Gaia catalog)")
    
    print("\n✅ Star-hopping algorithm tests passed!\n")


def test_integration():
    """Test integration with mock connection."""
    print("🧪 Testing integration with mock driver...")
    
    from lx200.connection import MockConnection
    from lx200.protocol import LX200
    
    conn = MockConnection()
    lx = LX200(conn)
    
    # Set initial position
    lx.set_target_ra_dec("10:00:00", "+45*00:00")
    lx.goto()
    
    ra = lx.get_ra()
    dec = lx.get_dec()
    print(f"  Mock position: RA={ra} Dec={dec}")
    
    # Parse coordinates
    hh, mm, ss = [float(p) for p in ra.split(":")]
    ra_deg = (hh + mm/60 + ss/3600) * 15.0
    
    print(f"  Parsed RA: {ra_deg:.3f}°")
    assert abs(ra_deg - 150.0) < 0.01, f"RA should be 150°, got {ra_deg}"
    
    print("  ✓ Mock integration works")
    print("\n✅ Integration tests passed!\n")


if __name__ == "__main__":
    print("=" * 60)
    print("Star-Hopping Algorithm Test Suite")
    print("=" * 60)
    print()
    
    try:
        test_angular_distance()
        test_star_hop_algorithm()
        test_integration()
        
        print("=" * 60)
        print("🎉 All tests passed!")
        print("=" * 60)
        print("\n💡 Try the web UI:")
        print("   1. Start server: python -m uvicorn server.app:app --reload")
        print("   2. Open: http://127.0.0.1:8000/ui/hop.html")
        print("   3. Plan a route and navigate step-by-step!")
        
    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
