# EldenOps

Multi-tenant team analytics platform combining Discord and GitHub data with AI-powered insights.

## Overview

EldenOps provides comprehensive visibility into team productivity, work patterns, and development velocity by integrating Discord activity tracking with GitHub analytics. The platform uses AI to generate intelligent reports and insights, helping teams understand their operational health.

### Key Features

- **Real-time Attendance Tracking** - Automatic check-in/check-out detection from Discord messages with AI-enhanced context understanding
- **Development Analytics** - GitHub commit, PR, and issue tracking with contributor metrics and activity heatmaps
- **AI-Powered Reports** - Scheduled and on-demand report generation using Claude, OpenAI, or Gemini
- **Multi-Tenant Architecture** - Discord guild-based isolation with per-tenant configuration
- **Live Dashboard** - Real-time updates via WebSocket with interactive charts

## Tech Stack

### Backend
- **Framework**: FastAPI (Python 3.9+)
- **Database**: PostgreSQL with SQLAlchemy 2.0 (async)
- **Cache/Queue**: Redis with arq task worker
- **Integrations**: discord.py, PyGithub

### Frontend
- **Framework**: Next.js 14 (App Router)
- **UI**: React 18, Tailwind CSS, Radix UI
- **State**: Zustand, TanStack React Query
- **Charts**: Recharts

### AI Providers
- Anthropic Claude
- OpenAI GPT
- Google Gemini
- DeepSeek

## Quick Start

### Prerequisites

- Python 3.9+
- Node.js 18+
- PostgreSQL 14+
- Redis

### 1. Clone and Setup Environment

```bash
# Clone the repository
git clone https://github.com/your-org/eldenops.git
cd eldenops

# Create Python virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install Python dependencies
pip install -e ".[dev]"

# Install frontend dependencies
cd dashboard && npm install && cd ..
```

### 2. Configure Environment

```bash
# Copy example environment file
cp .env.example .env

# Edit .env with your credentials
```

Required environment variables:

| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | PostgreSQL connection string |
| `REDIS_URL` | Redis connection string |
| `DISCORD_BOT_TOKEN` | Discord bot token |
| `DISCORD_CLIENT_ID` | Discord OAuth client ID |
| `DISCORD_CLIENT_SECRET` | Discord OAuth client secret |
| `JWT_SECRET_KEY` | JWT signing key (generate with `openssl rand -hex 32`) |
| `ENCRYPTION_KEY` | Data encryption key (generate with `openssl rand -hex 32`) |

### 3. Setup Database

```bash
# Create the database
createdb eldenops

# Run migrations
alembic upgrade head
```

### 4. Start Services

```bash
# Terminal 1: Start backend (API + Discord bot)
source .venv/bin/activate
python -m eldenops

# Terminal 2: Start frontend
cd dashboard
npm run dev
```

The application will be available at:
- **Dashboard**: http://localhost:3000
- **API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs

## Project Structure

```
EldenOps/
├── src/eldenops/           # Python backend
│   ├── api/                # FastAPI routes & dependencies
│   │   └── routes/         # API endpoints
│   ├── ai/                 # AI provider abstraction
│   │   └── providers/      # Claude, OpenAI implementations
│   ├── db/                 # Database layer
│   │   └── models/         # SQLAlchemy models
│   ├── integrations/       # External services
│   │   ├── discord/        # Bot, cogs, event handlers
│   │   └── github/         # GitHub client & webhooks
│   ├── services/           # Business logic
│   ├── tasks/              # Background workers
│   ├── config/             # Settings & constants
│   └── core/               # Security, exceptions, logging
│
├── dashboard/              # Next.js frontend
│   └── src/
│       ├── app/            # App Router pages
│       ├── components/     # React components
│       ├── hooks/          # Custom hooks
│       └── lib/            # Utilities
│
├── alembic/                # Database migrations
├── docs/                   # Documentation
└── tests/                  # Test suite
```

## API Endpoints

### Authentication
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/auth/discord` | Start Discord OAuth |
| GET | `/api/v1/auth/discord/callback` | OAuth callback |
| POST | `/api/v1/auth/refresh` | Refresh access token |
| GET | `/api/v1/auth/me` | Get current user |

### Analytics
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/analytics/overview` | Overview metrics |
| GET | `/api/v1/analytics/activity` | Activity data for charts |
| GET | `/api/v1/analytics/users` | Per-user activity summary |

### Attendance
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/attendance/status` | Current team status |
| GET | `/api/v1/attendance/history` | Attendance log history |
| GET | `/api/v1/attendance/patterns` | Attendance patterns |

### Reports
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/reports/configs` | List report configs |
| POST | `/api/v1/reports/configs` | Create report config |
| POST | `/api/v1/reports/generate` | Generate on-demand report |
| GET | `/api/v1/reports/{id}` | Get report content |

### Projects
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/tenants/{id}/projects` | List projects |
| POST | `/api/v1/tenants/{id}/projects` | Create project |
| PUT | `/api/v1/tenants/{id}/projects/{id}` | Update project |

## Discord Bot Commands

### Admin Commands
- `/setup` - Initialize tenant configuration
- `/config channels` - Configure monitored channels
- `/config ai` - Configure AI provider

### Attendance Commands
- `/status` - View team attendance status
- `/checkin` - Manual check-in
- `/checkout` - Manual check-out
- `/break` - Start/end break

### Sync Commands
- `/sync github` - Sync GitHub data
- `/sync attendance` - Recalculate attendance patterns

## Configuration

### AI Provider Configuration

Each tenant can configure their own AI provider:

```python
# Per-tenant configuration in database
AIProviderConfig(
    tenant_id=tenant.id,
    provider="claude",  # claude, openai, gemini, deepseek
    api_key="sk-...",
    model="claude-sonnet-4-20250514",
    is_default=True
)
```

### Report Scheduling

Reports can be scheduled using cron expressions:

```python
ReportConfig(
    name="Weekly Team Summary",
    report_type="weekly_digest",
    schedule="0 9 * * MON",  # Every Monday at 9 AM
    filters={"channels": ["general", "dev"]},
    delivery={"discord_channel": "reports"}
)
```

## Development

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=eldenops --cov-report=term-missing

# Run specific test file
pytest tests/test_attendance.py
```

### Code Quality

```bash
# Linting
ruff check src/

# Type checking
mypy src/

# Formatting
black src/
```

### Database Migrations

```bash
# Create a new migration
alembic revision --autogenerate -m "Description"

# Apply migrations
alembic upgrade head

# Rollback one migration
alembic downgrade -1
```

## Deployment

### Docker

```bash
docker build -t eldenops .
docker run -p 8000:8000 --env-file .env eldenops
```

### Railway

The project includes `railway.toml` for Railway.app deployment:

```bash
railway up
```

## Documentation

- [Quick Start Guide](docs/QUICKSTART.md) - 10-minute setup
- [Setup Guide](docs/SETUP_GUIDE.md) - Detailed configuration
- [Attendance System Design](docs/ATTENDANCE_SYSTEM_DESIGN.md) - Technical design

## License

MIT License - see [LICENSE](LICENSE) for details.
