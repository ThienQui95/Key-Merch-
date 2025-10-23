# addons_gop.py
# Công cụ "Phân tích Xu hướng Thị trường – PRO"
# - Theo dõi ASIN & keyword
# - Quét dữ liệu qua hook fetch_metrics(query, kind)
# - Tracker chạy nền theo chu kỳ
# - Phân tích xu hướng dựa trên BSR (giảm = lên xu hướng, tăng = mất xu hướng)

from __future__ import annotations
import os, sqlite3, threading, time, csv, json
from datetime import datetime, timedelta
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

# =======================
# UI toolkit (ttkbootstrap nếu có)
# =======================
try:
    import tkinter as tk
    from tkinter import messagebox, filedialog
    from ttkbootstrap import ttk
except Exception:
    import tkinter as tk
    from tkinter import messagebox, filedialog
    from tkinter import ttk

# =======================
# DB schema
# =======================
PRO_DDL = {
    "watches": """
        CREATE TABLE IF NOT EXISTS watches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            kind TEXT NOT NULL,                -- 'asin' | 'keyword'
            query TEXT NOT NULL,
            is_active INTEGER DEFAULT 1,
            created_at TEXT NOT NULL,
            UNIQUE(kind, query)
        );
    """,
    "product_metrics": """
        CREATE TABLE IF NOT EXISTS product_metrics (
            asin TEXT NOT NULL,
            date TEXT NOT NULL,                -- YYYY-MM-DD
            bsr INTEGER,
            price REAL,
            rating REAL,
            reviews INTEGER,
            title TEXT,
            img_url TEXT,
            url TEXT,
            UNIQUE(asin, date)
        );
    """,
}

# =======================
# Dataclass
# =======================
@dataclass
class Watch:
    id: int
    kind: str
    query: str
    is_active: int
    created_at: str

# =======================
# DB layer
# =======================
class ProDB:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._ensure()

    def _ensure(self):
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True) if os.path.dirname(self.db_path) else None
        with sqlite3.connect(self.db_path) as con:
            for ddl in PRO_DDL.values():
                con.execute(ddl)
            con.commit()

    # ----- watches -----
    def add_watch(self, kind: str, query: str):
        now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        with sqlite3.connect(self.db_path) as con:
            con.execute(
                "INSERT OR IGNORE INTO watches(kind, query, is_active, created_at) VALUES(?,?,1,?)",
                (kind, query, now),
            )
            con.commit()

    def list_watches(self, active_only: bool) -> List[Watch]:
        with sqlite3.connect(self.db_path) as con:
            cur = con.cursor()
            if active_only:
                cur.execute("SELECT id, kind, query, is_active, created_at FROM watches WHERE is_active=1 ORDER BY created_at DESC")
            else:
                cur.execute("SELECT id, kind, query, is_active, created_at FROM watches ORDER BY created_at DESC")
            rows = cur.fetchall()
        return [Watch(*r) for r in rows]

    def toggle_watch(self, watch_id: int, active: bool):
        with sqlite3.connect(self.db_path) as con:
            con.execute("UPDATE watches SET is_active=? WHERE id=?", (1 if active else 0, watch_id))
            con.commit()

    def delete_watch(self, watch_id: int):
        with sqlite3.connect(self.db_path) as con:
            con.execute("DELETE FROM watches WHERE id=?", (watch_id,))
            con.commit()

    # ----- metrics -----
    def upsert_pro_metrics(self, items: List[Dict[str, Any]]):
        """items: [{asin, date(optional), bsr, price, rating, reviews, title, img_url, url}]"""
        if not items:
            return
        today = datetime.utcnow().strftime("%Y-%m-%d")
        with sqlite3.connect(self.db_path) as con:
            for it in items:
                asin = it.get("asin")
                if not asin:
                    continue
                d = it.get("date") or today
                con.execute(
                    """
                    INSERT INTO product_metrics(asin, date, bsr, price, rating, reviews, title, img_url, url)
                    VALUES(?,?,?,?,?,?,?,?,?)
                    ON CONFLICT(asin, date) DO UPDATE SET
                        bsr=excluded.bsr,
                        price=excluded.price,
                        rating=excluded.rating,
                        reviews=excluded.reviews,
                        title=COALESCE(excluded.title, title),
                        img_url=COALESCE(excluded.img_url, img_url),
                        url=COALESCE(excluded.url, url)
                    """,
                    (
                        asin,
                        d,
                        it.get("bsr"),
                        it.get("price"),
                        it.get("rating"),
                        it.get("reviews"),
                        it.get("title"),
                        it.get("img_url"),
                        it.get("url"),
                    ),
                )
            con.commit()

    # ----- analysis -----
    def analyze_trends(self, days_ago: int = 7, min_change_pct: float = 20.0) -> Tuple[List[Dict], List[Dict]]:
        """Trả về (trending_up_list, trending_down_list) dựa trên mọi ASIN có dữ liệu."""
        since_date = (datetime.utcnow().date() - timedelta(days=days_ago)).isoformat()
        trending_up, trending_down = [], []

        with sqlite3.connect(self.db_path) as con:
            asins = [
                r[0]
                for r in con.execute(
                    "SELECT DISTINCT asin FROM product_metrics WHERE date >= ? AND bsr IS NOT NULL",
                    (since_date,),
                ).fetchall()
            ]

            for asin in asins:
                rows = con.execute(
                    """
                    SELECT date, bsr, title
                    FROM product_metrics
                    WHERE asin=? AND date >= ? AND bsr IS NOT NULL
                    ORDER BY date ASC
                    """,
                    (asin, since_date),
                ).fetchall()
                if len(rows) < 2:
                    continue

                first_bsr, last_bsr = rows[0][1], rows[-1][1]
                if not first_bsr or not last_bsr:
                    continue
                change_pct = ((first_bsr - last_bsr) / float(first_bsr)) * 100.0
                if abs(change_pct) < min_change_pct:
                    continue

                item = {
                    "asin": asin,
                    "title": rows[-1][2] or "N/A",
                    "change_pct": f"{change_pct:+.1f}%",
                    "bsr_start": first_bsr,
                    "bsr_end": last_bsr,
                    "days": (datetime.strptime(rows[-1][0], "%Y-%m-%d").date()
                             - datetime.strptime(rows[0][0], "%Y-%m-%d").date()).days + 1,
                }
                if change_pct > 0:
                    trending_up.append(item)
                else:
                    trending_down.append(item)

        trending_up.sort(key=lambda x: float(x["change_pct"][:-1]), reverse=True)
        trending_down.sort(key=lambda x: float(x["change_pct"][:-1]))
        return trending_up, trending_down

    # tiện ích export
    def export_metrics_csv(self, filepath: str):
        with sqlite3.connect(self.db_path) as con, open(filepath, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["asin", "date", "bsr", "price", "rating", "reviews", "title", "img_url", "url"])
            for row in con.execute("SELECT asin, date, bsr, price, rating, reviews, title, img_url, url FROM product_metrics ORDER BY date DESC"):
                w.writerow(row)

# =======================
# Tracker nền
# =======================
class ProTracker:
    def __init__(self, db: ProDB, fetch_metrics, interval_hours: int = 4):
        self.db = db
        self.fetch_metrics = fetch_metrics
        self.interval = max(1, int(interval_hours)) * 60  # phút
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()

    def _run(self):
        while not self._stop.is_set():
            # 1) Quét theo ASIN
            for w in [w for w in self.db.list_watches(True) if w.kind == "asin"]:
                if self._stop.is_set():
                    break
                try:
                    items = self.fetch_metrics(w.query, "asin")
                    self.db.upsert_pro_metrics(items)
                except Exception as e:
                    print(f"[ProTracker] error asin={w.query}: {e}")

            # 2) Quét theo KEYWORD
            for w in [w for w in self.db.list_watches(True) if w.kind == "keyword"]:
                if self._stop.is_set():
                    break
                try:
                    items = self.fetch_metrics(w.query, "keyword")
                    self.db.upsert_pro_metrics(items)
                except Exception as e:
                    print(f"[ProTracker] error keyword='{w.query}': {e}")

            # ngủ theo phút
            for _ in range(self.interval):
                if self._stop.is_set():
                    break
                time.sleep(60)

# =======================
# UI Window
# =======================
class MarketTrendWindow(tk.Toplevel):
    def __init__(self, master, db: ProDB, fetch_metrics):
        super().__init__(master)
        self.title("Phân tích Xu hướng Thị trường – PRO")
        self.geometry("1080x640")
        self.db = db
        self.tracker = ProTracker(db, fetch_metrics, interval_hours=4)

        # Khung chính
        outer = ttk.Frame(self, padding=8)
        outer.pack(fill=tk.BOTH, expand=True)

        # 1) Watchlist
        self._build_watchlist_frame(outer).pack(fill=tk.BOTH, expand=False, pady=(0, 8))

        # 2) Results – trending up / down
        result_frame = ttk.Frame(outer)
        result_frame.pack(fill=tk.BOTH, expand=True)

        self.up_tree = self._build_table(result_frame, "Đang Lên Xu Hướng (BSR giảm)")
        self.up_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 4))

        self.down_tree = self._build_table(result_frame, "Đang Mất Xu Hướng (BSR tăng)")
        self.down_tree.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(4, 0))

        self._reload_watchlist()
        self.refresh_analysis_display()

    # ----- UI builders -----
    def _build_watchlist_frame(self, master):
        frame = ttk.Labelframe(master, text="Quản lý Danh sách Theo dõi", padding=10)

        ctrl = ttk.Frame(frame); ctrl.pack(fill=tk.X, pady=(0, 10))

        # chọn loại
        self.kind_var = tk.StringVar(value="keyword")
        ttk.Label(ctrl, text="Loại:").pack(side=tk.LEFT, padx=(0, 5))
        ttk.Combobox(ctrl, textvariable=self.kind_var, values=("asin", "keyword"),
                     state="readonly", width=10).pack(side=tk.LEFT, padx=(0, 10))

        # nhập query
        self.q_var = tk.StringVar()
        ttk.Label(ctrl, text="ASIN/Từ khoá:").pack(side=tk.LEFT, padx=(0, 5))
        ttk.Entry(ctrl, textvariable=self.q_var, width=40).pack(side=tk.LEFT)

        ttk.Button(ctrl, text="Thêm Theo dõi", command=self._on_add).pack(side=tk.LEFT, padx=6)
        ttk.Button(ctrl, text="Quét Dữ liệu Ngay", command=self._scan_now).pack(side=tk.RIGHT, padx=6)
        ttk.Button(frame, text="⟳ Phân Tích Lại Xu Hướng",
                   command=self.refresh_analysis_display).pack(fill=tk.X, pady=5)

        tree_frame = ttk.Frame(frame); tree_frame.pack(fill=tk.BOTH, expand=True)
        cols = ("id", "query", "is_active", "created_at")
        widths = {"id": 60, "query": 300, "is_active": 80, "created_at": 160}
        self.watch_tree = ttk.Treeview(tree_frame, columns=cols, show="headings", height=6)
        for c, w in widths.items():
            self.watch_tree.heading(c, text=c)
            self.watch_tree.column(c, width=w, anchor="w")
        self.watch_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        btns = ttk.Frame(tree_frame, padding=(10, 0)); btns.pack(side=tk.RIGHT, fill=tk.Y)
        ttk.Button(btns, text="Bật", command=lambda: self._toggle(True)).pack(pady=2)
        ttk.Button(btns, text="Tắt", command=lambda: self._toggle(False)).pack(pady=2)
        ttk.Button(btns, text="Xóa", command=self._delete).pack(pady=2)
        ttk.Button(btns, text="Xuất CSV", command=self._export_csv).pack(pady=12)

        return frame

    def _build_table(self, master, title: str):
        lab = ttk.Labelframe(master, text=title, padding=6)
        cols = ("asin", "title", "change_pct", "bsr_end", "bsr_start", "days")
        widths = {"asin": 120, "title": 360, "change_pct": 90, "bsr_end": 90, "bsr_start": 90, "days": 60}
        tree = ttk.Treeview(lab, columns=cols, show="headings")
        for c, w in widths.items():
            tree.heading(c, text=c)
            tree.column(c, width=w, anchor="w")
        tree.pack(fill=tk.BOTH, expand=True)
        return lab if False else tree  # để trả về tree (không bọc lab)

    # ----- actions -----
    def _reload_watchlist(self):
        [self.watch_tree.delete(i) for i in self.watch_tree.get_children()]
        for w in self.db.list_watches(False):
            self.watch_tree.insert(
                "", tk.END,
                values=(w.id, f"[{w.kind}] {w.query}", "✔️" if w.is_active else "❌", w.created_at)
            )

    def _on_add(self):
        q = (self.q_var.get() or "").strip()
        if not q:
            return
        kind = (self.kind_var.get() or "asin").lower()
        try:
            self.db.add_watch("keyword" if kind == "keyword" else "asin", q)
            self._reload_watchlist()
        except Exception as e:
            messagebox.showerror("Lỗi", str(e))

    def _toggle(self, active: bool):
        sel = self.watch_tree.selection()
        if not sel:
            return
        try:
            _id = int(self.watch_tree.item(sel[0])["values"][0])
            self.db.toggle_watch(_id, active)
            self._reload_watchlist()
        except Exception as e:
            messagebox.showerror("Lỗi", str(e))

    def _delete(self):
        sel = self.watch_tree.selection()
        if not sel:
            return
        try:
            _id = int(self.watch_tree.item(sel[0])["values"][0])
            self.db.delete_watch(_id)
            self._reload_watchlist()
        except Exception as e:
            messagebox.showerror("Lỗi", str(e))

    def _export_csv(self):
        fp = filedialog.asksaveasfilename(
            title="Lưu dữ liệu",
            defaultextension=".csv",
            filetypes=[("CSV", "*.csv")]
        )
        if not fp:
            return
        try:
            self.db.export_metrics_csv(fp)
            messagebox.showinfo("Xuất CSV", f"Đã lưu: {fp}")
        except Exception as e:
            messagebox.showerror("Lỗi", str(e))

    def _scan_now(self):
        messagebox.showinfo("Quét dữ liệu", "Bắt đầu quét. Quá trình này có thể mất vài phút.")

        def run():
            try:
                # ASIN
                for w in [w for w in self.db.list_watches(True) if w.kind == "asin"]:
                    self.db.upsert_pro_metrics(self.tracker.fetch_metrics(w.query, "asin"))
                # KEYWORD
                for w in [w for w in self.db.list_watches(True) if w.kind == "keyword"]:
                    self.db.upsert_pro_metrics(self.tracker.fetch_metrics(w.query, "keyword"))

                self.after(100, lambda: messagebox.showinfo("Quét dữ liệu", "Quét xong. Nhấn 'Phân Tích Lại' để xem kết quả."))
            except Exception as e:
                self.after(100, lambda: messagebox.showerror("Lỗi Quét", str(e)))

        threading.Thread(target=run, daemon=True).start()

    def refresh_analysis_display(self):
        # clear
        for tree in (self.up_tree, self.down_tree):
            for i in tree.get_children():
                tree.delete(i)
        ups, downs = self.db.analyze_trends(days_ago=7, min_change_pct=20.0)
        for it in ups:
            self.up_tree.insert("", tk.END, values=(it["asin"], it["title"], it["change_pct"], it["bsr_end"], it["bsr_start"], it["days"]))
        for it in downs:
            self.down_tree.insert("", tk.END, values=(it["asin"], it["title"], it["change_pct"], it["bsr_end"], it["bsr_start"], it["days"]))

# =======================
# ToolManager: gắn menu vào root
# =======================
class ToolManager:
    def __init__(self, root, db_path: str, hooks: Dict):
        self.root = root
        self.db = ProDB(db_path)
        self.fetch_metrics = hooks.get("fetch_metrics", lambda q, k: [])
        self.pro_window: Optional[MarketTrendWindow] = None
        self.pro_tracker = ProTracker(self.db, self.fetch_metrics, interval_hours=4)

    def _ensure_menu(self):
        if not hasattr(self.root, "menu") and hasattr(self.root, "config"):
            m = tk.Menu(self.root)
            self.root.config(menu=m)
            self.root.menu = m  # type: ignore
        if hasattr(self.root, "menu"):
            return self.root.menu
        return None

    def mount_all_menus(self):
        menu = self._ensure_menu()
        if menu is None:
            return
        pro_menu = tk.Menu(menu, tearoff=0)
        menu.add_cascade(label="PRO", menu=pro_menu)

        def open_pro():
            if self.pro_window and tk.Toplevel.winfo_exists(self.pro_window):
                try:
                    self.pro_window.lift()
                    return
                except Exception:
                    pass
            self.pro_window = MarketTrendWindow(self.root, self.db, self.fetch_metrics)

        pro_menu.add_command(label="Phân tích Xu hướng…", command=open_pro)
        pro_menu.add_separator()
        pro_menu.add_checkbutton(label="Chạy nền (4h)", command=self._toggle_pro_tracker)

    def _toggle_pro_tracker(self):
        t = self.pro_tracker
        if not t._thread or not t._thread.is_alive():
            t.start()
            messagebox.showinfo("PRO", "Tracker chạy nền đã bật.")
        else:
            t.stop()
            messagebox.showinfo("PRO", "Tracker chạy nền đã tắt.")

# =======================
# API gắn vào app
# =======================
def attach_all_tools(root, db_path: str, hooks: Dict, **kwargs):
    if "fetch_metrics" not in hooks or not callable(hooks.get("fetch_metrics")):
        hooks["fetch_metrics"] = lambda q, k: []
    manager = ToolManager(root, db_path, hooks)
    manager.mount_all_menus()
    return manager
