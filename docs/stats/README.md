# Install Statistics Dashboard

Interactive dashboard showing download and clone tracking for [NCSI Resolver](https://github.com/DazzleTools/Windows-No-Internet-Secured-BUGFIX).

## How It Works

This is a **static page** — no server-side code, no daily commits. All data is fetched client-side from GitHub Gists at page load time.

### Data Collection

A [GitHub Actions workflow](../../.github/workflows/traffic-badges.yml) runs daily at 3:00 AM UTC and:

1. Fetches cumulative release download counts via the GitHub Releases API
2. Fetches 14-day clone data via the GitHub Traffic API
3. Accumulates clone counts beyond the 14-day API retention window
4. Records daily history (rolling 31-day window)
5. Archives monthly snapshots for long-term tracking
6. Updates a public Gist with the latest badge data and state

### Data Sources

| Source | Type | Contents |
|--------|------|----------|
| [Badge Gist](https://gist.github.com/djdarcy/1362078955559665832b72835b309e98) | Public | Current stats, rolling 31-day daily history |
| Archive Gist | Unlisted | Monthly snapshots with full daily breakdowns |

### What's Displayed

- **Total installs** (downloads + clones combined)
- **Downloads vs clones** breakdown with percentages
- **Recent activity** indicator (24h / 7-day / 30-day cascading)
- **Daily activity chart** with toggleable 31-day and all-history views
- **Activity window** dots showing at-a-glance health

## Viewing the Dashboard

The dashboard is hosted on GitHub Pages:

**https://dazzletools.github.io/Windows-No-Internet-Secured-BUGFIX/stats/**

You can also open `index.html` directly in a browser for local testing — the gist CDN has permissive CORS headers.
