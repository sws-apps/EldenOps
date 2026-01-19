# EldenOps Deployment Guide

Complete guide for deploying EldenOps to various environments.

---

## Table of Contents

1. [Local Development](#local-development)
2. [Docker Deployment](#docker-deployment)
3. [Railway Deployment](#railway-deployment)
4. [VPS/Cloud Deployment](#vpscloud-deployment)
5. [Database Setup](#database-setup)
6. [Environment Configuration](#environment-configuration)
7. [Post-Deployment Checklist](#post-deployment-checklist)
8. [Troubleshooting](#troubleshooting)

---

## Local Development

### Prerequisites

- Python 3.9+ (3.11 recommended)
- Node.js 18+
- PostgreSQL 14+ or 15
- Redis (optional for development)

### Quick Start

```bash
# 1. Clone the repository
git clone https://github.com/sws-apps/EldenOps.git
cd EldenOps

# 2. Create Python virtual environment
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# 3. Install dependencies
pip install -e ".[dev]"

# 4. Install frontend dependencies
cd dashboard && npm install && cd ..

# 5. Setup environment
cp .env.example .env
# Edit .env with your credentials

# 6. Create and setup database
createdb eldenops

# 7. Start the backend (creates tables automatically in dev mode)
source .venv/bin/activate
python -m eldenops

# 8. In another terminal, start the frontend
cd dashboard
npm run dev -- -p 3005  # Use port 3005 to avoid conflicts
```

### Services

| Service | URL | Description |
|---------|-----|-------------|
| Frontend | http://localhost:3005 | Next.js dashboard |
| Backend API | http://localhost:8000 | FastAPI server |
| API Docs | http://localhost:8000/docs | Swagger UI |
| Discord Bot | - | Runs with backend |

---

## Docker Deployment

### Build and Run

```bash
# Build the image
docker build -t eldenops .

# Run with environment file
docker run -d \
  --name eldenops \
  -p 8000:8000 \
  --env-file .env \
  eldenops

# Check logs
docker logs -f eldenops
```

### Docker Compose (Full Stack)

Create `docker-compose.yml`:

```yaml
version: '3.8'

services:
  api:
    build: .
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql+asyncpg://postgres:postgres@db:5432/eldenops
      - REDIS_URL=redis://redis:6379/0
    env_file:
      - .env
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_started
    restart: unless-stopped

  dashboard:
    build:
      context: ./dashboard
      dockerfile: Dockerfile
    ports:
      - "3000:3000"
    environment:
      - NEXT_PUBLIC_API_URL=http://localhost:8000
    depends_on:
      - api
    restart: unless-stopped

  db:
    image: postgres:15-alpine
    environment:
      - POSTGRES_USER=postgres
      - POSTGRES_PASSWORD=postgres
      - POSTGRES_DB=eldenops
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 5s
      timeout: 5s
      retries: 5
    restart: unless-stopped

  redis:
    image: redis:7-alpine
    volumes:
      - redis_data:/data
    restart: unless-stopped

volumes:
  postgres_data:
  redis_data:
```

Run with:

```bash
docker-compose up -d
```

### Dashboard Dockerfile

Create `dashboard/Dockerfile`:

```dockerfile
FROM node:18-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM node:18-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production
COPY --from=builder /app/next.config.js ./
COPY --from=builder /app/public ./public
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static

EXPOSE 3000
CMD ["node", "server.js"]
```

---

## Railway Deployment

Railway provides simple PaaS deployment with automatic builds.

### Setup

1. **Connect Repository**
   - Go to [railway.app](https://railway.app)
   - Click "New Project" > "Deploy from GitHub repo"
   - Select `EldenOps` repository

2. **Add PostgreSQL**
   - In your project, click "New" > "Database" > "PostgreSQL"
   - Railway automatically sets `DATABASE_URL`

3. **Add Redis**
   - Click "New" > "Database" > "Redis"
   - Railway automatically sets `REDIS_URL`

4. **Configure Environment Variables**
   - Go to your service > "Variables"
   - Add all required environment variables (see [Environment Configuration](#environment-configuration))

5. **Deploy**
   - Railway auto-deploys on git push
   - Or manually trigger via dashboard

### Railway Configuration

The project includes `railway.toml`:

```toml
[build]
builder = "dockerfile"
dockerfilePath = "Dockerfile"

[deploy]
startCommand = "python -m eldenops"
healthcheckPath = "/health"
healthcheckTimeout = 100
restartPolicyType = "on_failure"
restartPolicyMaxRetries = 3
```

### Custom Domain

1. Go to service settings > "Networking"
2. Click "Generate Domain" or add custom domain
3. Update `DISCORD_REDIRECT_URI` to use new domain
4. Update Discord Developer Portal OAuth redirects

---

## VPS/Cloud Deployment

For deployment on AWS, DigitalOcean, GCP, or any VPS.

### Server Setup (Ubuntu 22.04)

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Python 3.11
sudo add-apt-repository ppa:deadsnakes/ppa
sudo apt install python3.11 python3.11-venv python3.11-dev -y

# Install Node.js 18
curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
sudo apt install nodejs -y

# Install PostgreSQL
sudo apt install postgresql postgresql-contrib -y

# Install Redis
sudo apt install redis-server -y

# Install Nginx (reverse proxy)
sudo apt install nginx -y

# Install Certbot (SSL)
sudo apt install certbot python3-certbot-nginx -y
```

### Application Setup

```bash
# Create app user
sudo useradd -m -s /bin/bash eldenops
sudo su - eldenops

# Clone repository
git clone https://github.com/sws-apps/EldenOps.git
cd EldenOps

# Setup Python environment
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e .

# Setup frontend
cd dashboard && npm install && npm run build && cd ..

# Configure environment
cp .env.example .env
nano .env  # Edit with production values
```

### Database Setup

```bash
# Create PostgreSQL user and database
sudo -u postgres psql

CREATE USER eldenops WITH PASSWORD 'secure_password_here';
CREATE DATABASE eldenops OWNER eldenops;
GRANT ALL PRIVILEGES ON DATABASE eldenops TO eldenops;
\q

# Run migrations
source .venv/bin/activate
alembic upgrade head
```

### Systemd Service

Create `/etc/systemd/system/eldenops.service`:

```ini
[Unit]
Description=EldenOps API Server
After=network.target postgresql.service redis.service

[Service]
Type=simple
User=eldenops
WorkingDirectory=/home/eldenops/EldenOps
Environment="PATH=/home/eldenops/EldenOps/.venv/bin"
EnvironmentFile=/home/eldenops/EldenOps/.env
ExecStart=/home/eldenops/EldenOps/.venv/bin/python -m eldenops
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable eldenops
sudo systemctl start eldenops
sudo systemctl status eldenops
```

### Nginx Configuration

Create `/etc/nginx/sites-available/eldenops`:

```nginx
upstream eldenops_api {
    server 127.0.0.1:8000;
}

server {
    listen 80;
    server_name your-domain.com;

    # Redirect to HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name your-domain.com;

    # SSL certificates (managed by Certbot)
    ssl_certificate /etc/letsencrypt/live/your-domain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/your-domain.com/privkey.pem;

    # API proxy
    location /api {
        proxy_pass http://eldenops_api;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # WebSocket proxy
    location /ws {
        proxy_pass http://eldenops_api;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
    }

    # Health check
    location /health {
        proxy_pass http://eldenops_api;
    }

    # API docs
    location /docs {
        proxy_pass http://eldenops_api;
    }

    # Frontend (static files)
    location / {
        root /home/eldenops/EldenOps/dashboard/out;
        try_files $uri $uri/ /index.html;
    }
}
```

Enable the site:

```bash
sudo ln -s /etc/nginx/sites-available/eldenops /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

### SSL Certificate

```bash
sudo certbot --nginx -d your-domain.com
```

---

## Database Setup

### Initial Setup

```bash
# Create database (if not exists)
createdb eldenops

# The application auto-creates tables in development mode
# For production, use Alembic migrations:
alembic upgrade head
```

### Migrations

```bash
# Create a new migration after model changes
alembic revision --autogenerate -m "Description of changes"

# Apply pending migrations
alembic upgrade head

# Rollback last migration
alembic downgrade -1

# View migration history
alembic history
```

### Backup and Restore

```bash
# Backup
pg_dump eldenops > backup_$(date +%Y%m%d_%H%M%S).sql

# Restore
psql eldenops < backup_file.sql
```

### Multiple PostgreSQL Versions

If you have multiple PostgreSQL versions installed (common on macOS with Homebrew):

```bash
# List installed versions
brew services list | grep postgres

# Start specific version
brew services start postgresql@15

# Stop version
brew services stop postgresql@14

# Check which version is running
psql --version
```

Data is stored separately per version:
- PostgreSQL 14: `/opt/homebrew/var/postgresql@14/`
- PostgreSQL 15: `/opt/homebrew/var/postgresql@15/`

---

## Environment Configuration

### Required Variables

```bash
# Application
APP_ENV=production          # development, staging, production
APP_HOST=0.0.0.0
APP_PORT=8000
LOG_LEVEL=INFO

# Database
DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/eldenops

# Redis
REDIS_URL=redis://localhost:6379/0

# Discord
DISCORD_BOT_TOKEN=your_bot_token
DISCORD_CLIENT_ID=your_client_id
DISCORD_CLIENT_SECRET=your_client_secret
DISCORD_REDIRECT_URI=https://your-domain.com/auth/callback

# Security (generate with: openssl rand -hex 32)
JWT_SECRET_KEY=your_jwt_secret
ENCRYPTION_KEY=your_encryption_key

# AI Provider (at least one required)
ANTHROPIC_API_KEY=sk-ant-...
```

### Production Security Checklist

- [ ] Generate unique `JWT_SECRET_KEY` for production
- [ ] Generate unique `ENCRYPTION_KEY` for production
- [ ] Use strong database password
- [ ] Enable SSL for database connection
- [ ] Update `DISCORD_REDIRECT_URI` to production domain
- [ ] Update Discord Developer Portal with production redirect URI
- [ ] Configure CORS in `app.py` for your domain only
- [ ] Set `APP_ENV=production`

---

## Post-Deployment Checklist

### Verify Services

```bash
# Check API health
curl https://your-domain.com/health

# Check API docs load
curl -I https://your-domain.com/docs

# Check WebSocket endpoint
curl -I https://your-domain.com/ws
```

### Verify Discord Integration

1. Bot appears online in your Discord server
2. Slash commands are available (`/status`, `/checkin`, etc.)
3. OAuth login works from the dashboard

### Verify GitHub Integration

1. Webhook is receiving events (check GitHub webhook deliveries)
2. Events are being stored in database

### Monitor Logs

```bash
# Systemd
sudo journalctl -u eldenops -f

# Docker
docker logs -f eldenops

# Railway
# View in Railway dashboard > Deployments > Logs
```

---

## Troubleshooting

### Database Connection Errors

| Error | Solution |
|-------|----------|
| `database "eldenops" does not exist` | Run `createdb eldenops` |
| `connection refused` | Ensure PostgreSQL is running |
| `authentication failed` | Check DATABASE_URL credentials |
| `relation does not exist` | Run `alembic upgrade head` or restart in dev mode |

### Discord Errors

| Error | Solution |
|-------|----------|
| `Invalid redirect_uri` | Update DISCORD_REDIRECT_URI and Discord Developer Portal |
| `Bot not responding` | Check DISCORD_BOT_TOKEN and bot intents |
| `Missing Access` | Ensure bot has required permissions in channel |

### Port Conflicts

```bash
# Find process using port
lsof -i :3000
lsof -i :8000

# Kill process
kill -9 <PID>

# Or use different port
npm run dev -- -p 3005
```

### SSL/Certificate Issues

```bash
# Renew certificate
sudo certbot renew

# Test nginx config
sudo nginx -t

# Reload nginx
sudo systemctl reload nginx
```

---

## Support

For issues and questions:
- GitHub Issues: https://github.com/sws-apps/EldenOps/issues
- Documentation: See `docs/` folder
