# EldenOps Setup & Configuration Guide

Complete step-by-step guide to configure EldenOps for development and production environments.

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Discord Application Setup](#discord-application-setup)
3. [Discord Bot Setup](#discord-bot-setup)
4. [AI Provider Configuration](#ai-provider-configuration)
5. [GitHub Webhook Setup](#github-webhook-setup)
6. [Database Configuration](#database-configuration)
7. [Environment Variables Reference](#environment-variables-reference)
8. [Production Deployment](#production-deployment)

---

## Prerequisites

Before starting, ensure you have:

- [ ] Python 3.9+ installed
- [ ] Node.js 18+ installed
- [ ] PostgreSQL 14+ running
- [ ] Redis (optional, for production caching)
- [ ] A Discord account with access to Discord Developer Portal
- [ ] A GitHub account (for webhook integration)

---

## Discord Application Setup

### Step 1: Create a Discord Application

1. Go to [Discord Developer Portal](https://discord.com/developers/applications)
2. Click **"New Application"** (top right)
3. Enter application name: `EldenOps` (or your preferred name)
4. Accept the Terms of Service
5. Click **"Create"**

### Step 2: Get Client Credentials

1. In your application, go to **OAuth2 → General**
2. Copy the **Client ID** → Save as `DISCORD_CLIENT_ID`
3. Click **"Reset Secret"** to generate a new secret
4. Copy the **Client Secret** → Save as `DISCORD_CLIENT_SECRET`

### Step 3: Configure OAuth2 Redirects

1. Go to **OAuth2 → General**
2. Under **Redirects**, click **"Add Redirect"**
3. Add the following URLs:

| Environment | Redirect URI |
|-------------|--------------|
| Development | `http://localhost:8000/api/v1/auth/discord/callback` |
| Production  | `https://your-domain.com/api/v1/auth/discord/callback` |

4. Click **"Save Changes"**

### Step 4: Configure OAuth2 Scopes

The application uses these OAuth2 scopes (automatically requested):
- `identify` - Access user's Discord ID and username
- `guilds` - Access list of user's servers

---

## Discord Bot Setup

### Step 1: Create the Bot

1. In your Discord Application, go to **Bot** section
2. Click **"Add Bot"** → Confirm with **"Yes, do it!"**
3. Under the bot username, click **"Reset Token"**
4. Copy the token → Save as `DISCORD_BOT_TOKEN`

> **Security Warning**: Never share or commit your bot token. Anyone with this token has full control of your bot.

### Step 2: Configure Bot Permissions

1. In the **Bot** section, scroll to **Privileged Gateway Intents**
2. Enable the following intents:

| Intent | Required | Purpose |
|--------|----------|---------|
| **Presence Intent** | Optional | Track online status |
| **Server Members Intent** | Required | Access member information |
| **Message Content Intent** | Required | Read message content for analytics |

3. Click **"Save Changes"**

### Step 3: Generate Bot Invite URL

1. Go to **OAuth2 → URL Generator**
2. Select scopes:
   - `bot`
   - `applications.commands`
3. Select bot permissions:
   - `Read Messages/View Channels`
   - `Read Message History`
   - `Send Messages`
   - `Connect` (for voice analytics)
   - `View Channel`
4. Copy the generated URL at the bottom

### Step 4: Invite Bot to Your Server

1. Open the generated URL in your browser
2. Select the Discord server to add the bot
3. Authorize the permissions
4. Complete any CAPTCHA verification

### Step 5: Get Your Guild ID

1. In Discord, enable Developer Mode:
   - Go to **User Settings → App Settings → Advanced**
   - Enable **Developer Mode**
2. Right-click on your server name
3. Click **"Copy Server ID"**
4. Save this as your test `GUILD_ID` for development

---

## AI Provider Configuration

EldenOps supports multiple AI providers. Configure at least one.

### Option A: Anthropic Claude (Recommended)

1. Go to [Anthropic Console](https://console.anthropic.com/)
2. Sign up or log in
3. Navigate to **API Keys**
4. Click **"Create Key"**
5. Name it `EldenOps` and copy the key
6. Save as `ANTHROPIC_API_KEY`

**Pricing**: Pay-per-use, see [Anthropic Pricing](https://anthropic.com/pricing)

### Option B: OpenAI

1. Go to [OpenAI Platform](https://platform.openai.com/)
2. Sign up or log in
3. Navigate to **API Keys** (left sidebar)
4. Click **"Create new secret key"**
5. Name it `EldenOps` and copy the key
6. Save as `OPENAI_API_KEY`

**Pricing**: Pay-per-use, see [OpenAI Pricing](https://openai.com/pricing)

### Option C: Google AI (Gemini)

1. Go to [Google AI Studio](https://makersuite.google.com/app/apikey)
2. Sign in with your Google account
3. Click **"Create API key"**
4. Select or create a Google Cloud project
5. Copy the API key
6. Save as `GOOGLE_API_KEY`

**Pricing**: Free tier available, see [Google AI Pricing](https://ai.google.dev/pricing)

### Option D: DeepSeek

1. Go to [DeepSeek Platform](https://platform.deepseek.com/)
2. Sign up or log in
3. Navigate to API Keys section
4. Generate a new API key
5. Save as `DEEPSEEK_API_KEY`

### AI Provider Priority

EldenOps will use providers in this order (first available):
1. Anthropic Claude (if `ANTHROPIC_API_KEY` set)
2. OpenAI (if `OPENAI_API_KEY` set)
3. Google AI (if `GOOGLE_API_KEY` set)
4. DeepSeek (if `DEEPSEEK_API_KEY` set)

---

## GitHub Webhook Setup

### Step 1: Generate Webhook Secret

Generate a secure random string for webhook verification:

```bash
openssl rand -hex 32
```

Save this as `GITHUB_WEBHOOK_SECRET`

### Step 2: Configure Repository Webhook

For each repository you want to track:

1. Go to your GitHub repository
2. Navigate to **Settings → Webhooks**
3. Click **"Add webhook"**
4. Configure the webhook:

| Field | Value |
|-------|-------|
| Payload URL | `https://your-domain.com/api/v1/webhooks/github` |
| Content type | `application/json` |
| Secret | Your `GITHUB_WEBHOOK_SECRET` |

5. Select events to trigger:
   - `Push` - Track commits
   - `Pull requests` - Track PRs
   - `Pull request reviews` - Track code reviews
   - `Issues` - Track issue activity
   - Or select **"Send me everything"** for full tracking

6. Ensure **"Active"** is checked
7. Click **"Add webhook"**

### Step 3: Configure Organization Webhook (Optional)

For organization-wide tracking:

1. Go to your GitHub Organization
2. Navigate to **Settings → Webhooks**
3. Follow the same steps as repository webhook
4. This will apply to all repositories in the organization

### Step 4: For Local Development

Use a tunneling service to receive webhooks locally:

```bash
# Using ngrok
ngrok http 8000

# Use the generated URL as your webhook URL
# Example: https://abc123.ngrok.io/api/v1/webhooks/github
```

---

## Database Configuration

### Development Setup

1. Start PostgreSQL:
```bash
# macOS with Homebrew
brew services start postgresql@14

# Or manually
pg_ctl -D /usr/local/var/postgres start
```

2. Create the database:
```bash
createdb eldenops
```

3. Set connection string in `.env`:
```
DATABASE_URL=postgresql+asyncpg://localhost/eldenops
```

### Production Setup

1. Create a production PostgreSQL instance (AWS RDS, Google Cloud SQL, etc.)

2. Create database and user:
```sql
CREATE DATABASE eldenops;
CREATE USER eldenops_user WITH ENCRYPTED PASSWORD 'secure_password';
GRANT ALL PRIVILEGES ON DATABASE eldenops TO eldenops_user;
```

3. Set connection string:
```
DATABASE_URL=postgresql+asyncpg://eldenops_user:secure_password@db-host:5432/eldenops
```

### Redis Setup (Production)

1. Install and start Redis:
```bash
# macOS
brew install redis
brew services start redis

# Ubuntu/Debian
sudo apt install redis-server
sudo systemctl start redis
```

2. Configure in `.env`:
```
REDIS_URL=redis://localhost:6379/0
```

---

## Environment Variables Reference

Create a `.env` file in the project root with these variables:

```bash
# ===========================================
# REQUIRED - Application will not start without these
# ===========================================

# Security Keys (generate with: openssl rand -hex 32)
JWT_SECRET_KEY=your_jwt_secret_key_here
ENCRYPTION_KEY=your_encryption_key_here

# Discord OAuth (from Discord Developer Portal)
DISCORD_CLIENT_ID=your_client_id
DISCORD_CLIENT_SECRET=your_client_secret
DISCORD_REDIRECT_URI=http://localhost:8000/api/v1/auth/discord/callback

# Discord Bot
DISCORD_BOT_TOKEN=your_bot_token

# ===========================================
# REQUIRED - At least ONE AI provider
# ===========================================

ANTHROPIC_API_KEY=sk-ant-...
# OR
OPENAI_API_KEY=sk-...
# OR
GOOGLE_API_KEY=...
# OR
DEEPSEEK_API_KEY=...

# ===========================================
# OPTIONAL - Enhanced functionality
# ===========================================

# GitHub Webhooks
GITHUB_WEBHOOK_SECRET=your_webhook_secret

# Database (defaults to local PostgreSQL)
DATABASE_URL=postgresql+asyncpg://localhost/eldenops

# Redis (for production caching)
REDIS_URL=redis://localhost:6379/0

# Server Configuration
API_HOST=0.0.0.0
API_PORT=8000
ENVIRONMENT=development

# Dashboard
NEXT_PUBLIC_API_URL=http://localhost:8000
```

---

## Production Deployment

### Pre-Deployment Checklist

- [ ] All required environment variables configured
- [ ] Production database created and accessible
- [ ] Redis configured for caching
- [ ] Discord OAuth redirect URIs updated for production domain
- [ ] SSL/TLS certificates configured
- [ ] GitHub webhooks pointed to production URL

### Security Checklist

- [ ] Generate new `JWT_SECRET_KEY` for production
- [ ] Generate new `ENCRYPTION_KEY` for production
- [ ] Use strong database passwords
- [ ] Enable database connection encryption
- [ ] Configure CORS for your domain only
- [ ] Set `ENVIRONMENT=production`

### Deployment Steps

1. **Clone and Configure**
```bash
git clone https://github.com/your-org/eldenops.git
cd eldenops
cp .env.example .env
# Edit .env with production values
```

2. **Build Dashboard**
```bash
cd dashboard
npm install
npm run build
```

3. **Start Services**
```bash
# Using Docker Compose (recommended)
docker-compose -f docker-compose.prod.yml up -d

# Or manually
# Start API
cd src && uvicorn eldenops.main:app --host 0.0.0.0 --port 8000

# Start Dashboard
cd dashboard && npm start
```

4. **Run Database Migrations**
```bash
alembic upgrade head
```

5. **Verify Deployment**
- [ ] API health check: `curl https://your-domain.com/health`
- [ ] Dashboard loads at `https://your-domain.com`
- [ ] Discord login works
- [ ] Bot is online in Discord server

---

## Troubleshooting

### Discord OAuth Errors

| Error | Solution |
|-------|----------|
| Invalid redirect_uri | Ensure URI in `.env` matches Discord Developer Portal exactly |
| Invalid client_id | Check `DISCORD_CLIENT_ID` is correct |
| Access denied | User declined authorization, normal behavior |

### Bot Not Responding

1. Check bot is online in Discord server
2. Verify `DISCORD_BOT_TOKEN` is correct
3. Ensure required intents are enabled in Discord Developer Portal
4. Check bot has necessary permissions in the channel

### Webhook Not Receiving Events

1. Check webhook URL is accessible from internet
2. Verify `GITHUB_WEBHOOK_SECRET` matches GitHub configuration
3. Check webhook delivery history in GitHub for errors
4. For local dev, ensure ngrok/tunnel is running

### AI Provider Errors

| Error | Solution |
|-------|----------|
| Invalid API key | Regenerate and update the API key |
| Rate limited | Wait or upgrade to higher tier |
| Model not found | Check you have access to the model |

---

## Support

For issues and feature requests, please open an issue on GitHub.
