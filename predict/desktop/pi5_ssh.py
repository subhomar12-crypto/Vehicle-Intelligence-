"""SSH helper for Pi5 edge unit communication."""
import base64
import logging
import os
import secrets
from typing import Optional

logger = logging.getLogger(__name__)

try:
    import paramiko
    _has_paramiko = True
except ImportError:
    _has_paramiko = False

# Service name on Pi5
_SERVICE_NAME = "predict.service"

# All files that make up the Pi5 PREDICT software
_PI5_SOFTWARE_FILES = [
    "main.py",
    "ble_service.py",
    "consult2.py",
    "consult2_dtc.py",
    "database.py",
    "command_handler.py",
    "dtc_command_handler.py",
    "http_api.py",
    "odometer.py",
    "system_monitor.py",
    "time_sync.py",
    "wifi_manager.py",
    "autonomous_uploader.py",
    "bt_agent.py",
]

# Systemd unit file content
_PREDICT_SERVICE_UNIT = """\
[Unit]
Description=PREDICT Pi5 Consult-II OBD Service
After=multi-user.target

[Service]
Type=simple
ExecStart=/usr/bin/python3 /opt/predict/main.py
Restart=always
RestartSec=5
User=root
WorkingDirectory=/opt/predict
Environment=PYTHONUNBUFFERED=1
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
"""


class Pi5SSH:
    """SSH client for PREDICT Pi5 edge unit management."""

    # File paths on Pi5
    SECRET_KEY_FILE = "/boot/firmware/predict_ble_key.txt"
    SESSIONS_FILE = "/boot/firmware/predict_sessions.json"
    PHONE_MAC_FILE = "/boot/firmware/predict_phone.txt"
    PREDICT_DIR = "/opt/predict"

    def __init__(self, host: str = "192.168.5.1", username: str = "predict",
                 password: str = "12345678", port: int = 22):
        self._host = host
        self._username = username
        self._password = password
        self._port = port
        self._client: Optional["paramiko.SSHClient"] = None

    def connect(self) -> bool:
        """Connect to Pi5 via SSH."""
        if not _has_paramiko:
            logger.error("paramiko not installed")
            return False
        try:
            self._client = paramiko.SSHClient()
            self._client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            self._client.connect(self._host, port=self._port,
                                 username=self._username, password=self._password, timeout=5)
            return True
        except Exception as e:
            logger.error("SSH connect failed: %s", e)
            self._client = None
            return False

    def disconnect(self):
        if self._client:
            self._client.close()
            self._client = None

    def test_connection(self) -> dict:
        """Test SSH connection, return Pi5 info."""
        try:
            uptime = self._exec("uptime -p")
            hostname = self._exec("hostname")
            ble_active = "active" in self._exec(
                f"systemctl is-active {_SERVICE_NAME} 2>/dev/null || echo inactive"
            )
            fw = self._exec("grep -oP 'FW_VERSION\\s*=\\s*\"\\K[^\"]+' /opt/predict/main.py 2>/dev/null || echo unknown")
            return {
                "connected": True, "uptime": uptime,
                "hostname": hostname, "ble_active": ble_active,
                "firmware": fw,
            }
        except Exception as e:
            return {"connected": False, "error": str(e)}

    def read_ble_mac(self) -> Optional[str]:
        """Read Pi5 BLE MAC address."""
        try:
            output = self._exec("hciconfig hci0 | grep 'BD Address' | awk '{print $3}'")
            mac = output.strip()
            if ":" in mac and len(mac) == 17:
                return mac
            return None
        except Exception:
            return None

    def write_secret_key(self, key: str):
        """Write BLE secret key to Pi5."""
        self._exec(
            f"echo -n '{key}' > /tmp/predict_key_tmp && "
            f"sudo mv /tmp/predict_key_tmp {self.SECRET_KEY_FILE}"
        )

    def generate_and_write_key(self) -> str:
        """Generate new 32-char hex key and write to Pi5."""
        key = secrets.token_hex(16)
        self.write_secret_key(key)
        return key

    def read_whitelist(self) -> list:
        """Read whitelisted phone MACs."""
        try:
            output = self._exec(f"cat {self.PHONE_MAC_FILE} 2>/dev/null || echo ''")
            return [m.strip() for m in output.strip().split("\n") if m.strip() and ":" in m]
        except Exception:
            return []

    def clear_whitelist(self):
        """Clear all whitelisted phones."""
        self._exec(f"sudo truncate -s 0 {self.PHONE_MAC_FILE}")

    def clear_sessions(self):
        """Delete all session tokens."""
        self._exec(f"sudo rm -f {self.SESSIONS_FILE}")

    def restart_ble_service(self):
        """Restart the predict service (includes BLE)."""
        self._exec(f"sudo systemctl restart {_SERVICE_NAME}")

    def get_device_status(self) -> dict:
        """Get Pi5 device status."""
        try:
            cpu_temp = float(self._exec("cat /sys/class/thermal/thermal_zone0/temp")) / 1000
            ram = self._exec("free -m | awk '/Mem:/ {print $2, $3}'").split()
            ram_total = int(ram[0]) if len(ram) >= 2 else 0
            ram_used = int(ram[1]) if len(ram) >= 2 else 0
            disk = self._exec("df -BG /boot/firmware | tail -1 | awk '{print $2, $4}'").split()
            uptime = self._exec("uptime -p").strip()
            ble_status = self._exec(
                f"systemctl is-active {_SERVICE_NAME} 2>/dev/null || echo inactive"
            ).strip()

            # Count sessions and whitelist entries
            session_count = 0
            try:
                sc = self._exec(
                    f"python3 -c \"import json; print(len(json.load(open('{self.SESSIONS_FILE}'))))\" "
                    f"2>/dev/null || echo 0"
                )
                session_count = int(sc.strip())
            except Exception:
                pass

            whitelist = self.read_whitelist()

            # Check installed files
            installed = self._exec("ls /opt/predict/*.py 2>/dev/null | wc -l").strip()

            return {
                "cpu_temp": cpu_temp,
                "ram_total_mb": ram_total,
                "ram_used_mb": ram_used,
                "sd_total_gb": disk[0].rstrip('G') if disk else "0",
                "sd_free_gb": disk[1].rstrip('G') if len(disk) > 1 else "0",
                "uptime": uptime,
                "ble_service": ble_status,
                "session_count": session_count,
                "whitelist_count": len(whitelist),
                "whitelist": whitelist,
                "installed_files": int(installed) if installed.isdigit() else 0,
            }
        except Exception as e:
            return {"error": str(e)}

    def reset_security(self) -> str:
        """Full security reset: new key + clear whitelist + clear sessions + restart."""
        new_key = self.generate_and_write_key()
        self.clear_whitelist()
        self.clear_sessions()
        self.restart_ble_service()
        return new_key

    # ------------------------------------------------------------------
    # Software deployment
    # ------------------------------------------------------------------

    def upload_file(self, local_path: str, remote_path: str, use_overlayroot: bool = True):
        """Upload a single file to Pi5 via base64-through-SSH.

        If overlayroot is active, uses overlayroot-chroot for persistent writes,
        plus a direct write for immediate use in the live overlay.
        """
        with open(local_path, "rb") as f:
            content = f.read()

        b64 = base64.b64encode(content).decode("ascii")

        # Write base64 to temp file in chunks (shell has line-length limits)
        chunk_size = 50000
        for i in range(0, len(b64), chunk_size):
            chunk = b64[i:i + chunk_size]
            op = ">" if i == 0 else ">>"
            self._exec(f"echo -n '{chunk}' {op} /tmp/_predict_upload.b64")

        if use_overlayroot:
            # Check if overlayroot is active
            overlay = self._exec("mount | grep overlayroot 2>/dev/null || true")
            if "overlayroot" in overlay:
                # Persistent write via chroot
                self._exec(
                    f"base64 -d /tmp/_predict_upload.b64 | "
                    f"sudo overlayroot-chroot tee {remote_path} > /dev/null"
                )
                # Also write to live overlay for immediate use
                self._exec(
                    f"base64 -d /tmp/_predict_upload.b64 | "
                    f"sudo tee {remote_path} > /dev/null"
                )
            else:
                self._exec(
                    f"base64 -d /tmp/_predict_upload.b64 | "
                    f"sudo tee {remote_path} > /dev/null"
                )
        else:
            self._exec(
                f"base64 -d /tmp/_predict_upload.b64 | "
                f"sudo tee {remote_path} > /dev/null"
            )

        # Cleanup
        self._exec("rm -f /tmp/_predict_upload.b64")
        logger.info("Uploaded %s → %s (%d bytes)", local_path, remote_path, len(content))

    def install_software(self, local_dir: str, progress_cb=None) -> dict:
        """Install all PREDICT software files to Pi5.

        Args:
            local_dir: Path to local directory containing Pi5 software files.
            progress_cb: Optional callback(file_name, current, total) for progress.

        Returns:
            dict with 'installed', 'skipped', 'errors' lists.
        """
        result = {"installed": [], "skipped": [], "errors": []}

        # Ensure target directory exists
        self._exec(f"sudo mkdir -p {self.PREDICT_DIR}")

        # Discover which files to upload
        files_to_upload = []
        for fname in _PI5_SOFTWARE_FILES:
            local_path = os.path.join(local_dir, fname)
            if os.path.isfile(local_path):
                files_to_upload.append((fname, local_path))
            else:
                result["skipped"].append(fname)

        # Also pick up any extra .py files in local_dir not in the standard list
        for fname in os.listdir(local_dir):
            if fname.endswith(".py") and fname not in [f[0] for f in files_to_upload] \
                    and fname not in result["skipped"]:
                local_path = os.path.join(local_dir, fname)
                if os.path.isfile(local_path):
                    files_to_upload.append((fname, local_path))

        total = len(files_to_upload)
        for idx, (fname, local_path) in enumerate(files_to_upload, 1):
            try:
                if progress_cb:
                    progress_cb(fname, idx, total)
                remote_path = f"{self.PREDICT_DIR}/{fname}"
                self.upload_file(local_path, remote_path)
                result["installed"].append(fname)
            except Exception as e:
                logger.error("Failed to upload %s: %s", fname, e)
                result["errors"].append(f"{fname}: {e}")

        return result

    def install_service(self) -> str:
        """Install and enable the predict systemd service unit."""
        b64 = base64.b64encode(_PREDICT_SERVICE_UNIT.encode()).decode("ascii")
        unit_path = f"/etc/systemd/system/{_SERVICE_NAME}"

        # Write unit file
        overlay = self._exec("mount | grep overlayroot 2>/dev/null || true")
        if "overlayroot" in overlay:
            self._exec(
                f"echo '{b64}' | base64 -d | "
                f"sudo overlayroot-chroot tee {unit_path} > /dev/null"
            )
            self._exec(f"echo '{b64}' | base64 -d | sudo tee {unit_path} > /dev/null")
        else:
            self._exec(f"echo '{b64}' | base64 -d | sudo tee {unit_path} > /dev/null")

        # Enable and start
        self._exec("sudo systemctl daemon-reload")
        self._exec(f"sudo systemctl enable {_SERVICE_NAME}")
        self._exec(f"sudo systemctl restart {_SERVICE_NAME}")

        # Disable old Classic BT services if they exist
        self._exec("sudo systemctl disable predict-bonds.service bt-discoverable.service 2>/dev/null || true")
        self._exec("sudo systemctl stop predict-bonds.service bt-discoverable.service 2>/dev/null || true")

        # Check status
        status = self._exec(f"systemctl is-active {_SERVICE_NAME} 2>/dev/null || echo failed")
        return status.strip()

    def get_installed_files(self) -> list:
        """List currently installed .py files on the Pi5."""
        try:
            output = self._exec(f"ls -1 {self.PREDICT_DIR}/*.py 2>/dev/null || true")
            if not output:
                return []
            return [os.path.basename(f) for f in output.split("\n") if f.strip()]
        except Exception:
            return []

    def _exec(self, cmd: str) -> str:
        """Execute command on Pi5 and return stdout."""
        if not self._client:
            raise RuntimeError("Not connected")
        _, stdout, stderr = self._client.exec_command(cmd, timeout=30)
        return stdout.read().decode().strip()
