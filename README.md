# CS CSAT Weekly Trends Dashboard

A GitHub Pages site showing weekly ZD CSAT and Tidio CSAT trends by agent and supervisor.

## Quick Setup

1. **Create a new GitHub repo** (e.g., `csat-dashboard`)
2. **Push this folder** to the repo:
   ```bash
   cd csat-dashboard
   git init
   git add .
   git commit -m "Initial dashboard setup"
   git branch -M main
   git remote add origin https://github.com/YOUR_ORG/csat-dashboard.git
   git push -u origin main
   ```
3. **Enable GitHub Pages**: Go to repo Settings > Pages > Source: `main` / `/ (root)` > Save
4. **Your site is live** at `https://YOUR_ORG.github.io/csat-dashboard/`

## Automated Weekly Updates

The GitHub Action runs every Monday at 10am UTC and scrapes the HEX report.

### Setup secrets:
Go to repo Settings > Secrets and variables > Actions, then add:
- `HEX_EMAIL` â Your HEX login email
- `HEX_PASSWORD` â Your HEX login password

### Manual trigger:
Go to Actions tab > "Update CSAT Data" > "Run workflow"

## Manual Update (Alternative)

If automation doesn't work with HEX auth, you can update `data.json` manually:

1. Open `data.json`
2. Add the new week to the `weeks` array
3. Add agent/supervisor data for that week
4. Commit and push â the site updates automatically

## Files

| File | Purpose |
|------|---------|
| `index.html` | Dashboard (HTML + Chart.js) |
| `data.json` | All CSAT data |
| `scripts/update_data.py` | HEX scraper script |
| `.github/workflows/update-csat.yml` | Weekly automation |
