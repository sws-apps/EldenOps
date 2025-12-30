# EldenOps Quick Start

Get up and running in 10 minutes.

## 1. Discord Setup (5 min)

### Create Application
1. Go to https://discord.com/developers/applications
2. Click "New Application" → Name it "EldenOps"
3. Go to **OAuth2 → General**:
   - Copy **Client ID** → `DISCORD_CLIENT_ID`
   - Reset & copy **Client Secret** → `DISCORD_CLIENT_SECRET`
   - Add redirect: `http://localhost:8000/api/v1/auth/discord/callback`

### Create Bot
1. Go to **Bot** section → "Add Bot"
2. Reset & copy **Token** → `DISCORD_BOT_TOKEN`
3. Enable these **Privileged Gateway Intents**:
   - Server Members Intent ✓
   - Message Content Intent ✓
4. Go to **OAuth2 → URL Generator**:
   - Scopes: `bot`, `applications.commands`
   - Permissions: `Read Messages`, `Read Message History`, `Send Messages`, `Connect`
5. Open generated URL → Add bot to your server

## 2. AI Provider (2 min)

Choose one:

| Provider | Get Key | Env Variable |
|----------|---------|--------------|
| Anthropic | https://console.anthropic.com/api-keys | `ANTHROPIC_API_KEY` |
| OpenAI | https://platform.openai.com/api-keys | `OPENAI_API_KEY` |
| Google AI | https://makersuite.google.com/app/apikey | `GOOGLE_API_KEY` |

## 3. Configure Environment (1 min)

Create `.env` in project root:

```bash
# Discord (from step 1)
DISCORD_CLIENT_ID=paste_here
DISCORD_CLIENT_SECRET=paste_here
DISCORD_BOT_TOKEN=paste_here
DISCORD_REDIRECT_URI=http://localhost:8000/api/v1/auth/discord/callback

# Security (generate: openssl rand -hex 32)
JWT_SECRET_KEY=generate_new_key
ENCRYPTION_KEY=generate_new_key

# AI Provider (from step 2)
ANTHROPIC_API_KEY=paste_here
```

## 4. Start Services (2 min)

```bash
# Terminal 1: Database
createdb eldenops

# Terminal 2: API
cd src
python -m venv venv && source venv/bin/activate
pip install -e ..
uvicorn eldenops.main:app --reload

# Terminal 3: Dashboard
cd dashboard
npm install && npm run dev
```

## 5. Verify

1. Open http://localhost:3000
2. Click "Continue with Discord"
3. Authorize the application
4. You're in!

---

## GitHub Webhooks (Optional)

```bash
# Generate secret
openssl rand -hex 32
```

In your GitHub repo → Settings → Webhooks → Add webhook:
- URL: `https://your-domain.com/api/v1/webhooks/github`
- Secret: (paste generated secret)
- Events: Push, Pull requests, Pull request reviews

Add to `.env`:
```bash
GITHUB_WEBHOOK_SECRET=your_generated_secret
```

---

## Common Issues

**"Invalid redirect_uri"** → Check redirect URL matches exactly in Discord Developer Portal

**Bot not responding** → Enable Message Content Intent in Bot settings

**"No AI provider configured"** → Add at least one API key to `.env`
