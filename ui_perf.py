#!/usr/bin/env python3
"""Basic Tk UI timing harness for the save editor.

This opens the real application, measures common slow paths, and exits without
saving. Run from the repo root with:

    python ui_perf.py
"""
from __future__ import annotations

import json
import time
import tkinter as tk

import save_editor


def measure(label, fn, results):
    start = time.perf_counter()
    value = fn()
    elapsed = (time.perf_counter() - start) * 1000
    results[label] = round(elapsed, 1)
    return value


def close_popups(root):
    for child in root.winfo_children():
        if isinstance(child, tk.Toplevel):
            child.destroy()
    root.update_idletasks()


def main():
    results = {}
    app = measure("startup_and_auto_load_ms", save_editor.Editor, results)
    app.update()

    def switch_main_tabs():
        tabs = app.nb.tabs()
        for tab in tabs:
            app.nb.select(tab)
            app.update_idletasks()
        return len(tabs)

    results["main_tab_count"] = measure("main_tab_switch_pass_ms", switch_main_tabs, results)

    def first_box_pass():
        tabs = app.boxes_nb.tabs() if hasattr(app, "boxes_nb") else []
        for tab in tabs:
            app.boxes_nb.select(tab)
            app.update()
        return len(tabs)

    results["box_tab_count"] = measure("first_box_tab_render_pass_ms", first_box_pass, results)
    measure("cached_box_tab_switch_pass_ms", first_box_pass, results)

    def item_picker_open():
        id_var = tk.StringVar(value="1")
        name_var = tk.StringVar(value="")
        app._open_item_picker(id_var, name_var)
        app.update()
        close_popups(app)

    measure("item_picker_open_ms", item_picker_open, results)

    def pokemon_picker_open():
        app._open_pokemon_picker(lambda _sid: None)
        app.update()
        close_popups(app)

    measure("pokemon_picker_open_ms", pokemon_picker_open, results)

    def rerender_current_box():
        if not app.boxes_nb.tabs():
            return
        selected = app.boxes_nb.select()
        meta = app._box_tab_meta.get(selected)
        if meta:
            app._rerender_box(meta["bi"])
            app.update()

    measure("current_box_rerender_ms", rerender_current_box, results)

    app.destroy()
    print(json.dumps(results, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
