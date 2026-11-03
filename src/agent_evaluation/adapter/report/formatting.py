def percent(value: float | None) -> str:
    return "-" if value is None else f"{value * 100:.0f} %"


def seconds(value: float | None) -> str:
    if value is None:
        return "-"
    if value < 60:
        return f"{value:.1f} s"
    minutes, rest = divmod(int(value), 60)
    return f"{minutes} min {rest:02d} s"


def tokens(value: int) -> str:
    return f"{value / 1000:.1f}k" if value >= 1000 else str(value)


def score(value: float | None) -> str:
    return "-" if value is None else f"{value:.2f}"


def cell(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " ")


def excerpt(text: str, limit: int = 400) -> str:
    flat = " ".join(text.split())
    return flat if len(flat) <= limit else f"{flat[: limit - 1]}…"
