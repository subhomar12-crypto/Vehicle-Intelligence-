"""
Nisscom Device Helper
Central tool for working with your Nisscom diagnostic device
"""

import os
import subprocess
import sys

class NisscomHelper:
    """Helper menu for Nisscom device"""

    def __init__(self):
        self.base_path = r"C:\D Drive\Predict"

    def clear_screen(self):
        """Clear console"""
        os.system('cls' if os.name == 'nt' else 'clear')

    def print_header(self):
        """Print header"""
        print("=" * 70)
        print("NISSCOM DIAGNOSTIC DEVICE HELPER")
        print("Nissan Patrol 2003 - COM5")
        print("=" * 70)
        print()

    def print_status(self):
        """Print current status"""
        print("DEVICE STATUS:")
        print("  Port:    COM5 (USB Serial Port)")
        print("  Vehicle: Nissan Patrol 2003")
        print("  Status:  Device requires Nisscom proprietary software")
        print()
        print("IMPORTANT: Device does NOT work with open-source protocols")
        print()

    def show_menu(self):
        """Show main menu"""
        print("WHAT WOULD YOU LIKE TO DO?")
        print()
        print("  [1] Read Analysis Report")
        print("      - See detailed test results")
        print("      - Understand what was tested")
        print("      - Get recommendations")
        print()
        print("  [2] Run Protocol Sniffer (when you have Nisscom software)")
        print("      - Capture communication between software and device")
        print("      - Save protocol logs for analysis")
        print("      - Enable custom implementation")
        print()
        print("  [3] Re-test Device (run all tests again)")
        print("      - Test basic connectivity")
        print("      - Try alternative protocols")
        print("      - Check hardware settings")
        print()
        print("  [4] View Test Scripts")
        print("      - List all available test scripts")
        print("      - See what each script does")
        print()
        print("  [5] Check Sniffer Logs")
        print("      - View captured protocol data")
        print("      - Check if sniffer captured anything")
        print()
        print("  [0] Exit")
        print()

    def option_1_analysis(self):
        """Show analysis report"""
        self.clear_screen()
        self.print_header()

        analysis_file = os.path.join(self.base_path, "NISSCOM_DEVICE_ANALYSIS.md")

        if os.path.exists(analysis_file):
            print("Opening analysis report...")
            print(f"File: {analysis_file}")
            print()

            # Try to open with default application
            try:
                os.startfile(analysis_file)
                print("[OK] Report opened in default viewer")
            except:
                print("[INFO] Could not auto-open file")

            print()
            print("SUMMARY:")
            print("  - Device tested with 9 different protocols")
            print("  - All open-source protocols failed")
            print("  - Device echoes commands but doesn't process them")
            print("  - Requires Nisscom proprietary software")
            print()
            print("NEXT STEPS:")
            print("  1. Contact Nisscom/vendor for official software")
            print("  2. Use protocol sniffer (option 2) when software available")
            print("  3. We can create custom implementation from captured logs")
        else:
            print("[ERROR] Analysis file not found!")

        print()
        input("Press Enter to return to menu...")

    def option_2_sniffer(self):
        """Run protocol sniffer"""
        self.clear_screen()
        self.print_header()

        print("PROTOCOL SNIFFER")
        print()
        print("This tool captures communication between Nisscom software and device")
        print()
        print("INSTRUCTIONS:")
        print("  1. This sniffer will start monitoring COM5")
        print("  2. After it starts, open Nisscom software")
        print("  3. Connect to vehicle in Nisscom software")
        print("  4. Read some sensor data")
        print("  5. Come back here and press Ctrl+C to stop")
        print()
        print("Logs will be saved to:")
        print(f"  {os.path.join(self.base_path, 'nisscom_logs')}")
        print()

        choice = input("Ready to start sniffer? (y/n): ")

        if choice.lower() == 'y':
            print()
            print("[STARTING] Launching protocol sniffer...")
            print()

            sniffer_script = os.path.join(self.base_path, "nisscom_protocol_sniffer.py")

            try:
                subprocess.run([sys.executable, sniffer_script])
            except KeyboardInterrupt:
                print("\n[STOPPED] Sniffer stopped")
            except Exception as e:
                print(f"[ERROR] {e}")

        print()
        input("Press Enter to return to menu...")

    def option_3_retest(self):
        """Re-run all tests"""
        self.clear_screen()
        self.print_header()

        print("RE-TEST DEVICE")
        print()
        print("This will run comprehensive tests to check if device responds")
        print()
        print("WARNING: Previous tests showed device only echoes commands")
        print("         This is expected behavior for Nisscom devices")
        print()

        choice = input("Continue with tests? (y/n): ")

        if choice.lower() == 'y':
            scripts = [
                ("Basic Serial Test", "test_nisscom_basic.py"),
                ("Alternative Protocols", "nissan_consult2_alternative.py"),
                ("Hardware Settings", "nisscom_hardware_test.py"),
            ]

            for name, script in scripts:
                print()
                print(f"{'='*70}")
                print(f"Running: {name}")
                print(f"{'='*70}")
                print()

                script_path = os.path.join(self.base_path, script)

                try:
                    subprocess.run([sys.executable, script_path])
                except Exception as e:
                    print(f"[ERROR] {e}")

                print()
                input("Press Enter to continue to next test...")

        print()
        input("Press Enter to return to menu...")

    def option_4_list_scripts(self):
        """List available scripts"""
        self.clear_screen()
        self.print_header()

        print("AVAILABLE TEST SCRIPTS")
        print()

        scripts = {
            "Basic Tests": [
                ("test_nisscom_device.py", "OBD-II/ELM327 compatibility test"),
                ("test_nisscom_basic.py", "Basic serial communication test"),
                ("test_elm327_mode.py", "ELM327 mode detection test"),
            ],
            "Consult-II Protocol Tests": [
                ("consult2_reader.py", "Consult-II reader at 38400 baud"),
                ("consult2_live_monitor.py", "Live monitoring with CSV logging"),
                ("consult2_calibrate.py", "Register scanner and calibration"),
                ("nissan_consult2_native.py", "Native Consult-II at 9600 baud"),
                ("nissan_consult2_alternative.py", "Alternative initialization methods"),
            ],
            "Hardware Tests": [
                ("nisscom_hardware_test.py", "Hardware flow control test"),
            ],
            "Advanced Tools": [
                ("nisscom_protocol_sniffer.py", "Protocol capture tool (use with software)"),
                ("nisscom_helper.py", "This helper menu"),
            ],
        }

        for category, script_list in scripts.items():
            print(f"{category}:")
            for script, description in script_list:
                print(f"  - {script:35} {description}")
            print()

        print("All scripts are located in:")
        print(f"  {self.base_path}")
        print()

        print("To run any script:")
        print(f'  cd "{self.base_path}"')
        print("  python <script_name>.py")

        print()
        input("Press Enter to return to menu...")

    def option_5_check_logs(self):
        """Check sniffer logs"""
        self.clear_screen()
        self.print_header()

        print("SNIFFER LOGS")
        print()

        log_dir = os.path.join(self.base_path, "nisscom_logs")

        if not os.path.exists(log_dir):
            print("[INFO] No logs directory found")
            print("      Run protocol sniffer first (option 2)")
        else:
            logs = [f for f in os.listdir(log_dir) if f.startswith("nisscom_capture_")]

            if not logs:
                print("[INFO] No log files found")
                print("      Run protocol sniffer with Nisscom software to capture data")
            else:
                print(f"Found {len(logs)} log files:")
                print()

                for log in sorted(logs, reverse=True):
                    log_path = os.path.join(log_dir, log)
                    size = os.path.getsize(log_path)
                    print(f"  {log} ({size} bytes)")

                print()
                print(f"Location: {log_dir}")
                print()

                choice = input("Open logs folder? (y/n): ")
                if choice.lower() == 'y':
                    try:
                        os.startfile(log_dir)
                        print("[OK] Folder opened")
                    except:
                        print("[ERROR] Could not open folder")

        print()
        input("Press Enter to return to menu...")

    def run(self):
        """Run helper"""
        while True:
            self.clear_screen()
            self.print_header()
            self.print_status()
            self.show_menu()

            choice = input("Select option [0-5]: ").strip()

            if choice == '0':
                print("\nExiting...")
                break
            elif choice == '1':
                self.option_1_analysis()
            elif choice == '2':
                self.option_2_sniffer()
            elif choice == '3':
                self.option_3_retest()
            elif choice == '4':
                self.option_4_list_scripts()
            elif choice == '5':
                self.option_5_check_logs()
            else:
                print("\n[ERROR] Invalid option. Try again.")
                input("Press Enter to continue...")


def main():
    helper = NisscomHelper()

    try:
        helper.run()
    except KeyboardInterrupt:
        print("\n\n[STOPPED] Exiting...")
    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
