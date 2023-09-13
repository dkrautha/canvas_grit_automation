import os


def get_env_or_raise(key: str) -> str:
    if (env := os.getenv(key)) is None:
        raise ValueError(f"{key} not set in environment")
    return env


def get_quiz_ids() -> dict[str, int]:
    env = get_env_or_raise("CANVAS_QUIZ_IDS")
    pairs = env.split(",")
    list_of_pairs = [pair.split("=") for pair in pairs]
    return {pair[0]: int(pair[1]) for pair in list_of_pairs}
