"""
Install PREDICT as a Windows service using NSSM.

NSSM (Non-Sucking Service Manager) is required:
    https://nssm.cc/download

Usage:
    python scripts/install_service.py install
    python scripts/install_service.py remove
    python scripts/install_service.py start
    python scripts/install_service.py stop
    python scripts/install_service.py status

Requirements:
- Windows OS
- NSSM in PATH or specify --nssm-path
- Administrator privileges (for install/remove)
"""

import argparse
import logging
import os
import shutil
import subprocess
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

# Service configuration
SERVICE_NAME = "PredictServer"
SERVICE_DISPLAY_NAME = "PREDICT Vehicle Intelligence Server"
SERVICE_DESCRIPTION = "AI-powered vehicle diagnostics and predictive maintenance server"


def find_nssm() -> Path:
    """Find NSSM executable in PATH."""
    nssm_path = shutil.which("nssm")
    if nssm_path:
        return Path(nssm_path)
    
    # Common locations
    common_paths = [
        Path("C:/Program Files/nssm/nssm.exe"),
        Path("C:/Program Files (x86)/nssm/nssm.exe"),
        Path("C:/nssm/nssm.exe"),
        Path("C:/Windows/System32/nssm.exe"),
    ]
    
    for path in common_paths:
        if path.exists():
            return path
    
    return None


def install_service(nssm_path: Path, auto_start: bool = True):
    """Install the Windows service."""
    python_exe = sys.executable
    project_root = Path(__file__).parent.parent.resolve()
    
    # Service directories
    log_dir = project_root / "data" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    
    stdout_log = log_dir / "service_stdout.log"
    stderr_log = log_dir / "service_stderr.log"
    
    logger.info(f"Installing service '{SERVICE_NAME}'...")
    logger.info(f"  Python: {python_exe}")
    logger.info(f"  Working directory: {project_root}")
    logger.info(f"  Logs: {log_dir}")
    
    try:
        # Install service
        subprocess.run(
            [
                str(nssm_path), "install", SERVICE_NAME,
                python_exe,
                "-m", "predict", "--headless"
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        
        # Set working directory
        subprocess.run(
            [str(nssm_path), "set", SERVICE_NAME, "AppDirectory", str(project_root)],
            check=True,
            capture_output=True,
        )
        
        # Set display name
        subprocess.run(
            [str(nssm_path), "set", SERVICE_NAME, "DisplayName", SERVICE_DISPLAY_NAME],
            check=True,
            capture_output=True,
        )
        
        # Set description
        subprocess.run(
            [str(nssm_path), "set", SERVICE_NAME, "Description", SERVICE_DESCRIPTION],
            check=True,
            capture_output=True,
        )
        
        # Set log files
        subprocess.run(
            [str(nssm_path), "set", SERVICE_NAME, "AppStdout", str(stdout_log)],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            [str(nssm_path), "set", SERVICE_NAME, "AppStderr", str(stderr_log)],
            check=True,
            capture_output=True,
        )
        
        # Set restart policy
        subprocess.run(
            [str(nssm_path), "set", SERVICE_NAME, "AppRestartDelay", "5000"],
            check=True,
            capture_output=True,
        )
        
        # Set startup type
        start_type = "SERVICE_AUTO_START" if auto_start else "SERVICE_DEMAND_START"
        subprocess.run(
            [str(nssm_path), "set", SERVICE_NAME, "Start", start_type],
            check=True,
            capture_output=True,
        )
        
        logger.info(f"✅ Service '{SERVICE_NAME}' installed successfully!")
        logger.info(f"   Startup type: {'Auto' if auto_start else 'Manual'}")
        logger.info(f"   To start: python scripts/install_service.py start")
        
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to install service: {e}")
        if e.stderr:
            logger.error(f"NSSM error: {e.stderr}")
        sys.exit(1)


def remove_service(nssm_path: Path):
    """Remove the Windows service."""
    logger.info(f"Removing service '{SERVICE_NAME}'...")
    
    try:
        # Stop first if running
        try:
            subprocess.run(
                [str(nssm_path), "stop", SERVICE_NAME],
                check=True,
                capture_output=True,
                timeout=10,
            )
        except subprocess.CalledProcessError:
            pass  # May not be running
        
        # Remove service
        subprocess.run(
            [str(nssm_path), "remove", SERVICE_NAME, "confirm"],
            check=True,
            capture_output=True,
            text=True,
        )
        
        logger.info(f"✅ Service '{SERVICE_NAME}' removed successfully!")
    
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to remove service: {e}")
        if e.stderr:
            logger.error(f"NSSM error: {e.stderr}")
        sys.exit(1)


def start_service(nssm_path: Path):
    """Start the Windows service."""
    logger.info(f"Starting service '{SERVICE_NAME}'...")
    
    try:
        subprocess.run(
            [str(nssm_path), "start", SERVICE_NAME],
            check=True,
            capture_output=True,
            text=True,
        )
        logger.info(f"✅ Service '{SERVICE_NAME}' started!")
    
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to start service: {e}")
        if e.stderr:
            logger.error(f"NSSM error: {e.stderr}")
        sys.exit(1)


def stop_service(nssm_path: Path):
    """Stop the Windows service."""
    logger.info(f"Stopping service '{SERVICE_NAME}'...")
    
    try:
        subprocess.run(
            [str(nssm_path), "stop", SERVICE_NAME],
            check=True,
            capture_output=True,
            text=True,
        )
        logger.info(f"✅ Service '{SERVICE_NAME}' stopped!")
    
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to stop service: {e}")
        if e.stderr:
            logger.error(f"NSSM error: {e.stderr}")
        sys.exit(1)


def restart_service(nssm_path: Path):
    """Restart the Windows service."""
    logger.info(f"Restarting service '{SERVICE_NAME}'...")
    stop_service(nssm_path)
    start_service(nssm_path)


def get_service_status(nssm_path: Path) -> str:
    """Get service status."""
    try:
        result = subprocess.run(
            [str(nssm_path), "status", SERVICE_NAME],
            check=True,
            capture_output=True,
            text=True,
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError:
        return "NOT_INSTALLED"


def show_status(nssm_path: Path):
    """Show service status."""
    status = get_service_status(nssm_path)
    
    print(f"\n{'='*60}")
    print(f"Service: {SERVICE_NAME}")
    print(f"Display: {SERVICE_DISPLAY_NAME}")
    print(f"Status:  {status}")
    print(f"{'='*60}")
    
    if status == "NOT_INSTALLED":
        print("\nService is not installed.")
        print(f"Install with: python scripts/install_service.py install")
    elif status == "SERVICE_RUNNING":
        print("\n✅ Service is running!")
    elif status == "SERVICE_STOPPED":
        print("\n⏹️  Service is stopped.")
        print(f"Start with: python scripts/install_service.py start")
    else:
        print(f"\nService status: {status}")


def edit_service(nssm_path: Path):
    """Open NSSM GUI to edit service parameters."""
    logger.info(f"Opening NSSM editor for '{SERVICE_NAME}'...")
    
    try:
        subprocess.run([str(nssm_path), "edit", SERVICE_NAME], check=True)
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to open editor: {e}")
        sys.exit(1)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Manage PREDICT Windows Service",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s install              # Install service (auto-start)
  %(prog)s install --manual     # Install service (manual start)
  %(prog)s start                # Start the service
  %(prog)s stop                 # Stop the service
  %(prog)s restart              # Restart the service
  %(prog)s status               # Check service status
  %(prog)s edit                 # Edit service parameters (GUI)
  %(prog)s remove               # Remove the service

Requirements:
  - NSSM (Non-Sucking Service Manager) must be installed
  - Administrator privileges required for install/remove
  - Download NSSM: https://nssm.cc/download
        """
    )
    
    parser.add_argument(
        "action",
        choices=["install", "remove", "start", "stop", "restart", "status", "edit"],
        help="Action to perform",
    )
    
    parser.add_argument(
        "--nssm-path",
        type=str,
        help="Path to nssm.exe (if not in PATH)",
    )
    
    parser.add_argument(
        "--manual",
        action="store_true",
        help="Install with manual startup (not auto-start)",
    )
    
    args = parser.parse_args()
    
    # Find NSSM
    if args.nssm_path:
        nssm_path = Path(args.nssm_path)
    else:
        nssm_path = find_nssm()
    
    if not nssm_path or not nssm_path.exists():
        logger.error("NSSM not found!")
        logger.error("Please download NSSM from https://nssm.cc/download")
        logger.error("and either:")
        logger.error("  1. Add it to your PATH, or")
        logger.error("  2. Specify --nssm-path C:/path/to/nssm.exe")
        sys.exit(1)
    
    logger.debug(f"Using NSSM: {nssm_path}")
    
    # Perform action
    if args.action == "install":
        install_service(nssm_path, auto_start=not args.manual)
    elif args.action == "remove":
        remove_service(nssm_path)
    elif args.action == "start":
        start_service(nssm_path)
    elif args.action == "stop":
        stop_service(nssm_path)
    elif args.action == "restart":
        restart_service(nssm_path)
    elif args.action == "status":
        show_status(nssm_path)
    elif args.action == "edit":
        edit_service(nssm_path)


if __name__ == "__main__":
    main()
