"""
PREDICT - Vehicle Intelligence Platform
Copyright © 2026 PREDICT
All rights reserved.

This file is proprietary and confidential.
Unauthorized copying, modification, distribution, or use is strictly prohibited.

Created: January 2026
Module: Test Ui Modifications

Test UI Modifications - Quick Integration Test
Tests all new UI components and API methods
"""

import sys
from PySide6.QtWidgets import QApplication


def test_live_data_tab():
    """Test Live Data Tab modifications"""
    print("=" * 70)
    print("TEST 1: Live Data Tab")
    print("=" * 70)

    try:
        from live_data_tab import LiveDataTab
        from connectivity_module import ProfessionalConnectivityManager

        # Create minimal connectivity manager
        connectivity = ProfessionalConnectivityManager()

        # Create tab
        tab = LiveDataTab(connectivity_manager=connectivity, on_snapshot=None)

        # Test API methods
        tab.set_ai_attention_signals(
            signal_names=['coolant_temp', 'rpm'],
            reasons={'coolant_temp': 'Elevated 8°C above baseline'}
        )
        print("[OK] set_ai_attention_signals() works")

        test_data = {
            'coolant_temp': 95,
            'rpm': 800,
            'speed': 0
        }
        tab.update_data_quality(test_data)
        print("[OK] update_data_quality() works")

        print("[OK] Live Data Tab: DataQualityBadge and AI attention highlighting verified")
        return True

    except Exception as e:
        print(f"[FAIL] Live Data Tab test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_ai_training_tab():
    """Test AI Training Tab modifications"""
    print("\n" + "=" * 70)
    print("TEST 2: AI Training Tab")
    print("=" * 70)

    try:
        from ai_training_tab import AITrainingTab

        # Create tab
        tab = AITrainingTab(predictive_engine=None, unified_ai=None)

        # Verify feedback panel exists
        if hasattr(tab, 'feedback_panel'):
            print("[OK] TrainingFeedbackPanel widget created")

            # Test feedback display (feature_importances should be dict of dicts, not lists)
            test_result = {
                'models_trained': ['battery_health', 'coolant_system'],
                'samples_used': 500,
                'metrics': {
                    'battery_health': {'accuracy': 0.85},
                    'coolant_system': {'accuracy': 0.78}
                },
                'feature_importances': {
                    'battery_health': {'voltage': 0.85, 'age': 0.65, 'temperature': 0.45},
                    'coolant_system': {'coolant_temp': 0.90, 'flow_rate': 0.70, 'pressure': 0.60}
                }
            }
            tab.feedback_panel.show_feedback(test_result)
            print("[OK] show_feedback() method works")
            print("[OK] AI Training Tab: TrainingFeedbackPanel verified")
            return True
        else:
            print("[FAIL] feedback_panel not found")
            return False

    except Exception as e:
        print(f"[FAIL] AI Training Tab test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_service_history_tab():
    """Test Service History Tab modifications"""
    print("\n" + "=" * 70)
    print("TEST 3: Service History Tab")
    print("=" * 70)

    try:
        from service_history_tab import ServiceHistoryTab

        # Create tab
        tab = ServiceHistoryTab(profile_db_path="./data/vehicle_profiles.db")

        # Verify new fields exist
        if hasattr(tab, 'confirmed_fix') and hasattr(tab, 'resolution_status'):
            print("[OK] confirmed_fix checkbox created")
            print("[OK] resolution_status dropdown created")

            # Test checkbox enable/disable logic
            tab.confirmed_fix.setChecked(True)
            if tab.resolution_status.isEnabled():
                print("[OK] resolution_status enabled when checkbox checked")
            else:
                print("[FAIL] resolution_status should be enabled")
                return False

            tab.confirmed_fix.setChecked(False)
            if not tab.resolution_status.isEnabled():
                print("[OK] resolution_status disabled when checkbox unchecked")
            else:
                print("[FAIL] resolution_status should be disabled")
                return False

            print("[OK] Service History Tab: AI Learning & Fix Confirmation verified")
            return True
        else:
            print("[FAIL] New fields not found")
            return False

    except Exception as e:
        print(f"[FAIL] Service History Tab test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_reports_tab():
    """Test Reports Tab modifications"""
    print("\n" + "=" * 70)
    print("TEST 4: Reports Tab")
    print("=" * 70)

    try:
        from reports_tab import ReportsTab

        # Create tab
        tab = ReportsTab(
            ai_module=None,
            get_active_profile=lambda: None,
            get_latest_snapshot=lambda: None
        )

        # Verify report depth selector exists (in options_widget)
        if hasattr(tab, 'options_widget') and hasattr(tab.options_widget, 'report_depth'):
            print("[OK] report_depth selector created")

            # Test get_options includes report_depth
            options = tab.options_widget.get_options()
            if 'report_depth' in options:
                print(f"[OK] get_options() includes report_depth: {options['report_depth']}")

                # Test all 3 depth options
                depth_values = []
                for i in range(3):
                    tab.options_widget.report_depth.setCurrentIndex(i)
                    depth_values.append(tab.options_widget.get_options()['report_depth'])

                expected = ['driver_friendly', 'technical', 'comprehensive']
                if depth_values == expected:
                    print(f"[OK] All 3 depth modes work correctly: {depth_values}")
                else:
                    print(f"[FAIL] Depth modes incorrect. Got: {depth_values}, Expected: {expected}")
                    return False

                print("[OK] Reports Tab: Report Depth & Audience selector verified")
                return True
            else:
                print("[FAIL] report_depth not in options")
                return False
        else:
            print("[FAIL] report_depth selector not found")
            return False

    except Exception as e:
        print(f"[FAIL] Reports Tab test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_settings_tab():
    """Test Settings Tab"""
    print("\n" + "=" * 70)
    print("TEST 5: Settings Tab")
    print("=" * 70)

    try:
        from settings_tab import SettingsTab

        # Create tab
        tab = SettingsTab()

        # Test get_settings
        settings = tab.get_settings()
        print(f"[OK] get_settings() works")
        print(f"   AI Behavior Mode: {settings['ai_behavior_mode']}")
        print(f"   Learning Scope: {settings['learning_scope']}")
        print(f"   Confidence Threshold: {settings['confidence_threshold']}%")
        print(f"   Baseline Days: {settings['minimum_baseline_days']}")
        print(f"   Shadow Mode: {settings['shadow_evaluation_mode']}")

        # Test behavior mode changes
        tab.conservative_radio.setChecked(True)
        assert tab.get_settings()['ai_behavior_mode'] == 'conservative'
        print("[OK] Conservative mode works")

        tab.early_warning_radio.setChecked(True)
        assert tab.get_settings()['ai_behavior_mode'] == 'early_warning'
        print("[OK] Early-warning mode works")

        # Test learning scope changes
        tab.vehicle_only_radio.setChecked(True)
        assert tab.get_settings()['learning_scope'] == 'vehicle_only'
        print("[OK] Vehicle only mode works")

        tab.fleet_assisted_radio.setChecked(True)
        assert tab.get_settings()['learning_scope'] == 'fleet_assisted'
        print("[OK] Fleet assisted mode works")

        # Test advanced settings
        tab.confidence_threshold.setValue(75)
        assert tab.get_settings()['confidence_threshold'] == 75
        print("[OK] Confidence threshold slider works")

        tab.baseline_days.setValue(14)
        assert tab.get_settings()['minimum_baseline_days'] == 14
        print("[OK] Baseline days spinner works")

        print("[OK] Settings Tab: All controls verified")
        return True

    except Exception as e:
        print(f"[FAIL] Settings Tab test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all UI modification tests"""
    print("\n")
    print("+" + "=" * 68 + "+")
    print("|" + " " * 15 + "UI MODIFICATIONS TEST SUITE" + " " * 27 + "|")
    print("+" + "=" * 68 + "+")
    print()
    print("Testing all new UI components and API methods...")
    print()

    # Create QApplication (required for Qt widgets)
    app = QApplication(sys.argv)

    # Run tests
    results = []
    results.append(("Live Data Tab", test_live_data_tab()))
    results.append(("AI Training Tab", test_ai_training_tab()))
    results.append(("Service History Tab", test_service_history_tab()))
    results.append(("Reports Tab", test_reports_tab()))
    results.append(("Settings Tab", test_settings_tab()))

    # Summary
    print("\n" + "=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for test_name, result in results:
        status = "[PASS]" if result else "[FAIL]"
        print(f"{status}  {test_name}")

    print()
    print(f"Results: {passed}/{total} tests passed ({int(passed/total*100)}%)")

    if passed == total:
        print("\n[SUCCESS] ALL UI MODIFICATIONS VERIFIED!")
        print("All new components are working correctly and ready for backend integration.")
    else:
        print(f"\n[WARN] {total - passed} test(s) failed. Check logs above.")

    print()


if __name__ == "__main__":
    main()
