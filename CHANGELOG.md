# Changelog

All notable changes to the "Windows (No Internet, Secured) BUGFIX" NCSI Resolver project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.7.12-alpha] - 2026-02-27

### Changed
- **Schema versioning**: Gist state now carries `schemaVersion` (currently 3)
  with forward-only migration steps run on each workflow execution
- **Delta-based dedup**: Clone and view accumulation replaced boolean
  `lastSeenDates` sets with `lastSeenCloneCounts` / `lastSeenViewCounts`
  maps — tracks last-known count per date so only the increase (delta)
  is accumulated, fixing missed traffic on zero-count days that later
  gain activity
- **`totalOrganicClones`**: Accumulated per-day organic clones instead of
  global `totalClones - totalCiCheckouts` subtraction, which could
  produce phantom negatives when CI runs outnumber real clones on a
  given day
- Monthly archive `organicClones` now sourced from `totalOrganicClones`
  instead of global subtraction
- Badge organic total uses `totalOrganicClones` (per-day accumulation)
- Version bumped from 0.7.11 to 0.7.12

### Added
- **Schema migration v1→v2**: Converts boolean `lastSeenDates` to
  delta-based `lastSeenCloneCounts` / `lastSeenViewCounts` maps,
  seeding counts from existing `dailyHistory`
- **Schema migration v2→v3**: Computes initial `totalOrganicClones`
  from dailyHistory organic sums (takes max of per-day sum vs global
  subtraction estimate)
- `push` trigger on `main` branch with freshness check — skips
  collection if last run was less than 60 minutes ago
- `concurrency` group (`traffic-collection`, cancel-in-progress) to
  prevent overlapping workflow runs
- `repoCreatedAt` field: records GitHub repo creation date; used to
  filter pre-repo Traffic API backfill entries (14 days of zeros)
- `trackingSince` field: records when stat collection first started,
  distinguishing "no data collected" from "zero traffic"
- Pre-repo entry filtering: removes dailyHistory entries that predate
  the repo's creation
- Totals sanity repair: if cumulative totals fall below the sum of
  dailyHistory entries (from the first-run seeding bug), raises them
  to match — never lowers, safe for long-running installs

## [0.7.11-alpha] - 2026-02-25

### Added
- Dev tab: CI audit cards (Raw Clones, CI Checkouts, Organic Clones, Data Freshness)
- Dev tab: Raw vs Organic dual-line chart visualizing CI noise gap
- Dev tab: CI Checkout breakdown table with per-workflow detail (last 31 days)
- Dev tab: Commit activity bar chart (52-week history, client-side from GitHub API)
- Dev tab: Code frequency chart — weekly additions vs deletions
- Dev tab: Participation chart — maintainer vs community commits (52 weeks, clickable)
- Dev tab: Punch card heat map — commits by day-of-week and hour
- Dev tab: Contributors list with avatars, commit counts
- Dev tab: Operational status section (data freshness indicator, schedule, retention)
- Client-side GitHub Statistics API with `sessionStorage` caching and 202-retry logic
- Dev tab: loading indicators with inline spinner for each GitHub stats section
- Dev tab: error state messaging when GitHub stats computation times out

### Changed
- Chart visual hierarchy swapped: unique lines are now solid (primary signal),
  total/raw lines are dashed (secondary context) across Installs, Views, Overview
- Tab order: Overview, Installs, Views, Community, Dev
- Dashboard title: "Project Statistics" (was "Install Statistics")
- Participation chart labels: "Maintainer" vs "Community" (org-owned repo fix)
- Referrer table annotates mobile apps and platform variants (e.g., Reddit app)
- Unique clone/view labels clarified as "tracked" where counts are partial
- Version bumped from 0.7.10 to 0.7.11

## [0.7.10-alpha] - 2026-02-25

### Fixed
- Chart projection: rewrite `projectTrailingZeros` to be date-aware —
  only project today's incomplete zero from yesterday's confirmed value;
  past days with 0 are real data, not projected
- Installs tab chart: all three lines (Total, Clones, Downloads) now
  use trailing-zero projection with dashed line indicator
- Overview tab chart: Clones, Downloads, and Total Installs lines now
  use projection (previously only Views did)
- Chart totals computed from organic values instead of raw `d.total`

### Added
- `workflow_run` trigger: Track Downloads & Clones now runs automatically
  after Python Tests completes, capturing accurate CI checkout counts
- Unique cloners tracking: accumulate daily unique clone counts from
  Traffic API (`uniqueClones` per day, `totalUniqueClones` cumulative)
- Unique viewers tracking: accumulate daily unique view counts from
  Traffic API (`uniqueViews` per day, `totalUniqueViews` cumulative)
- Popular paths collection: top 10 visited pages from Traffic API
  stored as `state.popularPaths` for Views tab display
- Archive includes unique clone and view counts in both cumulative
  totals and monthly summaries
- Dashboard: unique clone count displayed on Installs tab card
- Dashboard: unique viewer count displayed on Views tab cards (total + today)
- Dashboard: Unique Clones line on Installs chart (dotted light purple `#d4b8ff`)
- Dashboard: Unique Views line on Views chart (dotted light blue `#8ec5ff`)
- Dashboard: Popular Pages table on Views tab — top 10 visited pages with
  cleaned titles, monospace paths, view/unique counts, and clickable links
- Dashboard: Overview tab toggles for Unique Clones and Unique Views
  (on by default; raw Clones/Views toggled off to highlight meaningful signal)
- `tests/one-offs/verify_dashboard_ids.py` — validates JS setText/getElementById
  references against HTML element IDs
- `tests/one-offs/backfill_unique_counts.py` — one-time gist backfill utility
  for unique clone/view data with `--dry-run` support

### Changed
- Overview tab toggle order: metrics paired by type (Views/Unique Views,
  Clones/Unique Clones, Downloads, Installs) with unique counts on by default
- Popular Pages titles cleaned for UTF-8 encoding artifacts (`Â·` → `·` → ` - `)

## [0.7.9-alpha] - 2026-02-25

### Fixed
- Date attribution: daily history entries now use Traffic API timestamps
  instead of wall-clock time, preventing yesterday's data from being
  filed under today
- Badge recency suffix uses ~24h window (yesterday + today partial)
  instead of only the last entry, which could misattribute data
- todayViews had same mislabeling bug as todayClones — both now fixed
- All user-facing numbers (badge, dashboard cards, charts, suffix) now
  show organic clones only, excluding CI/CD checkout noise

### Added
- CI clone detection: counts `actions/checkout` operations per workflow
  run via Actions API, stores `ciCheckouts` and `organicClones` per day
- `capturedAt` timestamp on daily history entries records when the script
  ran (operational metadata, separate from data date)
- Zero-data days explicitly recorded (`clones: 0`) to distinguish
  "nothing happened" from "script didn't run"
- `state.ciCheckouts` map with per-workflow breakdown and per-run arrays
  to detect matrix changes
- `state.totalCiCheckouts` cumulative counter (never trimmed) for
  accurate lifetime organic clone calculation
- Monthly archive includes both raw and organic clone fields

### Changed
- Dates normalized to `YYYY-MM-DDT00:00:00Z` format in dedup step
- Dashboard and badge show organic clones as primary metric; raw clones
  retained in gist state as secondary diagnostic data

## [0.7.8-alpha] - 2026-02-24

### Added
- Tabbed dashboard: Installs, Views, Community, Overview
- Views tab with daily chart, referrers table, top referrer card
- Community tab with star history (client-side from stargazers API),
  forks, issues, and daily community trends chart (dual-axis)
- Overview tab with toggleable multi-metric chart
- Trailing-zero projection: dashed line for incomplete data points
- Privacy note explaining all data comes from GitHub's traffic API
- Views badge (`views.json`) in gist output

### Changed
- Workflow collects views, stars, forks, issues, referrers daily
- Daily history entries include views, stars, forks, openIssues
- Chart dates use UTC to prevent timezone day-shift
- Deduplicate daily history entries by UTC date
- Total renders as area-only when overlapping individual metric lines

## [0.7.7-alpha] - 2026-02-24

### Added
- GitHub Pages stats dashboard (`docs/stats/index.html`) with daily activity
  chart, summary cards, and activity window indicators
- Dashboard fetches live data from public gist — zero daily commits required
- "All History" toggle to load monthly archive data for long-term trends
- Installs badge now links to stats dashboard instead of releases page

## [0.7.6-alpha] - 2026-02-24

### Added
- Cascading recency suffix on installs badge — shows `(+N 24h)`, `(+N wk)`,
  or `(+N mo)` based on most recent activity window with installs
- Rolling 31-day daily history in gist state for recency computation
- Download delta tracking (diffs cumulative total between runs)

## [0.7.5-alpha] - 2026-02-24

### Added
- GitHub Action workflow to track cumulative download and clone counts
- Combined installs badge (downloads + clones) in README

### Changed
- Consolidate version to single source of truth (`version.py`)
- Python module fallback versions changed from hardcoded strings to `"unknown"`
- `config_manager.py` now imports version from `version.py` instead of hardcoding
- Update badge references from `djdarcy` to `DazzleTools` (org transfer)
- Move license badge to end of badge row in README

## [0.7.4-alpha] - 2025-10-26

### Fixed
- NSIS installer directory structure (now creates `NCSIresolver\` subdirectory correctly)
- File locking issue during NSIS installation (`WinError 32` when copying files)
- Service wrapper path detection in `service_installer.py`
- Admin elevation prompt in quick mode causing `EOFError`
- Installer log file creation for better debugging (`%TEMP%\ncsi_install.log`)

### Changed
- Installer now skips file creation when files already exist (prevents conflicts)
- NSIS installer properly organizes files into root and `NCSIresolver\` subdirectory

## [0.7.3-alpha] - 2025-10-26

### Added
- Future-proof Python detection in NSIS installer (supports Python 3.8-3.13+)
- Python validation step to ensure executable actually works (not just exists)
- New `--diagnose` mode with 9 pre-installation checks
- Start Menu shortcut for "Run Diagnostics"
- Dynamic version detection loop for future Python releases

### Fixed
- NSIS installer now detects Python versions 3.11, 3.12, 3.13 and beyond
- Unicode encoding issues in diagnostic output on Windows console
- Python detection no longer requires hardcoded version updates

### Changed
- Enhanced FindPython function with multiple detection strategies
- Improved error messages with specific troubleshooting guidance
- Diagnostic mode uses ASCII-safe output for Windows compatibility

## [0.7.2-alpha] - 2025-06-21

### Added
- Initial NSIS (Nullsoft Scriptable Install System) installer implementation
- One-click installation with `NCSI_Resolver_v0.7.2_setup.exe`
- Automated Python detection for versions 3.8-3.10
- Automatic service installation and startup via NSIS installer
- Minimal installer build script (`build_installer.py`)

## [0.7.1-alpha] - 2025-04-01
- First major release
- Minor bug fixes (CI/CD, flake8, and other CI/CD related issues)
- Documentation updates
- Improved error handling and logging

## [0.7.0-alpha] - 2025-04-01

### Added
- Network Diagnostics module with layered testing (ICMP, DNS, HTTP, HTTPS)
- Security Monitoring feature to detect and log suspicious connection attempts
- Enhanced interactive HTML redirect page with diagnostics and more
- Detailed installation test script (test_installation.py)
- Windows default registry settings file for easier recovery
- Service start verification with connection testing

### Fixed
- Socket binding issue by using all interfaces (0.0.0.0) instead of specific IP
- Better error handling during socket binding with enhanced logging
- Enhanced service logging with debug information for troubleshooting
- Scope issues with TIMEOUT variable in service_installer.py (fixes Flake8 error)

### Changed
- Deprecated test_connectivity.py in favor of new modular network_diagnostics.py
- Improved redirect.html page with interactive features and modern design
- Enhanced installation process with better error detection and reporting
- Updated version to 0.7.0-alpha

## [0.6.0-alpha] - 2025-04-01

### Added
- Modular code structure with dedicated NCSIresolver package
- Configuration file (config.json) to replace hardcoded values
- Firewall helper module for managing Windows Firewall rules
- Improved service wrapper with enhanced error handling
- Static file handling instead of code-generated content
- Junction points between installation and backup directories
- Support for non-WiFi systems with better detection
- Documentation on Wi-Fi power management settings

### Fixed
- Service installation bugs and reliability issues
- Better handling of paths with spaces
- Improved port conflict detection and handling

## [0.5.4-alpha] - 2025-04-01

### Added
- Enhanced logging for service_installer.py to track installation issues

## [0.5.3-alpha] - 2025-03-31

### Added
- Improved port handling and conflict detection
- Documentation on Wi-Fi Power Management Settings
- Junction points between installation and backup directories

## [0.5.2-alpha] - 2025-03-31

### Fixed
- Enhanced registry backup and restoration process

## [0.5.1-alpha] - 2025-03-31

### Fixed
- Path handling for files with spaces
- Simplified service wrapper
- Modified default installation directory to C:\NCSI_Resolver
- Improved NSSM download with caching

## [0.5.0-alpha] - 2025-03-31

### Added
- Initial release of NCSI Resolver
- Core NCSI server with both `/connecttest.txt` and `/redirect` endpoint support
- Actual internet connectivity verification (ICMP, DNS, HTTP methods)
- System configuration utilities for registry and hosts file
- Windows service installer using NSSM (see: https://nssm.cc/)
- Wi-Fi adapter optimization for Intel chipsets
- Full installer and uninstaller scripts
- Batch files for easy installation
- Complete documentation
- Installer banner
- Robuster error handling and timeouts

### Fixed
- Windows incorrectly reporting "No Internet" despite working connectivity
- Applications failing to sync due to reliance on NCSI
- Handling of captive portal detection via `/redirect` endpoint
- Wi-Fi connection stability issues
- Desktop/non-wireless system detection and handling
