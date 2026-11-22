"""Look of the overlay: colours keyed out, fonts, spacing, icons."""
from icons import Icon, GifIcon

# Keyed out by the window: anything exactly this color is see-through. Near-black rather
# than magenta because Windows anti-aliases text against the background color, so text
# edges get blended with it: near-black blends into the dark outline, magenta leaves pink
# and blue fringes. Nothing else may use this exact color.
TRANSPARENT = "#010101"
TRANSPARENT_RGB = (1, 1, 1)

# Font tuples, not tkinter.font.Font objects: those would be freed on whatever thread
# drops them last, which Tk doesn't allow (see Window._release_tk)
HEADER_FONT   = ("Segoe UI Semibold", 9)
STATUS_FONT   = ("Segoe UI Semibold", 9)
SENTENCE_FONT = ("Segoe UI Semibold", 15)
SMALL_FONT    = ("Segoe UI", 10)
TITLE_FONT    = ("Segoe UI", 13, "bold")

PAD = 12              # px around the content
MIN_WIDTH = 300       # px, so short sentences don't make a tiny, jumpy overlay
MAX_TEXT_WIDTH = 460  # px, longer sentences wrap
BAR_HEIGHT = 4        # px
TICK_MS = 200         # how often the countdown redraws

mic_icon         = Icon("microphone-icon.png", 16)
loading_gif_icon = GifIcon("loading.gif", 24, 100)  # any smaller and the 12 spokes blur together

MIC_IDLE_COLOR = (239, 68, 68)       # red: not recording
MIC_RECORDING_COLOR = (34, 197, 94)  # green: recording
