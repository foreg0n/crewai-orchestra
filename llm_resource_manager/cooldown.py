import time
from .storage import KeyState, KeyStatus


class CooldownManager:
    # Cooldown duration in seconds by error type
    COOLDOWN_MAP = {
        429: 60,        # Rate limit — wait one minute
        "minute": 60,   # TPM/RPM limit exceeded
        "day": 86400,   # TPD limit exceeded — until next day
        "default": 30,  # Unknown error
    }

    def put_on_cooldown(self, state: KeyState, reason: str = "default",
                        retry_after: float = None):
        duration = retry_after or self.COOLDOWN_MAP.get(reason,
                   self.COOLDOWN_MAP["default"])
        state.status = KeyStatus.COOLDOWN
        state.cooldown_until = time.time() + duration
        state.errors += 1
        print(f"[COOLDOWN] {state.provider} key ...{state.key[:8]} "
              f"→ cooldown for {duration}s (reason: {reason})")

    def parse_retry_after(self, error_body: dict) -> tuple[str, float]:
        """Parse 429 response from provider"""
        msg = str(error_body.get("error", {}).get("message", "")).lower()

        # Groq returns "Please try again in Xs"
        import re
        match = re.search(r"try again in (\d+(?:\.\d+)?)(m|s)", msg)
        if match:
            val = float(match.group(1))
            unit = match.group(2)
            seconds = val * 60 if unit == "m" else val
            reason = "day" if seconds > 3600 else "minute"
            return reason, seconds

        if "day" in msg or "daily" in msg:
            return "day", 86400
        if "minute" in msg or "per minute" in msg:
            return "minute", 60

        return "default", 30