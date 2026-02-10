# Deployment Guide (Hostinger VPS)

This guide covers deploying the apartment scraper to a Hostinger VPS running Ubuntu.

## Prerequisites

- Hostinger VPS with Ubuntu 22.04+
- SSH access to your VPS
- Domain (optional, for future web dashboard)

## Quick Deploy

### 1. Connect to your VPS

```bash
ssh root@your-vps-ip
```

### 2. Clone the repository

```bash
cd /opt
git clone https://github.com/yourusername/apartment-scraper.git
cd apartment-scraper
```

### 3. Run setup script

```bash
chmod +x deploy/setup.sh
./deploy/setup.sh
```

### 4. Configure credentials

```bash
nano /opt/apartment-scraper/.env
```

Fill in:
- `FB_EMAIL` and `FB_PASSWORD` - Your dedicated Facebook account
- `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN` - From Twilio console
- `TWILIO_WHATSAPP_FROM` - Usually `whatsapp:+14155238886` for sandbox
- `TWILIO_WHATSAPP_TO` - Your phone number `whatsapp:+972501234567`
- `OPENAI_API_KEY` - From OpenAI dashboard

### 5. Configure search criteria

```bash
nano /opt/apartment-scraper/config.yaml
```

### 6. Start the service

```bash
sudo systemctl start apartment-scraper
```

## Management Commands

```bash
# Check status
sudo systemctl status apartment-scraper

# View logs (live)
journalctl -u apartment-scraper -f

# View recent logs
journalctl -u apartment-scraper -n 100

# Restart service
sudo systemctl restart apartment-scraper

# Stop service
sudo systemctl stop apartment-scraper

# Disable auto-start
sudo systemctl disable apartment-scraper
```

## First-Time Facebook Login

The first time you run the scraper, you may need to handle Facebook's security checks:

1. **Option A**: Run manually first
   ```bash
   cd /opt/apartment-scraper
   source venv/bin/activate
   python -m src.main
   ```
   Check logs for any 2FA or security checkpoint messages.

2. **Option B**: Log in on your local machine first
   - Run the scraper locally with `headless=False` in the browser config
   - Complete any 2FA/security checks
   - Copy the `data/session/` folder to your VPS

## Auto-Updating

The scraper runs inside an **auto-update runner** that handles updates automatically:

1. On startup it does a `git pull` and installs any new dependencies
2. Every 5 minutes (configurable) it checks the remote for new commits
3. If an update is found it gracefully stops the scraper, pulls the new code, installs dependencies, and restarts

This means you just need to `git push` your changes and the Hostinger instance will pick them up within a few minutes — no SSH required.

### Configuration

You can tune the update behavior via environment variables in the systemd service file:

| Variable | Default | Description |
|----------|---------|-------------|
| `UPDATE_CHECK_INTERVAL` | `300` | Seconds between Git update checks |
| `GIT_REMOTE` | `origin` | Git remote name |
| `GIT_BRANCH` | `main` | Branch to track |

To change these, edit `/etc/systemd/system/apartment-scraper.service` and run:

```bash
sudo systemctl daemon-reload
sudo systemctl restart apartment-scraper
```

### Manual Update (if needed)

If you want to update manually instead of waiting for the auto-check:

```bash
sudo systemctl restart apartment-scraper
```

This will trigger a fresh `git pull` on startup. Or the old-fashioned way:

```bash
cd /opt/apartment-scraper
git pull
source venv/bin/activate
pip install -r requirements.txt
sudo systemctl restart apartment-scraper
```

## Monitoring

### Set up basic monitoring with a health check

Add to your crontab:
```bash
crontab -e
```

Add this line to check every hour:
```
0 * * * * systemctl is-active apartment-scraper || systemctl restart apartment-scraper
```

### Optional: Email alerts

Install mailutils and configure to receive alerts when the service fails.

## Troubleshooting

### Service won't start

```bash
# Check logs for errors
journalctl -u apartment-scraper -n 50

# Try running manually
cd /opt/apartment-scraper
source venv/bin/activate
python -m src.main
```

### Playwright browser errors

```bash
# Reinstall Playwright browsers
source venv/bin/activate
playwright install firefox
playwright install-deps firefox
```

### Permission errors

```bash
# Fix ownership
sudo chown -R root:root /opt/apartment-scraper
chmod -R 755 /opt/apartment-scraper
```

### Database locked

```bash
# Stop service and check for zombie processes
sudo systemctl stop apartment-scraper
ps aux | grep apartment
kill -9 <pid>  # if any zombie processes
sudo systemctl start apartment-scraper
```
