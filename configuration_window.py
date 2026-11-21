import base64
import io
from configparser import ConfigParser
from pathlib import Path
import tkinter as tk
from tkinter import ttk

from PIL import Image

import config
from languages import LANGUAGES, LanguageProficiency

from window import Window, WindowPosition

WIDTH, HEIGHT = 500, 300
MIN_WORDS, MAX_WORDS, DEFAULT_MAX_WORDS = 1, 500, 15

ASSETS = Path(__file__).parent / "assets"
TOGGLE_ON_PATH  = ASSETS / "on-toggle-icon.png"
TOGGLE_OFF_PATH = ASSETS / "off-toggle-icon.png"
TOGGLE_SIZE = (60, 24)  # px; the source images are 100x40


def _load_icon(master, path: Path, size: tuple[int, int]) -> tk.PhotoImage:
    """A PNG resized with PIL, as a plain tk.PhotoImage (not ImageTk) so
    Window._release_tk frees it on the Tk thread."""
    buf = io.BytesIO()
    Image.open(path).convert("RGBA").resize(size, Image.LANCZOS).save(buf, format="PNG")
    return tk.PhotoImage(master=master, data=base64.b64encode(buf.getvalue()))

class ConfigurationWindow(Window):
    """Settings window. Construct it, then start(). It saves and closes when the
    app's stop_event is set."""

    def build(self):
        conf                  = config.get_config()
        self.gemini_key       = tk.StringVar(self.root, value=conf.get("AI", "gemini_key", fallback=""))
        self.lang             = tk.StringVar(self.root, value=conf.get("Language", "target", fallback=""))
        self.lang_proficiency = tk.StringVar(self.root, value=conf.get("Language", "proficiency", fallback=LanguageProficiency.FRESHY))
        self.max_words        = tk.IntVar(self.root, value=conf.getint("Sentence", "max_words", fallback=DEFAULT_MAX_WORDS))
        self.challenge_active = tk.BooleanVar(self.root, value=conf.getboolean("Challenge", "is_active", fallback=True))
        self.on_begin()
        self.render()

    def on_show(self):
        self.place_window_at(WindowPosition.BOTTOM_RIGHT)

    def create_root(self):
        root = tk.Tk()
        root.title("Say it or Lose it — Configuration")
        root.resizable(False, False)
        root.protocol("WM_DELETE_WINDOW", self.close)  # X button -> same path as an app-wide close
        root.columnconfigure(1, weight=1)

        return root

    def render(self):
        header = tk.Label(self.root, text="Configuration", font=("Segoe UI", 12, "bold"))
        header.grid(row=0, column=0, columnspan=2, pady=(10, 15))
        self.render_is_active(row=1)
        self.render_lang_combo(row=2)
        self.render_proficiency_combo(row=3)
        self.render_max_words(row=4)
        self.render_gemini_key(row=5)

    def render_lang_combo(self, row):
        self.render_input_label(row, "Target Language:")
        ttk.Combobox(self.root, textvariable=self.lang, values=LANGUAGES, state="readonly")\
            .grid(row=row, column=1, sticky="ew", padx=(5, 10), pady=5)

    def render_proficiency_combo(self, row):
        self.render_input_label(row, "Target Language Proficiency:")
        ttk.Combobox(self.root, textvariable=self.lang_proficiency, values=[level.value for level in LanguageProficiency], state="readonly")\
            .grid(row=row, column=1, sticky="ew", padx=(5, 10), pady=5)

    def render_max_words(self, row):
        self.render_input_label(row, "Maximum Word Count:")
        # Only allow digits to be typed (the empty string lets the user clear the box while editing)
        digits_only = (self.root.register(lambda text: text == "" or text.isdigit()), "%P")
        ttk.Spinbox(self.root, textvariable=self.max_words, from_=MIN_WORDS, to=MAX_WORDS, increment=1,
                    validate="key", validatecommand=digits_only)\
            .grid(row=row, column=1, sticky="ew", padx=(5, 10), pady=5)

    def render_gemini_key(self, row):
        self.render_input_label(row, "Gemini API Key:")

        # Entry + "Show" toggle share column 1
        frame = ttk.Frame(self.root)
        frame.grid(row=row, column=1, sticky="ew", padx=(5, 10), pady=5)
        frame.columnconfigure(0, weight=1)

        entry = ttk.Entry(frame, textvariable=self.gemini_key, show="•")  # masked by default
        entry.grid(row=0, column=0, sticky="ew")

        show_key = tk.BooleanVar(self.root, value=False)
        ttk.Checkbutton(frame, text="Show", variable=show_key,
                        command=lambda: entry.config(show="" if show_key.get() else "•"))\
            .grid(row=0, column=1, padx=(5, 0))

    def render_input_label(self, row, text):
        tk.Label(self.root, text=text)\
            .grid(row=row, column=0, sticky="w", padx=(10, 5), pady=5)

    def render_is_active(self, row):
        self.render_input_label(row, "Challenges Active:")

        # Keep references on self: Tk drops an image once Python frees it
        self.toggle_on_icon  = _load_icon(self.root, TOGGLE_ON_PATH, TOGGLE_SIZE)
        self.toggle_off_icon = _load_icon(self.root, TOGGLE_OFF_PATH, TOGGLE_SIZE)

        toggle = tk.Label(self.root, cursor="hand2", takefocus=1)
        toggle.grid(row=row, column=1, sticky="w", padx=(5, 10), pady=5)

        def show(*_):
            toggle.config(image=self.toggle_on_icon if self.challenge_active.get() else self.toggle_off_icon)

        def flip(_event=None):
            self.challenge_active.set(not self.challenge_active.get())

        toggle.bind("<Button-1>", flip)
        toggle.bind("<space>", flip)  # usable from the keyboard too (Tab to it, then Space)
        self.challenge_active.trace_add("write", show)
        show()

    def get_max_words(self) -> int:
        """The entered word count, clamped to the allowed range (default if the box is empty)."""
        try:
            value = self.max_words.get()
        except tk.TclError:  # box left empty
            return DEFAULT_MAX_WORDS
        return max(MIN_WORDS, min(MAX_WORDS, value))

    def on_begin(self):
       pass

    def update_lang_conf(self, conf: ConfigParser):
        old = conf.get("Language", "target")
        if old == self.lang.get(): return

        conf["Language"]["target"] = self.lang.get()
        self._app_context.on_change_target_language()

    def on_close(self):
        print("Closing Config Window")
        # Save any configuration
        conf = config.get_config()
        self.update_lang_conf(conf)
        conf["Language"]["proficiency"] = self.lang_proficiency.get()
        if not conf.has_section("Sentence"):
            conf.add_section("Sentence")
        conf["Sentence"]["max_words"] = str(self.get_max_words())
        if not conf.has_section("AI"):
            conf.add_section("AI")

        if not conf.has_section("Challenge"):
            conf.add_section("Challenge")
        conf["Challenge"]["is_active"] = str(self.challenge_active.get())  # configparser only stores strings
        conf["AI"]["gemini_key"] = self.gemini_key.get().strip()  # pasted keys often carry stray whitespace
        self._app_context.apply_config()  # the generator copies its settings, so hand it the new ones
        super().on_close()  # destroys the root