"""One busy signal for the whole GUI (molass-gui): while the program is working the user sees the same three things.

1. A busy mouse cursor over the window: the hourglass ("wait") while the window itself is blocked, the arrow with a
   small hourglass ("starting") while the work runs in the background and the window still answers.
2. The status line says what is going on, always as ``<what is being done>...`` (and goes back, or shows the result,
   when it is over).
3. The button that started it (if given) is disabled, so that it cannot be pressed twice.

Use ``begin()`` / ``Token.end()`` around work in a background thread and ``working()`` around work that runs on the main
thread. Several things may be busy at once: the cursor and the buttons come back when the last one has ended.
"""
import contextlib
import tkinter as tk

BLOCKING_CURSOR = "wait"        # the window cannot answer
BACKGROUND_CURSOR = "starting"  # arrow + hourglass: the window still answers (Windows; others fall back to "watch")


def _set_cursor(win, cursor):
    try:
        win.configure(cursor=cursor)
    except tk.TclError:
        try:
            win.configure(cursor="watch" if cursor else "")
        except tk.TclError:
            pass


class _WindowState:
    """What is busy in one window."""

    def __init__(self, win):
        self.win = win
        self.tokens = []
        self.original_cursor = None

    def refresh_cursor(self):
        if not self.tokens:
            _set_cursor(self.win, self.original_cursor or "")
            return
        blocking = any(t.blocking for t in self.tokens)
        _set_cursor(self.win, BLOCKING_CURSOR if blocking else BACKGROUND_CURSOR)


def _state(win):
    state = getattr(win, "_busy_state", None)
    if state is None:
        state = win._busy_state = _WindowState(win)
    return state


class Token:
    def __init__(self, state, status_var, message, buttons, key, blocking):
        self._state, self._status_var = state, status_var
        self.message, self.key, self.blocking = message, key, blocking
        self._previous_status = status_var.get() if status_var is not None else None
        # only the buttons that were enabled are enabled again (some are disabled for other reasons)
        self._buttons = [b for b in buttons if not b.instate(["disabled"])]
        self._ended = False

    def update(self, message, blocking=None):
        """Say something else while still busy (e.g. ``Rg: 12/1305``). ``blocking=True`` switches to the hourglass,
        for the next step that runs on the main thread."""
        self.message = message
        if self._ended:
            return
        if blocking is not None:
            self.blocking = blocking
            self._state.refresh_cursor()
        if self._status_var is not None:
            self._status_var.set(message)
        if blocking:
            _repaint(self._state.win)

    def end(self, status=None):
        """Over. ``status`` is the new status text; without it the previous text comes back, unless something else
        (an error message) has been put there in the meantime."""
        if self._ended:
            return
        self._ended = True
        tokens = self._state.tokens
        if self in tokens:
            tokens.remove(self)
        for b in self._buttons:
            # not while another busy period still holds the button
            if not any(b in t._buttons for t in tokens):
                b.state(["!disabled"])
        if self._status_var is not None:
            if status is not None:
                self._status_var.set(status)
            elif self._status_var.get() == self.message:
                self._status_var.set(self._previous_status or "")
        self._state.refresh_cursor()


def begin(win, status_var, message, buttons=(), key=None, blocking=False):
    """Start a busy period of ``win``; returns a Token whose ``end()`` finishes it.

    ``message`` goes to ``status_var`` (may be None), ``buttons`` are disabled until the end. With a ``key`` a second
    ``begin`` of the same key while the first is running does nothing and returns None (a double click)."""
    state = _state(win)
    if key is not None and any(t.key == key for t in state.tokens):
        return None
    if not state.tokens:
        try:
            state.original_cursor = str(win.cget("cursor"))
        except tk.TclError:
            state.original_cursor = ""
    token = Token(state, status_var, message, list(buttons), key, blocking)
    state.tokens.append(token)
    for b in token._buttons:
        b.state(["disabled"])
    if status_var is not None:
        status_var.set(message)
    state.refresh_cursor()
    _repaint(win)
    return token


def _repaint(win):
    """Show the cursor, the disabled buttons and the status now: a blocking call on the main thread would otherwise
    keep them off the screen until it is over."""
    try:
        win.update_idletasks()
    except tk.TclError:
        pass


@contextlib.contextmanager
def working(win, status_var, message, buttons=(), key=None):
    """``with working(...):`` for work on the main thread (the window is blocked meanwhile)."""
    token = begin(win, status_var, message, buttons=buttons, key=key, blocking=True)
    try:
        yield token
    finally:
        if token is not None:
            token.end()
