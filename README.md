# NCSI Resolver

<div align="center">
    
![NCSI Resolver Banner](docs/images/banner.png)
[![GitHub Workflow Status][workflow-badge]][workflow-url]
[![Version][version-badge]][version-url]
[![Python][python-badge]][python-url]
[![Installs][installs-badge]][installs-url]
[![GitHub Discussions][discussions-badge]][discussions-url]
[![License][license-badge]][license-url]

</div>

A one-click silent background solution to fix the "No Internet, Secured" Windows connectivity detection issue when Windows incorrectly reports no internet connection despite having working connectivity. 

Quick download links: [`NCSI_Resolver_v0.7.4_setup.exe`](https://github.com/DazzleTools/Windows-No-Internet-Secured-BUGFIX/releases/download/v0.7.4-alpha/NCSI_Resolver_v0.7.4_setup.exe) or [source zip](https://github.com/DazzleTools/Windows-No-Internet-Secured-BUGFIX/archive/refs/tags/v0.7.4-alpha.zip) 

**NOTE**: *It can take upwards of a few minutes for Windows to notice the change or requires a system restart*


[workflow-badge]: https://github.com/DazzleTools/Windows-No-Internet-Secured-BUGFIX/actions/workflows/python.yml/badge.svg
[workflow-url]: https://github.com/DazzleTools/Windows-No-Internet-Secured-BUGFIX/actions
[version-badge]: https://img.shields.io/github/v/release/DazzleTools/Windows-No-Internet-Secured-BUGFIX?sort=semver&color=darkgreen
[version-url]: https://github.com/DazzleTools/Windows-No-Internet-Secured-BUGFIX/releases
[python-badge]: https://img.shields.io/badge/python-3.8%2B-darkgreen
[python-url]: https://www.python.org/downloads/
[installs-badge]: https://img.shields.io/endpoint?url=https://gist.githubusercontent.com/djdarcy/1362078955559665832b72835b309e98/raw/installs.json
[installs-url]: https://dazzletools.github.io/Windows-No-Internet-Secured-BUGFIX/stats/
[license-badge]: https://img.shields.io/badge/license-MIT-blue
[license-url]: https://github.com/DazzleTools/Windows-No-Internet-Secured-BUGFIX/blob/main/LICENSE
[discussions-badge]: https://img.shields.io/github/discussions/DazzleTools/Windows-No-Internet-Secured-BUGFIX
[discussions-url]: https://github.com/DazzleTools/Windows-No-Internet-Secured-BUGFIX/discussions


## Overview

NCSI (Network Connectivity Status Indicator) Resolver addresses a common Windows networking frustration where the system incorrectly reports "No Internet" despite having actual connectivity. This affects applications that rely on Windows' connectivity status to function properly, such as Microsoft Store, OneDrive, and UWP apps.

The root causes typically involve:
- Intelligent firewalls or routers intercepting Windows connectivity checks
- Network security software scanning or interfering with NCSI probes
- Windows Wi-Fi adapter behavior causing connection instability
- Captive portal detection mechanisms behaving incorrectly

NCSI Resolver creates a lightweight HTTP server on your local machine to properly respond to the two key endpoints that Windows uses for connectivity checks:

1. `/connecttest.txt` - Must return exactly "Microsoft Connect Test"
2. `/redirect` - Used for captive portal detection

For those curious about the innerworkings of NCSI, the official documentation can be found [here](https://learn.microsoft.com/en-us/windows-server/networking/ncsi/ncsi-overview). There is an article on Medium I wrote that gives the blow-by-blows of the bug, along with the initial steps taken to resolve it. You can read all about it here, "[When Windows Says 'No Internet' But You Know Better: A Technical Walkthrough](https://medium.com/technical-curious/when-windows-says-no-internet-but-you-know-better-a-technical-walkthrough-ee6be0354224)".

## Features

- 🌐 **Local NCSI server** that responds to Windows connectivity tests
- 🔍 **Actual connectivity verification** ensuring internet is actually available
- 🛠️ **System configuration tools** for registry and hosts file setup
- 💻 **Windows service** for automatic operation on startup
- 📊 **Diagnostic logging** for understanding connectivity issues
- ⚡ **Wi-Fi adapter optimization** for connection stability
- 🔒 **Security monitoring** for tracking and detecting suspicious connection attempts
- 🔬 **Advanced network diagnostics** with layered testing (ICMP, DNS, HTTP, HTTPS)
- 🧪 **Installation validation** to ensure proper setup
- 🖥️ **Interactive diagnostic page** when accessing the server directly

## Installation

### Prerequisites

- Windows 10 or 11
- Administrator privileges
- Python 3.6 or higher

### Quick Install

1. Download the latest release from the [Releases page](https://github.com/DazzleTools/Windows-No-Internet-Secured-BUGFIX/releases) or the installer [NCSI_Resolver_v0.7.4_setup.exe](https://github.com/DazzleTools/Windows-No-Internet-Secured-BUGFIX/releases/download/v0.7.4-alpha/NCSI_Resolver_v0.7.4_setup.exe) 

2. Extract the ZIP file to a temporary location
3. Right-click on `_install.bat` and select "Run as administrator"

The installer will:
- Configure Windows system settings
- Install the NCSI Resolver service
- Start the service automatically

### Manual Installation

If you prefer to install manually or want more control:

```cmd
# Clone the repository
git clone https://github.com/djdarcy/Windows-No-Internet-Secured-BUGFIX.git
cd Windows-No-Internet-Secured-BUGFIX

# Install using the Python script
python installer.py --install
```

### Installation Options

You can customize the installation with various options:

```cmd
# Install to a custom directory
python installer.py --install --install-dir="C:\Custom Path\NCSI Resolver"

# Use a different port (if port 80 is in use)
python installer.py --install --port=8080

# Enable debug logging
python installer.py --install --debug
```

## Usage

Once installed, the NCSI Resolver runs automatically in the background. There's no user interface needed (though there is a local [http://localhost/redirect](http://localhost/redirect) you can use to check interface statistics) as it works silently to ensure Windows correctly detects internet connectivity.

### Checking Status

To check the current status:

```cmd
python installer.py --check
```

### Advanced Diagnostics

To run advanced network diagnostics:

```cmd
python test_installation.py --verbose
```

This validation test will check:
- System configuration (registry, hosts file)
- Service installation and status
- Network connectivity at multiple layers
- Troubleshoot any detected issues

### Service Management

The service can be managed like any other Windows service:

- Start: `net start NCSIResolver`
- Stop: `net stop NCSIResolver`
- Restart: Stop and then start the service

### Testing Connectivity

You can test if the resolver is working by:

1. Opening Command Prompt
2. Running `curl http://localhost/ncsi.txt`

If you see "Microsoft Connect Test", the server is running correctly.

You can also visit `http://localhost/redirect` in your browser to see an interactive diagnostic page.

## Security Features

NCSI Resolver now includes basic security monitoring that:

- Tracks connection attempts to the service
- Detects potential scanning or probing activity
- Logs suspicious connection patterns
- Provides a simple IDS-like capability

Security logs are stored in the `Logs` directory of your installation.

## Uninstallation

To completely remove NCSI Resolver:

1. Run `python installer.py --uninstall` or
2. Run `_uninstall.bat` as administrator

## How It Works

NCSI Resolver functions by:

1. Redirecting Windows NCSI test domains to your local machine via the registry & hosts file
2. Running a local HTTP server to respond to connectivity test requests
3. Verifying actual internet connectivity using multiple methods (ICMP, DNS, HTTP)
4. Updating the Windows registry to reference the local server
5. Running as a Windows service to ensure continuous operation
6. Monitoring and logging connection attempts for security purposes
7. Providing diagnostics to help troubleshoot connectivity issues

## Troubleshooting

### Common Issues

- **Service won't start**: Ensure port 80 is not in use by other applications
- **"No Internet" still showing**: Restart the Network Location Awareness service (`net stop NlaSvc && net start NlaSvc`)
- **Applications still offline**: Some applications may need to be restarted to recognize the new connectivity status
- **Port conflict**: Use the `--port` option during installation to specify an alternative port

### Advanced Troubleshooting

For more in-depth troubleshooting, run the comprehensive test script:

```cmd
python test_installation.py --verbose
```

This will check all aspects of the installation and provide specific recommendations for fixing issues.

### Logs & Backups

Check logs at:
- Service logs: `%LOCALAPPDATA%\NCSI_Resolver\Logs\ncsi_resolver.log`
- Service output: `%LOCALAPPDATA%\NCSI_Resolver\Logs\service_output.log`
- Security logs: `%LOCALAPPDATA%\NCSI_Resolver\Logs\security.log`
- Detailed debug: `%LOCALAPPDATA%\NCSI_Resolver\Logs\ncsi_debug.log`

Backups are at:
- Original registry and HOSTS file: `%LOCALAPPDATA%\NCSI_Resolver\Backups\`

### Development Setup

1. Clone the repository
2. Create a virtual environment: `python -m venv venv`
3. Activate it: `venv\Scripts\activate`
4. Install dependencies: `pip install -r dev-requirements.txt`
5. Make your changes
6. Test thoroughly preferably on different Windows versions and network configurations

### Building

To build a distributable package:

```cmd
python -m pip install pyinstaller
pyinstaller --onefile installer.py
```

## Contributions

Contributions are welcome! Issues, suggestions, and bug reports are all appreciated. Please open an [issue](https://github.com/djdarcy/Windows-No-Internet-Secured-BUGFIX/issues) if you find something that can be improved. Or feel free to submit a Pull Request: 

1. Make a fork and clone the repository
2. Setup a new branch and add your new feature (e.g., `feature/happy_little_fix`).
3. Submit a pull request describing your changes.

Like the project?

[!["Buy Me A Coffee"](https://www.buymeacoffee.com/assets/img/custom_images/orange_img.png)](https://www.buymeacoffee.com/djdarcy)

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgements

- Inspired by:
  - My onerous Surface 7 refusing to sync with OneNote while using a virtual KVM, making it exceedingly difficult to sync work between machines
  - Other folks who have attacked this problem in different ways including: [Dantmnf](https://github.com/dantmnf/NCSIOverride), [Jamesits](https://github.com/Jamesits/alwaysonline), along with a handful of other [NCSI trailblazers](https://github.com/topics/ncsi)
  - And [**numerous**](https://answers.microsoft.com/en-us/windows/forum/windows_10-networking/windows-shows-no-internet-access-but-my-internet/2e9b593f-c31c-4448-b5d9-6e6b2bd8560c?page=2) [community](https://www.youtube.com/watch?v=v3CkXHgj6Ig&lc=UgwCfOeDQI7vPPsX0lN4AaABAg) [discussions](https://www.quora.com/Why-does-my-WiFi-keep-saying-no-internet-secured-even-no-matter-what-I-do-to-fix-it) about Windows NCSI issues
- Uses [NSSM](https://nssm.cc/) for service management
