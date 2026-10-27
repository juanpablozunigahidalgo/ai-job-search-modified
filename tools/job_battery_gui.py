#!/usr/bin/env python3
"""
Mini UI for LinkedIn battery results + searches.
No Cursor needed. Double-click tools/RUN_JOB_GUI.cmd

Requires: Python 3.10+, bun on PATH (for Run search).
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import webbrowser
from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

ROOT = Path(__file__).resolve().parents[1]
RUNS = ROOT / "job_scraper" / "linkedin_runs"
CLI_LINKEDIN = ROOT / ".agents" / "skills" / "linkedin-search" / "cli" / "src" / "cli.ts"
CLI_AF = ROOT / ".agents" / "skills" / "arbetsformedlingen-search" / "cli" / "src" / "cli.ts"
PRESETS = ROOT / "job_scraper" / "role_presets.json"


def latest_unique() -> Path | None:
    RUNS.mkdir(parents=True, exist_ok=True)
    files = sorted(RUNS.glob("*_unique.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    return files[0] if files else None


def load_jobs(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    if isinstance(data, dict) and "results" in data:
        data = data["results"]
    if not isinstance(data, list):
        raise ValueError("JSON must be a list of jobs")
    return [j for j in data if isinstance(j, dict)]


def find_chrome() -> str | None:
    candidates = [
        Path(os.environ.get("PROGRAMFILES", r"C:\Program Files")) / "Google/Chrome/Application/chrome.exe",
        Path(os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)"))
        / "Google/Chrome/Application/chrome.exe",
        Path(os.environ.get("LOCALAPPDATA", "")) / "Google/Chrome/Application/chrome.exe",
    ]
    for c in candidates:
        if c.is_file():
            return str(c)
    return None


def _hidden_run_kwargs() -> dict:
    """Avoid flashing CMD windows on Windows when spawning bun/tasklist."""
    kw: dict = {
        "capture_output": True,
        "text": True,
        "encoding": "utf-8",
        "errors": "replace",
    }
    if sys.platform == "win32":
        # CREATE_NO_WINDOW = 0x08000000 — no console popup
        kw["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        si.wShowWindow = 0  # SW_HIDE
        kw["startupinfo"] = si
    return kw


def chrome_running() -> bool:
    try:
        out = subprocess.run(
            ["tasklist", "/FI", "IMAGENAME eq chrome.exe"],
            timeout=10,
            **_hidden_run_kwargs(),
        )
        return "chrome.exe" in (out.stdout or "").lower()
    except Exception:
        return False


def open_urls_in_chrome(urls: list[str]) -> None:
    """Open URLs as Chrome tabs using your normal profile (LinkedIn cookies).

    We do NOT auto-type LinkedIn passwords. Stay logged in once in Chrome;
    later opens reuse that session. Prefer Chrome already open.
    """
    clean = [u.strip() for u in urls if u and str(u).strip().startswith("http")]
    if not clean:
        raise ValueError("No hay URLs válidas")
    chrome = find_chrome()
    if not chrome:
        for u in clean:
            webbrowser.open(u)
        return

    # Use Default profile so LinkedIn login cookies apply.
    # If Chrome is already open with that profile, new tabs join that session.
    base = [chrome, "--profile-directory=Default"]
    for i in range(0, len(clean), 20):
        chunk = clean[i : i + 20]
        subprocess.Popen([*base, *chunk], close_fds=True)


class App(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Job Battery — LinkedIn results")
        self.geometry("1200x720")
        self.minsize(960, 560)
        self.jobs: list[dict] = []
        self.filtered: list[dict] = []
        self.current_file: Path | None = None
        self._build()
        newest = latest_unique()
        if newest:
            self._load_path(newest)

    def _build(self) -> None:
        nb = ttk.Notebook(self)
        nb.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        self.view = ttk.Frame(nb)
        self.run_tab = ttk.Frame(nb)
        nb.add(self.view, text="Resultados")
        nb.add(self.run_tab, text="Correr búsqueda")

        # --- Results tab ---
        top = ttk.Frame(self.view)
        top.pack(fill=tk.X, pady=(0, 4))
        ttk.Button(top, text="Abrir JSON…", command=self.open_file).pack(side=tk.LEFT)
        ttk.Button(top, text="Recargar último", command=self.reload_latest).pack(side=tk.LEFT, padx=4)
        ttk.Button(top, text="Abrir carpeta", command=lambda: os.startfile(RUNS)).pack(side=tk.LEFT, padx=4)
        ttk.Button(top, text="HTML con links", command=self.export_html).pack(side=tk.LEFT, padx=4)
        ttk.Button(top, text="Exportar CSV", command=self.export_csv).pack(side=tk.LEFT, padx=4)

        top2 = ttk.Frame(self.view)
        top2.pack(fill=tk.X, pady=(0, 6))
        ttk.Button(top2, text="▶ Abrir seleccionados en Chrome", command=self.open_selected_urls).pack(
            side=tk.LEFT
        )
        ttk.Button(top2, text="▶▶ Abrir TODOS los filtrados en Chrome", command=self.open_all_filtered_urls).pack(
            side=tk.LEFT, padx=8
        )
        ttk.Button(top2, text="Copiar links seleccionados", command=self.copy_selected_urls).pack(side=tk.LEFT, padx=4)
        ttk.Button(top2, text="1) Login LinkedIn", command=self.open_linkedin_login).pack(side=tk.LEFT, padx=8)

        self.file_label = ttk.Label(self.view, text="Sin archivo", foreground="#666")
        self.file_label.pack(anchor=tk.W)
        ttk.Label(
            self.view,
            text="Tip: primero «1) Login LinkedIn» (una vez) · deja Chrome abierto · luego abre jobs · Ctrl/Shift+clic = varios · clic en Link = uno",
            foreground="#444",
        ).pack(anchor=tk.W)

        filt = ttk.Frame(self.view)
        filt.pack(fill=tk.X, pady=4)
        ttk.Label(filt, text="Filtro texto").pack(side=tk.LEFT)
        self.q_var = tk.StringVar()
        self.q_var.trace_add("write", lambda *_: self.apply_filter())
        ttk.Entry(filt, textvariable=self.q_var, width=28).pack(side=tk.LEFT, padx=4)

        ttk.Label(filt, text="Ciudad búsqueda").pack(side=tk.LEFT, padx=(12, 0))
        self.loc_var = tk.StringVar(value="(todas)")
        self.loc_combo = ttk.Combobox(filt, textvariable=self.loc_var, width=28, state="readonly")
        self.loc_combo.pack(side=tk.LEFT, padx=4)
        self.loc_combo.bind("<<ComboboxSelected>>", lambda *_: self.apply_filter())

        ttk.Label(filt, text="Query").pack(side=tk.LEFT, padx=(12, 0))
        self.query_var = tk.StringVar(value="(todas)")
        self.query_combo = ttk.Combobox(filt, textvariable=self.query_var, width=28, state="readonly")
        self.query_combo.pack(side=tk.LEFT, padx=4)
        self.query_combo.bind("<<ComboboxSelected>>", lambda *_: self.apply_filter())

        table_frame = ttk.Frame(self.view)
        table_frame.pack(fill=tk.BOTH, expand=True)

        cols = ("title", "company", "location", "date", "query", "source", "url")
        self.tree = ttk.Treeview(table_frame, columns=cols, show="headings", selectmode="extended")
        headings = {
            "title": ("Título", 200),
            "company": ("Empresa", 130),
            "location": ("Ubicación", 130),
            "date": ("Fecha", 80),
            "query": ("Búsqueda", 120),
            "source": ("Fuente", 110),
            "url": ("Link (clic aquí)", 220),
        }
        for c, (text, w) in headings.items():
            self.tree.heading(c, text=text, command=lambda col=c: self.sort_by(col))
            self.tree.column(c, width=w, stretch=True)
        vsb = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=self.tree.yview)
        hsb = ttk.Scrollbar(table_frame, orient=tk.HORIZONTAL, command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        table_frame.rowconfigure(0, weight=1)
        table_frame.columnconfigure(0, weight=1)

        # Clic en columna Link (#7) → abrir ese job. Doble clic en cualquier lado → igual.
        self.tree.bind("<ButtonRelease-1>", self._on_tree_click)
        self.tree.bind("<Double-1>", lambda e: self.open_selected_urls())

        self.status = ttk.Label(self.view, text="0 jobs")
        self.status.pack(anchor=tk.W, pady=4)

        # --- Run tab ---
        form = ttk.Frame(self.run_tab, padding=8)
        form.pack(fill=tk.BOTH, expand=True)

        left = ttk.Frame(form)
        right = ttk.Frame(form)
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 8))
        right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # --- Roles checklist (persisted in role_presets.json) ---
        head_l = ttk.Frame(left)
        head_l.pack(fill=tk.X)
        ttk.Label(head_l, text="Roles estratégicos (marca los que quieres buscar)").pack(side=tk.LEFT)
        ttk.Button(head_l, text="Todos on", command=lambda: self._set_all_roles(True)).pack(side=tk.RIGHT, padx=2)
        ttk.Button(head_l, text="Todos off", command=lambda: self._set_all_roles(False)).pack(side=tk.RIGHT, padx=2)
        ttk.Button(head_l, text="Solo core+growth", command=self._enable_recommended).pack(side=tk.RIGHT, padx=2)

        roles_wrap = ttk.Frame(left)
        roles_wrap.pack(fill=tk.BOTH, expand=True)
        self.roles_canvas = tk.Canvas(roles_wrap, highlightthickness=0)
        roles_sb = ttk.Scrollbar(roles_wrap, orient=tk.VERTICAL, command=self.roles_canvas.yview)
        self.roles_inner = ttk.Frame(self.roles_canvas)
        self.roles_inner.bind(
            "<Configure>",
            lambda e: self.roles_canvas.configure(scrollregion=self.roles_canvas.bbox("all")),
        )
        self.roles_canvas.create_window((0, 0), window=self.roles_inner, anchor="nw")
        self.roles_canvas.configure(yscrollcommand=roles_sb.set)
        self.roles_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        roles_sb.pack(side=tk.RIGHT, fill=tk.Y)

        add_row = ttk.Frame(left)
        add_row.pack(fill=tk.X, pady=4)
        ttk.Label(add_row, text="Añadir rol").pack(side=tk.LEFT)
        self.new_role_var = tk.StringVar()
        ttk.Entry(add_row, textvariable=self.new_role_var, width=28).pack(side=tk.LEFT, padx=4)
        ttk.Button(add_row, text="+ Añadir", command=self.add_custom_role).pack(side=tk.LEFT)
        ttk.Button(add_row, text="💾 Guardar lista", command=self.save_presets).pack(side=tk.LEFT, padx=8)

        ttk.Label(right, text="Locations (una por línea — también se guardan)").pack(anchor=tk.W)
        self.locs_txt = tk.Text(right, height=16, wrap=tk.WORD)
        self.locs_txt.pack(fill=tk.BOTH, expand=True)

        src_row = ttk.Frame(self.run_tab, padding=(8, 4))
        src_row.pack(fill=tk.X)
        ttk.Label(src_row, text="Fuentes (marca las que quieres usar)").pack(side=tk.LEFT)
        self.src_linkedin = tk.BooleanVar(value=True)
        self.src_af = tk.BooleanVar(value=False)
        ttk.Checkbutton(src_row, text="LinkedIn (global)", variable=self.src_linkedin).pack(side=tk.LEFT, padx=12)
        ttk.Checkbutton(
            src_row,
            text="Arbetsförmedlingen / Platsbanken (Suecia)",
            variable=self.src_af,
        ).pack(side=tk.LEFT, padx=4)

        opts = ttk.Frame(self.run_tab, padding=8)
        opts.pack(fill=tk.X)
        ttk.Label(opts, text="Días").pack(side=tk.LEFT)
        self.jobage = tk.StringVar(value="14")
        ttk.Combobox(opts, textvariable=self.jobage, values=["7", "14", "30"], width=5, state="readonly").pack(
            side=tk.LEFT, padx=4
        )
        ttk.Label(opts, text="Modo (LinkedIn)").pack(side=tk.LEFT, padx=(12, 0))
        self.mode = tk.StringVar(value="hybrid")
        ttk.Combobox(opts, textvariable=self.mode, values=["hybrid", "onsite", "remote"], width=10, state="readonly").pack(
            side=tk.LEFT, padx=4
        )
        ttk.Label(opts, text="Límite / búsqueda").pack(side=tk.LEFT, padx=(12, 0))
        self.limit = tk.StringVar(value="8")
        ttk.Entry(opts, textvariable=self.limit, width=5).pack(side=tk.LEFT, padx=4)

        self.run_btn = ttk.Button(opts, text="▶ Correr batería", command=self.start_battery)
        self.run_btn.pack(side=tk.LEFT, padx=12)
        self.roles_count_lbl = ttk.Label(opts, text="")
        self.roles_count_lbl.pack(side=tk.LEFT, padx=8)
        ttk.Label(
            self.run_tab,
            text="Igual que los roles: ☑ LinkedIn y/o ☑ Arbetsförmedlingen. AF solo aplica a ciudades en Suecia.",
            foreground="#555",
        ).pack(anchor=tk.W, padx=8)

        self.log = tk.Text(self.run_tab, height=10, wrap=tk.WORD, state=tk.DISABLED)
        self.log.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        self._sort_col = None
        self._sort_desc = False
        self.role_vars: dict[str, tk.BooleanVar] = {}
        self.presets: dict = {"roles": [], "locations": [], "defaults": {}}
        self.load_presets_into_ui()

    def log_line(self, msg: str) -> None:
        def _():
            self.log.configure(state=tk.NORMAL)
            self.log.insert(tk.END, msg + "\n")
            self.log.see(tk.END)
            self.log.configure(state=tk.DISABLED)

        self.after(0, _)

    def load_presets_into_ui(self) -> None:
        if not PRESETS.exists():
            messagebox.showwarning("Presets", f"No encuentro {PRESETS}")
            return
        self.presets = json.loads(PRESETS.read_text(encoding="utf-8-sig"))
        defaults = self.presets.get("defaults") or {}
        if defaults.get("jobage"):
            self.jobage.set(str(defaults["jobage"]))
        if defaults.get("mode"):
            self.mode.set(str(defaults["mode"]))
        if defaults.get("limit"):
            self.limit.set(str(defaults["limit"]))
        srcs = defaults.get("sources") or {}
        if "linkedin" in srcs:
            self.src_linkedin.set(bool(srcs["linkedin"]))
        if "arbetsformedlingen" in srcs:
            self.src_af.set(bool(srcs["arbetsformedlingen"]))
        locs = self.presets.get("locations") or []
        self.locs_txt.delete("1.0", tk.END)
        self.locs_txt.insert("1.0", "\n".join(locs))
        self._rebuild_roles_checklist()

    def _rebuild_roles_checklist(self) -> None:
        for child in self.roles_inner.winfo_children():
            child.destroy()
        self.role_vars = {}
        for role in self.presets.get("roles") or []:
            rid = str(role.get("id") or role.get("title"))
            title = str(role.get("title") or "")
            tier = str(role.get("tier") or "")
            why = str(role.get("why") or "")
            var = tk.BooleanVar(value=bool(role.get("enabled")))
            self.role_vars[rid] = var
            row = ttk.Frame(self.roles_inner)
            row.pack(fill=tk.X, anchor=tk.W, pady=1)
            cb = ttk.Checkbutton(row, variable=var, command=self._update_roles_count)
            cb.pack(side=tk.LEFT)
            label = f"[{tier}] {title}"
            ttk.Label(row, text=label).pack(side=tk.LEFT)
            if why:
                ttk.Label(row, text=f" — {why[:70]}", foreground="#666").pack(side=tk.LEFT)
        self._update_roles_count()

    def _update_roles_count(self) -> None:
        n = sum(1 for v in self.role_vars.values() if v.get())
        total = len(self.role_vars)
        if hasattr(self, "roles_count_lbl"):
            self.roles_count_lbl.config(text=f"{n}/{total} roles activos")

    def _sync_enabled_from_ui(self) -> None:
        for role in self.presets.get("roles") or []:
            rid = str(role.get("id") or role.get("title"))
            if rid in self.role_vars:
                role["enabled"] = bool(self.role_vars[rid].get())
        locs = [ln.strip() for ln in self.locs_txt.get("1.0", tk.END).splitlines() if ln.strip()]
        self.presets["locations"] = locs
        self.presets["defaults"] = {
            "jobage": int(self.jobage.get() or 14),
            "mode": self.mode.get(),
            "limit": int(self.limit.get() or 8),
            "sources": {
                "linkedin": bool(self.src_linkedin.get()),
                "arbetsformedlingen": bool(self.src_af.get()),
            },
        }

    def save_presets(self) -> None:
        self._sync_enabled_from_ui()
        PRESETS.write_text(json.dumps(self.presets, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        self._update_roles_count()
        messagebox.showinfo("Guardado", f"Lista guardada en:\n{PRESETS}\n\nNo se pierde al correr otra batería.")

    def add_custom_role(self) -> None:
        title = self.new_role_var.get().strip()
        if not title:
            return
        rid = "custom-" + "".join(ch.lower() if ch.isalnum() else "-" for ch in title).strip("-")
        existing = {str(r.get("id")) for r in self.presets.get("roles") or []}
        if rid in existing:
            messagebox.showinfo("Ya existe", "Ese rol (o id similar) ya está en la lista.")
            return
        self.presets.setdefault("roles", []).append(
            {
                "id": rid,
                "title": title,
                "tier": "custom",
                "why": "Añadido por ti",
                "horizon": "2026-2027",
                "enabled": True,
            }
        )
        self.new_role_var.set("")
        self._rebuild_roles_checklist()
        self.save_presets()

    def _set_all_roles(self, value: bool) -> None:
        for v in self.role_vars.values():
            v.set(value)
        self._update_roles_count()

    def _enable_recommended(self) -> None:
        recommended = {"core", "growth", "differentiator", "nordic"}
        for role in self.presets.get("roles") or []:
            rid = str(role.get("id") or role.get("title"))
            if rid in self.role_vars:
                tier = str(role.get("tier") or "")
                self.role_vars[rid].set(tier in recommended)
        self._update_roles_count()

    def selected_query_titles(self) -> list[str]:
        self._sync_enabled_from_ui()
        out = []
        for role in self.presets.get("roles") or []:
            if role.get("enabled"):
                t = str(role.get("title") or "").strip()
                if t:
                    out.append(t)
        return out

    def open_file(self) -> None:
        path = filedialog.askopenfilename(
            initialdir=str(RUNS),
            filetypes=[("JSON", "*.json"), ("All", "*.*")],
        )
        if path:
            self._load_path(Path(path))

    def reload_latest(self) -> None:
        p = latest_unique()
        if not p:
            messagebox.showinfo("Sin datos", "No hay *_unique.json en job_scraper/linkedin_runs")
            return
        self._load_path(p)

    def _load_path(self, path: Path) -> None:
        try:
            self.jobs = load_jobs(path)
        except Exception as e:
            messagebox.showerror("Error", str(e))
            return
        self.current_file = path
        self.file_label.config(text=str(path))
        locs = sorted({str(j.get("searchLocation") or "") for j in self.jobs if j.get("searchLocation")})
        qs = sorted({str(j.get("query") or "") for j in self.jobs if j.get("query")})
        self.loc_combo["values"] = ["(todas)"] + locs
        self.query_combo["values"] = ["(todas)"] + qs
        self.loc_var.set("(todas)")
        self.query_var.set("(todas)")
        self.q_var.set("")
        self.apply_filter()

    def apply_filter(self) -> None:
        text = self.q_var.get().strip().lower()
        loc = self.loc_var.get()
        query = self.query_var.get()
        out = []
        for j in self.jobs:
            if loc != "(todas)" and str(j.get("searchLocation") or "") != loc:
                continue
            if query != "(todas)" and str(j.get("query") or "") != query:
                continue
            blob = " ".join(
                str(j.get(k) or "") for k in ("title", "company", "location", "query", "searchLocation")
            ).lower()
            if text and text not in blob:
                continue
            out.append(j)
        self.filtered = out
        self._render_tree()

    def _render_tree(self) -> None:
        self.tree.delete(*self.tree.get_children())
        for i, j in enumerate(self.filtered):
            url = str(j.get("url") or "")
            # Texto corto y claro en la columna Link (el URL real sigue en el job)
            link_label = "▶ ABRIR EN CHROME" if url else "(sin link)"
            self.tree.insert(
                "",
                tk.END,
                iid=str(i),
                values=(
                    j.get("title") or "",
                    j.get("company") or "",
                    j.get("location") or "",
                    j.get("date") or "",
                    j.get("query") or "",
                    j.get("source") or j.get("workplace") or "",
                    link_label,
                ),
            )
        nsel = len(self.tree.selection())
        self.status.config(
            text=f"{len(self.filtered)} / {len(self.jobs)} jobs · seleccionados: {nsel} · Chrome: {'OK' if find_chrome() else 'no encontrado (usará navegador default)'}"
        )

    def sort_by(self, col: str) -> None:
        if self._sort_col == col:
            self._sort_desc = not self._sort_desc
        else:
            self._sort_col = col
            self._sort_desc = False
        self.filtered.sort(key=lambda j: str(j.get(col) or "").lower(), reverse=self._sort_desc)
        self._render_tree()

    def _selected_jobs(self) -> list[dict]:
        out = []
        for iid in self.tree.selection():
            try:
                out.append(self.filtered[int(iid)])
            except (ValueError, IndexError):
                continue
        return out

    def _on_tree_click(self, event) -> None:
        # Columna #7 = Link → abrir solo esa fila en Chrome
        if self.tree.identify_region(event.x, event.y) != "cell":
            return
        col = self.tree.identify_column(event.x)  # '#1'..'#7'
        row = self.tree.identify_row(event.y)
        if not row or col != "#7":
            self.status.config(
                text=f"{len(self.filtered)} / {len(self.jobs)} jobs · seleccionados: {len(self.tree.selection())}"
            )
            return
        try:
            job = self.filtered[int(row)]
        except (ValueError, IndexError):
            return
        url = job.get("url")
        if not url:
            return
        try:
            open_urls_in_chrome([str(url)])
            self.status.config(text=f"Abierto: {job.get('title') or url}")
        except Exception as e:
            messagebox.showerror("Chrome", str(e))

    def open_linkedin_login(self) -> None:
        """Open LinkedIn login once — you sign in manually; we never store your password."""
        if not chrome_running():
            messagebox.showinfo(
                "LinkedIn login",
                "Se abrirá LinkedIn en Chrome.\n\n"
                "1) Inicia sesión tú (Google o email)\n"
                "2) Deja Chrome abierto\n"
                "3) Vuelve aquí y abre los jobs\n\n"
                "La app NO guarda ni escribe tu contraseña.",
            )
        try:
            open_urls_in_chrome(["https://www.linkedin.com/login"])
            self.status.config(text="Abre LinkedIn → inicia sesión → deja Chrome abierto")
        except Exception as e:
            messagebox.showerror("Chrome", str(e))

    def _warn_if_chrome_logged_out_hint(self) -> None:
        if not chrome_running():
            messagebox.showinfo(
                "Chrome / LinkedIn",
                "Chrome no estaba abierto.\n\n"
                "Si ves el popup «Log ind», pulsa «1) Login LinkedIn», "
                "entra una vez, deja Chrome abierto, y vuelve a abrir los jobs.\n\n"
                "No automatizamos la contraseña (seguridad + reglas de LinkedIn).",
            )

    def open_selected_urls(self) -> None:
        jobs = self._selected_jobs()
        if not jobs:
            messagebox.showinfo(
                "Selecciona",
                "Selecciona una o más filas (Ctrl+clic / Shift+clic),\n"
                "o haz un clic en la columna «Link» de una fila.",
            )
            return
        urls = [str(j.get("url") or "") for j in jobs]
        urls = [u for u in urls if u.startswith("http")]
        if not urls:
            messagebox.showwarning("Sin URL", "Las filas seleccionadas no tienen link.")
            return
        was_running = chrome_running()
        try:
            open_urls_in_chrome(urls)
            self.status.config(text=f"Abiertos en Chrome: {len(urls)} tabs")
            if not was_running:
                self._warn_if_chrome_logged_out_hint()
        except Exception as e:
            messagebox.showerror("Chrome", str(e))

    def open_all_filtered_urls(self) -> None:
        urls = [str(j.get("url") or "") for j in self.filtered if str(j.get("url") or "").startswith("http")]
        if not urls:
            messagebox.showinfo("Vacío", "No hay links en la vista filtrada.")
            return
        if len(urls) > 25:
            ok = messagebox.askyesno(
                "¿Abrir muchos tabs?",
                f"Vas a abrir {len(urls)} pestañas en Chrome.\n"
                "Puede ir lento. ¿Continuar?\n\n"
                "Tip: filtra antes (ciudad / query / texto) para abrir menos.",
            )
            if not ok:
                return
        was_running = chrome_running()
        try:
            open_urls_in_chrome(urls)
            self.status.config(text=f"Abiertos en Chrome: {len(urls)} tabs (filtrados)")
            if not was_running:
                self._warn_if_chrome_logged_out_hint()
        except Exception as e:
            messagebox.showerror("Chrome", str(e))

    def copy_selected_urls(self) -> None:
        jobs = self._selected_jobs()
        urls = [str(j.get("url") or "") for j in jobs if str(j.get("url") or "").startswith("http")]
        if not urls:
            messagebox.showinfo("Selecciona", "Selecciona filas que tengan link.")
            return
        self.clipboard_clear()
        self.clipboard_append("\n".join(urls))
        self.status.config(text=f"Copiados {len(urls)} links al portapapeles")

    def export_html(self) -> None:
        rows_src = self.filtered or self.jobs
        if not rows_src:
            messagebox.showinfo("Vacío", "No hay jobs para exportar.")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".html",
            initialdir=str(RUNS),
            initialfile=f"jobs_links_{datetime.now():%Y%m%d_%H%M}.html",
            filetypes=[("HTML", "*.html")],
        )
        if not path:
            return
        parts = []
        for j in rows_src:
            title = str(j.get("title") or "").replace("<", "&lt;")
            company = str(j.get("company") or "").replace("<", "&lt;")
            loc = str(j.get("location") or "").replace("<", "&lt;")
            url = str(j.get("url") or "")
            date = str(j.get("date") or "")
            q = str(j.get("query") or "").replace("<", "&lt;")
            link = f'<a href="{url}" target="_blank" rel="noopener">{url}</a>' if url else "(sin url)"
            parts.append(
                f"<tr><td>{date}</td><td>{title}</td><td>{company}</td><td>{loc}</td><td>{q}</td><td>{link}</td></tr>"
            )
        html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>LinkedIn jobs</title>
<style>
body{{font-family:Segoe UI,Arial,sans-serif;margin:24px;background:#111;color:#eee}}
input{{width:100%;max-width:480px;padding:8px;margin-bottom:12px}}
table{{border-collapse:collapse;width:100%;font-size:13px}}
th,td{{border-bottom:1px solid #333;padding:8px;text-align:left;vertical-align:top}}
th{{position:sticky;top:0;background:#1a1a1a}}
a{{color:#6cb6ff;word-break:break-all}}
</style></head><body>
<h1>LinkedIn jobs</h1>
<p>{len(rows_src)} ofertas — clic en el link</p>
<input id="f" placeholder="Filtrar..." oninput="filter()">
<table><thead><tr><th>Fecha</th><th>Titulo</th><th>Empresa</th><th>Ubicacion</th><th>Query</th><th>Link</th></tr></thead>
<tbody id="tb">{"".join(parts)}</tbody></table>
<script>
function filter(){{
  const q=document.getElementById('f').value.toLowerCase();
  for (const tr of document.querySelectorAll('#tb tr')) {{
    tr.style.display = tr.innerText.toLowerCase().includes(q) ? '' : 'none';
  }}
}}
</script></body></html>"""
        Path(path).write_text(html, encoding="utf-8")
        webbrowser.open(Path(path).as_uri())

    def export_csv(self) -> None:
        if not self.filtered:
            messagebox.showinfo("Vacío", "No hay filas filtradas.")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            initialdir=str(RUNS),
            initialfile=f"filtered_{datetime.now():%Y%m%d_%H%M}.csv",
            filetypes=[("CSV", "*.csv")],
        )
        if not path:
            return
        cols = ["title", "company", "location", "date", "query", "searchLocation", "url", "id"]
        lines = [",".join(cols)]
        for j in self.filtered:
            cells = []
            for c in cols:
                v = str(j.get(c) or "").replace('"', '""')
                cells.append(f'"{v}"')
            lines.append(",".join(cells))
        Path(path).write_text("\n".join(lines), encoding="utf-8-sig")
        messagebox.showinfo("OK", f"Guardado:\n{path}")

    def start_battery(self) -> None:
        sources: list[str] = []
        if self.src_linkedin.get():
            sources.append("linkedin")
        if self.src_af.get():
            sources.append("arbetsformedlingen")
        if not sources:
            messagebox.showwarning("Fuentes", "Marca al menos una fuente: LinkedIn y/o Arbetsförmedlingen.")
            return
        if "linkedin" in sources and not CLI_LINKEDIN.exists():
            messagebox.showerror("Falta CLI", f"No encuentro:\n{CLI_LINKEDIN}")
            return
        if "arbetsformedlingen" in sources and not CLI_AF.exists():
            messagebox.showerror("Falta CLI", f"No encuentro:\n{CLI_AF}")
            return
        # Persist selection BEFORE running so a new call never "loses" the list
        self._sync_enabled_from_ui()
        PRESETS.write_text(json.dumps(self.presets, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        queries = self.selected_query_titles()
        locs = [ln.strip() for ln in self.locs_txt.get("1.0", tk.END).splitlines() if ln.strip()]
        if not queries or not locs:
            messagebox.showwarning("Vacío", "Marca al menos 1 rol y 1 location.")
            return
        try:
            jobage = int(self.jobage.get())
            limit = int(self.limit.get())
        except ValueError:
            messagebox.showerror("Error", "Días y límite deben ser números.")
            return
        mode = self.mode.get()
        n_calls = len(queries) * len(locs) * len(sources)
        if n_calls > 80:
            ok = messagebox.askyesno(
                "Batería grande",
                f"{len(queries)} roles × {len(locs)} ciudades × {len(sources)} fuentes = {n_calls} búsquedas.\n"
                "Puede tardar / LinkedIn puede limitar. ¿Continuar?\n\n"
                "Tip: usa solo Arbetsförmedlingen + ciudades SE, o menos roles.",
            )
            if not ok:
                return
        self.run_btn.configure(state=tk.DISABLED)
        self.log.configure(state=tk.NORMAL)
        self.log.delete("1.0", tk.END)
        self.log.configure(state=tk.DISABLED)
        self.log_line(f"Saved presets → {PRESETS.name}")
        self.log_line(f"Fuente(s): {', '.join(sources)} · {n_calls} searches…")
        threading.Thread(
            target=self._run_battery,
            args=(queries, locs, jobage, mode, limit, sources),
            daemon=True,
        ).start()

    def _run_one_search(
        self,
        bun: str,
        env: dict,
        cli: Path,
        source: str,
        q: str,
        loc: str,
        jobage: int,
        mode: str,
        limit: int,
    ) -> list[dict]:
        cmd = [
            bun,
            "run",
            str(cli),
            "search",
            "-q",
            q,
            "-l",
            loc,
            "--jobage",
            str(jobage),
            "--limit",
            str(limit),
            "--format",
            "json",
        ]
        if source == "linkedin":
            cmd.extend(["--remote", mode])
        proc = subprocess.run(
            cmd,
            cwd=str(ROOT),
            env=env,
            timeout=120,
            **_hidden_run_kwargs(),
        )
        if proc.returncode != 0:
            self.log_line(f"   [{source}] error: {(proc.stderr or proc.stdout)[:200]}")
            return []
        try:
            payload = json.loads(proc.stdout)
            rows = payload.get("results") or []
        except json.JSONDecodeError:
            self.log_line(f"   [{source}] JSON parse fail")
            return []
        out = []
        for r in rows:
            jid = str(r.get("id") or "")
            if not jid:
                continue
            out.append(
                {
                    "query": q,
                    "searchLocation": loc,
                    "workplace": mode if source == "linkedin" else (r.get("source") or "arbetsformedlingen"),
                    "source": source,
                    "id": f"{source}:{jid}",
                    "title": r.get("title"),
                    "company": r.get("company"),
                    "location": r.get("location"),
                    "date": r.get("date"),
                    "url": r.get("url"),
                }
            )
        return out

    def _run_battery(
        self,
        queries: list[str],
        locs: list[str],
        jobage: int,
        mode: str,
        limit: int,
        sources: list[str],
    ) -> None:
        stamp = datetime.now().strftime("%Y%m%d_%H%M")
        out_jsonl = RUNS / f"battery_{stamp}.jsonl"
        out_unique = RUNS / f"battery_{stamp}_unique.json"
        RUNS.mkdir(parents=True, exist_ok=True)
        seen: dict[str, dict] = {}
        total = len(queries) * len(locs) * len(sources)
        n = 0
        env = os.environ.copy()
        extras = [
            str(Path.home() / ".bun" / "bin"),
            str(Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Bun"),
        ]
        for extra in extras:
            if extra and Path(extra).exists() and extra not in env.get("PATH", ""):
                env["PATH"] = extra + os.pathsep + env.get("PATH", "")

        bun = "bun"
        cli_map = {
            "linkedin": CLI_LINKEDIN,
            "arbetsformedlingen": CLI_AF,
        }
        self.log_line(f"Starting {total} searches → {out_unique.name}")
        try:
            for source in sources:
                cli = cli_map[source]
                for q in queries:
                    for loc in locs:
                        n += 1
                        self.log_line(f"[{n}/{total}] [{source}] {q} | {loc}")
                        try:
                            rows = self._run_one_search(bun, env, cli, source, q, loc, jobage, mode, limit)
                        except FileNotFoundError:
                            self.log_line("ERROR: bun no está en PATH. Abre una terminal nueva o reinstala Bun.")
                            self.after(0, lambda: self.run_btn.configure(state=tk.NORMAL))
                            return
                        except subprocess.TimeoutExpired:
                            self.log_line("   timeout")
                            continue
                        added = 0
                        with out_jsonl.open("a", encoding="utf-8") as fh:
                            for obj in rows:
                                fh.write(json.dumps(obj, ensure_ascii=False) + "\n")
                                jid = obj["id"]
                                if jid not in seen:
                                    seen[jid] = obj
                                    added += 1
                        self.log_line(f"   +{len(rows)} raw, +{added} new unique (total {len(seen)})")
        except Exception as e:
            self.log_line(f"FATAL: {e}")
            self.after(0, lambda: self.run_btn.configure(state=tk.NORMAL))
            return

        unique_list = list(seen.values())
        out_unique.write_text(json.dumps(unique_list, ensure_ascii=False, indent=2), encoding="utf-8")
        self.log_line(f"DONE. Unique={len(unique_list)}")
        self.log_line(str(out_unique))

        def finish():
            self.run_btn.configure(state=tk.NORMAL)
            self._load_path(out_unique)
            messagebox.showinfo("Listo", f"{len(unique_list)} jobs únicos.\nYa cargados en Resultados.")

        self.after(0, finish)


def main() -> None:
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
