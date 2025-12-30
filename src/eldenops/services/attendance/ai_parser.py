"""AI-powered attendance message parser using OpenAI.

Uses OpenAI to intelligently detect attendance events from natural language messages,
handling variations in phrasing, emojis, and context.
"""

from __future__ import annotations

import json
from typing import Optional

from openai import OpenAI, APIError
import structlog

from eldenops.config.settings import settings
from eldenops.services.attendance.parser import (
    ParsedAttendance,
    ParsedEventType,
    BreakReasonCategory,
)

logger = structlog.get_logger()

# System prompt for attendance detection
SYSTEM_PROMPT = """You are an attendance tracking assistant that analyzes Discord messages from a team check-in channel.

Your job is to detect attendance events from messages. Team members post status updates in various formats:

**Check-in (starting work):**
- "✅ Available" or just "Available"
- "Good morning", "GM", "Online", "In"
- Emojis like ✅, 🟢, 👋 followed by availability
- Any message indicating they're starting work or are now available

**Check-out (ending work):**
- "👋 Signing Out" or "Signing Out"
- "EOD", "End of day", "Logging off", "Done for the day"
- "Good night", "GN", "Bye", "Leaving"
- Any message indicating they're done working

**Break Start (temporarily away):**
- "BRB", "BRB - reason", "AFK"
- "Taking a break", "Lunch", "Stepping out"
- Any message indicating temporary absence
- Look for reasons (lunch, errand, rest, meeting, etc.)
- Look for duration hints ("30 mins", "1 hour", "back in 15")

**Break End (returning from break):**
- "Back", "I'm back", "Here", "Returned"
- Any message indicating return from break

**Not an attendance event:**
- General chat, questions, work updates
- Messages that don't indicate status changes

Be flexible with:
- Different emoji usage or no emojis
- Typos and abbreviations
- Natural language variations
- Context clues"""

# Tool/function definition for structured output
ATTENDANCE_FUNCTION = {
    "name": "record_attendance",
    "description": "Record an attendance event detected from a message",
    "parameters": {
        "type": "object",
        "properties": {
            "event_type": {
                "type": "string",
                "enum": ["checkin", "checkout", "break_start", "break_end", "none"],
                "description": "The type of attendance event detected"
            },
            "confidence": {
                "type": "number",
                "minimum": 0,
                "maximum": 1,
                "description": "Confidence score from 0 to 1"
            },
            "reason": {
                "type": "string",
                "description": "For breaks, the reason given (if any)"
            },
            "reason_category": {
                "type": "string",
                "enum": ["meal", "personal", "rest", "meeting", "emergency", "other"],
                "description": "Category of the break reason"
            },
            "expected_duration_minutes": {
                "type": "integer",
                "description": "Expected duration in minutes (if mentioned)"
            },
            "urgency": {
                "type": "string",
                "enum": ["normal", "urgent"],
                "description": "Whether this seems urgent/emergency"
            }
        },
        "required": ["event_type", "confidence"]
    }
}


class AIAttendanceParser:
    """AI-powered attendance message parser using OpenAI."""

    def __init__(self):
        api_key = settings.openai_api_key.get_secret_value()
        if api_key:
            self.client = OpenAI(api_key=api_key)
            self.model = "gpt-4o-mini"  # Fast and cheap for simple classification
        else:
            self.client = None
            logger.warning("OpenAI API key not configured, AI parser disabled")

    @property
    def is_available(self) -> bool:
        """Check if AI parsing is available."""
        return self.client is not None

    async def parse(self, message: str) -> Optional[ParsedAttendance]:
        """Parse a message using OpenAI.

        Args:
            message: The Discord message content

        Returns:
            ParsedAttendance if detected, None if AI unavailable or error
        """
        if not self.client:
            return None

        message = message.strip()
        if not message:
            return ParsedAttendance(
                event_type=ParsedEventType.NONE,
                confidence=1.0,
                parsed_by="ai",
            )

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                max_tokens=256,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": f"Analyze this attendance message:\n\n{message}"}
                ],
                tools=[{"type": "function", "function": ATTENDANCE_FUNCTION}],
                tool_choice={"type": "function", "function": {"name": "record_attendance"}}
            )

            # Extract function call from response
            if response.choices and response.choices[0].message.tool_calls:
                tool_call = response.choices[0].message.tool_calls[0]
                if tool_call.function.name == "record_attendance":
                    args = json.loads(tool_call.function.arguments)
                    return self._parse_function_response(args)

            logger.warning("No function call in AI response", message=message[:50])
            return None

        except APIError as e:
            logger.error("OpenAI API error", error=str(e))
            return None
        except Exception as e:
            logger.error("AI parsing error", error=str(e), message=message[:50])
            return None

    def _parse_function_response(self, args: dict) -> ParsedAttendance:
        """Convert function response to ParsedAttendance."""
        event_type_str = args.get("event_type", "none")

        # Map string to enum
        event_type_map = {
            "checkin": ParsedEventType.CHECKIN,
            "checkout": ParsedEventType.CHECKOUT,
            "break_start": ParsedEventType.BREAK_START,
            "break_end": ParsedEventType.BREAK_END,
            "none": ParsedEventType.NONE,
        }
        event_type = event_type_map.get(event_type_str, ParsedEventType.NONE)

        # Map reason category
        reason_category = None
        if args.get("reason_category"):
            category_map = {
                "meal": BreakReasonCategory.MEAL,
                "personal": BreakReasonCategory.PERSONAL,
                "rest": BreakReasonCategory.REST,
                "meeting": BreakReasonCategory.MEETING,
                "emergency": BreakReasonCategory.EMERGENCY,
                "other": BreakReasonCategory.OTHER,
            }
            reason_category = category_map.get(args["reason_category"])

        return ParsedAttendance(
            event_type=event_type,
            confidence=args.get("confidence", 0.8),
            reason=args.get("reason"),
            reason_category=reason_category,
            expected_duration_minutes=args.get("expected_duration_minutes"),
            urgency=args.get("urgency", "normal"),
            parsed_by="ai",
        )


# Singleton instance
_ai_parser: Optional[AIAttendanceParser] = None


def get_ai_parser() -> AIAttendanceParser:
    """Get or create AI parser instance."""
    global _ai_parser
    if _ai_parser is None:
        _ai_parser = AIAttendanceParser()
    return _ai_parser
