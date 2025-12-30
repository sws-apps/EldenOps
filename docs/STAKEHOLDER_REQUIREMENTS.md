# EldenOps - Stakeholder Requirements

## Overview

EldenOps is a team operations platform that combines Discord attendance tracking with GitHub development analytics to provide comprehensive visibility into team productivity and work patterns.

---

## Stakeholder Needs

### Operations Manager / Team Lead

**Primary Goal:** Real-time team visibility and attendance accountability

**Key Questions:**
- Who is currently working? Who is on break? Who hasn't checked in yet?
- Are team members following expected work hours?
- Is there adequate coverage during business hours?
- Are breaks reasonable in frequency and duration?

**Required Features:**
| Feature | Priority | Description |
|---------|----------|-------------|
| Real-time status dashboard | High | See who's active, on break, or offline at a glance |
| Check-in/check-out tracking | High | Automatic detection from Discord messages |
| Break monitoring | High | Track break frequency, duration, and stated reasons |
| Late arrival alerts | Medium | Notification when someone checks in late |
| Extended break alerts | Medium | Alert when breaks exceed threshold (e.g., 2 hours) |
| Daily attendance summary | Medium | End-of-day report showing attendance for the team |
| Coverage gaps | Low | Identify times when team availability is low |

**Key Metrics:**
- Average check-in time per team member
- Average work hours per day
- Break frequency and average duration
- Attendance rate (days present / expected days)

---

### CTO / Engineering Manager

**Primary Goal:** Development velocity and team productivity insights

**Key Questions:**
- How productive is the team? Is output increasing or decreasing?
- Who are the top contributors? Who might need support?
- Where are the bottlenecks in the development process?
- When is the team most productive?
- Is workload distributed fairly across the team?

**Required Features:**
| Feature | Priority | Description |
|---------|----------|-------------|
| Commit tracking | High | Track commits per developer, per repo |
| PR analytics | High | PRs opened, merged, time-to-merge, review time |
| Contributor leaderboard | High | Rank team members by output |
| Code velocity trends | High | Week-over-week commit/PR trends |
| Activity heatmap | Medium | When does the team work? (hour/day patterns) |
| PR review bottlenecks | Medium | Identify PRs waiting for review |
| Issue tracking | Medium | Issues opened, closed, time-to-close |
| Workload distribution | Low | Visualize work distribution across team |

**Key Metrics:**
- Commits per developer per week
- PRs merged per week
- Average time from PR open to merge
- Code churn (lines added/deleted)
- Issue closure rate

---

### CEO / Executive Leadership

**Primary Goal:** High-level team health and ROI visibility

**Key Questions:**
- Is the team productive? Are we getting value for payroll?
- What are the trends? Is productivity improving or declining?
- Are there any red flags (burnout, disengagement)?
- How do we compare to industry benchmarks?

**Required Features:**
| Feature | Priority | Description |
|---------|----------|-------------|
| Executive dashboard | High | Single-page summary of key metrics |
| Weekly/monthly reports | High | Automated summary reports |
| Productivity trends | High | Month-over-month output comparison |
| Team utilization | Medium | Average hours worked vs expected |
| Health indicators | Medium | Overtime hours, weekend work (burnout risk) |
| Cost efficiency | Low | Output metrics relative to team size/cost |

**Key Metrics:**
- Team utilization rate (hours worked / expected hours)
- Productivity score (composite of commits, PRs, attendance)
- Trend indicators (up/down vs previous period)
- Health score (based on work-life balance indicators)

---

### Individual Team Members

**Primary Goal:** Personal visibility and fair tracking

**Key Questions:**
- Are my contributions being tracked accurately?
- How do I compare to my past performance?
- Is the tracking fair and transparent?

**Required Features:**
| Feature | Priority | Description |
|---------|----------|-------------|
| Personal dashboard | Medium | View own attendance and contribution stats |
| Self-service history | Medium | See own check-in/check-out history |
| Privacy controls | Medium | Understand what is being tracked |
| Achievement recognition | Low | Highlight personal milestones |

---

## Feature Priority Matrix

### Phase 1: Attendance Foundation (Current)
- [x] Discord check-in/check-out detection
- [x] Break tracking with reasons
- [x] Real-time team status dashboard
- [x] Attendance insights (patterns, timing)
- [ ] Daily attendance summary

### Phase 2: GitHub Integration
- [ ] Connect GitHub repositories
- [ ] Track commits, PRs, issues
- [ ] Contributor analytics
- [ ] Development velocity metrics

### Phase 3: Reporting & Alerts
- [ ] Weekly summary reports (automated)
- [ ] Late check-in alerts
- [ ] Extended break alerts
- [ ] Email/Discord notifications

### Phase 4: Executive Features
- [ ] Executive summary dashboard
- [ ] Month-over-month trends
- [ ] Productivity scoring
- [ ] Export reports (PDF/CSV)

### Phase 5: Advanced Analytics
- [ ] AI-powered insights
- [ ] Anomaly detection
- [ ] Predictive analytics
- [ ] Custom report builder

---

## Data Points Tracked

### From Discord
| Data | Purpose | Retention |
|------|---------|-----------|
| Check-in time | Attendance tracking | 90 days |
| Check-out time | Work hours calculation | 90 days |
| Break start/end | Break pattern analysis | 90 days |
| Break reason | Accountability & patterns | 90 days |
| Channel | Context (which channel used) | 90 days |

### From GitHub
| Data | Purpose | Retention |
|------|---------|-----------|
| Commits | Productivity tracking | 90 days |
| PRs (opened/merged) | Output measurement | 90 days |
| Issues (opened/closed) | Work tracking | 90 days |
| Lines changed | Code volume | 90 days |
| Review activity | Collaboration metrics | 90 days |

---

## Success Metrics

### For Operations
- Reduce time spent manually tracking attendance by 80%
- Identify attendance issues within 24 hours instead of weeks
- Improve on-time check-in rate by 15%

### For Engineering Leadership
- Visibility into team velocity without manual reporting
- Identify bottlenecks in PR review process
- Balance workload distribution across team

### For Executive Leadership
- Weekly productivity reports without manual compilation
- Data-driven decisions on team structure
- Early warning on team health issues

---

## Privacy & Transparency

**Principles:**
1. Only track work-related activity in designated channels
2. No private message monitoring
3. Team members can view their own data
4. Clear communication about what is tracked
5. Data used for insights, not punishment

**What We DON'T Track:**
- Private messages or DMs
- Personal Discord servers
- Activity outside work hours (unless in work channels)
- Screen time or keystroke monitoring
- Location data

---

## Implementation Notes

### Current State
- Discord bot deployed and tracking attendance
- Dashboard showing real-time team status
- Behavioral insights (check-in times, break patterns)

### Next Steps
1. Add GitHub repository connections
2. Build GitHub analytics dashboard
3. Create automated weekly reports
4. Add alert system for concerning patterns

---

*Document Version: 1.0*
*Last Updated: December 2024*
