"""
hunter/scroll.py
================
Mousewheel / scroll-wheel binding utilities used by all three panes.

The core problem with tkinter scroll on Windows:
  - <MouseWheel> does NOT bubble up from child widgets to parent canvases
    the way mouse clicks do.  Each widget that the cursor is physically
    over must have its own explicit binding, otherwise scrolling silently
    does nothing.
  - On Linux, Button-4 / Button-5 are used instead of MouseWheel.

Strategy:
  bind_scroll_recursive  — walks the ENTIRE widget tree and binds every
                           node.  Call this once at startup per pane, and
                           again after any refresh that creates new widgets.
  rebind_scroll          — alias for clarity; same implementation.
"""


def _make_handler(canvas):
    """Return a scroll event handler closure bound to *canvas*.

    We create a new closure for each canvas so that multiple panes
    (library, plan, detail) each scroll their own canvas independently.
    """
    def _on_scroll(e):
        if e.num == 4:        # Linux scroll-up
            canvas.yview_scroll(-1, "units")
        elif e.num == 5:      # Linux scroll-down
            canvas.yview_scroll(1, "units")
        elif e.delta:         # Windows / macOS
            canvas.yview_scroll(-1 * (e.delta // 120), "units")
    return _on_scroll


def _apply(widget, fn):
    """Recursively attach *fn* to *widget* and every descendant.

    Using add="+" preserves any existing bindings (e.g. drag bindings
    on library cards) instead of replacing them.
    """
    widget.bind("<MouseWheel>", fn, add="+")
    widget.bind("<Button-4>",   fn, add="+")
    widget.bind("<Button-5>",   fn, add="+")
    for child in widget.winfo_children():
        _apply(child, fn)


def bind_scroll_recursive(widget, canvas):
    """Bind mousewheel scrolling on *widget* and ALL descendants.

    Call this:
      - Once at startup for each scrollable pane (library, plan, detail).
      - Again after refresh_library() / refresh_plan() / show_module()
        because those methods destroy and recreate child widgets, losing
        all previously attached bindings.

    The canvas itself is also bound so that scrolling works when the
    cursor is over empty space inside the canvas (no card underneath).
    """
    fn = _make_handler(canvas)
    # Bind the canvas itself (empty space between cards)
    canvas.bind("<MouseWheel>", fn, add="+")
    canvas.bind("<Button-4>",   fn, add="+")
    canvas.bind("<Button-5>",   fn, add="+")
    # Bind inner frame and every widget inside it
    _apply(widget, fn)


# rebind_scroll is kept as an alias — after the mousewheel bug we use the
# same full recursive strategy for both startup and post-refresh binding.
rebind_scroll = bind_scroll_recursive
