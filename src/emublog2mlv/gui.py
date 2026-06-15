"""
Simple Tkinter GUI for emublog2mlv (standard-library only).

Launch:
    emublog2mlv-gui              (installed GUI script)
    python -m emublog2mlv.gui
or just double-click ``emublog2mlv-gui.exe``.

Pick one or more ``.emublog`` files (or a whole folder), choose ``.msl``/``.csv``,
optionally set an output folder and — for a single file — a custom output name,
then Convert. Multiple files convert in one batch with a progress bar.
"""
from __future__ import annotations

import glob
import os
import queue
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from . import __version__
from .core import convert, planned_output


class ConverterApp:
    def __init__(self, root):
        self.root = root
        root.title(f"emublog2mlv {__version__} — EMU Black log converter")
        root.minsize(640, 480)

        self.files = []                      # queued input paths
        self.fmt = tk.StringVar(value="msl")
        self.out_dir = tk.StringVar(value="")
        self.out_name = tk.StringVar(value="")
        self.same_dir = tk.BooleanVar(value=True)
        self._q = queue.Queue()

        main = ttk.Frame(root, padding=10)
        main.pack(fill="both", expand=True)

        ttk.Label(main, text="Logs to convert (.emublog):").grid(
            row=0, column=0, columnspan=4, sticky="w")

        listframe = ttk.Frame(main)
        listframe.grid(row=1, column=0, columnspan=4, sticky="nsew", pady=(2, 6))
        self.listbox = tk.Listbox(listframe, selectmode="extended", height=8, activestyle="none")
        sb = ttk.Scrollbar(listframe, orient="vertical", command=self.listbox.yview)
        self.listbox.configure(yscrollcommand=sb.set)
        self.listbox.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

        btns = ttk.Frame(main)
        btns.grid(row=2, column=0, columnspan=4, sticky="w")
        ttk.Button(btns, text="Add files…", command=self.add_files).pack(side="left", padx=(0, 4))
        ttk.Button(btns, text="Add folder…", command=self.add_folder).pack(side="left", padx=4)
        ttk.Button(btns, text="Remove selected", command=self.remove_selected).pack(side="left", padx=4)
        ttk.Button(btns, text="Clear", command=self.clear_files).pack(side="left", padx=4)

        fmtframe = ttk.LabelFrame(main, text="Output format")
        fmtframe.grid(row=3, column=0, columnspan=4, sticky="ew", pady=(8, 4))
        ttk.Radiobutton(fmtframe, text="MegaLogViewer .msl (tab-delimited)",
                        variable=self.fmt, value="msl").pack(side="left", padx=8, pady=4)
        ttk.Radiobutton(fmtframe, text=".csv", variable=self.fmt, value="csv").pack(side="left", padx=8, pady=4)

        outframe = ttk.LabelFrame(main, text="Output location")
        outframe.grid(row=4, column=0, columnspan=4, sticky="ew", pady=4)
        ttk.Radiobutton(outframe, text="Next to each source file", variable=self.same_dir,
                        value=True, command=self._refresh).grid(
            row=0, column=0, columnspan=3, sticky="w", padx=8, pady=2)
        ttk.Radiobutton(outframe, text="Into folder:", variable=self.same_dir,
                        value=False, command=self._refresh).grid(row=1, column=0, sticky="w", padx=8, pady=2)
        self.out_entry = ttk.Entry(outframe, textvariable=self.out_dir, width=46)
        self.out_entry.grid(row=1, column=1, sticky="ew", padx=4)
        self.browse_btn = ttk.Button(outframe, text="Browse…", command=self.browse_out_dir)
        self.browse_btn.grid(row=1, column=2, padx=4)
        self.name_label = ttk.Label(outframe, text="Output file name (single file only):")
        self.name_label.grid(row=2, column=0, sticky="w", padx=8, pady=(4, 2))
        self.name_entry = ttk.Entry(outframe, textvariable=self.out_name, width=46)
        self.name_entry.grid(row=2, column=1, sticky="ew", padx=4, pady=(4, 2))
        outframe.columnconfigure(1, weight=1)

        actionframe = ttk.Frame(main)
        actionframe.grid(row=5, column=0, columnspan=4, sticky="ew", pady=(8, 4))
        self.convert_btn = ttk.Button(actionframe, text="Convert", command=self.start_convert)
        self.convert_btn.pack(side="left")
        self.progress = ttk.Progressbar(actionframe, mode="determinate")
        self.progress.pack(side="left", fill="x", expand=True, padx=8)

        ttk.Label(main, text="Results:").grid(row=6, column=0, sticky="w")
        self.log = tk.Text(main, height=8, state="disabled", wrap="none")
        self.log.grid(row=7, column=0, columnspan=4, sticky="nsew", pady=(2, 0))

        main.rowconfigure(1, weight=1)
        main.rowconfigure(7, weight=1)
        main.columnconfigure(0, weight=1)

        self._refresh()

    # ----- file list -----
    def add_files(self):
        paths = filedialog.askopenfilenames(
            title="Select .emublog files",
            filetypes=[("EMU Black logs", "*.emublog"), ("All files", "*.*")])
        self._add(paths)

    def add_folder(self):
        d = filedialog.askdirectory(title="Select a folder of .emublog files")
        if d:
            found = sorted(glob.glob(os.path.join(d, "*.emublog")))
            if not found:
                messagebox.showinfo("No logs", f"No .emublog files found in:\n{d}")
            self._add(found)

    def _add(self, paths):
        for p in paths:
            if p and p not in self.files:
                self.files.append(p)
                self.listbox.insert("end", p)
        self._refresh()

    def remove_selected(self):
        for i in reversed(self.listbox.curselection()):
            self.listbox.delete(i)
            del self.files[i]
        self._refresh()

    def clear_files(self):
        self.listbox.delete(0, "end")
        self.files.clear()
        self._refresh()

    def browse_out_dir(self):
        d = filedialog.askdirectory(title="Choose output folder")
        if d:
            self.out_dir.set(d)
            self.same_dir.set(False)
            self._refresh()

    # ----- ui state -----
    def _refresh(self):
        use_folder = not self.same_dir.get()
        folder_state = "normal" if use_folder else "disabled"
        self.out_entry.configure(state=folder_state)
        self.browse_btn.configure(state=folder_state)
        single = len(self.files) == 1
        self.name_entry.configure(state="normal" if single else "disabled")
        self.name_label.configure(state="normal" if single else "disabled")
        if not single:
            self.out_name.set("")

    # ----- convert (threaded so the UI stays responsive on big logs) -----
    def start_convert(self):
        if not self.files:
            messagebox.showwarning("No files", "Add at least one .emublog file first.")
            return
        out_dir = self.out_dir.get() if not self.same_dir.get() else None
        if out_dir and not os.path.isdir(out_dir):
            messagebox.showerror("Bad folder", f"Output folder does not exist:\n{out_dir}")
            return
        out_name = self.out_name.get() if len(self.files) == 1 else None
        self.convert_btn.configure(state="disabled")
        self._clear_log()
        self.progress.configure(maximum=len(self.files), value=0)
        worker = threading.Thread(
            target=self._worker,
            args=(list(self.files), self.fmt.get(), out_dir, out_name),
            daemon=True)
        worker.start()
        self.root.after(100, self._poll)

    def _worker(self, files, fmt, out_dir, out_name):
        ok = 0
        for p in files:
            try:
                out = planned_output(p, fmt, out_dir, out_name)
                st = convert(p, out, fmt)
                self._q.put(("log", f"OK   {os.path.basename(p)}  ->  {os.path.basename(out)}"
                                    f"   ({st['records']} samples, {st['duration_s']:.0f}s)"))
                ok += 1
            except Exception as e:  # report per-file, keep going
                self._q.put(("log", f"FAIL {os.path.basename(p)}: {e}"))
            self._q.put(("tick", None))
        self._q.put(("done", f"Done — {ok}/{len(files)} converted."))

    def _poll(self):
        try:
            while True:
                kind, payload = self._q.get_nowait()
                if kind == "log":
                    self._append_log(payload)
                elif kind == "tick":
                    self.progress.step(1)
                elif kind == "done":
                    self._append_log(payload)
                    self.convert_btn.configure(state="normal")
                    return
        except queue.Empty:
            pass
        self.root.after(100, self._poll)

    # ----- log helpers -----
    def _clear_log(self):
        self.log.configure(state="normal")
        self.log.delete("1.0", "end")
        self.log.configure(state="disabled")

    def _append_log(self, line):
        self.log.configure(state="normal")
        self.log.insert("end", line + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")


def main():
    root = tk.Tk()
    ConverterApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
