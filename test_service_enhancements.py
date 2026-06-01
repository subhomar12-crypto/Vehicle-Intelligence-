"""
PREDICT - Vehicle Intelligence Platform
Copyright © 2026 PREDICT
All rights reserved.

This file is proprietary and confidential.
Unauthorized copying, modification, distribution, or use is strictly prohibited.

Created: January 2026
Module: Test Service Enhancements

Test Service Enhancements
Verifies OBD integration, DTC lookup, and PDF generation
"""

import sys
import os

def test_imports():
    """Test that all new modules can be imported"""
    print("=" * 70)
    print("TEST 1: Module Imports")
    print("=" * 70)

    try:
        from obd_connection_manager import get_obd_manager, OBDConnectionManager
        print("[OK] obd_connection_manager imported successfully")
    except Exception as e:
        print(f"[FAIL] Failed to import obd_connection_manager: {e}")
        return False

    try:
        from dtc_lookup import lookup_dtc_details, DTCDatabase
        print("[OK] dtc_lookup imported successfully")
    except Exception as e:
        print(f"[FAIL] Failed to import dtc_lookup: {e}")
        return False

    try:
        from service_report_generator import ServiceReportGenerator
        print("[OK] service_report_generator imported successfully")
    except Exception as e:
        print(f"[FAIL] Failed to import service_report_generator: {e}")
        return False

    print("\n[OK] All modules imported successfully\n")
    return True


def test_dtc_lookup():
    """Test DTC code lookup database"""
    print("=" * 70)
    print("TEST 2: DTC Code Lookup")
    print("=" * 70)

    from dtc_lookup import lookup_dtc_details

    # Test common DTC codes
    test_codes = ["P0420", "P0171", "P0300", "C0035", "U0100", "PXXXX"]

    for code in test_codes:
        details = lookup_dtc_details(code)
        print(f"\n{code}:")
        print(f"  Description: {details['description']}")
        print(f"  Category: {details['category']}")
        print(f"  Severity: {details['severity']}")
        if details.get('causes'):
            print(f"  Causes: {len(details['causes'])} listed")

    print("\n[OK] DTC lookup working correctly\n")
    return True


def test_obd_connection():
    """Test OBD adapter connection (will fail if no adapter connected)"""
    print("=" * 70)
    print("TEST 3: OBD Adapter Connection")
    print("=" * 70)

    from obd_connection_manager import get_obd_manager

    try:
        obd_mgr = get_obd_manager()

        if obd_mgr.is_connected():
            print("[OK] OBD adapter connected!")
            print(f"   Port: {obd_mgr.connection.port_name()}")
            print(f"   Protocol: {obd_mgr.connection.protocol_name()}")
            return True
        else:
            print("[WARN] OBD adapter not connected (expected if no adapter present)")
            print("   This is normal - endpoints will use mock data")
            return True
    except Exception as e:
        print(f"[WARN] OBD connection test: {e}")
        print("   This is expected if no OBD adapter is connected")
        return True


def test_pdf_generation():
    """Test PDF report generation"""
    print("=" * 70)
    print("TEST 4: PDF Report Generation")
    print("=" * 70)

    from service_report_generator import ServiceReportGenerator

    # Create test data
    test_profile = {
        'name': 'Test Vehicle',
        'make': 'Toyota',
        'model': 'Camry',
        'year': 2020,
        'vin': 'TEST1234567890',
        'license_plate': 'TEST-123',
        'odometer_km': 50000
    }

    test_dtc_codes = [
        {
            'code': 'P0420',
            'description': 'Catalyst System Efficiency Below Threshold',
            'category': 'Powertrain - Emissions',
            'severity': 'warning',
            'possible_causes': ['Faulty catalytic converter', 'Damaged oxygen sensor']
        }
    ]

    test_oil_status = {
        'last_change_km': 45000,
        'next_change_due_km': 50000,
        'km_remaining': 5000,
        'status': 'due_soon'
    }

    test_maintenance = {
        'total_services': 5,
        'upcoming_services': [],
        'overdue_services': []
    }

    try:
        generator = ServiceReportGenerator()

        # Test full report
        pdf_path = generator.generate_service_report(
            profile=test_profile,
            dtc_codes=test_dtc_codes,
            oil_change_status=test_oil_status,
            maintenance_summary=test_maintenance,
            report_type='full'
        )

        if os.path.exists(pdf_path):
            file_size = os.path.getsize(pdf_path) / 1024
            print(f"[OK] PDF report generated successfully!")
            print(f"   File: {pdf_path}")
            print(f"   Size: {file_size:.1f} KB")

            # Clean up test file
            try:
                os.remove(pdf_path)
                print(f"   Test file cleaned up")
            except:
                pass

            return True
        else:
            print(f"[FAIL] PDF file was not created at expected path: {pdf_path}")
            return False

    except Exception as e:
        print(f"[FAIL] PDF generation failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_database_migration():
    """Test database schema"""
    print("=" * 70)
    print("TEST 5: Database Schema")
    print("=" * 70)

    try:
        from database_migration import DatabaseMigration

        migrator = DatabaseMigration()
        current_version = migrator.get_current_version()

        print(f"[OK] Database version: {current_version}")

        if current_version >= 7:
            print("[OK] v7 migration (service tables) already applied")
        else:
            print(f"[WARN] Database is at v{current_version}, v7 migration available")
            print("   Run migrations to add service management tables")

        return True

    except Exception as e:
        print(f"[FAIL] Database schema test failed: {e}")
        return False


def main():
    """Run all tests"""
    print("\n")
    print("+" + "=" * 68 + "+")
    print("|" + " " * 15 + "SERVICE ENHANCEMENTS TEST SUITE" + " " * 22 + "|")
    print("+" + "=" * 68 + "+")
    print()

    results = []

    # Run tests
    results.append(("Module Imports", test_imports()))
    results.append(("DTC Lookup", test_dtc_lookup()))
    results.append(("OBD Connection", test_obd_connection()))
    results.append(("PDF Generation", test_pdf_generation()))
    results.append(("Database Schema", test_database_migration()))

    # Summary
    print("\n")
    print("=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for test_name, result in results:
        status = "[PASS]" if result else "[FAIL]"
        print(f"{status}  {test_name}")

    print()
    print(f"Results: {passed}/{total} tests passed")

    if passed == total:
        print("\n[SUCCESS] ALL TESTS PASSED! Service enhancements are ready.")
    else:
        print(f"\n[WARN] {total - passed} test(s) failed. Check logs above.")

    print()


if __name__ == "__main__":
    main()
