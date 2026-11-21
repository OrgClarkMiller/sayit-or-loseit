import tkinter as tk
from tkinter import ttk
import config
from languages import LANGUAGES

from window import Window, WindowPosition

WIDTH, HEIGHT = 500, 300


class ConfigurationWindow(Window):
    """Settings window. Construct it, then start(). Pass the app's stop_event so it
    saves and closes when the app quits."""

    def build(self):
        conf = config.get_config()
        self.language = tk.StringVar(self.root, value=conf.get("Language", "target", fallback=""))
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
        self.render_lang_combo(row=1)

    def render_lang_combo(self, row):
        tk.Label(self.root, text="Target language:")\
            .grid(row=row, column=0, sticky="w", padx=(10, 5), pady=5)

        ttk.Combobox(self.root, textvariable=self.language, values=LANGUAGES, state="readonly")\
            .grid(row=row, column=1, sticky="ew", padx=(5, 10), pady=5)

    def on_begin(self):
       pass

    def on_close(self):
        print("Closing Config Window")
        # Save any configuration
        conf = config.get_config()
        conf["Language"]["target"] = self.language.get()
        super().on_close()  # destroys the root