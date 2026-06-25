import re

PATTERNS = {
    "REVIEW_TASK": [
        r"(check|review|is it correct|find error)",
        r"(evaluate|is it valid|is it correct|double-check)",
    ],
    "CODE_TASK": [
        r"write (code|function|class|script|program)",
        r"(implement|write code)",
        r"(html|css|javascript|python|sql|bash)",
    ],
    "SUMMARY_TASK": [
        r"(summary|briefly|conclusion|overview|compress|retell)",
        r"(main points from|key points|key takeaways)",
    ],
    "SIMPLE_CHAT": [
        r"^(hello|hi|how are you)",
        r"(recommend|what do you think|thank you|got it|okay)",
    ],
}


def classify_task(text: str) -> str:
    text_lower = text.lower().strip()
    for task_type, patterns in PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, text_lower):
                return task_type
    return "ANALYSIS_TASK"