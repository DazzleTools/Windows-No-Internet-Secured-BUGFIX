#!/usr/bin/env python3
"""
Windows System Configuration Utilities for NCSI Resolver

This module provides functions to configure Windows system settings required for
the NCSI Resolver to work properly, including registry edits and hosts file modifications.
"""

import ctypes
import datetime
import logging
import os
import platform
import re
import subprocess
import sys
import time
import winreg
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

try:
    from version import get_version_info
    
    # Get version information
    __version_info__ = get_version_info("system_config")
    __version__ = __version_info__["version"]
    __description__ = __version_info__["description"]
except ImportError:
    # Fallback version info if version.py is missing
    __version__ = "unknown"
    __description__ = "Windows System Configuration for NCSI Resolver"

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger('system_config')

# Constants
HOSTS_FILE_PATH = r"C:\Windows\System32\drivers\etc\hosts"
NCSI_REGISTRY_KEY = r"SYSTEM\CurrentControlSet\Services\NlaSvc\Parameters\Internet"
DEFAULT_NCSI_HOST = "www.msftconnecttest.com"
DEFAULT_NCSI_HOST_V6 = "ipv6.msftconnecttest.com"  # IPv6 active web probe host (differs from V4)
DEFAULT_NCSI_IP = "127.0.0.1"
# NCSI registry string values this tool may modify. Backed up and restored as a
# SET so the existing reset/uninstall path cleanly reverses both the IPv4 and the
# IPv6 redirect. (The full `reg export` in backup_registry_values is the
# belt-and-suspenders safety net; this list drives the per-value restore.)
NCSI_MANAGED_VALUES = (
    "ActiveWebProbeHost",
    "ActiveWebProbePath",
    "ActiveWebProbeHostV6",
    "ActiveWebProbePathV6",
)
TIMEOUT = 10  # seconds
BACKUP_DIR = os.path.join(os.environ.get('LOCALAPPDATA', os.path.expanduser('~')), "NCSI_Resolver", "Backups")

def create_timestamp():
    """Create a timestamp string for backup files."""
    return datetime.datetime.now().strftime("%Y%m%d-%H%M%S")

def is_admin() -> bool:
    """
    Check if the current process has administrative privileges.
    
    Returns:
        bool: True if running with admin privileges, False otherwise
    """
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False

def run_as_admin(script_path: str, *args) -> None:
    """
    Restart the current script with administrative privileges.
    
    Args:
        script_path: Path to the script to run
        *args: Additional arguments to pass
    """
    if not is_admin():
        logger.info("Requesting administrative privileges...")
        
        # Convert to a list for easier handling
        arg_list = list(args)
        
        # Prepare the arguments
        if script_path.endswith('.py'):
            # If it's a .py file, we need to call it with python
            cmd = [sys.executable, script_path] + arg_list
        else:
            # Otherwise assume it's executable
            cmd = [script_path] + arg_list
        
        try:
            # Request elevation via ShellExecute
            ctypes.windll.shell32.ShellExecuteW(
                None, "runas", cmd[0], ' '.join(f'"{arg}"' for arg in cmd[1:]), None, 1
            )
            sys.exit(0)
        except Exception as e:
            logger.error(f"Failed to get admin privileges: {e}")
            sys.exit(1)

def get_local_ip() -> Optional[str]:
    """
    Get the local IP address of the machine.
    
    Returns:
        str: The local IP address, or None if it can't be determined
    """
    try:
        import socket
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
        return local_ip
    except Exception as e:
        logger.error(f"Failed to get local IP: {e}")
        return None

def backup_registry_values() -> Dict[str, Dict[str, Tuple[int, Union[str, bytes]]]]:
    """
    Backup existing NCSI registry values before modification.
    
    Returns:
        Dict containing original registry values, empty if none existed
    """
    original_values = {}
    timestamp = create_timestamp()
    
    try:
        # Ensure backup directory exists
        os.makedirs(BACKUP_DIR, exist_ok=True)
        
        # Create a backup registry file path
        backup_file = os.path.join(BACKUP_DIR, f"ncsi_registry_backup_{timestamp}.reg")
        
        try:
            # Try to open the registry key
            reg_key = winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                NCSI_REGISTRY_KEY,
                0,
                winreg.KEY_READ
            )
            
            # Dictionary to store original values
            original_values[NCSI_REGISTRY_KEY] = {}

            # Check for existing values (V4 + V6 managed set)
            for value_name in NCSI_MANAGED_VALUES:
                try:
                    value, value_type = winreg.QueryValueEx(reg_key, value_name)
                    original_values[NCSI_REGISTRY_KEY][value_name] = (value_type, value)
                    logger.info(f"Backing up existing registry value: {value_name} = {value}")
                except FileNotFoundError:
                    logger.info(f"Registry value '{value_name}' did not exist before modification")

            # Close the key
            winreg.CloseKey(reg_key)
        
        except FileNotFoundError:
            logger.info(f"Registry key {NCSI_REGISTRY_KEY} not found, nothing to backup")
        
        # Export registry key to .reg file if we found any values
        if original_values and original_values[NCSI_REGISTRY_KEY]:
            try:
                # Use reg.exe to export the key
                subprocess.run(
                    [
                        "reg", "export", 
                        f"HKLM\\{NCSI_REGISTRY_KEY}", 
                        backup_file
                    ],
                    check=True,
                    capture_output=True,
                    timeout=TIMEOUT
                )
                logger.info(f"Registry backup saved to {backup_file}")
            except subprocess.CalledProcessError as e:
                logger.warning(f"Could not export registry key: {e.stderr.decode() if e.stderr else str(e)}")
        
        return original_values
    
    except Exception as e:
        logger.error(f"Error backing up registry values: {e}")
        return {}

def backup_hosts_file() -> str:
    """
    Create a timestamped backup of the hosts file.
    
    Returns:
        str: Path to the backup file, or empty string if backup failed
    """
    hosts_path = Path(HOSTS_FILE_PATH)
    timestamp = create_timestamp()
    
    try:
        # Ensure backup directory exists
        os.makedirs(BACKUP_DIR, exist_ok=True)
        
        # Create backup filename
        backup_path = os.path.join(BACKUP_DIR, f"hosts.original.{timestamp}.bak")
        
        # Check if we already have a hosts file entry for the NCSI host
        has_ncsi_entry = False
        if hosts_path.exists():
            with open(hosts_path, 'r') as f:
                hosts_content = f.read()
                pattern = re.compile(rf'^\s*\d+\.\d+\.\d+\.\d+\s+{re.escape(DEFAULT_NCSI_HOST)}(?:\s|$)', re.MULTILINE)
                has_ncsi_entry = bool(pattern.search(hosts_content))
        
        # Create a full backup
        if hosts_path.exists():
            with open(hosts_path, 'r') as f:
                hosts_content = f.read()
            
            with open(backup_path, 'w') as f:
                f.write(hosts_content)
            
            logger.info(f"Created hosts file backup at {backup_path}")
            
            # Also create a standard .bak file in the same directory for easier restoration
            standard_backup = hosts_path.with_suffix('.ncsi_backup.bak')
            if not standard_backup.exists():  # Only create if it doesn't exist already
                with open(standard_backup, 'w') as f:
                    f.write(hosts_content)
                logger.info(f"Created standard hosts backup at {standard_backup}")
            
            # Log if we're overriding an existing entry
            if has_ncsi_entry:
                logger.warning(f"Hosts file already contains an entry for {DEFAULT_NCSI_HOST}, will be modified")
            
            return backup_path
    
    except Exception as e:
        logger.error(f"Error backing up hosts file: {e}")
    
    return ""

def update_hosts_file(hostname: str = DEFAULT_NCSI_HOST, ip: str = None) -> bool:
    """
    Update the Windows hosts file to redirect NCSI requests.
    
    Args:
        hostname: The hostname to redirect
        ip: The IP address to redirect to (default: local IP)
        
    Returns:
        bool: True if successful, False otherwise
    """
    if not is_admin():
        logger.error("Administrative privileges required to update hosts file")
        return False
    
    # Use local IP if not specified
    if ip is None:
        ip = get_local_ip() or DEFAULT_NCSI_IP
    
    hosts_path = Path(HOSTS_FILE_PATH)
    
    # Check if hosts file exists
    if not hosts_path.exists():
        logger.error(f"Hosts file not found at {HOSTS_FILE_PATH}")
        return False
    
    # Create a backup of the hosts file
    backup_path = backup_hosts_file()
    if not backup_path:
        logger.warning("Could not create hosts file backup, proceeding with caution")
    
    try:
        # Read current hosts file
        with open(hosts_path, 'r') as f:
            hosts_content = f.read()
        
        # Check if the hostname is already in the hosts file
        pattern = re.compile(rf'^\s*\d+\.\d+\.\d+\.\d+\s+{re.escape(hostname)}(?:\s|$)', re.MULTILINE)
        match = pattern.search(hosts_content)
        
        if match:
            # Update existing entry
            hosts_content = pattern.sub(f"{ip} {hostname}", hosts_content)
            logger.info(f"Updated hosts file entry for {hostname} to {ip}")
        else:
            # Add new entry
            if not hosts_content.endswith('\n'):
                hosts_content += '\n'
            hosts_content += f"{ip} {hostname}\n"
            logger.info(f"Added new hosts file entry for {hostname} to {ip}")
        
        # Write updated hosts file
        with open(hosts_path, 'w') as f:
            f.write(hosts_content)
        
        return True
    
    except Exception as e:
        logger.error(f"Error updating hosts file: {e}")
        
        # Try to restore from backup if we have one
        if backup_path and os.path.exists(backup_path):
            try:
                with open(backup_path, 'r') as f:
                    backup_content = f.read()
                
                with open(hosts_path, 'w') as f:
                    f.write(backup_content)
                
                logger.info("Restored hosts file from backup after error")
            except Exception as restore_error:
                logger.error(f"Error restoring hosts file from backup: {restore_error}")

        return False

def update_hosts_file_v6(hostname: str = DEFAULT_NCSI_HOST_V6, ipv6: str = "::1") -> bool:
    """
    Add or update an IPv6 hosts-file entry redirecting the IPv6 NCSI probe host.

    Mirrors update_hosts_file but matches IPv6 literals (the V4 version's regex is
    dotted-quad only). Uses the same backup_hosts_file(); the (extended)
    restore_hosts_file() removes this entry on reset/uninstall.

    Args:
        hostname: IPv6 NCSI probe host (default: ipv6.msftconnecttest.com)
        ipv6: IPv6 address to redirect to (e.g. the interface global address; ::1 fallback)

    Returns:
        bool: True if successful, False otherwise
    """
    if not is_admin():
        logger.error("Administrative privileges required to update hosts file")
        return False

    hosts_path = Path(HOSTS_FILE_PATH)
    if not hosts_path.exists():
        logger.error(f"Hosts file not found at {HOSTS_FILE_PATH}")
        return False

    backup_path = backup_hosts_file()
    if not backup_path:
        logger.warning("Could not create hosts file backup, proceeding with caution")

    try:
        with open(hosts_path, 'r') as f:
            hosts_content = f.read()

        # Match "<ipv6-literal> <hostname>" (hex groups + colons, not dotted-quad)
        pattern = re.compile(rf'^\s*[0-9A-Fa-f:]+\s+{re.escape(hostname)}(?:\s|$)', re.MULTILINE)
        if pattern.search(hosts_content):
            hosts_content = pattern.sub(f"{ipv6} {hostname}", hosts_content)
            logger.info(f"Updated hosts file IPv6 entry for {hostname} to {ipv6}")
        else:
            if not hosts_content.endswith('\n'):
                hosts_content += '\n'
            hosts_content += f"{ipv6} {hostname}\n"
            logger.info(f"Added new hosts file IPv6 entry for {hostname} to {ipv6}")

        with open(hosts_path, 'w') as f:
            f.write(hosts_content)

        return True

    except Exception as e:
        logger.error(f"Error updating hosts file (IPv6): {e}")
        if backup_path and os.path.exists(backup_path):
            try:
                with open(backup_path, 'r') as f:
                    backup_content = f.read()
                with open(hosts_path, 'w') as f:
                    f.write(backup_content)
                logger.info("Restored hosts file from backup after error")
            except Exception as restore_error:
                logger.error(f"Error restoring hosts file from backup: {restore_error}")
        return False

def update_ncsi_registry(probe_host: str = None, probe_path: str = "/ncsi.txt", port: int = 80) -> bool:
    """
    Update the Windows registry for NCSI settings.
    
    Args:
        probe_host: The hostname to use for NCSI probes (default: local IP)
        probe_path: The path to use for NCSI probes
        port: The port to use for NCSI probes
        
    Returns:
        bool: True if successful, False otherwise
    """
    if not is_admin():
        logger.error("Administrative privileges required to update registry")
        return False
    
    # Use local IP if not specified
    if probe_host is None:
        probe_host = get_local_ip() or DEFAULT_NCSI_IP
    
    # Backup existing registry values
    original_values = backup_registry_values()
    
    try:
        # Open the registry key
        reg_key = winreg.CreateKeyEx(
            winreg.HKEY_LOCAL_MACHINE,
            NCSI_REGISTRY_KEY,
            0,
            winreg.KEY_WRITE
        )
        
        # Format the host with port if not using default HTTP port
        if port != 80:
            formatted_host = f"{probe_host}:{port}"
        else:
            formatted_host = probe_host
            
        # Update registry values
        winreg.SetValueEx(reg_key, "ActiveWebProbeHost", 0, winreg.REG_SZ, formatted_host)
        winreg.SetValueEx(reg_key, "ActiveWebProbePath", 0, winreg.REG_SZ, probe_path)
        
        # Close the key
        winreg.CloseKey(reg_key)
        
        logger.info(f"Updated NCSI registry settings to use {formatted_host}{probe_path}")
        return True
    
    except Exception as e:
        logger.error(f"Error updating registry: {e}")
        
        # Try to restore original values if available
        if original_values:
            try:
                restore_registry_from_backup(original_values)
                logger.info("Restored registry from backup after error")
            except Exception as restore_error:
                logger.error(f"Error restoring registry from backup: {restore_error}")

        return False

def update_ncsi_registry_v6(probe_host: str, probe_path: str = "/connecttest.txt", port: int = 80) -> bool:
    """
    Update the Windows registry IPv6 NCSI probe values (ActiveWebProbeHostV6 /
    ActiveWebProbePathV6) to redirect the IPv6 active web probe.

    Mirrors update_ncsi_registry for the V6 values. Backs up first (the existing
    backup covers the V6 values via NCSI_MANAGED_VALUES), so the existing
    reset/uninstall path reverses this with no new restore code.

    Args:
        probe_host: IPv6 address (or host) to point the V6 probe at -- typically
            the interface's global address. Required; no auto-default.
        probe_path: Path for the V6 probe (Windows default: connecttest.txt)
        port: Port for the V6 probe

    Returns:
        bool: True if successful, False otherwise
    """
    if not is_admin():
        logger.error("Administrative privileges required to update registry")
        return False
    if not probe_host:
        logger.error("update_ncsi_registry_v6 requires a probe_host (IPv6 target)")
        return False

    # Backup existing registry values (covers V6 via the managed-value set)
    original_values = backup_registry_values()

    try:
        reg_key = winreg.CreateKeyEx(
            winreg.HKEY_LOCAL_MACHINE, NCSI_REGISTRY_KEY, 0, winreg.KEY_WRITE
        )

        # IPv6 literals take bracket notation when a non-default port is appended.
        if port != 80:
            formatted_host = f"[{probe_host}]:{port}"
        else:
            formatted_host = probe_host

        winreg.SetValueEx(reg_key, "ActiveWebProbeHostV6", 0, winreg.REG_SZ, formatted_host)
        winreg.SetValueEx(reg_key, "ActiveWebProbePathV6", 0, winreg.REG_SZ, probe_path)
        winreg.CloseKey(reg_key)

        logger.info(f"Updated IPv6 NCSI registry settings to use {formatted_host}{probe_path}")
        return True

    except Exception as e:
        logger.error(f"Error updating IPv6 registry: {e}")
        if original_values:
            try:
                restore_registry_from_backup(original_values)
                logger.info("Restored registry from backup after error")
            except Exception as restore_error:
                logger.error(f"Error restoring registry from backup: {restore_error}")
        return False

def check_ncsi_registry() -> Dict[str, str]:
    """
    Check the current NCSI registry settings.
    
    Returns:
        Dict[str, str]: A dictionary of current settings
    """
    result = {}
    
    try:
        # Open the registry key
        reg_key = winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            NCSI_REGISTRY_KEY,
            0,
            winreg.KEY_READ
        )
        
        # Read managed registry values (V4 + V6)
        for value_name in NCSI_MANAGED_VALUES:
            try:
                result[value_name] = winreg.QueryValueEx(reg_key, value_name)[0]
            except FileNotFoundError:
                result[value_name] = "default (not set)"

        # Close the key
        winreg.CloseKey(reg_key)
        
    except Exception as e:
        logger.error(f"Error reading registry: {e}")
    
    return result

def check_hosts_file(hostname: str = DEFAULT_NCSI_HOST) -> Optional[str]:
    """
    Check if the hostname is redirected in the hosts file.
    
    Args:
        hostname: The hostname to check
        
    Returns:
        Optional[str]: The IP address if found, None otherwise
    """
    try:
        with open(HOSTS_FILE_PATH, 'r') as f:
            hosts_content = f.read()
        
        # Look for the hostname in the hosts file
        pattern = re.compile(rf'^\s*(\d+\.\d+\.\d+\.\d+)\s+{re.escape(hostname)}(?:\s|$)', re.MULTILINE)
        match = pattern.search(hosts_content)
        
        if match:
            return match.group(1)
        
        return None
    
    except Exception as e:
        logger.error(f"Error reading hosts file: {e}")
        return None

def restore_registry_from_backup(original_values: Dict[str, Dict[str, Tuple[int, Union[str, bytes]]]] = None) -> bool:
    """
    Restore registry values from backup.
    
    Args:
        original_values: Dictionary with original registry values
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Open the registry key
        reg_key = winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            NCSI_REGISTRY_KEY,
            0,
            winreg.KEY_WRITE
        )
        
        # Restore each managed value (V4 + V6) to its original, or delete it if
        # it did not exist before we modified it. Looping over the managed set
        # means the existing reset/uninstall path reverses the IPv6 redirect too.
        values = original_values.get(NCSI_REGISTRY_KEY, {}) if original_values else {}
        for value_name in NCSI_MANAGED_VALUES:
            if value_name in values:
                value_type, value = values[value_name]
                winreg.SetValueEx(reg_key, value_name, 0, value_type, value)
                logger.info(f"Restored original registry value: {value_name} = {value}")
            else:
                # Either no backup, or this value did not exist originally -> remove our addition
                try:
                    winreg.DeleteValue(reg_key, value_name)
                    logger.info(f"Removed registry value: {value_name}")
                except FileNotFoundError:
                    pass

        # Close the key
        winreg.CloseKey(reg_key)
        
        # Look for the most recent backup file
        try:
            backup_files = []
            if os.path.exists(BACKUP_DIR):
                for file in os.listdir(BACKUP_DIR):
                    if file.startswith("ncsi_registry_backup_") and file.endswith(".reg"):
                        backup_files.append(os.path.join(BACKUP_DIR, file))
            
            if backup_files:
                # Sort by modification time (newest first)
                backup_files.sort(key=os.path.getmtime, reverse=True)
                newest_backup = backup_files[0]
                
                logger.info(f"Registry backup file available at: {newest_backup}")
                logger.info("You can manually restore registry settings by double-clicking this file if needed")
        except Exception as e:
            logger.warning(f"Could not find registry backup files: {e}")
        
        return True
    
    except Exception as e:
        logger.error(f"Error restoring registry values: {e}")
        return False

def restore_hosts_file() -> bool:
    """
    Restore hosts file from backup.
    
    Returns:
        bool: True if successful, False otherwise
    """
    hosts_path = Path(HOSTS_FILE_PATH)
    
    try:
        # First, look for our standard backup in the hosts directory
        standard_backup = hosts_path.with_suffix('.ncsi_backup.bak')
        
        if standard_backup.exists():
            logger.info(f"Found standard hosts backup at {standard_backup}")
            
            # Read the backup
            with open(standard_backup, 'r') as f:
                backup_content = f.read()
            
            # Read current hosts file
            with open(hosts_path, 'r') as f:
                current_content = f.read()
            
            # Check if our entry is in the current hosts file
            pattern = re.compile(rf'^\s*[0-9A-Fa-f.:]+\s+(?:{re.escape(DEFAULT_NCSI_HOST)}|{re.escape(DEFAULT_NCSI_HOST_V6)})(?:\s|$).*$\n?', re.MULTILINE)
            
            if pattern.search(current_content):
                # Remove only our entry
                modified_content = pattern.sub('', current_content)
                
                # Write the modified content back
                with open(hosts_path, 'w') as f:
                    f.write(modified_content)
                
                logger.info(f"Removed {DEFAULT_NCSI_HOST} entry from hosts file")
                
                # Don't restore from backup, as we only removed our entry
                # This preserves any other changes the user might have made
                return True
            else:
                # If our entry is not in the file, restore from backup
                with open(hosts_path, 'w') as f:
                    f.write(backup_content)
                
                logger.info("Restored hosts file from backup")
                return True
        
        # If standard backup doesn't exist, look for timestamped backups
        backup_files = []
        if os.path.exists(BACKUP_DIR):
            for file in os.listdir(BACKUP_DIR):
                if file.startswith("hosts.original.") and file.endswith(".bak"):
                    backup_files.append(os.path.join(BACKUP_DIR, file))
        
        if backup_files:
            # Sort by modification time (newest first)
            backup_files.sort(key=os.path.getmtime, reverse=True)
            newest_backup = backup_files[0]
            
            logger.info(f"Using backup file: {newest_backup}")
            
            # Restore from the backup
            with open(newest_backup, 'r') as f:
                backup_content = f.read()
            
            # Read current hosts file
            with open(hosts_path, 'r') as f:
                current_content = f.read()
            
            # Check if our entry is in the current hosts file
            pattern = re.compile(rf'^\s*[0-9A-Fa-f.:]+\s+(?:{re.escape(DEFAULT_NCSI_HOST)}|{re.escape(DEFAULT_NCSI_HOST_V6)})(?:\s|$).*$\n?', re.MULTILINE)
            
            if pattern.search(current_content):
                # Remove only our entry
                modified_content = pattern.sub('', current_content)
                
                # Write the modified content back
                with open(hosts_path, 'w') as f:
                    f.write(modified_content)
                
                logger.info(f"Removed {DEFAULT_NCSI_HOST} entry from hosts file")
                return True
            else:
                # If our entry is not in the file, restore from backup
                with open(hosts_path, 'w') as f:
                    f.write(backup_content)
                
                logger.info("Restored hosts file from backup")
                return True
        
        # If no backup is found, just remove our entry from the hosts file
        if hosts_path.exists():
            with open(hosts_path, 'r') as f:
                hosts_content = f.read()
            
            # Remove the NCSI host entry
            pattern = re.compile(rf'^\s*[0-9A-Fa-f.:]+\s+(?:{re.escape(DEFAULT_NCSI_HOST)}|{re.escape(DEFAULT_NCSI_HOST_V6)})(?:\s|$).*$\n?', re.MULTILINE)
            hosts_content = pattern.sub('', hosts_content)
            
            with open(hosts_path, 'w') as f:
                f.write(hosts_content)
            
            logger.info(f"Removed {DEFAULT_NCSI_HOST} entry from hosts file")
            return True
    
    except Exception as e:
        logger.error(f"Error restoring hosts file: {e}")
    
    return False

def restart_network_service() -> bool:
    """
    Restart the Network Location Awareness (NLA) service to apply changes.
    
    Returns:
        bool: True if successful, False otherwise
    """
    if not is_admin():
        logger.error("Administrative privileges required to restart network service")
        return False
    
    try:
        # Try restart instead of stop/start
        logger.info("Attempting to restart Network Location Awareness service...")
        restart_result = subprocess.run(
            ["net", "stop", "NlaSvc", "/y"], 
            check=False,  # Don't raise exception if command fails
            capture_output=True,
            timeout=TIMEOUT
        )
        
        if restart_result.returncode != 0:
            # If direct stop fails, try SC command to restart
            logger.info("Direct stop failed, trying SC to restart service...")
            sc_result = subprocess.run(
                ["sc", "stop", "NlaSvc"], 
                check=False,
                capture_output=True,
                timeout=TIMEOUT
            )
            
            # Even if SC fails, continue since we'll still flush DNS and renew IP
            if sc_result.returncode != 0:
                logger.warning("Could not stop NlaSvc service, changes may require a system restart to take effect")
        
        # Try to start the service again
        start_result = subprocess.run(
            ["net", "start", "NlaSvc"],
            check=False,
            capture_output=True,
            timeout=TIMEOUT
        )
        
        if start_result.returncode == 0:
            logger.info("Successfully restarted Network Location Awareness service")
        else:
            logger.warning("Could not start NlaSvc service, it may start automatically or require a system restart")
        
        # Return true even if we couldn't restart the service
        # The registry changes will still take effect eventually
        return True
    
    except Exception as e:
        logger.error(f"Error managing network service: {e}")
        # Continue with other network operations
        return False

def detect_wifi_adapters() -> List[str]:
    """
    Detect Wi-Fi adapters on the system.
    
    Returns:
        List[str]: List of Wi-Fi adapter names, or empty list if none found
    """
    try:
        # Method 1: Try using netsh (Windows-specific)
        result = subprocess.run(
            ["netsh", "wlan", "show", "interfaces"], 
            check=False,  # Don't raise exception if command fails
            capture_output=True, 
            text=True,
            timeout=TIMEOUT
        )
        
        # Extract adapter names
        adapters = []
        if result.returncode == 0:
            for line in result.stdout.splitlines():
                if "Name" in line and ":" in line:
                    adapters.append(line.split(":", 1)[1].strip())
            
            if adapters:
                return adapters
        
        # Method 2: Try using WMI for more detailed information
        try:
            import wmi
            c = wmi.WMI()
            wifi_adapters = []
            
            # Look for wireless adapters
            for nic in c.Win32_NetworkAdapter():
                # Check various properties that might indicate wireless
                if any(wifi_term.lower() in nic.Name.lower() for wifi_term in 
                      ["wireless", "wifi", "wi-fi", "802.11", "wlan"]):
                    wifi_adapters.append(nic.Name)
            
            if wifi_adapters:
                return wifi_adapters
            
        except ImportError:
            # WMI module not available, try one more approach
            pass
            
        # Method 3: Try using ipconfig
        result = subprocess.run(
            ["ipconfig", "/all"], 
            check=False,
            capture_output=True, 
            text=True,
            timeout=TIMEOUT
        )
        
        if result.returncode == 0:
            wifi_sections = []
            current_section = []
            in_section = False
            
            for line in result.stdout.splitlines():
                if "adapter" in line.lower() and ":" in line:
                    if in_section and any(wifi_term.lower() in "\n".join(current_section).lower() 
                                         for wifi_term in ["wireless", "wifi", "wi-fi", "802.11", "wlan"]):
                        wifi_name = current_section[0].split(":")[0].strip()
                        wifi_sections.append(wifi_name)
                    
                    current_section = [line]
                    in_section = True
                elif in_section:
                    current_section.append(line)
            
            # Check the last section
            if in_section and any(wifi_term.lower() in "\n".join(current_section).lower() 
                                for wifi_term in ["wireless", "wifi", "wi-fi", "802.11", "wlan"]):
                wifi_name = current_section[0].split(":")[0].strip()
                wifi_sections.append(wifi_name)
            
            return wifi_sections
    
    except Exception as e:
        logger.warning(f"Error detecting Wi-Fi adapters: {e}")
    
    return []

def configure_wifi_adapter(skip_if_no_wifi: bool = True) -> bool:
    """
    Configure Wi-Fi adapter for optimal stability.
    
    Args:
        skip_if_no_wifi: Whether to skip silently if no Wi-Fi adapter is found
        
    Returns:
        bool: True if successful or skipped, False otherwise
    """
    if not is_admin():
        logger.error("Administrative privileges required to configure network adapter")
        return False
    
    try:
        # Get list of wireless adapters using our detection function
        adapters = detect_wifi_adapters()
        
        if not adapters:
            if skip_if_no_wifi:
                logger.info("No wireless adapters found. Skipping Wi-Fi optimization.")
                return True  # Return success since we're skipping
            else:
                logger.warning("No wireless adapters found")
                return False
        
        logger.info(f"Found {len(adapters)} wireless adapters: {', '.join(adapters)}")
        
        # Configure each adapter
        for adapter in adapters:
            # Check if Intel adapter (common troublemakers)
            if "intel" in adapter.lower():
                logger.info(f"Configuring Intel adapter: {adapter}")
                
                # Lower the roaming aggressiveness
                subprocess.run([
                    "netsh", "wlan", "set", "profileparameter", 
                    f'name="{adapter}"', "roaming=1"
                ], check=False, timeout=TIMEOUT)
                
                # Prefer 5GHz band
                subprocess.run([
                    "netsh", "wlan", "set", "profileparameter", 
                    f'name="{adapter}"', "preferredband=5"
                ], check=False, timeout=TIMEOUT)
            
            # General settings for any adapter
            # Disable power saving
            try:
                subprocess.run([
                    "powercfg", "-setacvalueindex", "scheme_current", 
                    "19cbb8fa-5279-450e-9fac-8a3d5fedd0c1", 
                    "12bbebe6-58d6-4636-95bb-3217ef867c1a", "0"
                ], check=False, timeout=TIMEOUT)
                
                # Apply changes
                subprocess.run(["powercfg", "-setactive", "scheme_current"], check=False, timeout=TIMEOUT)
                
                logger.info(f"Configured power settings for {adapter}")
            except Exception as e:
                logger.warning(f"Failed to configure power settings: {e}")
        
        return True
    
    except Exception as e:
        logger.error(f"Error configuring Wi-Fi adapter: {e}")
        return False

def refresh_network() -> bool:
    """
    Refresh network settings and DNS cache.
    
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Flush DNS cache
        subprocess.run(["ipconfig", "/flushdns"], check=True, capture_output=True, timeout=TIMEOUT)
        logger.info("Flushed DNS cache")
        
        # Release and renew IP
        subprocess.run(["ipconfig", "/release"], check=False, capture_output=True, timeout=TIMEOUT)
        subprocess.run(["ipconfig", "/renew"], check=False, capture_output=True, timeout=TIMEOUT)
        logger.info("Released and renewed IP address")
        
        return True
    
    except Exception as e:
        logger.error(f"Error refreshing network: {e}")
        return False

def configure_system(probe_host: str = None, 
                     probe_path: str = "/ncsi.txt",
                     port: int = 80,
                     restart_services: bool = True,
                     configure_wifi: bool = True) -> bool:
    """
    Configure all system settings for NCSI Resolver.
    
    Args:
        probe_host: The hostname to use for NCSI probes (default: local IP)
        probe_path: The path to use for NCSI probes
        port: The port to use for NCSI probes
        restart_services: Whether to restart network services
        configure_wifi: Whether to attempt Wi-Fi adapter configuration
        
    Returns:
        bool: True if all operations successful, False otherwise
    """
    if not is_admin():
        logger.warning("Administrative privileges required to configure system")
        return False
    
    # Use local IP if not specified
    if probe_host is None:
        probe_host = get_local_ip() or DEFAULT_NCSI_IP
    
    success = True
    
    # Update hosts file
    if not update_hosts_file(DEFAULT_NCSI_HOST, probe_host):
        success = False
    
    # Update registry
    if not update_ncsi_registry(probe_host, probe_path, port):
        success = False
    
    # Configure Wi-Fi adapter only if requested
    if configure_wifi:
        if not configure_wifi_adapter(skip_if_no_wifi=True):
            logger.warning("Failed to configure Wi-Fi adapter, continuing with other operations")
    
    # Restart services if requested
    if restart_services:
        if not restart_network_service():
            success = False
        
        if not refresh_network():
            logger.warning("Failed to refresh network, continuing with other operations")
    
    # Print summary of current configuration
    if success:
        logger.info("System configuration successful")
        
        # Show current settings
        registry_settings = check_ncsi_registry()
        hosts_redirect = check_hosts_file(DEFAULT_NCSI_HOST)
        
        logger.info("Current NCSI configuration:")
        logger.info(f"  Registry settings:")
        for key, value in registry_settings.items():
            logger.info(f"    {key}: {value}")
        
        logger.info(f"  Hosts file redirect: {DEFAULT_NCSI_HOST} -> {hosts_redirect or 'not set'}")
    else:
        logger.error("System configuration failed")

    return success

def configure_system_ipv6(target_ipv6: str = None, probe_path: str = "/connecttest.txt",
                          port: int = 80, restart_services: bool = True,
                          allow_loopback: bool = False) -> bool:
    """
    Configure the IPv6 NCSI redirect: point the IPv6 active web probe
    (ipv6.msftconnecttest.com) at a local target so the local server answers it.

    EXPERIMENTAL (Phase 2, issue #9). Diagnostic-gated by design: if the machine
    has no global IPv6 address (GUA), this refuses and makes NO changes -- the
    redirect cannot satisfy Windows' passive 'NoGlobalAddress' check, which is a
    router-side problem. Fully reversible via the existing reset/uninstall path
    (registry + hosts cleanup already cover the V6 values).

    Args:
        target_ipv6: IPv6 address to redirect the probe to. If None, the
            interface's global address is auto-discovered.
        probe_path: V6 probe path (Windows default: connecttest.txt)
        port: V6 probe port
        restart_services: whether to restart NlaSvc + refresh network
        allow_loopback: permit ::1 as the target (default False -- loopback is
            unlikely to be credited to the real interface; opt-in for testing)

    Returns:
        bool: True if the redirect was applied, False otherwise
    """
    if not is_admin():
        logger.warning("Administrative privileges required to configure IPv6 NCSI")
        return False

    # Discover a global IPv6 address if no explicit target was given.
    if target_ipv6 is None:
        globals_found = []
        try:
            try:
                from NCSIresolver.network_diagnostics import gather_ipv6_addresses
            except ImportError:
                from network_diagnostics import gather_ipv6_addresses
            globals_found = [a["address"].split("%", 1)[0]
                             for a in gather_ipv6_addresses() if a["scope"] == "global"]
        except Exception as e:
            logger.error(f"Could not enumerate IPv6 addresses: {e}")

        if not globals_found:
            logger.error(
                "No global IPv6 address (GUA) found. The IPv6 redirect cannot help "
                "without a GUA -- this is a router-side issue (NoGlobalAddress). Run "
                "'installer.py --diagnose-ipv6' for details. Aborting (no changes made)."
            )
            return False
        target_ipv6 = globals_found[0]
        logger.info(f"Auto-selected IPv6 target (global address): {target_ipv6}")

    # Guard against an accidental loopback target unless explicitly allowed.
    if target_ipv6 == "::1" and not allow_loopback:
        logger.error(
            "Refusing to redirect to ::1 by default (loopback is unlikely to be "
            "credited to the real interface). Pass allow_loopback=True to override."
        )
        return False

    success = True
    if not update_hosts_file_v6(DEFAULT_NCSI_HOST_V6, target_ipv6):
        success = False
    if not update_ncsi_registry_v6(target_ipv6, probe_path, port):
        success = False

    if restart_services:
        if not restart_network_service():
            success = False
        if not refresh_network():
            logger.warning("Failed to refresh network, continuing with other operations")

    if success:
        logger.info(
            f"IPv6 NCSI redirect applied: {DEFAULT_NCSI_HOST_V6} -> {target_ipv6} "
            f"(probe path {probe_path}). EXPERIMENTAL. Reverse with "
            f"'installer.py --uninstall' (or system_config reset). Registry backup "
            f"saved under {BACKUP_DIR}."
        )
    else:
        logger.error("IPv6 NCSI configuration failed (see log). Reverse with reset/uninstall.")
    return success

def check_configuration() -> Dict[str, Union[str, bool]]:
    """
    Check the current NCSI configuration status.
    
    Returns:
        Dict: A dictionary with configuration status
    """
    result = {
        "registry_settings": check_ncsi_registry(),
        "hosts_file_redirect": check_hosts_file(DEFAULT_NCSI_HOST),
        "is_configured": False
    }
    
    # Check if properly configured
    if (result["registry_settings"].get("ActiveWebProbeHost") != "default (not set)" and
        result["hosts_file_redirect"] is not None):
        result["is_configured"] = True
    
    return result

def create_windows_defaults_reg(target_path: str) -> bool:
    """
    Create the Windows default registry settings file at the specified path.
    
    Args:
        target_path: Path where the file should be created
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Ensure directory exists
        os.makedirs(os.path.dirname(os.path.abspath(target_path)), exist_ok=True)
        
        # Create Windows default registry content with correct values
        # Note: ActiveWebProbePath does NOT have a leading slash
        content = """Windows Registry Editor Version 5.00

[HKEY_LOCAL_MACHINE\\SYSTEM\\CurrentControlSet\\Services\\NlaSvc\\Parameters\\Internet]
"EnableActiveProbing"=dword:00000001
"ActiveWebProbeHost"="www.msftconnecttest.com"
"ActiveWebProbePath"="connecttest.txt"
"ActiveWebProbeContent"="Microsoft Connect Test"
"ActiveWebProbeHostV6"="ipv6.msftconnecttest.com"
"ActiveWebProbePathV6"="connecttest.txt"
"ActiveWebProbeContentV6"="Microsoft Connect Test"
"ActiveDnsProbeHostV6"="dns.msftncsi.com"
"ActiveDnsProbeContentV6"="fd3e:4f5a:5b81::1"
"EnableActiveHTTPS"=dword:00000001
"""
        
        # Write to file
        with open(target_path, 'w') as f:
            f.write(content)
            
        logger.info(f"Created Windows default registry settings file at {target_path}")
        return True
    except Exception as e:
        logger.error(f"Error creating Windows default registry file: {e}")
        return False

def reset_configuration() -> bool:
    """
    Reset NCSI configuration to default Windows settings.
    
    Returns:
        bool: True if successful, False otherwise
    """
    if not is_admin():
        logger.warning("Administrative privileges required to reset configuration")
        return False
    
    success = True
    
    # Restore hosts file
    if not restore_hosts_file():
        success = False
    
    # Restore registry settings
    if not restore_registry_from_backup():
        success = False
    
    # Create or find Windows default registry file
    backup_dir = os.path.join(os.environ.get('LOCALAPPDATA', os.path.expanduser('~')), 
                             "NCSI_Resolver", "Backups")
    default_reg_path = os.path.join(backup_dir, "Windows_Defaults.reg")
    
    # Create DirectoryManager instance
    try:
        from directory_manager import DirectoryManager
        dir_manager = DirectoryManager()
        
        # Try to find existing Windows_Defaults.reg file
        windows_defaults_file = dir_manager.find_file("Windows_Defaults.reg")
        
        if windows_defaults_file:
            # Copy file to backup location
            copied_path = dir_manager.copy_file_to_destination(
                windows_defaults_file, 
                backup_dir, 
                "Windows_Defaults.reg"
            )
            
            if copied_path:
                logger.info(f"Windows default registry settings file available at: {copied_path}")
            else:
                # If copy failed, create the file
                create_windows_defaults_reg(default_reg_path)
        else:
            # If file not found, create it
            create_windows_defaults_reg(default_reg_path)
            
    except ImportError:
        # DirectoryManager not available, create file directly
        create_windows_defaults_reg(default_reg_path)
    
    # If registry values were removed, suggest restoring defaults
    reg_key = winreg.OpenKey(
        winreg.HKEY_LOCAL_MACHINE,
        NCSI_REGISTRY_KEY,
        0,
        winreg.KEY_READ
    )
    
    try:
        winreg.QueryValueEx(reg_key, "ActiveWebProbeHost")
        host_exists = True
    except FileNotFoundError:
        host_exists = False
    
    try:
        winreg.QueryValueEx(reg_key, "ActiveWebProbePath")
        path_exists = True
    except FileNotFoundError:
        path_exists = False
    
    winreg.CloseKey(reg_key)
    
    if not host_exists or not path_exists:
        logger.warning("NCSI registry values were removed. Windows network connectivity detection may not work properly.")
        logger.info(f"You can restore Windows default settings by double-clicking {default_reg_path}")
    
    # Restart network services
    if not restart_network_service():
        success = False
    
    if not refresh_network():
        logger.warning("Failed to refresh network")
    
    return success

def main():
    """Main entry point when running as a script."""
    import argparse
    
    parser = argparse.ArgumentParser(description=__description__)
    parser.add_argument("--action", choices=["configure", "check", "reset"], default="check",
                       help="Action to perform: configure, check or reset (default: check)")
    parser.add_argument("--host", help="Host address to use (default: auto-detect)")
    parser.add_argument("--path", default="/ncsi.txt", help="Path to use for NCSI probe")
    parser.add_argument("--no-restart", action="store_true", help="Don't restart network services")
    parser.add_argument("--no-wifi", action="store_true", help="Skip Wi-Fi adapter configuration")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    parser.add_argument('--version', action='version', version=f"{__description__} v{__version__}")
    
    args = parser.parse_args()
    
    # Configure logging
    if args.debug:
        logger.setLevel(logging.DEBUG)
    
    # Check admin privileges
    if args.action in ["configure", "reset"] and not is_admin():
        logger.info("Administrative privileges required, requesting elevation...")
        run_as_admin(
            sys.argv[0],
            f"--action={args.action}",
            f"--host={args.host}" if args.host else "",
            f"--path={args.path}",
            "--no-restart" if args.no_restart else "",
            "--no-wifi" if args.no_wifi else "",
            "--debug" if args.debug else ""
        )
        return
    
    # Perform requested action
    if args.action == "configure":
        configure_system(
            probe_host=args.host,
            probe_path=args.path,
            restart_services=not args.no_restart,
            configure_wifi=not args.no_wifi
        )
    elif args.action == "check":
        config = check_configuration()
        
        print("\nNCSI Configuration Status:")
        print("-------------------------")
        print(f"Configuration Status: {'Configured' if config['is_configured'] else 'Not Configured'}")
        print("\nRegistry Settings:")
        for key, value in config["registry_settings"].items():
            print(f"  {key}: {value}")
        
        print(f"\nHosts File Redirect: {DEFAULT_NCSI_HOST} -> {config['hosts_file_redirect'] or 'not set'}")
    elif args.action == "reset":
        reset_configuration()

if __name__ == "__main__":
    main()