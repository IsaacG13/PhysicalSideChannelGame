"""
config.py -- the tunable numbers of the simulated smart lock.

Change a value, relaunch (python retro_game.py), and the game follows:
  * Level 1 (game_with_hints.py -> screen_level1.py) reads the key and timing
    numbers below.
  * sim.py (the power-trace model for Levels 2 and 3, not playable yet) reads
    the power-trace numbers.
Run  python selftest.py  afterwards: it tests the same simulator players get.
"""

# ----------------------------------------------------------------------------
# The target device (the "smart lock")
# ----------------------------------------------------------------------------
KEY_BITS = 16            # length of the secret exponent
MODULUS_BITS = 32        # the lock does 32-bit modular arithmetic, so the data
                         # words it processes have a mean Hamming weight of 16

# Keep the number of 1 bits in the key inside this range so Level 1 always has
# a meaningful answer (an all-zero or all-one key would be boring).
MIN_ONES = 5
MAX_ONES = 11

# ----------------------------------------------------------------------------
# Timing model (Level 1)
# ----------------------------------------------------------------------------
T_S_US = 150.0           # duration of one squaring, in microseconds (shown to students)
M_TO_S_RATIO = 1.5       # t_M = 1.5 * t_S   (students are told this)
T_M_US = T_S_US * M_TO_S_RATIO
T_S_MS = T_S_US / 1000.0  # the same squaring time in milliseconds (used by sim.py)

# Run-to-run timing jitter (Gaussian), expressed in units of t_M.
# The proposal used 0.5. That made Level 1 trivial (20 runs already gives a
# ~0.11 t_M error on the mean), so it is raised here. Rough error rates for
# rounding the mean to the nearest whole multiply count:
#     1.25 -> ~7% wrong at 20 runs, ~0.5% wrong at 50 runs
# Run  python selftest.py  after changing this to see the real numbers.
L1_JITTER_SIGMA_IN_TM = 1.25

L1_MIN_RUNS = 20         # students choose a batch size between these
L1_MAX_RUNS = 50
L1_MAX_BATCHES = 10      # most batches per measurement session (one plot colour each)

# ----------------------------------------------------------------------------
# Power-trace model (Levels 2 and 3)
# ----------------------------------------------------------------------------
SAMPLES_PER_S = 10                              # samples in one squaring block
SAMPLES_PER_M = round(SAMPLES_PER_S * M_TO_S_RATIO)   # = 15 for a 1.5 ratio
GAP_SAMPLES = 4          # idle samples after each key-bit iteration
PAD_SAMPLES = 6          # idle samples before the first / after the last bit
AMPLITUDE_PER_HW_BIT = 1.0   # current units per set bit in the processed word
                             # (so a block of Hamming weight 16 has height 16)

L2_NOISE_SIGMA = 2.0     # SNR = 16 / 2  = 8   (readable by eye)
L3_NOISE_SIGMA = 16.0    # SNR = 16 / 16 = 1   (unreadable until averaged)
L3_MAX_TRACES = 200      # acquisition budget per device in Level 3
L3_MAX_PER_BATCH = 50    # largest single "Acquire" click

# ----------------------------------------------------------------------------
# Submissions
# ----------------------------------------------------------------------------
MAX_ATTEMPTS = 3         # tries per submission box. Feedback is only
                         # "correct" / "incorrect", never "3 of 16 bits right".
