"""The smallest difference between two arms the frozen question set can detect under the bet's rule.

Measures: for n questions, k runs per question and arm, the smallest true difference in accuracy between two
arms that the rule (RULE.md: per-question paired differences of the share of runs right, a percentile
bootstrap 95% interval over questions, "different" when it excludes zero) detects in 80% of simulated evals.
The simulation draws each question's chance of a right answer per arm as logistic(arm + question + interaction):
a shared question difficulty (most questions are easy or hard for every arm) plus an arm-by-question term
(what one arm knows and another does not), then k Bernoulli runs per arm; the shift between arms is solved
for the accuracy difference it gives. Its spreads are assumptions, printed with the result.
Run (from the repo root): python3 -I docs/research/semantic-bet/probes/325_power.py [n ...]
Offline: no files, no network, no model calls; pure standard library, seeded, about a minute.
"""

import math
import random
import sys

QUESTION_SD = 2.0  # shared difficulty: most questions right or wrong for every arm
INTERACTION_SD = 1.0  # what one arm gets that another does not, per question
BASE = 1.0  # arm A's logit offset: about 0.67 accuracy
SIMS = 300
BOOT = 600
POWER = 0.8


def logistic(x: float) -> float:
    return 1 / (1 + math.exp(-x))


def one_eval(
    rng: random.Random, n: int, k: int, shift: float
) -> tuple[list[float], float]:
    """Per-question differences (B minus A, share of k runs right) and the true accuracy difference."""
    diffs, true_diff = [], 0.0
    for _ in range(n):
        q = rng.gauss(0, QUESTION_SD)
        pa = logistic(BASE + q + rng.gauss(0, INTERACTION_SD))
        pb = logistic(BASE + shift + q + rng.gauss(0, INTERACTION_SD))
        true_diff += pb - pa
        a = sum(rng.random() < pa for _ in range(k)) / k
        b = sum(rng.random() < pb for _ in range(k)) / k
        diffs.append(b - a)
    return diffs, true_diff / n


def interval(rng: random.Random, diffs: list[float]) -> tuple[float, float]:
    """The percentile bootstrap 95% interval of the mean paired difference, resampling questions."""
    n = len(diffs)
    means = sorted(sum(rng.choice(diffs) for _ in range(n)) / n for _ in range(BOOT))
    return means[int(0.025 * BOOT)], means[int(0.975 * BOOT) - 1]


def power(n: int, k: int, shift: float, seed: int) -> tuple[float, float]:
    rng = random.Random(seed)
    hits, true = 0, 0.0
    for _ in range(SIMS):
        diffs, t = one_eval(rng, n, k, shift)
        lo, hi = interval(rng, diffs)
        hits += lo > 0 or hi < 0
        true += t
    return hits / SIMS, true / SIMS


def smallest_detectable(n: int, k: int) -> tuple[float, float]:
    """Bisect the logit shift for 80% power; return (accuracy difference, power there)."""
    lo, hi = 0.0, 3.0
    for step in range(9):
        mid = (lo + hi) / 2
        p, _ = power(n, k, mid, seed=step)
        lo, hi = (lo, mid) if p >= POWER else (mid, hi)
    p, diff = power(n, k, hi, seed=99)
    return diff, p


def main() -> int:
    sizes = [int(a) for a in sys.argv[1:]] or [80, 120]
    print(
        f"spreads: question {QUESTION_SD}, interaction {INTERACTION_SD}; arm A ~{logistic(BASE):.2f}"
    )
    print(f"sims {SIMS}, bootstrap {BOOT}, power {POWER}")
    print("n\tk\tsmallest detectable accuracy difference (points)\tpower there")
    for n in sizes:
        for k in (1, 3, 5):
            diff, p = smallest_detectable(n, k)
            print(f"{n}\t{k}\t{100 * diff:.1f}\t{p:.2f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
