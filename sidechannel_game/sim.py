"""
sim.py -- the simulated smart lock and the "oscilloscope" that measures it.

(Level 1's timing model is game_with_hints.TimingSimulator -- the one the
game actually uses. This file is the power-trace model for Levels 2 and 3.)

No GUI code in here, so it can be tested and tinkered with on its own:

    >>> import sim
    >>> t = sim.Target(seed=1234)
    >>> t.key_bits                       # the secret (students never see it)
    >>> t.acquire_trace(sigma=2.0)       # Level 2 / 3 data

What is modelled (see the proposal): the key-dependent operation sequence,
operation durations, run-to-run timing jitter, Hamming-weight-dependent
amplitude, and additive Gaussian noise.
What is NOT modelled: circuit-level effects, probe filtering, clock jitter,
trace misalignment, non-Gaussian noise.
"""

import hashlib

import numpy as np

import config as cfg


def seed_from_student_id(student_id: str) -> int:
    """Turn a student ID string into a repeatable integer seed.
    Same ID -> same key, modulus and message every time."""
    digest = hashlib.sha256(student_id.strip().lower().encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big")


def hamming_weight(x: int) -> int:
    """Number of 1 bits in x."""
    return bin(x).count("1")


class Target:
    """One student's smart lock: secret key, modulus, fixed input message."""

    def __init__(self, seed: int):
        self.seed = seed

        # Separate random streams: one decides the secrets, one the measurements.
        secret_rng = np.random.default_rng(seed)
        self._meas_rng = np.random.default_rng([seed, 1])

        # --- the secret key: KEY_BITS bits, with a sensible number of 1s ----
        while True:
            key = int(secret_rng.integers(0, 2 ** cfg.KEY_BITS))
            if cfg.MIN_ONES <= hamming_weight(key) <= cfg.MAX_ONES:
                break
        self.key = key
        # MSB first, because square-and-multiply scans from the top bit down.
        self.key_bits = [(key >> i) & 1 for i in range(cfg.KEY_BITS - 1, -1, -1)]

        # --- modulus and message ---------------------------------------------
        # Random odd 32-bit modulus with the top bit set. It is NOT a real RSA
        # modulus; only the *data* flowing through the multiplier matters here.
        self.n = int(secret_rng.integers(2 ** (cfg.MODULUS_BITS - 1),
                                         2 ** cfg.MODULUS_BITS)) | 1
        # Fixed message: the same on every run, so the data (and therefore the
        # signal) repeats exactly while the noise does not. That repeatability
        # is why averaging works.
        self.message = int(secret_rng.integers(2, self.n - 1))

        # Pre-compute both devices' noise-free traces once.
        self._clean = {
            False: self._render(self._run_device(protected=False)),
            True: self._render(self._run_device(protected=True)),
        }

    # ------------------------------------------------------------------ device
    def _run_device(self, protected: bool):
        """Actually run the modular exponentiation and record every operation.

        Returns one list per key bit; each list holds ('S' or 'M', hamming
        weight of the 32-bit result) tuples.

        protected=False : plain square-and-multiply
                          (multiply only when the key bit is 1)
        protected=True  : square-and-multiply-ALWAYS
                          (a dummy multiply runs on 0 bits, result discarded)
        """
        # The accumulator starts at 2^32 mod n (the Montgomery form of 1) rather
        # than at 1. This keeps the very first block realistic: starting at 1
        # would make the first squaring process the word "1" (Hamming weight 1),
        # an unrealistically tiny block that confuses students.
        x = (1 << cfg.MODULUS_BITS) % self.n

        iterations = []
        for bit in self.key_bits:
            ops = []
            x = (x * x) % self.n                      # squaring: every bit
            ops.append(("S", hamming_weight(x)))
            if bit == 1:
                x = (x * self.message) % self.n       # real multiply
                ops.append(("M", hamming_weight(x)))
            elif protected:
                dummy = (x * self.message) % self.n   # computed, then thrown away
                # Its data looks just like real data (same distribution), so the
                # protected device leaks nothing through amplitude either.
                ops.append(("M", hamming_weight(dummy)))
            iterations.append(ops)
        return iterations

    def _render(self, iterations) -> np.ndarray:
        """Turn the operation list into a noise-free supply-current trace.

        Layout:  pad | [S (+M)] gap | [S (+M)] gap | ... | pad
        Each block is a flat plateau whose height = Hamming weight * scale.
        """
        parts = [np.zeros(cfg.PAD_SAMPLES)]
        for ops in iterations:
            for kind, hw in ops:
                length = cfg.SAMPLES_PER_S if kind == "S" else cfg.SAMPLES_PER_M
                parts.append(np.full(length, hw * cfg.AMPLITUDE_PER_HW_BIT))
            parts.append(np.zeros(cfg.GAP_SAMPLES))
        parts.append(np.zeros(cfg.PAD_SAMPLES))
        return np.concatenate(parts)

    # ------------------------------------------------------------ measurements
    @property
    def sample_period_ms(self) -> float:
        """One scope sample lasts t_S / SAMPLES_PER_S milliseconds."""
        return cfg.T_S_MS / cfg.SAMPLES_PER_S

    def acquire_trace(self, sigma: float, protected: bool = False) -> np.ndarray:
        """Levels 2/3: one power trace = clean signal + fresh Gaussian noise."""
        clean = self._clean[protected]
        return clean + self._meas_rng.normal(0.0, sigma, size=clean.shape)

    # ----------------------------------------------------------------- answers
    def check_count(self, guess: int) -> bool:
        return int(guess) == sum(self.key_bits)

    def check_key(self, guess_bits) -> bool:
        return list(guess_bits) == self.key_bits
