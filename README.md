# Tel Aviv Apartment Scraper

Automatically scrapes Facebook groups for apartment listings in Tel Aviv and sends WhatsApp notifications when matches are found.

## Features

- 🏠 **Facebook Scraping**: Monitors configured Facebook groups for new listings
- 🔍 **Smart Parsing**: Hybrid regex + AI parser extracts price, location, rooms from Hebrew posts
- 🎯 **Criteria Filtering**: Filter by budget, neighborhood, rooms, and listing type
- 📱 **WhatsApp Notifications**: Get instant alerts via Twilio WhatsApp
- 🔄 **Deduplication**: Avoids notifying about the same listing twice
- ⏰ **Scheduled**: Runs automatically every 5-10 minutes

## Quick Start

### 1. Install Dependencies

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Install Playwright browsers
playwright install firefox
```

### 2. Configure Environment

Copy `.env.example` to `.env` and fill in your credentials:

```bash
cp .env.example .env
```

Required credentials:
- **Facebook**: Email and password for a dedicated Facebook account
- **Twilio**: Account SID, Auth Token, and WhatsApp numbers
- **OpenAI**: API key for AI parsing (optional but recommended)

### 3. Configure Criteria

Edit `config.yaml` to set your search criteria:

```yaml
criteria:
  budget:
    min: 3000
    max: 7000
  locations:
    - florentin
    - פלורנטין
    - neve tzedek
    - נווה צדק
  rooms:
    min: 2
    max: 4
  listing_type: whole_apartment
```

### 4. Add Facebook Groups

Add the groups you want to monitor in `config.yaml`:

```yaml
facebook:
  groups:
    - name: "דירות להשכרה בתל אביב"
      url: "https://www.facebook.com/groups/groupname"
```

### 5. Run

```bash
python -m src.main
```

## Twilio WhatsApp Setup

1. Create a [Twilio account](https://www.twilio.com/)
2. Go to Messaging > Try it out > Send a WhatsApp message
3. Follow the sandbox setup instructions
4. Add your phone number to the sandbox
5. Copy the Account SID, Auth Token, and WhatsApp number to `.env`

For group chats, you'll need to use Twilio's WhatsApp Business API (requires approval).

## Project Structure

```
apartment-scraper/
├── src/
│   ├── scraper/         # Facebook scraping with Playwright
│   ├── parser/          # Hebrew text parsing (regex + AI)
│   ├── storage/         # SQLite database and deduplication
│   ├── filters/         # Criteria matching
│   ├── notifier/        # WhatsApp via Twilio
│   ├── config.py        # Configuration management
│   └── main.py          # Entry point and scheduler
├── config.yaml          # Your search criteria
├── .env                 # API keys (not committed)
└── data/                # Database and session storage
```

## Deployment (Hostinger VPS)

See [deploy/README.md](deploy/README.md) for deployment instructions.

Quick deploy:

```bash
# On your VPS
git clone <your-repo>
cd apartment-scraper
./deploy/setup.sh
```

## Cost Estimate

| Service | Monthly Cost |
|---------|-------------|
| Hostinger VPS | ~$5-10 |
| Twilio WhatsApp | ~$5-15 |
| OpenAI API | ~$2-10 |
| **Total** | **~$12-35** |

## Troubleshooting

### Facebook Login Issues

- **2FA Required**: Log in manually first and complete 2FA, then run the scraper
- **Account Restricted**: Use a warmed-up account, avoid scraping too aggressively
- **Session Expired**: Delete `data/session/` and re-login

### No Listings Found

- Check that your Facebook groups are correct and public/joined
- Verify your criteria aren't too restrictive
- Check logs for parsing errors

### WhatsApp Not Working

- Verify Twilio credentials in `.env`
- For sandbox: Make sure you've sent the join message
- Check rate limits in Twilio dashboard

## License

MIT
