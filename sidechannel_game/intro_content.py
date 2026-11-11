"""
intro_content.py -- the text of the Introduction level. EDIT THIS FILE to
change what players read; no other code needs to change.

Each page is a dictionary. There are two kinds:

  A reading page:
      {"title": "SOME TITLE",
       "text": ["First paragraph.", "Second paragraph with a **highlighted term**."],
       "figure": "square_multiply"}

  A true/false check page:
      {"title": "CHECK YOURSELF",
       "tf": {"statement": "A sentence the player judges.",
              "answer": False,                       # the correct answer
              "explanation": "Shown after they answer."}}

Notes
  * Wrap a phrase in **double asterisks** to highlight it as a key term.
  * "figure" is optional. It can be the name of a built-in drawing (see
    FIGURES at the bottom of screen_intro.py: padlock, leak, square_multiply,
    hamming, trace) OR the path of your own picture, e.g. "assets/my_figure.png"
    (PNG or GIF, roughly 560 x 340 pixels works best). Put the file in a folder
    called assets next to the game files.
  * Everything here is SAMPLE TEXT adapted from the first prototype.
"""

PAGES = [
    {
        "title": "WHY HARDWARE SECURITY MATTERS",
        "text": [
            "Smart locks, bank cards and phones all keep a secret **key** inside a "
            "tiny chip. The math that protects the key can be practically unbreakable.",
            "But a chip is a physical object. Every calculation it performs takes "
            "time and draws power, and someone standing next to it can measure both.",
            "**Hardware security** is about making sure the device itself does not "
            "give its secret away, not only the software running on it.",
        ],
        "figure": "padlock",
    },
    {
        "title": "SIDE CHANNELS AND LEAKAGE",
        "text": [
            "A **side channel** is any unintended signal a device gives off while it "
            "works: how long it takes, how much power it draws, the radio noise it "
            "emits.",
            "**Leakage** means that signal depends on the secret. If a key bit changes "
            "what the chip does, the measurement changes too, and an attacker can read "
            "the bit from the measurement.",
            "In this game you play the attacker. You never see the key or the code, "
            "only measurements.",
        ],
        "figure": "leak",
    },
    {
        "title": "THE TARGET: A SMART LOCK",
        "text": [
            "The lock proves who it is using **modular exponentiation**. It scans its "
            "secret 16-bit key one bit at a time, from the top bit down.",
            "For every bit it **squares** (S). If the bit is 1, it also **multiplies** "
            "(M). A 0 bit is just S. A 1 bit is S followed by M.",
            "So the work the chip does depends on the key. A 1 bit costs extra time, "
            "which means a key with more 1 bits takes longer to run.",
        ],
        "figure": "square_multiply",
    },
    {
        "title": "CHECK YOURSELF",
        "tf": {
            "statement": "A multiply happens on every key bit.",
            "answer": False,
            "explanation": "The multiply happens only when the key bit is 1.",
        },
    },
    {
        "title": "THE LEAKAGE MODEL",
        "text": [
            "Every operation draws supply current. In this game the height of a block "
            "is proportional to the **Hamming weight** of the data being processed: "
            "the number of 1 bits in the 32-bit word.",
            "Random 32-bit words have an average Hamming weight of 16, so a typical "
            "block is about 16 units tall.",
            "You will see these blocks on an oscilloscope-style plot: one block per "
            "operation.",
        ],
        "figure": "hamming",
    },
    {
        "title": "SPA AND SNR",
        "text": [
            "**Simple power analysis (SPA)** reads the secret directly from the shape "
            "of a power trace. A long block (S then M) means a 1 bit. A short block "
            "(S alone) means a 0 bit.",
            "**Signal-to-noise ratio (SNR)** compares the size of the useful signal "
            "with the size of the noise. With a high SNR the pattern is easy to read. "
            "With a low SNR it is buried, and you need extra tricks to dig it out.",
        ],
        "figure": "trace",
    },
    {
        "title": "CHECK YOURSELF",
        "tf": {
            "statement": "Simple power analysis can sometimes recover a key from a "
                         "single trace.",
            "answer": True,
            "explanation": "If the operations are visibly different, one trace can be "
                           "enough.",
        },
    },
]
