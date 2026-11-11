"""
power_rules.py -- the rules of Levels 2 and 3 (PROTOTYPES): questions, hints
and the short-answer rubric. The screens are in screen_power.py; the power
traces come from sim.py, tuned in config.py.

Level 2 - Simple power analysis (SPA)
    One clean power trace. Every key bit is a square block (S); a 1 bit adds a
    longer multiply block (M). Read all 16 key bits from the trace.
Level 3 - Noise and protection (SPA advanced)
    Single traces are buried in noise: average many of them to read the key from
    the standard lock. A second, protected lock (square-and-multiply-always)
    shows the same pattern for every bit, so averaging does not help there.

Scoring is the same as Level 1: 3 / 2 / 1 points for the key (attempt 1 / 2 / 3)
and RUBRIC_POINTS for the written explanation, 10 in total.

TINKER: edit the text, hints and rubric words below. Each rubric item needs ONE
sentence of the student's answer to match every pattern listed in its "needs".
"""

import re

import game_with_hints as g

# ---------------------------------------------------------------- patterns
_T = {
    "mult": g._T["mult"],
    "one": g._T["one"],
    "zero": r"\b0\b|\bzeros?\b|\b0s\b|\b0-bits?\b|\bs only\b|\bjust (a |one )?squar\w*"
            r"|\bonly (a |one )?squar\w*",
    "long": r"\blong\w*\b|\bwider\b|\bwidth\b|\bextra\b|\badditional\b|\bmore samples\b"
            r"|\blasts?\b|\bduration\b|\blength\b|\bshort\w*\b|\btwo blocks\b|\bsecond block\b",
    "height": r"\bheight\w*\b|\btall\w*\b|\bamplitude\b|\blevel\b|\bhigher\b|\bpeaks?\b"
              r"|\bcurrent\b|\bpower\b",
    "hw": r"\bhamming\b|\bweight\b|\bdata\b|\bvalue\b|\boperand\b|\bword\b|\bnumber being\b"
          r"|\bbits? (in|of) the (result|data|number|value|word)\b",
    "avg": r"\baverag\w*\b|\bmean\b|\bcombin\w*\b|\bstack\w*\b|\bsum\w*\b",
    "noise": r"\bnois\w*\b|\brandom\w*\b|\bjitter\b|\bfluctuat\w*\b",
    "cancel": r"\bcancel\w*\b|\bshrink\w*\b|\breduc\w*\b|\bsmaller\b|\bless\b|\bout\b"
              r"|\bdisappear\w*\b|\bsqrt\b|\bsquare root\b|\bfades?\b|\blower\w*\b",
    "always": r"\balways\b|\bevery (key )?bit\b|\beach (key )?bit\b|\ball (the )?bits\b"
              r"|\bdummy\b|\bregardless\b|\bno matter\b|\beven (for|when|on) (a )?(0|zero)",
    "same": r"\bsame\b|\bidentical\b|\bindistinguish\w*\b|\blooks? alike\b|\bno difference\b"
            r"|\bnothing to read\b|\bconstant\b|\buniform\b|\bcan(no|')t tell\b",
    "bit": r"\bbits?\b|\bkey\b|\bsegments?\b|\bblocks?\b|\boperations?\b",
}
RX = {k: re.compile(v, re.IGNORECASE) for k, v in _T.items()}


LEVELS = {
    "level2": {
        "name": "LEVEL 2: SPA",
        "kicker": "LEVEL 2  -  SIMPLE POWER ANALYSIS  -  PROTOTYPE",
        "lab_title": "Read the key from one trace",
        "brief": (
            "Your probe now measures the lock's power supply: each operation shows "
            "up as a block in the trace.\n\n"
            "Every key bit starts with a square (S). A 1 bit adds a multiply (M), "
            "which takes 1.5 times as long."),
        "objective": "read all 16 key bits from ONE clean trace. 3 attempts.",
        "question": ("In a few full sentences: how did you tell a 1 bit from a 0 bit "
                     "in the trace, and what decides how tall each block is?"),
        "hints": [
            "Each flat block is one operation, and there is a short gap after every "
            "key bit. Find where each bit's segment starts and ends.",
            "A square lasts 10 samples, a multiply 15. A segment with a second, "
            "longer block after the square is a 1; a square on its own is a 0.",
            "Read left to right: the first segment is bit 15. Ignore the block "
            "heights when reading bits - only the number of blocks per segment "
            "matters.",
        ],
        "rubric": [
            ("R1", ("mult", "one"),
             "A 1 bit adds a multiply block after the square.",
             "What extra operation shows up in the trace, and for which key bits?"),
            ("R2", ("long",),
             "So a 1-bit segment (S+M) is longer than a 0-bit segment (S only).",
             "How do the segments of a 0 bit and a 1 bit differ in the trace?"),
            ("R3", ("height", "hw"),
             "Each block's height follows the Hamming weight of the data being "
             "processed, not the key bit.",
             "What makes some blocks taller than others?"),
        ],
        "points": {"R1": 3, "R2": 2, "R3": 2},
        "explanation": [
            "Every key bit is processed as a square (S). A 1 bit adds a multiply "
            "(M), which lasts 1.5 times as long as a square. So in the trace a "
            "0 bit is one short block, and a 1 bit is a square followed by a longer "
            "block. Reading the segments left to right gives the key, top bit first.",
            "The height of a block is the supply current, which follows the Hamming "
            "weight (the number of 1 bits) of the 32-bit word the chip is working "
            "on. It changes with the data, so it says nothing about the key bit.",
        ],
    },
    "level3": {
        "name": "LEVEL 3: SPA ADVANCED",
        "kicker": "LEVEL 3  -  NOISE AND PROTECTION  -  PROTOTYPE",
        "lab_title": "Average the noise away",
        "brief": (
            "The probe is noisy now: one trace is buried in noise as large as the "
            "signal. The lock repeats itself exactly, the noise doesn't - so "
            "average many traces.\n\n"
            "A PROTECTED lock is on the bench too. Try it and compare."),
        "objective": ("read the STANDARD lock's 16 key bits from your average. "
                      "3 attempts."),
        "question": ("In a few full sentences: why does averaging many traces let you "
                     "read the key from the standard lock, and why doesn't it work on "
                     "the protected lock?"),
        "hints": [
            "One trace is mostly noise. Acquire a batch: the bright line is the "
            "average of every trace so far, the faint one is the latest single trace.",
            "Noise shrinks roughly with the square root of the number of traces: four "
            "times the traces halves the noise. Keep acquiring until the blocks are "
            "clear, then read the bits as in Level 2.",
            "Use the zoom buttons and read one segment at a time: a square on its own "
            "is a 0, a square plus a longer multiply is a 1. Then switch to the "
            "protected lock and compare what you see.",
        ],
        "rubric": [
            ("R1", ("avg", "noise", "cancel"),
             "Averaging cancels the random noise (it shrinks like 1/sqrt(N)) while "
             "the repeating signal stays.",
             "What happens to random noise when you average many traces?"),
            ("R2", ("mult", "always"),
             "The protected lock multiplies on every bit (square-and-multiply-always).",
             "What does the protected lock do differently on a 0 bit?"),
            ("R3", ("same", "bit"),
             "So every bit looks the same and there is nothing key-dependent to read, "
             "however many traces you average.",
             "After averaging, what does the protected lock's trace look like for 0 "
             "bits compared with 1 bits?"),
        ],
        "points": {"R1": 3, "R2": 2, "R3": 2},
        "explanation": [
            "The lock does exactly the same thing on every run, so its signal repeats "
            "while the noise is random. Averaging N traces keeps the signal and shrinks "
            "the noise by about the square root of N, until the S and S+M segments "
            "can be read just like in Level 2.",
            "The protected lock uses square-and-multiply-ALWAYS: it also multiplies on "
            "a 0 bit and throws the result away. Every bit then shows the same S+M "
            "pattern, so there is nothing key-dependent to average out. It also takes "
            "the same time for every key, which defeats the Level 1 timing attack.",
        ],
    },
}

for _rules in LEVELS.values():
    _rules["sa_max"] = sum(_rules["points"].values())


def score_answer(level_id, text):
    """[(rubric_id, met, description, hint), ...] for a level's written answer."""
    return g.score_with_rubric(text, LEVELS[level_id]["rubric"], RX)
