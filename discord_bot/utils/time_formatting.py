# --- Time Formatting ---

def format_time(seconds: int) -> str:
    """Formats seconds into a human-readable string (e.g., 1h 5m 30s)."""
    if seconds < 0:
        seconds = 0  # Or handle negative display if needed
    m, s = divmod(seconds, 60)
    h, m = divmod(m, 60)
    parts = []
    if h > 0:
        parts.append(f"{h}h")
    if m > 0:
        parts.append(f"{m}m")
    if s > 0 or not parts:  # Show seconds if it's non-zero or if hours/minutes are zero
        parts.append(f"{s}s")
    return " ".join(parts) if parts else "0s"
