#!/usr/bin/env python3
"""
Test suite for Sequence Automation and Session Management
"""

import sys
sys.path.insert(0, '/Users/michelebigi/Documents/Develop/VSC/ObservationManager')

from server.session_manager import SessionManager
from server.sequence import ObservingSequence, SequenceStep, StepType
import json
from pathlib import Path


def test_session_creation():
    """Test creating and managing sessions."""
    print("🧪 Testing session creation...")
    
    # Create session
    session_id = SessionManager.create_session(site_id="TestSite")
    assert session_id.startswith("sess_"), f"Invalid session ID: {session_id}"
    print(f"✓ Session created: {session_id}")
    
    # Get session
    session = SessionManager.get_session(session_id)
    assert session is not None, "Session not found"
    assert session["site_id"] == "TestSite", "Site ID mismatch"
    print(f"✓ Session retrieved: {session['id']}")
    
    print("✅ Session creation tests passed!\n")
    return session_id


def test_alignment_logging(session_id):
    """Test alignment logging."""
    print("🧪 Testing alignment logging...")
    
    # Log alignment
    align_id = SessionManager.log_alignment(
        session_id,
        star_name="Vega",
        ra_deg=279.234,
        dec_deg=38.783,
        alt_deg=65.2,
        az_deg=180.5,
        residual_arcmin=2.3
    )
    assert align_id.startswith("align_"), f"Invalid alignment ID: {align_id}"
    print(f"✓ Alignment logged: {align_id}")
    
    # Log more alignments
    SessionManager.log_alignment(session_id, "Deneb", 310.358, 45.280, 58.7, 210.3, 1.8)
    SessionManager.log_alignment(session_id, "Altair", 297.695, 8.868, 42.1, 145.2, 3.1)
    print("✓ Multiple alignments logged")
    
    # Get alignments
    alignments = SessionManager.get_session_alignments(session_id)
    assert len(alignments) == 3, f"Expected 3 alignments, got {len(alignments)}"
    print(f"✓ Retrieved {len(alignments)} alignments")
    
    # Check average residual
    mean_residual = sum(a["residual_arcmin"] for a in alignments) / len(alignments)
    print(f"✓ Mean alignment residual: {mean_residual:.2f} arcmin")
    
    print("✅ Alignment logging tests passed!\n")


def test_sync_logging(session_id):
    """Test sync logging."""
    print("🧪 Testing sync logging...")
    
    # Log sync
    sync_id = SessionManager.log_sync(
        session_id,
        ra_deg=279.234,
        dec_deg=38.783,
        pointing_ra=279.245,
        pointing_dec=38.795,
        alignment_quality=0.95
    )
    assert sync_id.startswith("sync_"), f"Invalid sync ID: {sync_id}"
    print(f"✓ Sync logged: {sync_id}")
    
    # Get syncs
    syncs = SessionManager.get_session_syncs(session_id)
    assert len(syncs) == 1, f"Expected 1 sync, got {len(syncs)}"
    print(f"✓ Retrieved {len(syncs)} sync(s)")
    
    print("✅ Sync logging tests passed!\n")


def test_observation_logging(session_id):
    """Test observation logging."""
    print("🧪 Testing observation logging...")
    
    # Log observation
    obs_id = SessionManager.log_observation(
        session_id,
        object_name="Jupiter",
        ra_deg=12.456,
        dec_deg=-3.234,
        obs_type="imaging",
        duration_sec=300,
        exposure_sec=0.5,
        gain=100,
        binning="1x1",
        notes="Excellent seeing"
    )
    assert obs_id.startswith("obs_"), f"Invalid observation ID: {obs_id}"
    print(f"✓ Observation logged: {obs_id}")
    
    # Log more observations
    SessionManager.log_observation(
        session_id,
        object_name="Saturn",
        ra_deg=20.123,
        dec_deg=-18.567,
        obs_type="imaging",
        duration_sec=180,
        exposure_sec=1.0,
        gain=80,
        binning="2x2",
        notes="Good conditions"
    )
    print("✓ Multiple observations logged")
    
    # Get observations
    observations = SessionManager.get_session_observations(session_id)
    assert len(observations) == 2, f"Expected 2 observations, got {len(observations)}"
    print(f"✓ Retrieved {len(observations)} observations")
    
    # Check total duration
    total_duration = sum(o["duration_sec"] for o in observations)
    print(f"✓ Total observation time: {total_duration}s ({total_duration/60:.1f} min)")
    
    print("✅ Observation logging tests passed!\n")


def test_session_summary(session_id):
    """Test session summary."""
    print("🧪 Testing session summary...")
    
    summary = SessionManager.get_session_summary(session_id)
    
    assert summary["total_alignments"] == 3
    assert summary["total_syncs"] == 1
    assert summary["total_observations"] == 2
    
    print(f"✓ Alignments: {summary['total_alignments']}")
    print(f"✓ Syncs: {summary['total_syncs']}")
    print(f"✓ Observations: {summary['total_observations']}")
    print(f"✓ Observation duration: {summary['observation_duration_sec']}s")
    print(f"✓ Objects observed: {summary['objects_observed']}")
    
    print("✅ Session summary tests passed!\n")


def test_json_export(session_id):
    """Test JSON export."""
    print("🧪 Testing JSON export...")
    
    export_data = SessionManager.export_session_json(session_id)
    
    assert "session" in export_data
    assert "alignments" in export_data
    assert "syncs" in export_data
    assert "observations" in export_data
    assert "summary" in export_data
    
    # Verify JSON serialization
    json_str = json.dumps(export_data, indent=2)
    assert len(json_str) > 0
    print(f"✓ JSON export: {len(json_str)} bytes")
    
    # Save export
    export_file = Path("test_session_export.json")
    with open(export_file, "w") as f:
        json.dump(export_data, f, indent=2)
    print(f"✓ Export saved to {export_file}")
    
    # Verify file
    assert export_file.exists()
    assert export_file.stat().st_size > 0
    print(f"✓ File verified: {export_file.stat().st_size} bytes")
    
    # Cleanup
    export_file.unlink()
    
    print("✅ JSON export tests passed!\n")


def test_sequence_integration():
    """Test sequence creation and integration."""
    print("🧪 Testing sequence integration...")
    
    # Create sequence
    seq = ObservingSequence(
        name="Test Imaging Sequence",
        description="Test sequence for integration",
        target="M31"
    )
    assert seq.name == "Test Imaging Sequence"
    print(f"✓ Sequence created: {seq.id}")
    
    # Add steps
    step1 = SequenceStep(
        StepType.GOTO,
        {"ra_deg": 10.6847, "dec_deg": 41.2688},
        name="Slew to M31"
    )
    seq.add_step(step1)
    print(f"✓ Step added: {step1.name}")
    
    step2 = SequenceStep(
        StepType.IMAGE,
        {"count": 10, "exposure": 2.0, "binning": "1x1"},
        name="Capture 10 images"
    )
    seq.add_step(step2)
    print(f"✓ Step added: {step2.name}")
    
    # Serialize
    seq_dict = seq.to_dict()
    assert len(seq_dict["steps"]) == 2
    print(f"✓ Sequence serialized: {len(seq_dict['steps'])} steps")
    
    # Verify JSON
    json_str = json.dumps(seq_dict, indent=2)
    assert len(json_str) > 0
    print(f"✓ JSON serialization: {len(json_str)} bytes")
    
    print("✅ Sequence integration tests passed!\n")


def test_database_integrity():
    """Test database file integrity."""
    print("🧪 Testing database integrity...")
    
    db_path = Path("data/sessions.db")
    assert db_path.exists(), "Database file not found"
    print(f"✓ Database exists: {db_path}")
    
    size_mb = db_path.stat().st_size / (1024 * 1024)
    print(f"✓ Database size: {size_mb:.2f} MB")
    
    # Verify we can list sessions
    sessions = SessionManager.list_sessions()
    print(f"✓ Total sessions in DB: {len(sessions)}")
    
    print("✅ Database integrity tests passed!\n")


if __name__ == "__main__":
    print("=" * 60)
    print("Sequence Automation & Session Management Test Suite")
    print("=" * 60)
    print()
    
    try:
        # Run tests
        session_id = test_session_creation()
        test_alignment_logging(session_id)
        test_sync_logging(session_id)
        test_observation_logging(session_id)
        test_session_summary(session_id)
        test_json_export(session_id)
        test_sequence_integration()
        test_database_integrity()
        
        print("=" * 60)
        print("🎉 All tests passed!")
        print("=" * 60)
        print("\n💡 Next steps:")
        print("   1. Start server: python -m uvicorn server.app:app --reload")
        print("   2. Open: http://127.0.0.1:8000/ui/sequence.html")
        print("   3. Create and execute sequences!")
        
    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
