#!/usr/bin/env python3
"""
Test script for set-specific sorting functionality

This script tests the set sorting system without requiring full hardware.
Run with: python robot/test_set_sorting.py
"""

import os
import sys


def test_imports():
    """Test that all required modules can be imported"""
    print("✓ Testing imports...")
    try:
        from robot.set_manager import SetManager
        from robot.external.rebrickable import RebrickableClient
        from robot.sorting.set_aware_sorting_profile import SetAwareSortingProfile
        from robot.sorting.set_aware_profile_factory import mkSetAwareSortingProfile
        print("  ✓ All imports successful")
        return True
    except ImportError as e:
        print(f"  ✗ Import failed: {e}")
        return False


def test_database_migration():
    """Test that database migration runs successfully"""
    print("\n✓ Testing database migration...")
    try:
        from robot.global_config import buildGlobalConfig
        from robot.storage.sqlite3.migrations import initializeDatabase

        # Build config (this will use test database if DB_PATH is set)
        gc = buildGlobalConfig()

        # Run migrations
        initializeDatabase(gc)

        # Check that set tables exist
        import sqlite3
        from robot.storage.sqlite3.migrations import getDatabaseConnection

        conn = getDatabaseConnection(gc)
        cursor = conn.cursor()

        # Check for our new tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]

        required_tables = ['lego_sets', 'set_inventories', 'active_sorting_sets', 'set_piece_observations']
        missing = [t for t in required_tables if t not in tables]

        conn.close()

        if missing:
            print(f"  ✗ Missing tables: {missing}")
            return False

        print(f"  ✓ All set tables exist: {required_tables}")
        return True

    except Exception as e:
        print(f"  ✗ Migration failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_rebrickable_api():
    """Test Rebrickable API connection"""
    print("\n✓ Testing Rebrickable API...")

    api_key = os.getenv("REBRICKABLE_API_KEY")
    if not api_key:
        print("  ⚠ REBRICKABLE_API_KEY not set - skipping API test")
        print("  Set it with: export REBRICKABLE_API_KEY='your_key'")
        return True  # Not a failure, just skipped

    try:
        from robot.external.rebrickable import RebrickableClient

        client = RebrickableClient(api_key)

        # Try a simple search
        results = client.search_sets("21318", page_size=5)  # LEGO Ideas Tree House

        if results and len(results.get('results', [])) > 0:
            set_data = results['results'][0]
            print(f"  ✓ API connection successful")
            print(f"    Found set: {set_data.get('name', 'Unknown')}")
            return True
        else:
            print("  ✗ API returned no results")
            return False

    except Exception as e:
        print(f"  ✗ API test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_set_manager():
    """Test SetManager basic operations"""
    print("\n✓ Testing SetManager...")

    api_key = os.getenv("REBRICKABLE_API_KEY")
    if not api_key:
        print("  ⚠ REBRICKABLE_API_KEY not set - skipping SetManager test")
        return True

    try:
        from robot.global_config import buildGlobalConfig
        from robot.set_manager import SetManager

        gc = buildGlobalConfig()
        set_mgr = SetManager(gc)

        # Test search
        print("  → Searching for sets...")
        results = set_mgr.search_sets("21318")
        if not results or len(results) == 0:
            print("  ✗ Search returned no results")
            return False
        print(f"    Found {len(results)} sets")

        # Test add set (use a small set for testing)
        print("  → Adding set to database...")
        set_num = "21318-1"  # LEGO Ideas Tree House (~3000 pieces)
        set_id = set_mgr.add_set(set_num)

        if not set_id:
            print("  ✗ Failed to add set")
            return False
        print(f"    Added set: {set_id}")

        # Test activate
        print("  → Activating set...")
        success = set_mgr.activate_set(set_id, priority=1)
        if not success:
            print("  ✗ Failed to activate set")
            return False
        print(f"    Activated set with priority 1")

        # Test get active sets
        print("  → Getting active sets...")
        active = set_mgr.get_active_sets()
        if len(active) == 0:
            print("  ✗ No active sets found")
            return False
        print(f"    Found {len(active)} active set(s)")
        print(f"    Set: {active[0]['name']}")
        print(f"    Parts needed: {active[0]['total_parts_needed']}")

        # Test get progress
        print("  → Getting set progress...")
        progress = set_mgr.get_set_progress(set_id)
        if not progress:
            print("  ✗ Failed to get progress")
            return False
        print(f"    Progress: {progress['completion_percentage']:.1f}%")
        print(f"    Parts: {progress['total_parts_found']}/{progress['total_parts_needed']}")

        # Test check piece in sets
        print("  → Testing piece lookup...")
        # Just test with a common piece ID
        matches = set_mgr.check_piece_in_sets("3001")  # 2x4 brick
        print(f"    Piece '3001' matches {len(matches)} active set(s)")

        # Test deactivate
        print("  → Deactivating set...")
        success = set_mgr.deactivate_set(set_id)
        if not success:
            print("  ✗ Failed to deactivate set")
            return False
        print(f"    Deactivated set")

        print("  ✓ All SetManager tests passed")
        return True

    except Exception as e:
        print(f"  ✗ SetManager test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_sorting_profile():
    """Test set-aware sorting profile"""
    print("\n✓ Testing SetAwareSortingProfile...")

    try:
        from robot.global_config import buildGlobalConfig
        from robot.sorting.set_aware_profile_factory import mkSetAwareSortingProfile

        gc = buildGlobalConfig()

        # Create set-aware profile
        profile = mkSetAwareSortingProfile(gc)

        print(f"  ✓ Created profile: {profile.profile_name}")

        # Test that it has the base category mappings
        if len(profile.item_id_to_category_id_mapping) == 0:
            print("  ⚠ Warning: No category mappings loaded (database may be empty)")
        else:
            print(f"    Loaded {len(profile.item_id_to_category_id_mapping)} piece mappings")

        # Test get_destination with no active sets (should return category)
        category_id, set_dest = profile.get_destination("3001")
        if category_id or set_dest:
            if category_id:
                print(f"    Test piece '3001' → category: {category_id}")
            if set_dest:
                print(f"    Test piece '3001' → set: {set_dest.set_id}")
        else:
            print("    Test piece '3001' not found (database may be empty)")

        print("  ✓ Sorting profile tests passed")
        return True

    except Exception as e:
        print(f"  ✗ Sorting profile test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_api_endpoints():
    """Test that API endpoints are defined"""
    print("\n✓ Testing API endpoints...")

    try:
        from robot.api.server import app

        # Get all routes
        routes = [route.path for route in app.routes]

        # Check for set endpoints
        required_endpoints = [
            '/sets/search',
            '/sets/add',
            '/sets/activate',
            '/sets/active',
        ]

        missing = [e for e in required_endpoints if e not in routes]

        if missing:
            print(f"  ✗ Missing endpoints: {missing}")
            return False

        print(f"  ✓ All {len(required_endpoints)} set endpoints defined")
        return True

    except Exception as e:
        print(f"  ✗ API endpoint test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests"""
    print("=" * 60)
    print("LEGO Sorter - Set-Specific Sorting Tests")
    print("=" * 60)

    tests = [
        ("Imports", test_imports),
        ("Database Migration", test_database_migration),
        ("Rebrickable API", test_rebrickable_api),
        ("SetManager", test_set_manager),
        ("Sorting Profile", test_sorting_profile),
        ("API Endpoints", test_api_endpoints),
    ]

    results = []
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result))
        except Exception as e:
            print(f"\n✗ Test '{name}' crashed: {e}")
            import traceback
            traceback.print_exc()
            results.append((name, False))

    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status:8} {name}")

    print("-" * 60)
    print(f"Result: {passed}/{total} tests passed")

    if passed == total:
        print("\n✓ All tests passed! Set-specific sorting is ready.")
        print("\nNext steps:")
        print("1. Set REBRICKABLE_API_KEY environment variable")
        print("2. Run: make run --enable-set-sorting")
        print("3. Use API endpoints to add and activate sets")
        return 0
    else:
        print("\n✗ Some tests failed. Check errors above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
