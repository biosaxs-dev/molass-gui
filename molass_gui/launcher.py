"""Launcher — Phase 0: choose New Analysis vs Open Existing Analysis.

This is the actual Tk root for the whole session. Every other window
(App/NaiveView/QuickView/UpgradedView/RigorousView, or the "Open Existing
Analysis" path) is a Toplevel built with parent=self, app_root=self --
close_session() here tears down whichever branch is currently open.
"""
import tkinter as tk
from tkinter import ttk


class Launcher(tk.Tk):
    def __init__(self):
        super().__init__()
        from molass_gui import get_version
        self.title("Molass %s" % get_version())
        self.resizable(False, False)
        self._configure_style()
        self._build_ui()
        self.update_idletasks()
        # widen if needed so the titlebar text isn't clipped by content width
        width = max(self.winfo_reqwidth(), 320)
        self.geometry("%dx%d" % (width, self.winfo_reqheight()))
        self.protocol("WM_DELETE_WINDOW", self.close_session)

    def close_session(self):
        """Close every window that belongs to this session in one action --
        wired to the close button of the root AND every child phase window,
        so closing any one of them tears down the whole session, not just itself.
        Confirms first if a long-running job (e.g. rigorous optimization) is
        active anywhere in the session (see window_tree.confirm_and_close)."""
        from molass_gui.window_tree import confirm_and_close
        if confirm_and_close(self):
            import sys
            sys.exit(0)

    def _configure_style(self):
        # 'clam' honors custom background/foreground on TButton, unlike the
        # native 'vista' theme -- needed for Accent/Danger to actually show.
        # Applied once here since ttk.Style is process-global, not per-window --
        # every Toplevel built from this root (App, NaiveView, ..., RigorousView)
        # picks it up automatically.
        style = ttk.Style(self)
        style.theme_use('clam')

        style.configure('Accent.TButton', background='#2563eb', foreground='white',
                         padding=6)
        # 'disabled' must precede 'active' -- ttk matches state specs in list
        # order, and the button is still 'active' (mouse still hovering right
        # after the click that disabled it) as well as 'disabled' at that
        # moment, so 'disabled' has to win the match or the background stays
        # looking enabled even though the text correctly turns gray.
        style.map('Accent.TButton',
                  background=[('disabled', '#93b4f5'), ('active', '#1d4ed8')])

        style.configure('Danger.TButton', background='#dc2626', foreground='white',
                         padding=6)
        style.map('Danger.TButton',
                  background=[('disabled', '#eba6a6'), ('active', '#b91c1c')])

    def _build_ui(self):
        f = ttk.Frame(self, padding=24)
        f.pack(fill=tk.BOTH, expand=True)

        ttk.Label(f, text="Molass", font=("", 14, "bold")).pack(pady=(0, 4))
        ttk.Label(f, text="What would you like to do?", foreground="gray").pack(
            pady=(0, 16))

        ttk.Button(f, text="New Analysis", command=self._new_analysis,
                  style="Accent.TButton", width=28).pack(pady=6)
        ttk.Button(f, text="Open Existing Analysis", command=self._open_existing,
                  width=28).pack(pady=6)

    def _new_analysis(self):
        from molass_gui.app import App
        App(parent=self, app_root=self).show()
        self.withdraw()  # unmap, not just minimize -- keeps only the child on the taskbar

    def _open_existing(self):
        from molass_gui.view_analysis import ViewAnalysisView
        ViewAnalysisView(parent=self, app_root=self).show()
        self.withdraw()


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--dropbox-support", action="store_true",
                        help="Enable Dropbox folder auto-detection/sync (experimental, off by default)")
    args = parser.parse_args()

    from molass_gui import feature_flags
    feature_flags.DROPBOX_SUPPORT_ENABLED = args.dropbox_support

    Launcher().mainloop()


if __name__ == "__main__":
    main()
