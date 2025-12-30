# EldenOps Attendance Tracking System - Design Specification

## Overview

An AI-powered attendance and behavior tracking system that monitors Discord channels to track team member check-ins, check-outs, and breaks. Provides real-time status visibility and behavioral analytics.

---

## 1. Core Concepts

### Event Types
| Event | Description | Example Messages |
|-------|-------------|------------------|
| `CHECKIN` | Start of work day | "Good morning!", "Starting work", "IN" |
| `CHECKOUT` | End of work day | "Logging off", "Done for today", "OUT" |
| `BREAK_START` | Taking a break | "BRB lunch", "Taking 15", "Break - errands" |
| `BREAK_END` | Returning from break | "Back", "I'm here", "Resuming work" |

### User Status (Derived)
| Status | Meaning |
|--------|---------|
| `ACTIVE` | Checked in, not on break |
| `ON_BREAK` | Checked in, currently on break |
| `OFFLINE` | Not checked in or checked out |
| `UNKNOWN` | No recent activity |

---

## 2. Database Schema

### 2.1 AttendanceLog (New Table)

```sql
CREATE TABLE attendance_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,

    -- Event classification
    event_type VARCHAR(20) NOT NULL,  -- CHECKIN, CHECKOUT, BREAK_START, BREAK_END
    confidence FLOAT,                  -- AI confidence score (0-1)

    -- Timing
    event_time TIMESTAMP WITH TIME ZONE NOT NULL,
    expected_return_time TIMESTAMP WITH TIME ZONE,  -- For breaks
    actual_duration_minutes INT,                     -- Calculated after break ends

    -- Context (AI-extracted)
    reason VARCHAR(255),              -- "lunch", "errand", "rest", "meeting", etc.
    reason_category VARCHAR(50),      -- MEAL, PERSONAL, REST, MEETING, OTHER
    urgency VARCHAR(20),              -- NORMAL, URGENT (e.g., emergency)
    notes TEXT,                       -- Additional context from message

    -- Source
    channel_id BIGINT NOT NULL,
    message_id BIGINT NOT NULL,
    raw_message TEXT,                 -- Original message for audit/reprocessing

    -- Metadata
    parsed_by VARCHAR(50),            -- 'ai', 'regex', 'manual'
    ai_model VARCHAR(50),             -- Model used for parsing
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    -- Indexes
    INDEX idx_attendance_tenant_user (tenant_id, user_id),
    INDEX idx_attendance_event_time (event_time),
    INDEX idx_attendance_event_type (event_type)
);
```

### 2.2 UserAttendanceStatus (Materialized/Cached)

```sql
CREATE TABLE user_attendance_status (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,

    -- Current status
    status VARCHAR(20) NOT NULL,      -- ACTIVE, ON_BREAK, OFFLINE, UNKNOWN
    last_checkin_at TIMESTAMP WITH TIME ZONE,
    last_checkout_at TIMESTAMP WITH TIME ZONE,
    last_break_start_at TIMESTAMP WITH TIME ZONE,
    current_break_reason VARCHAR(255),
    expected_return_at TIMESTAMP WITH TIME ZONE,

    -- Today's summary (reset daily)
    today_checkin_at TIMESTAMP WITH TIME ZONE,
    today_total_break_minutes INT DEFAULT 0,
    today_break_count INT DEFAULT 0,

    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    UNIQUE(tenant_id, user_id)
);
```

### 2.3 AttendancePattern (Analytics)

```sql
CREATE TABLE attendance_patterns (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,

    -- Computed patterns (updated weekly)
    avg_checkin_time TIME,            -- e.g., 09:15
    avg_checkout_time TIME,           -- e.g., 18:30
    avg_work_hours_per_day FLOAT,     -- e.g., 8.5
    avg_breaks_per_day FLOAT,         -- e.g., 2.3
    avg_break_duration_minutes FLOAT, -- e.g., 18.5

    -- Day-of-week patterns (JSONB)
    weekly_patterns JSONB,            -- {"monday": {"avg_checkin": "09:00", ...}, ...}

    -- Break patterns
    common_break_times JSONB,         -- ["12:00-12:30", "15:00-15:15"]
    common_break_reasons JSONB,       -- {"lunch": 45%, "rest": 30%, ...}

    -- Anomaly thresholds (auto-calculated)
    late_checkin_threshold TIME,      -- checkin > this is "late"
    long_break_threshold_minutes INT, -- break > this is "long"

    period_start DATE NOT NULL,
    period_end DATE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    UNIQUE(tenant_id, user_id, period_start)
);
```

### 2.4 MonitoredChannel Updates

Add to `tracking_config` JSONB:
```json
{
  "channel_purpose": "attendance",  // "attendance" | "general" | "voice"
  "parse_mode": "ai",               // "ai" | "regex" | "both"
  "notify_on_anomaly": true,
  "auto_reminder_minutes": 480      // Remind if no checkout after 8hrs
}
```

---

## 3. AI Message Parser

### 3.1 Parser Input/Output

**Input:**
```json
{
  "message": "Taking a quick break, grabbing lunch. Back in 30 min",
  "author": "kat.hervera",
  "timestamp": "2024-01-15T12:05:00Z",
  "channel": "attendance"
}
```

**Output:**
```json
{
  "event_type": "BREAK_START",
  "confidence": 0.95,
  "reason": "grabbing lunch",
  "reason_category": "MEAL",
  "expected_duration_minutes": 30,
  "urgency": "NORMAL",
  "notes": null
}
```

### 3.2 Parser Prompt Template

```
You are an attendance message parser. Analyze the following Discord message and extract attendance information.

Message: "{message}"
Author: {author}
Time: {timestamp}
Previous status: {previous_status}

Determine:
1. event_type: CHECKIN, CHECKOUT, BREAK_START, BREAK_END, or NONE (not attendance-related)
2. confidence: 0.0 to 1.0
3. reason: Brief description if applicable
4. reason_category: MEAL, PERSONAL, REST, MEETING, EMERGENCY, OTHER, or null
5. expected_duration_minutes: Integer or null
6. urgency: NORMAL or URGENT
7. notes: Any additional relevant context

Respond in JSON format only.
```

### 3.3 Regex Patterns (EldenDev Team Specific)

Based on actual team usage in `#checkin-status`:

```python
PATTERNS = {
    "CHECKIN": [
        r"(?i)^[✅☑️]?\s*available",           # "✅ Available" or "Available"
        r"(?i)^(good\s*morning|gm|online|in\b)",
    ],
    "CHECKOUT": [
        r"(?i)^[👋🖐️]?\s*signing\s*out",       # "👋 Signing Out"
        r"(?i)^(logging\s*off|out\b|eod|done)",
    ],
    "BREAK_START": [
        r"(?i)^brb(\s*-\s*(?P<reason>.+))?",  # "BRB" or "BRB - reason here"
        r"(?i)^(break|afk|lunch|stepping\s*out)",
    ],
    "BREAK_END": [
        r"(?i)^back\s*$",                      # "back"
        r"(?i)^(i'?m\s*back|here|returned)",
    ]
}

# Extract reason from BRB messages
def parse_brb_reason(message: str) -> str | None:
    """Extract reason from 'BRB - reason' format."""
    match = re.match(r"(?i)^brb\s*-\s*(.+)", message)
    return match.group(1).strip() if match else None
```

**Example Messages (from actual Discord):**
| Time | User | Message | Parsed As |
|------|------|---------|-----------|
| 9:54 AM | Alvin | ✅ Available | CHECKIN |
| 1:02 PM | Alvin | BRB | BREAK_START |
| 1:59 PM | Alvin | back | BREAK_END |
| 2:25 PM | Byron | BRB - Need to get my daughter's eyeglass get fixed. will be quick. | BREAK_START (reason: "Need to get my daughter's eyeglass get fixed. will be quick.") |
| 4:37 PM | Byron | back | BREAK_END |
| 7:00 PM | Alvin | 👋 Signing Out | CHECKOUT |

---

## 4. API Endpoints

### 4.1 Real-time Status

```
GET /api/v1/attendance/status
```
Returns current status for all team members:
```json
{
  "team_status": [
    {
      "user_id": "uuid",
      "discord_username": "kat.hervera",
      "status": "ON_BREAK",
      "since": "2024-01-15T12:05:00Z",
      "break_reason": "lunch",
      "expected_return": "2024-01-15T12:35:00Z",
      "today_stats": {
        "checkin_at": "2024-01-15T09:12:00Z",
        "break_count": 2,
        "total_break_minutes": 25
      }
    }
  ],
  "summary": {
    "active": 5,
    "on_break": 2,
    "offline": 3
  }
}
```

### 4.2 User History

```
GET /api/v1/attendance/users/{user_id}/history?days=7
```
Returns attendance log for a user.

### 4.3 User Patterns

```
GET /api/v1/attendance/users/{user_id}/patterns
```
Returns behavioral patterns:
```json
{
  "user_id": "uuid",
  "patterns": {
    "avg_checkin_time": "09:15",
    "avg_checkout_time": "18:30",
    "avg_work_hours": 8.5,
    "avg_breaks_per_day": 2.3,
    "avg_break_duration": 18,
    "weekly_patterns": {
      "monday": {"avg_checkin": "09:00", "avg_breaks": 2},
      "friday": {"avg_checkin": "09:30", "avg_breaks": 3}
    },
    "common_break_reasons": {
      "lunch": 45,
      "rest": 30,
      "meeting": 15,
      "personal": 10
    }
  },
  "anomalies_this_week": [
    {
      "date": "2024-01-14",
      "type": "late_checkin",
      "expected": "09:15",
      "actual": "11:30",
      "deviation_minutes": 135
    }
  ]
}
```

### 4.4 Team Analytics

```
GET /api/v1/attendance/analytics?days=30
```
Returns team-wide analytics and AI insights.

### 4.5 Manual Correction

```
POST /api/v1/attendance/logs/{log_id}/correct
```
For admin to correct misclassified events.

---

## 5. Dashboard UI

### 5.1 Live Status Panel

```
┌─────────────────────────────────────────────────────────┐
│  Team Status                            [Auto-refresh]  │
├─────────────────────────────────────────────────────────┤
│  🟢 Active (5)    🟡 On Break (2)    ⚫ Offline (3)     │
├─────────────────────────────────────────────────────────┤
│  👤 kat.hervera      🟢 Active      Since 9:12 AM      │
│  👤 john.doe         🟡 Lunch       Back ~12:35 PM     │
│  👤 jane.smith       🟢 Active      Since 8:45 AM      │
│  👤 bob.wilson       ⚫ Offline     Last: Yesterday    │
└─────────────────────────────────────────────────────────┘
```

### 5.2 User Detail View

- Timeline of today's events
- Week view calendar
- Pattern charts (line chart of check-in times over past month)
- Break distribution pie chart
- Anomaly highlights

### 5.3 Team Analytics View

- Average team check-in/out times
- Total team hours per day (trend)
- Break patterns across team
- AI-generated weekly summary

---

## 6. AI Insights Engine

### 6.1 Daily Digest (Scheduled)

Generated each evening:
```
## EldenDev Team - Daily Attendance Summary (Jan 15, 2024)

**Team Activity:**
- 8/10 members checked in today
- Average work hours: 7.8 hrs
- Total breaks: 23 (avg 18 min each)

**Notable Patterns:**
- 🕐 John's check-in time shifted 2hrs later this week (was 9am, now 11am)
- ☕ Team takes 40% more breaks on Fridays
- ⚠️ Sarah hasn't stated break reasons last 3 days

**Recommendations:**
- Consider checking in with John about schedule change
- Friday afternoon meetings might benefit from earlier scheduling
```

### 6.2 Real-time Alerts

- Long break alert: "John has been on break for 2+ hours (expected: 30 min)"
- No checkout alert: "Sarah hasn't checked out after 10 hours"
- Pattern deviation: "Bob checked in 3 hours later than usual"

---

## 7. Implementation Phases

### Phase 1: Core Infrastructure (Week 1)
- [ ] Create database migrations for new tables
- [ ] Implement AttendanceLog model and basic CRUD
- [ ] Set up attendance channel monitoring (separate from general messages)
- [ ] Basic regex parser for immediate functionality

### Phase 2: AI Parser (Week 2)
- [ ] Integrate Claude API for message parsing
- [ ] Implement confidence thresholds and fallback logic
- [ ] Add manual correction endpoint
- [ ] Build status computation service

### Phase 3: Real-time Dashboard (Week 3)
- [ ] Live status API endpoint
- [ ] WebSocket or polling for real-time updates
- [ ] Dashboard UI components
- [ ] User detail view

### Phase 4: Analytics & Insights (Week 4)
- [ ] Pattern computation job (daily/weekly)
- [ ] Historical analytics API
- [ ] AI insights generation
- [ ] Daily digest reports

### Phase 5: Refinement (Ongoing)
- [ ] Anomaly detection tuning
- [ ] User feedback incorporation
- [ ] Performance optimization
- [ ] Additional integrations

---

## 8. Configuration

### Environment Variables
```bash
# Attendance-specific settings
ATTENDANCE_AI_CONFIDENCE_THRESHOLD=0.7        # Below this, use regex
ATTENDANCE_LONG_BREAK_ALERT_HOURS=2           # Alert if break > 2hrs without return
ATTENDANCE_NO_CHECKOUT_HOURS=10               # Alert if no checkout after 10hrs
```

### Channel Configuration (EldenDev)
| Channel | Purpose | Monitor For |
|---------|---------|-------------|
| `#checkin-status` | Primary attendance | CHECKIN, CHECKOUT, short BRB |
| `#extended-breaks` | Extended breaks (1hr+) | BREAK_START with detailed reason |

**Rules:**
- `#checkin-status`: Regular check-ins, check-outs, and quick breaks
- `#extended-breaks`: When break will be 1+ hour, must include reason
- Alert if break > 2 hours without "back" message in either channel

### Tenant Settings (in tenant.settings JSONB)
```json
{
  "attendance": {
    "enabled": true,
    "channels": ["attendance", "standup"],
    "timezone": "Asia/Manila",
    "work_day_start": "08:00",
    "work_day_end": "18:00",
    "notify_admins_on_anomaly": true,
    "daily_digest_time": "18:00",
    "digest_channel_id": 123456789
  }
}
```

---

## 9. Privacy Considerations

1. **Message Content**: Raw messages stored for audit/reprocessing but not displayed
2. **AI Processing**: Messages processed but not stored in AI provider's systems (use Claude's privacy-preserving options)
3. **Data Retention**: Configurable retention period (default: 90 days for logs, forever for patterns)
4. **Access Control**: Only tenant admins can view individual user patterns
5. **Opt-out**: Users can request their attendance data not be tracked (requires admin approval)

---

## 10. Open Questions

1. Should breaks have a maximum "expected" duration before auto-alerting?
2. Should the system auto-checkout users at end of day if they forget?
3. Do we need integration with external HR/time-tracking systems?
4. Should users be able to see their own patterns, or admin-only?
