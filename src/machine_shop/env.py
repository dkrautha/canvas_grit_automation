import os

def get_quiz_ids() -> dict[str, int]:
    ENV = os.getenv("CANVAS_QUIZ_IDS")
    if ENV is None:
        raise ValueError("CANVAS_QUIZ_IDS not set")
    PAIRS = ENV.split(",")
    LIST_OF_PAIRS = [pair.split("=") for pair in PAIRS]
    return {pair[0]: int(pair[1]) for pair in LIST_OF_PAIRS}


def try_get_env(key: str) -> str:
    if (ENV := os.getenv(key)) is None:
        raise ValueError(f"{key} not set")
    return ENV
