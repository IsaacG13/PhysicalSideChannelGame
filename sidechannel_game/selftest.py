"""
selftest.py -- check that the difficulty settings in config.py do what you
think they do, WITHOUT launching the GUI.

    python selftest.py

It simulates many students (many random seeds) and reports:
  * Level 1: how often rounding the mean timing gives the right 1-bit count
  * Level 2: how often a simple automatic decoder reads the key from ONE trace
  * Level 3: how often it reads the key from the average of N traces
  * Protected device: the same decoder should do no better than chance

The decoder here is a testing tool, not part of the game.
"""

import numpy as np

import config as cfg
import sim

STUDENTS = 300          # number of random targets to try; raise for smoother numbers


def level1_success(n_runs: int) -> float:
    ok = 0
    for seed in range(STUDENTS):
        t = sim.Target(seed)
        mean_time = t.timing_runs(n_runs).mean()
        k_est = (mean_time - cfg.KEY_BITS * cfg.T_S_MS) / cfg.T_M_MS
        ok += t.check_count(round(k_est))
    return ok / STUDENTS


def decode(trace: np.ndarray, amplitude: float = 16.0):
    """Matched-filter decoder that knows the block layout. After each squaring
    it asks: do the next M samples look like a multiply block, or like
    'gap then next squaring'? Picks whichever fits better."""
    s, m, g = cfg.SAMPLES_PER_S, cfg.SAMPLES_PER_M, cfg.GAP_SAMPLES
    pos, bits = cfg.PAD_SAMPLES, []
    # Zero-pad so the last windows can't run off the end of the trace
    # (also protects against position drift after a decoding error).
    trace = np.concatenate([trace, np.zeros(cfg.KEY_BITS * (s + m + g))])
    for i in range(cfg.KEY_BITS):
        win = trace[pos + s: pos + s + m]
        last = i == cfg.KEY_BITS - 1
        tmpl_multiply = np.full(m, amplitude)
        tmpl_no_multiply = np.concatenate(
            [np.zeros(g), np.full(m - g, 0.0 if last else amplitude)])
        bit = int(np.sum((win - tmpl_multiply) ** 2)
                  < np.sum((win - tmpl_no_multiply) ** 2))
        bits.append(bit)
        pos += s + (m if bit else 0) + g
    return bits


def trace_success(sigma: float, n_traces: int, protected: bool = False) -> float:
    ok = 0
    for seed in range(STUDENTS):
        t = sim.Target(seed)
        avg = np.mean([t.acquire_trace(sigma, protected) for _ in range(n_traces)],
                      axis=0)
        ok += decode(avg) == t.key_bits
    return ok / STUDENTS


if __name__ == "__main__":
    print(f"({STUDENTS} simulated students per row)\n")

    print("LEVEL 1 - correct 1-bit count from rounding the mean timing")
    for n in (1, 5, cfg.L1_MIN_RUNS, 35, cfg.L1_MAX_RUNS):
        print(f"  {n:3d} runs: {level1_success(n):6.1%}")

    print(f"\nLEVEL 2 - full key from one trace (sigma = {cfg.L2_NOISE_SIGMA})")
    print(f"  1 trace : {trace_success(cfg.L2_NOISE_SIGMA, 1):6.1%}")

    print(f"\nLEVEL 3 - full key from averaged traces (sigma = {cfg.L3_NOISE_SIGMA})")
    for n in (1, 5, 10, 20, 30, 45, 60, 100, cfg.L3_MAX_TRACES):
        print(f"  {n:3d} traces: {trace_success(cfg.L3_NOISE_SIGMA, n):6.1%}")

    print("\nPROTECTED device (should stay near 0% no matter how many traces)")
    for n in (1, 60, cfg.L3_MAX_TRACES):
        print(f"  {n:3d} traces: "
              f"{trace_success(cfg.L3_NOISE_SIGMA, n, protected=True):6.1%}")
