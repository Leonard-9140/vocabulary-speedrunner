"""FSRS-4.5 memory model and interval calculations.

Formulas and default weights follow the pinned open-spaced-repetition wiki
reference listed in readme.md. The application maps binary answers to Again
(1) and Good (3).
"""

import math


DEFAULT_WEIGHTS = (
    0.4, 0.6, 2.4, 5.8, 4.93, 0.94, 0.86, 0.01, 1.49,
    0.14, 0.94, 2.18, 0.05, 0.34, 1.26, 0.29, 2.61,
)
DECAY = -0.5
FACTOR = 19 / 81
MIN_STABILITY_DAYS = 0.1
MAX_STABILITY_DAYS = 36500.0


def initial_memory_state(grade, weights=DEFAULT_WEIGHTS):
    """Return initial (stability, difficulty) for an FSRS grade from 1 to 4."""
    if grade not in (1, 2, 3, 4):
        raise ValueError("FSRS grade must be between 1 and 4")
    stability = weights[grade - 1]
    difficulty = weights[4] - (grade - 3) * weights[5]
    return clamp_stability(stability), clamp_difficulty(difficulty)


def clamp_difficulty(difficulty):
    return min(10.0, max(1.0, difficulty))


def clamp_stability(stability):
    return min(MAX_STABILITY_DAYS, max(MIN_STABILITY_DAYS, stability))


def retrievability(elapsed_days, stability):
    """FSRS-4.5 power-law forgetting curve R(t,S)."""
    stability = clamp_stability(stability)
    elapsed_days = max(0.0, elapsed_days)
    return (1 + FACTOR * elapsed_days / stability) ** DECAY


def interval_days(stability, desired_retention=0.9, maximum_interval=36500):
    """Invert the forgetting curve and return a whole-day review interval."""
    if not 0 < desired_retention < 1:
        raise ValueError("desired_retention must be between 0 and 1")
    raw_interval = stability / FACTOR * (desired_retention ** (1 / DECAY) - 1)
    rounded_interval = math.floor(raw_interval + 0.5)
    return min(maximum_interval, max(1, rounded_interval))


def next_memory_state(stability, difficulty, elapsed_days, grade,
                      desired_retention=0.9, maximum_interval=36500,
                      weights=DEFAULT_WEIGHTS):
    """Update D/S after a review and calculate the next interval and recall rate."""
    if grade not in (1, 2, 3, 4):
        raise ValueError("FSRS grade must be between 1 and 4")

    old_stability = clamp_stability(stability)
    old_difficulty = clamp_difficulty(difficulty)
    recall_probability = retrievability(elapsed_days, old_stability)

    initial_good_difficulty = weights[4]
    difficulty_delta = old_difficulty - weights[6] * (grade - 3)
    new_difficulty = (
        weights[7] * initial_good_difficulty
        + (1 - weights[7]) * difficulty_delta
    )
    new_difficulty = clamp_difficulty(new_difficulty)

    if grade == 1:
        new_stability = (
            weights[11]
            * old_difficulty ** (-weights[12])
            * ((old_stability + 1) ** weights[13] - 1)
            * math.exp(weights[14] * (1 - recall_probability))
        )
    else:
        hard_penalty = weights[15] if grade == 2 else 1.0
        easy_bonus = weights[16] if grade == 4 else 1.0
        new_stability = old_stability * (
            math.exp(weights[8])
            * (11 - old_difficulty)
            * old_stability ** (-weights[9])
            * (math.exp(weights[10] * (1 - recall_probability)) - 1)
            * hard_penalty
            * easy_bonus
            + 1
        )
    new_stability = clamp_stability(new_stability)
    interval = interval_days(new_stability, desired_retention, maximum_interval)
    return {
        "stability": new_stability,
        "difficulty": new_difficulty,
        "retrievability": recall_probability,
        "interval_days": interval,
    }
