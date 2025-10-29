# -*- coding: utf-8 -*-
"""
Visual Spy — Key-only final build (Optimized Version - Full Restore)
- Khôi phục code đầy đủ, giữ tất cả tính năng.
- Tối ưu hóa khởi động bằng cách chạy xác thực license ở luồng nền.
- Tối ưu hóa hiệu năng cuộn và tải ảnh bằng ThreadPoolExecutor.
- Tái cấu trúc code để dễ đọc và bảo trì hơn.
- Sửa lỗi hiển thị (lệch hàng và bị cắt ở cuối).
- SỬA LỖI KHỞI ĐỘNG: Chỉ dùng 1 root window duy nhất.
- SỬA LỖI GIAO DIỆN: Kích hoạt DPI Awareness cho Windows.
- Thêm tùy chọn bật/tắt DPI Awareness.
- Sửa lỗi nút Phân tích, Yêu thích. Khôi phục Phân tích Niche.
- Sửa lỗi Phân tích Niche và thêm copy/link/biểu đồ cho Twitter Trends.
- Thêm bộ lọc ngày đăng thực tế cho chế độ Quét Mới.
- Cập nhật Phân Tích Niche để lấy cả áo Mới và Bán Chạy.
- Thêm copy và biểu đồ cho Phân Tích Niche, lọc thêm stop words.
- Thêm bộ lọc từ khóa, xem chi tiết SP, cải thiện phân tích keyword (card).
- Sửa lỗi AttributeError bằng cách sắp xếp lại thứ tự hàm.
"""

import sys
import requests
import tkinter as tk
from tkinter import simpledialog, messagebox, filedialog, Menu # Thêm Menu
import sqlite3
import httpx
from parsel import Selector
# Sửa: Import datetime chuẩn
from datetime import datetime, timedelta
import threading
from PIL import Image, ImageTk, ImageDraw, ImageFont # Thêm ImageFont
from io import BytesIO
import webbrowser
import time
import random
import math
import bcrypt
import re
from collections import Counter
from queue import Queue
import csv
import os
from concurrent.futures import ThreadPoolExecutor
# SỬA LỖI GIAO DIỆN MỜ: Import ctypes
import ctypes
# Thêm urllib.parse để tạo URL an toàn
import urllib.parse

# SỬA LỖI: Chỉ import ttk và Toplevel, không import Window nữa
from ttkbootstrap import Style, ttk, Toplevel
from ttkbootstrap.constants import *

# ===== Cài đặt Giao diện =====
# Đặt thành True để giao diện rõ nét trên màn hình phân giải cao (cần khởi động lại)
# Đặt thành False để giao diện mờ (có thể hơi khác biệt)
ENABLE_HIGH_DPI = True
# ============================

# ===== Cài đặt Bộ lọc =====
# Đặt thành True để lọc bỏ áo "Mới" có ngày đăng thực tế quá cũ
FILTER_NEWEST_BY_ACTUAL_DATE = True
# Số ngày tối đa cho phép đối với áo "Mới" (nếu FILTER_NEWEST_BY_ACTUAL_DATE = True)
MAX_NEWEST_AGE_DAYS = 30
# =========================

# ===== Supabase config (điền đúng dự án của bạn) =====
# !!! KIỂM TRA LẠI URL NÀY !!!
SUPABASE_URL = "https://vkrsmgzgfbzcwwlwqkcg.supabase.co"
# !!! KIỂM TRA LẠI KEY NÀY - ĐÂY LÀ NGUYÊN NHÂN LỖI 401 !!!
SUPABASE_ANON_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InZrcnNtZ3pnZmJ6Y3d3bHdxa2NnIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc2MTEyMjY1NiwiZXhwIjoyMDc2Njk4NjU2fQ.vbBc82Hsm9GaaTcJAgXaybwETS9BgOtgKJW7x1NVYKg"
LICENSE_TABLE  = "licenses"
LICENSE_COLUMN = "license key"
ACTIVE_COLUMN  = "is active"
ACTIVE_TRUTHY  = True
# =====================================================

# TỐI ƯU HÓA (HIỆU NĂNG): Tạo một session duy nhất để Supabase tái sử dụng kết nối
# Cập nhật session nếu key thay đổi
supabase_session = requests.Session()
supabase_session.headers.update({
    "apikey": SUPABASE_ANON_KEY, # Sẽ dùng key mới cập nhật
    "Authorization": f"Bearer {SUPABASE_ANON_KEY}", # Sẽ dùng key mới cập nhật
    "Accept": "application/json",
    "Prefer": "count=exact",
})

def verify_license_with_supabase(user_key: str):
    # Cập nhật lại header phòng trường hợp key bị thay đổi sau khi khởi tạo session
    supabase_session.headers.update({
        "apikey": SUPABASE_ANON_KEY,
        "Authorization": f"Bearer {SUPABASE_ANON_KEY}",
    })

    base = SUPABASE_URL.strip().rstrip("/")
    if not base or not SUPABASE_ANON_KEY or "DÁN_KEY_ANON" in SUPABASE_ANON_KEY: # Thêm kiểm tra placeholder
        return False, "Thiếu SUPABASE_URL hoặc SUPABASE_ANON_KEY."
    rest = f"{base}/rest/v1/{LICENSE_TABLE}"
    key = (user_key or "").strip() # Thống nhất dùng keep original case (no forced uppercase)

    def _get(params: dict):
        try:
            r = supabase_session.get(rest, params=params, timeout=12)
            # print(f"Verifying key with params: {params}") # Bỏ print này đi cho đỡ rối console
            # print(f"Response: {r.status_code}")
            return r
        except requests.RequestException as e:
            print(f"Supabase request failed: {e}")
            return None

    col = LICENSE_COLUMN.strip()
    key_conditions = f'"{col}".eq.{key}'
    active_condition = f'"{ACTIVE_COLUMN}".is.{str(ACTIVE_TRUTHY).lower()}'
    params = {
        "select": "*",
        "and": f'({key_conditions},{active_condition})'
    }

    r = _get(params)

    if r is None:
        return False, "Lỗi kết nối mạng khi xác thực."

    if r.status_code == 401:
        return False, "Lỗi xác thực (401): API Key không hợp lệ. Vui lòng kiểm tra lại SUPABASE_ANON_KEY trong code."
    elif r.status_code == 404:
        return False, f"Lỗi (404): Không tìm thấy tài nguyên. Kiểm tra lại SUPABASE_URL ('{SUPABASE_URL}') và LICENSE_TABLE ('{LICENSE_TABLE}')."
    elif r.status_code == 400:
        try:
            err_details = r.json(); msg = err_details.get("message", "Lỗi không rõ")
            if "does not exist" in msg:
                return False, f"Lỗi cấu hình (400): Cột không tồn tại. Kiểm tra lại LICENSE_COLUMN ('{LICENSE_COLUMN}') hoặc ACTIVE_COLUMN ('{ACTIVE_COLUMN}'). Chi tiết: {msg}"
        except Exception: pass
        return False, f"Lỗi truy vấn (400): {r.text[:200]}"
    elif r.status_code != 200:
        return False, f"Lỗi không xác định ({r.status_code}): {r.text[:200]}"

    data = r.json()
    if isinstance(data, list) and data:
        # print(f"Success: Found {len(data)} matching active key(s).") # Tắt bớt log
        return True, data[0]

    return False, "License Key không hợp lệ hoặc chưa được kích hoạt."


class LicenseDialog:
    def __init__(self, parent_root):
        self.root = parent_root
        try: self.root.update()
        except Exception: pass
        self.result = None; self.dialog = None; self.key_entry = None
        self.verification_result = (False, None)

    def ask(self):
        self._build_dialog_ui()
        # SỬA LỖI: Không cần wait_window nếu root đang hiển thị
        # self.root.wait_window(self.dialog)
        self.dialog.wait_window() # Dialog tự chờ chính nó

        if self.result is None: return False
        key_to_verify = self.result
        while True:
            progress_win = self._create_progress_window()
            verify_thread = threading.Thread(target=self._verify_in_background, args=(key_to_verify,), daemon=True); verify_thread.start()
            while verify_thread.is_alive(): self.root.update_idletasks(); self.root.update(); time.sleep(0.05)
            # SỬA LỖI: Hủy progress_win an toàn hơn
            try: progress_win.destroy()
            except tk.TclError: pass

            ok, info = self.verification_result
            if ok: self.result = key_to_verify; break
            else:
                messagebox.showerror("Không xác thực được", f"Lỗi: {info}", parent=self.root)
                self._build_dialog_ui(initial_value=key_to_verify)
                # self.root.wait_window(self.dialog) # Không cần wait root
                self.dialog.wait_window() # Dialog tự chờ
                if self.result is None: return False
                key_to_verify = self.result
        return self.result

    def _build_dialog_ui(self, initial_value=""):
        self.dialog = Toplevel(master=self.root, title="Xác thực License")
        self.dialog.geometry("400x200"); self.dialog.transient(self.root); self.dialog.grab_set(); self.dialog.resizable(False, False)
        main_frame = ttk.Frame(self.dialog, padding=20); main_frame.pack(fill=BOTH, expand=True)
        ttk.Label(main_frame, text="Vui lòng nhập License Key của bạn:", font=("-size 11")).pack(pady=(0, 10))
        self.key_entry = ttk.Entry(main_frame, font=("-size 10"), bootstyle=PRIMARY); self.key_entry.insert(0, initial_value); self.key_entry.pack(fill=X, ipady=5, pady=10); self.key_entry.focus_set()
        submit_btn = ttk.Button(main_frame, text="Xác thực", bootstyle=SUCCESS, command=self._on_submit); submit_btn.pack(fill=X, ipady=5, pady=5)
        self.key_entry.bind("<Return>", lambda e: self._on_submit()); self.dialog.protocol("WM_DELETE_WINDOW", self._on_cancel)
        self._center_dialog(); self.dialog.update_idletasks()
        # SỬA LỖI: Đảm bảo dialog hiện lên trên
        self.dialog.lift()
        self.dialog.attributes("-topmost", True)
        self.dialog.after(100, lambda: self.dialog.attributes("-topmost", False))
        self.dialog.focus_force()

    def _center_dialog(self):
        self.root.update_idletasks(); d_width = self.dialog.winfo_reqwidth(); d_height = self.dialog.winfo_reqheight()
        s_width = self.root.winfo_screenwidth(); s_height = self.root.winfo_screenheight()
        x = (s_width // 2) - (d_width // 2); y = (s_height // 2) - (d_height // 2)
        self.dialog.geometry(f"{d_width}x{d_height}+{x}+{y}")

    def _on_submit(self):
        key = self.key_entry.get().strip()
        if not key: messagebox.showwarning("Chưa nhập", "Vui lòng nhập key.", parent=self.dialog); return
        self.result = key;
        if self.dialog: self.dialog.destroy(); self.dialog = None

    def _on_cancel(self):
        self.result = None;
        if self.dialog: self.dialog.destroy(); self.dialog = None

    def _create_progress_window(self):
        win = Toplevel(master=self.root); win.title("Đang kiểm tra..."); win.geometry("300x100"); win.transient(self.root); win.grab_set(); win.resizable(False, False)
        f = ttk.Frame(win, padding=20); f.pack(fill=BOTH, expand=True); ttk.Label(f, text="Đang xác thực key, vui lòng chờ...").pack(pady=5)
        pb = ttk.Progressbar(f, mode=INDETERMINATE, bootstyle=SUCCESS); pb.pack(fill=X, pady=5); pb.start(10)
        self._center_dialog_over_dialog(win); win.update(); return win

    def _center_dialog_over_dialog(self, win):
        self.root.update_idletasks(); d_width = win.winfo_reqwidth(); d_height = win.winfo_reqheight()
        s_width = self.root.winfo_screenwidth(); s_height = self.root.winfo_screenheight()
        x = (s_width // 2) - (d_width // 2); y = (s_height // 2) - (d_height // 2)
        win.geometry(f"{d_width}x{d_height}+{x}+{y}")

    def _verify_in_background(self, key): self.verification_result = verify_license_with_supabase(key)

# ==============================================================================
# --- LỚP CẤU HÌNH (CONFIG) ---
# ==============================================================================
class Config:
    DATABASE_FILE = 'memory.db'
    MAX_PRODUCTS_IN_DB = 100000
    BASE_URL = "https://www.amazon.com/s?k=t-shirt&i=fashion-novelty&rh=p_6%3AATVPDKIKX0DER&hidden-keywords=Lightweight%2C+Classic+fit%2C+Double-needle+sleeve+and+bottom+hem+-Longsleeve+-Raglan+-Vneck+-Tanktop"
    USER_AGENTS = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36'
    ]
    HEADERS = {'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8', 'Accept-Language': 'en-US,en;q=0.9'}
    PRODUCTS_PER_PAGE = 30
    MAX_SCAN_PAGES = 3
    DEFAULT_BSR = 9999999
    MAX_SCAN_WORKERS = 8
    MAX_IMAGE_WORKERS = 10
    IMAGE_WIDTH, IMAGE_HEIGHT = 200, 200 # Kích thước ảnh card
    DETAIL_IMAGE_WIDTH, DETAIL_IMAGE_HEIGHT = 400, 400 # Kích thước ảnh chi tiết
    CARD_BORDER_RADIUS = 15

    # Cập nhật STOP_WORDS
    STOP_WORDS = set([
        # General
        'the', 'and', 'for', 'with', 'a', 'an', 'is', 'it', 'to', 'of', 'in', 'on',
        'buy', 'now', 'my', 'your', 'from', 'at', 'i', 'you', 'he', 'she', 'we', 'they',
        'me', 'him', 'her', 'us', 'them',
        # Clothing Specific
        'shirt', 'tshirt', 't-shirt', 'tee', 'graphic', 'sleeve', 'clothing', 'apparel', 'wear', 'top', 'design',
        # Common descriptors
        'men', 'women', 'mens', 'womens', 'boys', 'girls', 'kids', 'youth', 'adult',
        'funny', 'cute', 'vintage', 'retro', 'awesome', 'cool', 'great',
        # Occasions/Themes (optional, có thể giữ lại tùy niche)
         'gift', 'gifts', 'birthday', 'christmas', 'halloween', 'party'
    ])
    MIN_WORD_LENGTH = 3

    TRADEMARK_DATABASE = [
        {"keyword": "just do it", "class": "IC 025", "status": "Live", "risk": "High"},
        {"keyword": "disney", "class": "Multiple", "status": "Live", "risk": "High"},
        {"keyword": "marvel", "class": "Multiple", "status": "Live", "risk": "High"},
        {"keyword": "star wars", "class": "Multiple", "status": "Live", "risk": "High"},
        {"keyword": "keep calm and carry on", "class": "IC 025", "status": "Live", "risk": "Medium"}
    ]

    BG_COLOR, SIDEBAR_COLOR, CARD_COLOR = "#0D1117", "#161B22", "#161B22"
    BORDER_COLOR, ACCENT_COLOR = "#30363d", "#58A6FF"
    PRIMARY_TEXT, SECONDARY_TEXT = "#c9d1d9", "#8b949e"
    SUCCESS_COLOR, ERROR_COLOR, WARNING_COLOR = "#238636", "#f85149", "#e3b341"
    PRO_FEATURE_COLOR = "#f97316"

# ==============================================================================
# --- LỚP TIỆN ÍCH ---
# ==============================================================================

class CreateToolTip:
    def __init__(self, widget, text):
        self.widget, self.text, self.tooltip = widget, text, None
        self.widget.bind("<Enter>", self.show); self.widget.bind("<Leave>", self.hide)
    def show(self, e):
        if self.tooltip: return
        x, y, _, _ = self.widget.bbox("insert"); x += self.widget.winfo_rootx() + 25; y += self.widget.winfo_rooty() + 25
        # SỬA LỖI: master phải là cửa sổ gốc của widget (self.widget.winfo_toplevel())
        self.tooltip = Toplevel(master=self.widget.winfo_toplevel());
        self.tooltip.wm_overrideredirect(True); self.tooltip.wm_geometry(f"+{x}+{y}")
        label = ttk.Label(self.tooltip, text=self.text, background="#30363d", foreground="white", relief='solid', borderwidth=1, padding=5); label.pack()
    def hide(self, e):
        if self.tooltip: self.tooltip.destroy(); self.tooltip = None


# ===========================
# --- BANNER (AFFILIATE) ----
# ===========================
class BannerConfig:
    # Sửa các link/ảnh tại đây
    BANNERS = [
        {"image": "banners/banner1.png", "url": "https://www.creativefabrica.com/ref/16426302/"},
        {"image": "banners/banner2.png", "url": "https://example.com/aff2"},
        {"image": "banners/banner3.png", "url": "https://example.com/aff3"},
    ]
    WIDTH = 120
    HEIGHT = 600
    SWITCH_INTERVAL = 5000

class BannerWindow:
    def __init__(self, parent_root):
        self.root = Toplevel(master=parent_root, title="Affiliate Banner")
        self.root.overrideredirect(True)
        # SỬA: Không set topmost=True để banner không đè lên các app khác
        # self.root.attributes("-topmost", True)

        try:
            parent_root.update_idletasks()
            x = parent_root.winfo_x() + parent_root.winfo_width() + 10
            y = parent_root.winfo_y()
        except Exception:
            x, y = 100, 100

        self.root.geometry(f"{BannerConfig.WIDTH}x{BannerConfig.HEIGHT}+{x}+{y}")
        self.root.configure(bg="black")

        self.photo_label = ttk.Label(self.root, cursor="hand2")
        self.photo_label.pack(fill=BOTH, expand=True)

        self.images = []
        self.banner_index = 0

        self._load_images()
        if self.images:
            self._show_current()
            self.root.after(BannerConfig.SWITCH_INTERVAL, self._next)

        self.photo_label.bind("<Button-1>", self._open_link)

        try:
            def follow_parent(_event=None):
                try:
                    # SỬA: Chỉ di chuyển banner khi parent di chuyển
                    # và chỉ hiện banner khi parent đang active
                    if parent_root.state() == 'normal':
                        px = parent_root.winfo_x() + parent_root.winfo_width() + 10
                        py = parent_root.winfo_y()
                        self.root.geometry(f"+{px}+{py}")
                        self.root.deiconify()  # Hiện banner
                    else:
                        self.root.withdraw()  # Ẩn banner khi parent bị minimize
                except Exception:
                    pass
            
            parent_root.bind("<Configure>", follow_parent)
            
            # Ẩn banner khi parent bị minimize hoặc mất focus
            def on_parent_state_change(_event=None):
                try:
                    if parent_root.state() in ['iconic', 'withdrawn']:
                        self.root.withdraw()
                    else:
                        self.root.deiconify()
                except Exception:
                    pass
            
            parent_root.bind("<Unmap>", lambda e: self.root.withdraw())
            parent_root.bind("<Map>", lambda e: self.root.deiconify())
        except Exception:
            pass

    def _load_images(self):
        for item in BannerConfig.BANNERS:
            path = item.get("image", "")
            try:
                # Kiểm tra file có tồn tại không
                if not os.path.exists(path):
                    print(f"[Banner] File không tồn tại: '{path}'")
                    # Tạo ảnh placeholder nếu không tìm thấy
                    img = Image.new("RGB", (BannerConfig.WIDTH, BannerConfig.HEIGHT), color="#161B22")
                    draw = ImageDraw.Draw(img)
                    # Vẽ text "No Image"
                    draw.text((10, BannerConfig.HEIGHT//2), "No Image", fill="white")
                    self.images.append(ImageTk.PhotoImage(img))
                    continue
                
                img = Image.open(path).convert("RGBA")
                img = img.resize((BannerConfig.WIDTH, BannerConfig.HEIGHT), Image.LANCZOS)
                self.images.append(ImageTk.PhotoImage(img))
                print(f"[Banner] Load thành công: '{path}'")
            except Exception as e:
                print(f"[Banner] Lỗi load ảnh '{path}': {e}")

    def _show_current(self):
        self.photo_label.configure(image=self.images[self.banner_index])
        self.photo_label.image = self.images[self.banner_index]

    def _next(self):
        if not self.images:
            return
        self.banner_index = (self.banner_index + 1) % len(self.images)
        self._show_current()
        self.root.after(BannerConfig.SWITCH_INTERVAL, self._next)

    def _open_link(self, event):
        try:
            url = BannerConfig.BANNERS[self.banner_index].get("url")
            if url:
                webbrowser.open_new(url)
        except Exception as e:
            print(f"[Banner] Lỗi mở link: {e}")
# ------------- HẾT BANNER ---------------

class TrademarkAPIService:
    def __init__(self): self.db = Config.TRADEMARK_DATABASE
    def check(self, text, options):
        time.sleep(0.05); text_lower = text.lower(); keywords_to_check = set()
        if '\n' not in text and ',' not in text:
            words = re.findall(r'\b\w+\b', text_lower); [keywords_to_check.add(" ".join(words[i:i+n])) for n in range(5, 0, -1) for i in range(len(words) - n + 1)]
        else: items = text.split('\n') if '\n' in text else text.split(','); keywords_to_check.update(k.strip() for k in items if k.strip())
        active_db = [i for i in self.db if (options.get("class_25") and "IC 025" in i["class"]) or (options.get("class_general") and any(c in i["class"] for c in ["General", "Political", "Multiple"]))]; found_risks = [] # Sửa lỗi Pol -> Political, Mul -> Multiple
        for check_kw in keywords_to_check: [found_risks.append({**db_item, 'source_text': text.strip().replace('\n', ' | ')}) for db_item in active_db if db_item["keyword"] == check_kw]
        unique_risks = [dict(t) for t in {tuple(d.items()) for d in found_risks}]; return sorted(unique_risks, key=lambda x: ('High', 'Medium', 'Low').index(x.get('risk', 'Low'))) # Thêm get với default

class DatabaseManager:
    def __init__(self, db_file): self.db_file = db_file; self.init_db()
    def get_connection(self): return sqlite3.connect(self.db_file, timeout=10)
    def init_db(self):
        with self.get_connection() as conn:
            c = conn.cursor(); c.execute("""CREATE TABLE IF NOT EXISTS products (id INTEGER PRIMARY KEY, asin TEXT UNIQUE, discovery_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP, product_url TEXT, title TEXT, image_url TEXT, amazon_upload_date TEXT, is_favorite INTEGER DEFAULT 0, bsr INTEGER DEFAULT 9999999, scan_type TEXT DEFAULT 'newest')""")
            try: c.execute("ALTER TABLE products ADD COLUMN bsr INTEGER DEFAULT 9999999")
            except sqlite3.OperationalError: pass
            try: c.execute("ALTER TABLE products ADD COLUMN scan_type TEXT DEFAULT 'newest'")
            except sqlite3.OperationalError: pass
            c.execute("CREATE TABLE IF NOT EXISTS seen_asins (asin TEXT PRIMARY KEY)"); conn.commit()
    def get_all_seen_asins(self):
        with self.get_connection() as conn: return {r[0] for r in conn.cursor().execute("SELECT asin FROM seen_asins").fetchall()}
    def add_product(self, p):
        with self.get_connection() as conn:
            c = conn.cursor();
            try:
                c.execute("INSERT OR IGNORE INTO products (asin, product_url, title, image_url, amazon_upload_date, bsr, scan_type) VALUES (?,?,?,?,?,?,?)", (p['asin'], p['product_url'], p['title'], p['image_url'], p['amazon_upload_date'], p['bsr'], p['scan_type']))
                c.execute("INSERT OR IGNORE INTO seen_asins (asin) VALUES (?)", (p['asin'],)); conn.commit(); ts = c.execute("SELECT discovery_timestamp FROM products WHERE asin=?", (p['asin'],)).fetchone(); return ts[0] if ts else None
            except sqlite3.IntegrityError: return None
    def get_initial_products(self, limit=200):
        with self.get_connection() as conn: return conn.cursor().execute("SELECT asin, discovery_timestamp, product_url, title, image_url, amazon_upload_date, is_favorite, bsr, scan_type FROM products ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    def toggle_favorite_status(self, asin, status):
        with self.get_connection() as conn: conn.cursor().execute("UPDATE products SET is_favorite = ? WHERE asin = ?", (status, asin)); conn.commit()

def bypass_password_on(MainApplication): pass

class AmazonScraper:
    def __init__(self, db, status_cb, completion_cb):
        self.db, self.status_cb, self.completion_cb = db, status_cb, completion_cb; self.stop_flag = threading.Event()
        self.client = httpx.Client(headers=Config.HEADERS, timeout=30.0, follow_redirects=True, http2=True)
    def start_scan(self, scan_mode='newest'): self.stop_flag.clear(); threading.Thread(target=self._run_scan, args=(scan_mode,), daemon=True).start()
    def stop_scan(self): self.stop_flag.set(); print("Scan stop requested.")
    def _run_scan(self, scan_mode):
        sort_param = "&s=salesrank" if scan_mode == 'bestseller' else "&s=date-desc-rank"; self.status_cb(f"Đang tìm {'Bán Chạy' if scan_mode == 'bestseller' else 'Mới'}...", "primary")
        seen = self.db.get_all_seen_asins();
        
        # --- THÊM 3 DÒNG NÀY ---
        if scan_mode == 'bestseller':
            print("Chế độ Bestseller: Tạm thời bỏ qua bộ lọc 'seen'.")
            seen = set() # Coi như chưa thấy áo nào, quét TẤT CẢ
        # --- KẾT THÚC THÊM ---
            
        found_products, err = [], None
        for i in range(1, Config.MAX_SCAN_PAGES + 1):
            if self.stop_flag.is_set(): print("Scan terminated."); break; self.status_cb(f"Quét trang {i}/{Config.MAX_SCAN_PAGES}...", "primary")
            try:
                self.client.headers['User-Agent'] = random.choice(Config.USER_AGENTS); r = self.client.get(f"{Config.BASE_URL}{sort_param}&page={i}")
                r.raise_for_status(); s = Selector(text=r.text); [found_products.append({"asin": asin, "image_url": img}) for div in s.css('div[data-component-type="s-search-result"]') if (asin := div.attrib.get('data-asin')) and asin.strip() not in seen and (img := div.css('img.s-image::attr(src)').get())]; time.sleep(random.uniform(1.0, 2.0))
            except Exception as e: err = f"Lỗi Trang {i}: {e}"; print(err); break
        if self.stop_flag.is_set(): return self.completion_cb([], "Đã tạm ngưng.", "warning")
        if not found_products: return self.completion_cb([], f"Không có SP mới. {err or ''}", "warning")
        self.status_cb(f"Tìm thấy {len(found_products)}. Lấy chi tiết...", "success"); product_queue = Queue(); [product_queue.put(p) for p in found_products]; results = []
        threads = [threading.Thread(target=self._worker, args=(product_queue, results, len(found_products), scan_mode), daemon=True) for _ in range(Config.MAX_SCAN_WORKERS)]
        [t.start() for t in threads]; [t.join() for t in threads]; msg = f"Hoàn tất! Thêm {len(results)} SP." if not self.stop_flag.is_set() else f"Đã ngưng, xử lý {len(results)} SP."; color = "success" if not self.stop_flag.is_set() else "warning"
        self.completion_cb(results, msg, color)

    def _worker(self, queue, results, total, scan_mode):
        with httpx.Client(headers=Config.HEADERS, timeout=30.0, follow_redirects=True) as worker_client:
            while not queue.empty() and not self.stop_flag.is_set():
                try:
                    p_data = queue.get(); self.status_cb(f"Xử lý {len(results)+1}/{total}...", "success"); worker_client.headers['User-Agent'] = random.choice(Config.USER_AGENTS)
                    r = worker_client.get(f"https://www.amazon.com/dp/{p_data['asin']}"); s = Selector(text=r.text); title = s.css("#productTitle::text").get(default="N/A").strip()
                    date_str = next((d.strip() for d in s.xpath("//span[contains(text(), 'Date First Available')]/following-sibling::span[1]/text()").getall()), "N/A")

                    # --- Thêm bộ lọc ngày đăng ---
                    if scan_mode == 'newest' and FILTER_NEWEST_BY_ACTUAL_DATE and date_str != "N/A":
                        try:
                            # Cố gắng parse ngày tháng (hỗ trợ nhiều định dạng hơn)
                            product_date = None
                            for fmt in ("%B %d, %Y", "%b %d, %Y", "%m/%d/%Y"): # Thêm các định dạng phổ biến
                                try:
                                    product_date = datetime.strptime(date_str, fmt)
                                    break # Thoát nếu parse thành công
                                except ValueError:
                                    continue # Thử định dạng tiếp theo
                            
                            if product_date: # Nếu parse thành công
                                if datetime.now() - product_date > timedelta(days=MAX_NEWEST_AGE_DAYS):
                                    # print(f"Skipping old 'new' product {p_data['asin']} (Date: {date_str})") # Bỏ log này
                                    queue.task_done()
                                    continue # Bỏ qua sản phẩm này
                            # else:
                                # print(f"Could not parse date '{date_str}' for {p_data['asin']}") # Bỏ log này

                        except Exception as date_e:
                            print(f"Error checking date for {p_data['asin']}: {date_e}")
                            # Vẫn tiếp tục xử lý nếu có lỗi parse ngày
                    # --- Kết thúc bộ lọc ngày đăng ---
                            
                    db_data = {**p_data, 'title': title, 'product_url': f"https://www.amazon.com/dp/{p_data['asin']}", 'amazon_upload_date': date_str, 'bsr': Config.DEFAULT_BSR, 'scan_type': scan_mode}
                    ts = self.db.add_product(db_data);
                    if ts: results.append({**db_data, 'is_favorite': 0, 'timestamp': ts})
                    queue.task_done(); time.sleep(random.uniform(0.5, 1.0))
                except Exception as e: print(f"Lỗi worker ASIN {p_data.get('asin', 'NA')}: {e}"); queue.task_done()
    def close(self): self.client.close()

# SỬA LỖI: Kế thừa từ ttk.Frame thay vì Window
class MainApplication(ttk.Frame):
    # SỬA LỖI: Di chuyển 2 hàm callback lên đầu lớp
    def update_status_from_thread(self,message,color):
        safe_color = {"success":Config.SUCCESS_COLOR,"error":Config.ERROR_COLOR,"warning":Config.WARNING_COLOR}.get(color,Config.PRIMARY_TEXT)
        # Sửa: Dùng bootstyle thay vì foreground
        # Kiểm tra xem status_label đã được tạo chưa
        if hasattr(self, 'status_label') and self.status_label.winfo_exists():
            self.status_label.config(text=message,bootstyle=color if color in ("success", "error", "warning") else "default")

    def handle_scan_completion(self,new,msg,color):
        # Schedule the UI update on the main thread
        self.after(0,self._finalize_ui_update,new,msg,color)
    
    # SỬA LỖI: Di chuyển on_closing lên đây
    def on_closing(self): 
        print(" Closing..."); 
        # Đảm bảo executor và scraper tồn tại trước khi shutdown/close
        if hasattr(self, 'image_load_executor'):
            self.image_load_executor.shutdown(wait=False, cancel_futures=True); 
        if hasattr(self, 'scraper'):
            self.scraper.close(); 
        supabase_session.close(); 
        self.master.destroy()
        
    def __init__(self, master, db, auth, license_key=""): # Thêm 'master'
        super().__init__(master) # Gọi __init__ của ttk.Frame
        self.master = master # Lưu lại cửa sổ root
        self.db, self.auth = db, auth
        # SỬA LỖI: Truyền đúng hàm callback đã được định nghĩa
        self.scraper = AmazonScraper(db, self.update_status_from_thread, self.handle_scan_completion)
        self.tm_service, self.license_key = TrademarkAPIService(), license_key
        self.all_products, self.cached_products, self.image_references = [], [], []
        self.scroll_timer, self.current_page, self.total_pages = None, 1, 1
        self.viewing_favorites, self.current_filter = False, 'all'
        self.image_load_executor = ThreadPoolExecutor(max_workers=Config.MAX_IMAGE_WORKERS)
        self.image_load_queue = Queue()
        # Khôi phục niche_analyzer_win
        self.tm_window, self.trends_window, self.niche_analyzer_win = None, None, None
        self.fav_buttons = {}
        # Thêm biến lưu trữ keyword đang tìm kiếm
        self.search_keyword = tk.StringVar()

        self.pack(fill=BOTH, expand=True)

    # --- SỬA LỖI: Di chuyển tất cả các hàm xử lý/helper lên trước `run` ---
    
    def toggle_favorites_view(self):
        self.viewing_favorites = not self.viewing_favorites; 
        text, style = ("⬅️ Xem Tất Cả", INFO) if self.viewing_favorites else ("⭐ Xem Yêu Thích", (INFO, OUTLINE)); 
        if hasattr(self, 'fav_view_button') and self.fav_view_button.winfo_exists():
            self.fav_view_button.config(text=text, bootstyle=style); 
        self.filter_products('favorites' if self.viewing_favorites else self.current_filter)
        
    def export_data_to_csv(self):
        if not self.cached_products: messagebox.showinfo("Xuất CSV", "Không có data."); return
        fp = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV","*.csv"),("All","*.*")], title="Lưu CSV", initialfile=f"export_{datetime.now():%Y%m%d_%H%M}.csv");
        if not fp: return;
        try:
            d = self.cached_products; fields = ['number','asin','title','bsr','amazon_upload_date','discovery_timestamp','is_favorite','product_url','image_url','scan_type']
            with open(fp, 'w', newline='', encoding='utf-8') as f: writer=csv.DictWriter(f, fieldnames=fields); writer.writeheader(); [writer.writerow({**{k: item.get(k, 'N/A') for k in fields}, 'number': i}) for i, item in enumerate(d, 1)]
            messagebox.showinfo("Xuất CSV", f"Đã xuất {len(d)} SP:\n{fp}"); self.status_label.config(text=f"Đã xuất {len(d)}.", bootstyle="success")
        except Exception as e: messagebox.showerror("Lỗi Xuất CSV", f"Lỗi: {e}"); self.status_label.config(text=f"Lỗi Xuất: {e}", bootstyle="error")
        
    def show_trademark_window(self,prefill_text=""):
        try:
            if self.tm_window and self.tm_window.winfo_exists(): self.tm_window.lift();
            if prefill_text: self._update_tm_window_text(prefill_text); self.tm_window.focus_force(); return # Thêm focus_force
        except Exception: pass
        self.tm_window = Toplevel(master=self.master, title="Phân Tích TM");
        self.tm_window.geometry("700x500"); self.tm_window.transient(self.master)
        mf=ttk.Frame(self.tm_window,padding=15); mf.pack(fill=BOTH,expand=True); mf.rowconfigure(3,weight=1); mf.columnconfigure(0,weight=1);
        tf=ttk.Frame(mf); tf.grid(row=0,column=0,sticky='ew',pady=(0,10)); tf.columnconfigure(0,weight=1); ttk.Label(tf,text="Dán tiêu đề/từ khóa (1 dòng/mục):").grid(row=0,column=0,columnspan=2,sticky='w');
        self.tm_text_in=tk.Text(tf,height=5,relief='solid',bd=1, wrap='word', font=('Segoe UI', 10), fg=Config.PRIMARY_TEXT, bg=Config.BG_COLOR, insertbackground=Config.PRIMARY_TEXT, selectbackground=Config.ACCENT_COLOR, highlightcolor=Config.ACCENT_COLOR, highlightbackground=Config.BORDER_COLOR, highlightthickness=1); self.tm_text_in.grid(row=1,column=0,columnspan=2,sticky='ew',pady=5);
        of=ttk.Frame(tf); of.grid(row=2,column=0,sticky='w',pady=5); ttk.Label(of,text="Kiểm tra lớp:").pack(side=LEFT,padx=(0,10)); self.check_class_25=tk.BooleanVar(value=True); self.check_class_general=tk.BooleanVar(value=True);
        ttk.Checkbutton(of,text="IC 025",variable=self.check_class_25,bootstyle="round-toggle").pack(side=LEFT,padx=5); ttk.Checkbutton(of,text="Chung",variable=self.check_class_general,bootstyle="round-toggle").pack(side=LEFT,padx=5);
        af=ttk.Frame(tf); af.grid(row=2,column=1,sticky='e'); cols_s=("Keyword","Status","Class","Risk"); cols_b=("Source","Keyword","Status","Class","Risk");
        trf=ttk.Frame(mf); trf.grid(row=3,column=0,sticky='nsew'); trf.rowconfigure(0,weight=1); trf.columnconfigure(0,weight=1); self.tm_tree=ttk.Treeview(trf,columns=cols_b,show='headings',bootstyle=PRIMARY); [self.tm_tree.heading(c, text=c) for c in cols_b]
        self.tm_tree.column("Source", width=250, anchor=W); self.tm_tree.column("Keyword", width=120, anchor=W); self.tm_tree.column("Status", width=80, anchor=CENTER); self.tm_tree.column("Class", width=70, anchor=CENTER); self.tm_tree.column("Risk", width=70, anchor=CENTER);
        sb=ttk.Scrollbar(trf,orient=VERTICAL,command=self.tm_tree.yview); self.tm_tree.configure(yscrollcommand=sb.set); self.tm_tree.grid(row=0,column=0,sticky='nsew'); sb.grid(row=0,column=1,sticky='ns');
        [self.tm_tree.tag_configure(tag, background=color, foreground=fg) for tag, color, fg in [('High', Config.ERROR_COLOR,'white'), ('Medium', Config.WARNING_COLOR,'black'), ('Low', '#4e5d6c','white')]]
        cb=ttk.Button(af,text="Phân Tích",bootstyle=SUCCESS, command=lambda: self._handle_tm_bulk_check_thread(self.tm_text_in.get("1.0",END), self.tm_tree, cb)); ttk.Button(af,text="Xóa",command=lambda:[self.tm_text_in.delete("1.0",END), self._clear_treeview(self.tm_tree)],bootstyle=SECONDARY).pack(side=LEFT,padx=5); cb.pack(side=LEFT);
        if prefill_text: self._update_tm_window_text(prefill_text); self.tm_tree.config(columns=cols_s); [self.tm_tree.heading(i, text=c) for i, c in enumerate(cols_s)]; self.tm_tree.column("Keyword", width=200, anchor=W); self.tm_tree.column("Status", width=100); self.tm_tree.column("Class", width=100); self.tm_tree.column("Risk", width=100); self.tm_tree.column("#0", width=0, stretch=NO); cb.config(command=lambda: self._handle_tm_check_thread(self.tm_text_in.get("1.0",END), self.tm_tree, cb)); self._handle_tm_check_thread(prefill_text, self.tm_tree, cb)
        self.tm_text_in.bind("<KeyRelease>", lambda e, c=cb, b=cols_b, s=cols_s: self._tm_text_changed(e, c, b, s))
        self.tm_window.lift() # Thêm lift để đảm bảo hiện lên trên
        self.tm_window.focus_force() # Thêm focus_force
        
    def show_twitter_trends(self):
        try:
            if self.trends_window and self.trends_window.winfo_exists(): self.trends_window.lift(); self.trends_window.focus_force(); return
        except Exception: pass
        self.trends_window = Toplevel(master=self.master, title="Trends Twitter (US)");
        self.trends_window.geometry("500x400"); self.trends_window.transient(self.master);
        cols=("rank","trend","volume"); self.trends_tree=ttk.Treeview(self.trends_window, columns=cols, show='headings', bootstyle=PRIMARY); # Lưu tree vào self
        [self.trends_tree.heading(c, text=h) for c,h in zip(cols,("Hạng","Trend","Lượt Tweet"))];
        self.trends_tree.column("rank", width=60, anchor=CENTER); self.trends_tree.column("trend", width=300); self.trends_tree.column("volume", width=120, anchor=E);
        self.trends_tree.pack(fill=BOTH, expand=True, padx=10, pady=10);
        self._clear_treeview(self.trends_tree); self.trends_tree.insert("", END, values=("...", "Đang tải...", ""));

        # Thêm binding và menu
        self.trends_tree.bind("<Double-1>", self.on_trend_double_click)
        self.trends_menu = Menu(self.trends_window, tearoff=0)
        self.trends_menu.add_command(label="Sao chép Trend", command=self.copy_selected_trend)
        self.trends_menu.add_command(label="Tìm trên Twitter", command=self.search_selected_trend)
        self.trends_tree.bind("<Button-3>", self.show_trend_menu) # Nút chuột phải

        threading.Thread(target=self._fetch_twitter_trends, args=(self.trends_tree,), daemon=True).start()
        self.trends_window.lift(); self.trends_window.focus_force()
        
    def show_niche_analyzer_window(self):
        try:
            if self.niche_analyzer_win and self.niche_analyzer_win.winfo_exists(): self.niche_analyzer_win.lift(); self.niche_analyzer_win.focus_force(); return # Thêm focus
        except Exception: pass
        self.niche_analyzer_win = Toplevel(master=self.master, title="Phân Tích Niche");
        self.niche_analyzer_win.geometry("600x650"); # Tăng chiều cao cho biểu đồ
        self.niche_analyzer_win.transient(self.master);

        # Chia cửa sổ thành 2 phần: Bảng và Biểu đồ
        main_frame = ttk.Frame(self.niche_analyzer_win, padding=10)
        main_frame.pack(fill=BOTH, expand=True)
        main_frame.rowconfigure(2, weight=1) # Row 2 cho biểu đồ
        main_frame.columnconfigure(0, weight=1)

        top=ttk.Frame(main_frame); top.grid(row=0, column=0, sticky='ew', pady=(0, 5));
        ttk.Label(top, text="Top keywords từ 100 áo Mới + 100 áo Bán Chạy.", wraplength=480).pack(side=LEFT, fill=X, expand=True); # Tăng wraplength
        
        trf=ttk.Frame(main_frame); trf.grid(row=1, column=0, sticky='nsew', pady=(0,10)); # Row 1 cho bảng
        trf.rowconfigure(0, weight=1); trf.columnconfigure(0, weight=1);
        cols=("rank","keyword","count");
        # Lưu tree vào self để _update dùng được
        self.niche_tree=ttk.Treeview(trf, columns=cols, show='headings', bootstyle=PRIMARY, height=10); # Giới hạn chiều cao bảng
        [self.niche_tree.heading(c, text=h) for c,h in zip(cols,("Hạng","Keyword","Số lần"))];
        self.niche_tree.column("rank", width=60, anchor=CENTER); self.niche_tree.column("keyword", width=400); self.niche_tree.column("count", width=100, anchor=CENTER);
        sb=ttk.Scrollbar(trf, orient=VERTICAL, command=self.niche_tree.yview); self.niche_tree.configure(yscrollcommand=sb.set);
        self.niche_tree.grid(row=0, column=0, sticky='nsew'); sb.grid(row=0, column=1, sticky='ns');

        # Thêm menu chuột phải cho Niche Tree
        self.niche_menu = Menu(self.niche_analyzer_win, tearoff=0)
        self.niche_menu.add_command(label="Sao chép Keyword", command=self.copy_selected_niche_keyword)
        self.niche_tree.bind("<Button-3>", self.show_niche_menu)

        # Thêm Canvas cho biểu đồ
        chart_frame = ttk.Frame(main_frame, height=250) # Frame chứa biểu đồ
        chart_frame.grid(row=2, column=0, sticky='nsew')
        chart_frame.grid_propagate(False) # Ngăn co lại
        self.niche_chart_canvas = tk.Canvas(chart_frame, bg=Config.BG_COLOR, highlightthickness=0)
        self.niche_chart_canvas.pack(fill=BOTH, expand=True)
        
        # Truyền self.niche_tree vào command
        ref=ttk.Button(top, text="Tải Lại", bootstyle=(INFO, OUTLINE), command=lambda t=self.niche_tree: self._start_fetch_niche_analysis(t));
        ref.pack(side=RIGHT, padx=5);
        # Truyền self.niche_tree vào hàm chạy lần đầu
        self._start_fetch_niche_analysis(self.niche_tree)
        self.niche_analyzer_win.lift(); self.niche_analyzer_win.focus_force() # Thêm lift/focus
        
    def switch_user_and_restart(self):
        if messagebox.askyesno("Đổi License", "Khởi động lại?", parent=self.master):
            try: self.on_closing(); os.execl(sys.executable, sys.executable, *sys.argv)
            except Exception as e: print(f"Lỗi restart: {e}"); self.quit()

    def run(self):
        self.show_main_app_ui(); self.load_initial_products()
        self.after(500, self._process_image_queue)

    
        # Hiển thị banner affiliate (cửa sổ nổi, không dính app)
        try:
            self.after(1000, lambda: BannerWindow(self.master))
        except Exception as _e:
            print(f"[Banner] Không thể khởi tạo: {_e}")

    def on_scroll(self, *a):
        if self.scroll_timer: self.after_cancel(self.scroll_timer)
        self.canvas.yview(*a); self.scroll_timer = self.after(300, self.lazy_load_visible_images)

    def _on_mousewheel(self, e):
        if self.scroll_timer: self.after_cancel(self.scroll_timer)
        self.canvas.yview_scroll(int(-1 * (e.delta / 120)), "units")
        self.scroll_timer = self.after(300, self.lazy_load_visible_images)

    def _process_image_queue(self):
        try:
            while not self.image_load_queue.empty():
                (label, url) = self.image_load_queue.get()
                if label.winfo_exists() and not hasattr(label, 'image_loaded'):
                    future = self.image_load_executor.submit(self._process_image_in_thread, url)
                    future.add_done_callback(lambda f, l=label: self._update_image_in_main_thread(l, f.result()))
        except Exception as e: print(f"Lỗi queue ảnh: {e}")
        finally: self.after(100, self._process_image_queue)

    def _process_image_in_thread(self, url, size=(Config.IMAGE_WIDTH, Config.IMAGE_HEIGHT)): # Thêm size default
        """ Tải và xử lý ảnh (có thể dùng cho cả card và detail view) """
        try:
            with httpx.Client(timeout=10.0) as client: r = client.get(url); r.raise_for_status()
            img_data = BytesIO(r.content)
            with Image.open(img_data) as img:
                img = img.convert("RGBA"); img.thumbnail(size); # Dùng size truyền vào
                mask = Image.new('L', img.size, 0); draw = ImageDraw.Draw(mask)
                draw.rounded_rectangle((0, 0, *img.size), radius=Config.CARD_BORDER_RADIUS, fill=255);
                final_img = Image.new("RGBA", img.size); final_img.paste(img, (0, 0), mask); return final_img
        except Exception as e: return None

    def _update_image_in_main_thread(self, label, pil_image):
        try:
            if label.winfo_exists() and pil_image: photo = ImageTk.PhotoImage(pil_image); label.image = photo; label.configure(image=photo); label.image_loaded = True
            else: pass # Có thể thêm placeholder nếu lỗi
        except Exception as e: pass

    def show_main_app_ui(self):
        self.master.geometry("1400x800");
        key_display = self.license_key
        if len(key_display) > 20: key_display = f"{key_display[:10]}...{key_display[-4:]}"
        self.master.title(f"Merch Spy Pro v9.7 - License: {key_display}"); # Cập nhật version
        self._build_main_layout();
        self.master.deiconify()
        self.master.update(); self.master.focus_force(); self.master.lift(); self.master.attributes("-topmost", True)
        self.after(500, lambda: self.master.attributes("-topmost", False))

    def _build_main_layout(self):
        # --- THÊM STYLE CHO RANK ---
        try:
            style = Style.get_instance()
            
            # Hạng 1-10 (Màu cam)
            style.configure(
                "Rank.Top10.TLabel",
                background=Config.PRO_FEATURE_COLOR, # "#f97316"
                foreground="white",
                font=("Segoe UI", 10, "bold"),
                padding=(5, 2),
                anchor="center",
                border_radius=5 # Bo góc label
            )
            
            # Hạng 11-20 (Màu xanh)
            style.configure(
                "Rank.Top20.TLabel",
                background=Config.ACCENT_COLOR, # "#58A6FF"
                foreground="black",
                font=("Segoe UI", 10, "bold"),
                padding=(5, 2),
                anchor="center",
                border_radius=5 # Bo góc label
            )
        except Exception as e:
            print(f"Lỗi định nghĩa style rank: {e}")
        # --- KẾT THÚC THÊM STYLE ---

        self.grid_rowconfigure(0, weight=1); self.grid_columnconfigure(1, weight=1);
        sidebar = ttk.Frame(self, width=250, style='Sidebar.TFrame'); sidebar.grid(row=0, column=0, sticky='nsew'); sidebar.pack_propagate(False);
        # ... (phần còn lại của hàm giữ nguyên) ...
        self.grid_rowconfigure(0, weight=1); self.grid_columnconfigure(1, weight=1);
        sidebar = ttk.Frame(self, width=250, style='Sidebar.TFrame'); sidebar.grid(row=0, column=0, sticky='nsew'); sidebar.pack_propagate(False);
        ttk.Label(sidebar,text="Merch Spy Pro",style='Sidebar.TLabel',font=('Segoe UI',16,'bold'),anchor='center').pack(pady=20,fill=X);
        self.status_label=ttk.Label(sidebar,text="Sẵn sàng...",style='Sidebar.TLabel',anchor='center',wraplength=230); self.status_label.pack(pady=10,fill=X,padx=10);
        self.progressbar=ttk.Progressbar(sidebar,orient=HORIZONTAL,mode=INDETERMINATE,bootstyle=SUCCESS); self.progressbar.pack(fill=X,padx=10,pady=5); self.progressbar.pack_forget();
        ttk.Separator(sidebar).pack(fill=X,padx=10,pady=10);
        self.start_button=ttk.Button(sidebar,text="▶️ Quét Áo Mới",bootstyle=(SUCCESS,OUTLINE),command=lambda: self.start_scan(scan_mode='newest')); self.start_button.pack(fill=X,padx=10,pady=5)
        self.bestseller_button=ttk.Button(sidebar,text="🏆 Quét Bán Chạy",bootstyle=(SUCCESS,OUTLINE),command=lambda: self.start_scan(scan_mode='bestseller')); self.bestseller_button.pack(fill=X,padx=10,pady=5)
        self.stop_button=ttk.Button(sidebar,text="⏹️ Tạm Ngưng",bootstyle=(DANGER,OUTLINE),command=self.scraper.stop_scan,state=tk.DISABLED); self.stop_button.pack(fill=X,padx=10,pady=5);
        ttk.Separator(sidebar).pack(fill=X,padx=10,pady=10); ttk.Label(sidebar,text="Bộ lọc hiển thị:",style='Sidebar.TLabel').pack(fill=X,padx=10,pady=(0,5))
        filter_frame = ttk.Frame(sidebar, style='Sidebar.TFrame'); filter_frame.pack(fill=X, padx=10); filter_frame.columnconfigure((0,1,2), weight=1)
        self.filter_all_btn = ttk.Button(filter_frame, text="Tất Cả", bootstyle=PRIMARY, command=lambda: self.filter_products('all')); self.filter_all_btn.grid(row=0, column=0, sticky='ew', padx=(0,2))
        self.filter_new_btn = ttk.Button(filter_frame, text="Áo Mới", bootstyle=(SECONDARY, OUTLINE), command=lambda: self.filter_products('newest')); self.filter_new_btn.grid(row=0, column=1, sticky='ew', padx=(2,2))
        self.filter_best_btn = ttk.Button(filter_frame, text="Bán Chạy", bootstyle=(SECONDARY, OUTLINE), command=lambda: self.filter_products('bestseller')); self.filter_best_btn.grid(row=0, column=2, sticky='ew', padx=(2,0))
        ttk.Separator(sidebar).pack(fill=X,padx=10,pady=10); 
        # SỬA LỖI: Gán nút vào self.fav_view_button
        self.fav_view_button=ttk.Button(sidebar,text="⭐ Xem Yêu Thích",bootstyle=(INFO,OUTLINE),command=self.toggle_favorites_view); 
        self.fav_view_button.pack(fill=X,padx=10,pady=5);
        # SỬA LỖI: Gán đúng command cho nút export
        export_button = ttk.Button(sidebar, text="💾 Xuất CSV", bootstyle=(PRIMARY, OUTLINE), style='Pro.TButton', command=self.export_data_to_csv); 
        export_button.pack(fill=X, padx=10, pady=5);
        tm_button=ttk.Button(sidebar,text="🛡️ Phân Tích TM Chung",bootstyle=(WARNING,OUTLINE),style='Pro.TButton',command=self.show_trademark_window); tm_button.pack(fill=X,padx=10,pady=5);
        twitter_button = ttk.Button(sidebar, text="🐦 Xu Hướng Twitter", bootstyle=(INFO, OUTLINE), command=self.show_twitter_trends); twitter_button.pack(fill=X, padx=10, pady=5)
        niche_analyzer_button = ttk.Button(sidebar, text="🔥 Phân Tích Niche", bootstyle=(WARNING, OUTLINE), style='Pro.TButton', command=self.show_niche_analyzer_window); niche_analyzer_button.pack(fill=X, padx=10, pady=5)
        switch_key_button = ttk.Button(sidebar, text="🔑 Đăng xuất (Đổi Key)", bootstyle=(SECONDARY, OUTLINE), command=self.switch_user_and_restart); switch_key_button.pack(side=BOTTOM, fill=X, padx=10, pady=5)
        CreateToolTip(switch_key_button, "Đăng xuất và khởi động lại app để nhập key khác")
        key_display = self.license_key;
        if len(key_display) > 20: key_display = f"{key_display[:10]}...{key_display[-4:]}"
        ttk.Label(sidebar,text=f"License: {key_display}",style='Sidebar.TLabel',anchor='center', font=("Segoe UI", 8)).pack(side=BOTTOM,pady=10)
        content_area = ttk.Frame(self); content_area.grid(row=0, column=1, sticky='nsew', padx=10, pady=10); content_area.grid_rowconfigure(1, weight=1); content_area.grid_columnconfigure(0, weight=1);

        # --- Header Area ---
        header_frame=ttk.Frame(content_area); header_frame.grid(row=0,column=0,sticky='ew',pady=(0,10));
        header_frame.columnconfigure(1, weight=1) # Cho phép ô search co giãn
        ttk.Label(header_frame,text="Sản Phẩm",style='Header.TLabel').grid(row=0, column=0, sticky='w')

        # Thêm ô tìm kiếm và nút
        search_frame = ttk.Frame(header_frame)
        search_frame.grid(row=0, column=1, sticky='ew', padx=(20, 5))
        search_entry = ttk.Entry(search_frame, textvariable=self.search_keyword)
        search_entry.pack(side=LEFT, fill=X, expand=True, padx=(0, 5))
        search_entry.bind("<Return>", lambda e: self.filter_products(self.current_filter)) # Tìm khi nhấn Enter
        search_button = ttk.Button(search_frame, text="Tìm kiếm", bootstyle=(INFO, OUTLINE), command=lambda: self.filter_products(self.current_filter))
        search_button.pack(side=LEFT)
        clear_button = ttk.Button(search_frame, text="Xóa", bootstyle=(SECONDARY, OUTLINE), command=self.clear_search)
        clear_button.pack(side=LEFT, padx=(5,0))
        CreateToolTip(search_entry, "Nhập từ khóa cần tìm trong tiêu đề")

        # --- Results Frame (Scrollable) ---
        results_frame=ttk.Frame(content_area); results_frame.grid(row=1,column=0,sticky='nsew'); results_frame.grid_rowconfigure(0,weight=1); results_frame.grid_columnconfigure(0,weight=1);
        self.canvas=tk.Canvas(results_frame,highlightthickness=0,bg=Config.BG_COLOR); self.scrollbar=ttk.Scrollbar(results_frame,orient=VERTICAL,command=self.on_scroll);
        self.scrollable_frame=ttk.Frame(self.canvas); self.canvas_window=self.canvas.create_window((0,0),window=self.scrollable_frame,anchor="nw");
        self.canvas.configure(yscrollcommand=self.scrollbar.set); self.canvas.bind("<Configure>",lambda e:self.canvas.itemconfig(self.canvas_window,width=e.width));
        self.canvas.grid(row=0,column=0,sticky='nsew'); self.scrollbar.grid(row=0,column=1,sticky='ns');
        self.canvas.bind("<MouseWheel>", self._on_mousewheel); self.scrollable_frame.bind("<MouseWheel>", self._on_mousewheel)
        for i in range(5): self.scrollable_frame.columnconfigure(i, weight=1)
        self.pagination_frame=ttk.Frame(content_area,padding=5); self.pagination_frame.grid(row=2,column=0,sticky='ew'); self.pagination_frame.grid_columnconfigure(1,weight=1);
        self.prev_button=ttk.Button(self.pagination_frame,text="< Trước",command=self.prev_page,state=tk.DISABLED); self.prev_button.grid(row=0,column=0);
        self.page_label=ttk.Label(self.pagination_frame,text="Trang 1 / 1",font=('Segoe UI',10,'bold'),anchor='center'); self.page_label.grid(row=0,column=1);
        self.next_button=ttk.Button(self.pagination_frame,text="Sau >",command=self.next_page,state=tk.DISABLED); self.next_button.grid(row=0,column=2);
        self.pagination_frame.grid_remove()

    def clear_search(self):
        """ Xóa nội dung ô tìm kiếm và lọc lại """
        self.search_keyword.set("")
        self.filter_products(self.current_filter)

    def filter_products(self, filter_type):
        if not self.viewing_favorites: self.current_filter = filter_type
        # Đảm bảo nút tồn tại trước khi config
        if hasattr(self, 'filter_all_btn') and self.filter_all_btn.winfo_exists():
            self.filter_all_btn.config(bootstyle=PRIMARY if self.current_filter == 'all' and not self.viewing_favorites else (SECONDARY, OUTLINE))
        if hasattr(self, 'filter_new_btn') and self.filter_new_btn.winfo_exists():
            self.filter_new_btn.config(bootstyle=PRIMARY if self.current_filter == 'newest' and not self.viewing_favorites else (SECONDARY, OUTLINE))
        if hasattr(self, 'filter_best_btn') and self.filter_best_btn.winfo_exists():
            self.filter_best_btn.config(bootstyle=PRIMARY if self.current_filter == 'bestseller' and not self.viewing_favorites else (SECONDARY, OUTLINE))

        source_list = self.cached_products
        keyword = self.search_keyword.get().strip().lower()

        # 1. Lọc theo loại (All, Newest, Bestseller) hoặc Yêu thích
        if self.viewing_favorites:
            filtered_list = [p for p in source_list if p.get('is_favorite') == 1]
            status_base = "yêu thích"
        elif self.current_filter == 'newest':
            filtered_list = [p for p in source_list if p.get('scan_type') == 'newest']
            status_base = "áo mới"
        elif self.current_filter == 'bestseller':
            filtered_list = [p for p in source_list if p.get('scan_type') == 'bestseller']
            status_base = "áo bán chạy"
        else: # 'all'
            filtered_list = source_list.copy() # Lấy bản sao để không ảnh hưởng list gốc
            status_base = "tổng SP"

        # 2. Lọc theo từ khóa (nếu có)
        if keyword:
            self.all_products = [p for p in filtered_list if keyword in p.get('title', '').lower()]
            status_text = f"Tìm thấy {len(self.all_products)} {status_base} với '{keyword}'"
        else:
            self.all_products = filtered_list
            status_text = f"Hiển thị {len(self.all_products)} {status_base}"

        # Đảm bảo status_label tồn tại
        if hasattr(self, 'status_label') and self.status_label.winfo_exists():
            self.status_label.config(text=f"{status_text}.")
        self.sort_products()

    # --- Các hàm khác ---
    def sort_products(self,event=None):
        # --- SỬA LOGIC SẮP XẾP ---
        if self.current_filter == 'bestseller' and not self.viewing_favorites:
            # Nếu là Bestseller, KHÔNG sắp xếp. 
            # Thứ tự từ API đã là thứ tự xếp hạng.
            pass
        else:
            # Đối với 'Mới' hoặc 'Tất Cả', sắp xếp theo ngày tìm thấy
            self.all_products.sort(key=lambda p:p.get('timestamp','')or '',reverse=True)
        # --- KẾT THÚC SỬA ---
            
        for i,p in enumerate(self.all_products):p['number']=i+1 # 'number' BÂY GIỜ LÀ HẠNG
        self.setup_pagination_and_render_first_page()

    def start_scan(self, scan_mode='newest'):
        self.start_button.config(state=tk.DISABLED); self.bestseller_button.config(state=tk.DISABLED); self.stop_button.config(state=tk.NORMAL)
        self.status_label.config(text="Đang quét..."); self.progressbar.pack(fill=X,padx=10,pady=5); self.progressbar.start(10)
        self.scraper.start_scan(scan_mode)

    def _finalize_ui_update(self,new,msg,color):
        self.update_status_from_thread(msg,color); self.start_button.config(state=NORMAL); self.bestseller_button.config(state=NORMAL)
        self.stop_button.config(state=DISABLED);self.progressbar.stop();self.progressbar.pack_forget()
        if new:
            asins={p['asin']for p in new}; old=[p for p in self.cached_products if p['asin']not in asins]
            self.cached_products = sorted(new, key=lambda x:x.get('timestamp',''), reverse=True) + old
            self.filter_products(self.current_filter if not self.viewing_favorites else 'favorites')

    def load_initial_products(self):
        db_products=self.db.get_initial_products()
        if db_products:
            self.cached_products=[{'asin':p[0],'timestamp':p[1],'product_url':p[2], 'title':p[3],'image_url':p[4], 'amazon_upload_date':p[5], 'is_favorite':p[6],'bsr':p[7], 'scan_type':p[8]} for p in db_products]
            self.status_label.config(text=f"Đã tải {len(self.cached_products)} SP.")
            self.filter_products(self.current_filter)
        else: self.status_label.config(text="Bộ nhớ trống. Quét ngay.", bootstyle="warning")

    def setup_pagination_and_render_first_page(self):
        if not self.all_products: self.clear_display(); self.pagination_frame.grid_remove(); self.canvas.configure(scrollregion=self.canvas.bbox("all")); return
        self.total_pages=math.ceil(len(self.all_products)/Config.PRODUCTS_PER_PAGE); self.current_page=1; self.pagination_frame.grid(); self.render_page()

    def render_page(self):
        self.clear_display(); self.canvas.yview_moveto(0); start=(self.current_page-1)*Config.PRODUCTS_PER_PAGE
        products = self.all_products[start:start+Config.PRODUCTS_PER_PAGE]; num_cols = 5
        for i,p in enumerate(products): self._display_product_card(p, *divmod(i, num_cols))
        last_row = (len(products) - 1) // num_cols if products else 0
        spacer = ttk.Frame(self.scrollable_frame, height=50, style='TFrame'); spacer.grid(row=last_row + 1, column=0, columnspan=num_cols, pady=10)
        self.update_pagination_controls(); self.update_idletasks(); bbox = self.canvas.bbox("all");
        if bbox: self.canvas.configure(scrollregion=bbox)
        self.after(250,self.lazy_load_visible_images); self._bind_mousewheel_recursive(self.scrollable_frame)

    def update_pagination_controls(self):
        self.page_label.config(text=f"Trang {self.current_page}/{self.total_pages}"); self.prev_button.config(state=NORMAL if self.current_page>1 else DISABLED); self.next_button.config(state=NORMAL if self.current_page<self.total_pages else DISABLED)

    def prev_page(self):
        if self.current_page>1:self.current_page-=1;self.render_page()
    def next_page(self):
        if self.current_page<self.total_pages:self.current_page+=1;self.render_page()

    def clear_display(self):
        [w.destroy() for w in self.scrollable_frame.winfo_children()];
        self.image_references.clear();
        self.fav_buttons.clear() # SỬA LỖI YÊU THÍCH: Clear map nút fav

    def _display_product_card(self, p, row, col):
        card = ttk.Frame(self.scrollable_frame, style='Card.TFrame', borderwidth=1, relief="solid"); card.grid(row=row, column=col, padx=8, pady=8, sticky="nsew")
        
        # --- Phần Ảnh (thêm binding để mở chi tiết) ---
        img_cont = ttk.Frame(card, style='Card.TFrame'); img_cont.pack(fill=X, padx=10, pady=10); 
        w, h = Config.IMAGE_WIDTH, Config.IMAGE_HEIGHT; placeholder = Image.new("RGBA", (w,h), Config.BG_COLOR); draw = ImageDraw.Draw(placeholder); draw.rounded_rectangle((0,0,w,h), radius=Config.CARD_BORDER_RADIUS, fill=Config.BORDER_COLOR); img_tk = ImageTk.PhotoImage(placeholder)
        img_label = ttk.Label(img_cont, image=img_tk, anchor='center', style='Card.TLabel', cursor="hand2"); # Thêm cursor
        img_label.image = img_tk; img_label.pack(); 

        # --- THÊM NHÃN XẾP HẠNG ---
        # Chỉ hiển thị hạng nếu đang ở bộ lọc 'bestseller' (và không xem Yêu thích)
        if self.current_filter == 'bestseller' and not self.viewing_favorites:
            rank = p.get('number', 0) # Lấy hạng từ 'number'
            
            if 1 <= rank <= 20:
                # Chọn style dựa trên hạng
                if 1 <= rank <= 10:
                    rank_style = "Rank.Top10.TLabel"
                else: # 11 <= rank <= 20
                    rank_style = "Rank.Top20.TLabel"
                    
                # Tạo label và đặt ở góc trên bên trái
                rank_label = ttk.Label(
                    img_cont, # Đặt bên trong 'img_cont'
                    text=f"#{rank}",
                    style=rank_style
                )
                rank_label.place(x=5, y=5) # Đặt ở góc
        # --- KẾT THÚC THÊM NHÃN ---

        self.image_load_queue.put((img_label, p['image_url']))
        # Bind click vào ảnh
        img_label.bind("<Button-1>", lambda e, data=p: self._show_product_detail_window(data))
        # --- Kết thúc Phần Ảnh ---

        details = ttk.Frame(card, style='Card.TFrame'); details.pack(fill=BOTH, expand=True, padx=10); meta = ttk.Frame(details, style='Card.TFrame'); meta.pack(fill=X, anchor='w')
        bsr = f"BSR: {p['bsr']}" if p['bsr'] != Config.DEFAULT_BSR else "BSR: N/A"; ttk.Label(meta, text=bsr, style='CardSecondary.TLabel', font=('Segoe UI', 9)).pack(side=LEFT, anchor='w')
        scan = p.get('scan_type', 'newest');
        if self.current_filter == 'all' and not self.viewing_favorites: tag, style = ("🏆 Bán Chạy", "warning") if scan == 'bestseller' else ("✨ Áo Mới", "info"); ttk.Label(meta, text=f" | {tag}", bootstyle=style, font=('Segoe UI',9,'bold')).pack(side=LEFT, anchor='w', padx=(5,0))
        ttk.Label(details, text=f"Ngày đăng: {p['amazon_upload_date']}", style='CardSecondary.TLabel', font=('Segoe UI',9)).pack(anchor='w', pady=(5,0))
        title_f = ttk.Frame(details, style='Card.TFrame', height=60); title_f.pack(fill=X, pady=5); title_f.pack_propagate(False); title_t = p['title'] if p['title'] != "N/A" else "N/A"; title_l = ttk.Label(title_f, text=title_t, style='Title.TLabel', wraplength=230); title_l.pack(anchor='w', fill=X)
        acts = ttk.Frame(card, style='Card.TFrame'); acts.pack(fill=X, padx=5); [acts.columnconfigure(i, weight=1) for i in range(3)]; btn_w = 3;
        fav = ttk.Button(acts, text="⭐", bootstyle=("warning") if p.get('is_favorite') else (SECONDARY, OUTLINE), width=btn_w)
        fav.configure(command=lambda a=p['asin']: self.toggle_favorite(a));
        fav.grid(row=0, column=0, sticky='ew', padx=1);
        self.fav_buttons[p['asin']] = fav
        copy = ttk.Button(acts, text="📋", bootstyle=(SECONDARY, OUTLINE), width=btn_w); copy.configure(command=lambda t=p['title'], b=copy: self.copy_to_clipboard(t, b)); copy.grid(row=0, column=1, sticky='ew', padx=1)
        link = ttk.Button(acts, text="🔗", bootstyle=(SECONDARY, OUTLINE), width=btn_w, command=lambda u=p['product_url']: webbrowser.open_new(u)); link.grid(row=0, column=2, sticky='ew', padx=1)
        ttk.Separator(card, orient=HORIZONTAL).pack(fill=X, padx=10, pady=5); pro_f = ttk.Frame(card, style='Card.TFrame'); pro_f.pack(fill=X, padx=10, pady=(0, 10)); pro_f.columnconfigure((0, 1), weight=1)
        anl = ttk.Button(pro_f, text="📊 Phân tích", style='Pro.TButton', bootstyle=(SECONDARY, OUTLINE), command=lambda t=p['title']: self.show_keyword_analyzer(t)); anl.grid(row=0, column=0, sticky='ew', padx=(0, 2))
        tmc = ttk.Button(pro_f, text="🛡️ Check TM", style='Pro.TButton', bootstyle=(SECONDARY, OUTLINE), command=lambda t=p['title']: self.show_trademark_window(prefill_text=t)); tmc.grid(row=0, column=1, sticky='ew', padx=(2, 0))
        CreateToolTip(fav, "Yêu thích"); CreateToolTip(copy, "Sao chép"); CreateToolTip(link, "Mở link"); CreateToolTip(anl, "[PRO] Phân tích Keyword"); CreateToolTip(tmc, "[PRO] Check TM")
        CreateToolTip(img_label, "Nhấn để xem chi tiết") # Thêm tooltip cho ảnh

    def lazy_load_visible_images(self):
        if not self.winfo_viewable(): return; h=self.canvas.winfo_height(); top=self.canvas.yview()[0]*(self.scrollable_frame.winfo_height() or 1); bottom=top+h
        for card in self.scrollable_frame.winfo_children():
            if not isinstance(card, ttk.Frame): continue
            try:
                img_c = card.winfo_children()[0]; img_l = img_c.winfo_children()[0];
                if not img_l.winfo_exists() or hasattr(img_l, 'image_loaded'): continue
                y = card.winfo_y(); card_h = card.winfo_height();
                if (y + card_h > top - 200) and (y < bottom + 200): img_l.image_loaded = True; pass
            except Exception: pass

    # --- Thêm cửa sổ chi tiết sản phẩm ---
    def _show_product_detail_window(self, product_data):
        detail_win = Toplevel(master=self.master, title="Chi tiết sản phẩm")
        detail_win.geometry("500x700") # Kích thước cửa sổ
        detail_win.transient(self.master)
        detail_win.grab_set() # Giữ focus

        main_frame = ttk.Frame(detail_win, padding=20)
        main_frame.pack(fill=BOTH, expand=True)

        # 1. Ảnh lớn
        img_label = ttk.Label(main_frame, anchor='center')
        img_label.pack(pady=(0, 15))
        # Tải ảnh lớn hơn
        future = self.image_load_executor.submit(
            self._process_image_in_thread, 
            product_data['image_url'], 
            size=(Config.DETAIL_IMAGE_WIDTH, Config.DETAIL_IMAGE_HEIGHT) # Size lớn hơn
        )
        future.add_done_callback(lambda f, l=img_label: self._update_image_in_main_thread(l, f.result()))

        # 2. Tiêu đề đầy đủ
        ttk.Label(main_frame, text="Tiêu đề:", font="-weight bold").pack(anchor='w')
        title_text = tk.Text(main_frame, height=4, wrap='word', relief='flat', font=('Segoe UI', 10), 
                             fg=Config.PRIMARY_TEXT, bg=Config.BG_COLOR, highlightthickness=0)
        title_text.insert('1.0', product_data.get('title', 'N/A'))
        title_text.config(state='disabled') # Không cho sửa
        title_text.pack(fill=X, pady=(0, 10))

        # 3. Thông tin khác (ASIN, Ngày đăng)
        info_frame = ttk.Frame(main_frame)
        info_frame.pack(fill=X, pady=5)
        ttk.Label(info_frame, text=f"ASIN: {product_data.get('asin', 'N/A')}").pack(side=LEFT, anchor='w')
        ttk.Label(info_frame, text=f"Ngày đăng: {product_data.get('amazon_upload_date', 'N/A')}", anchor='e').pack(side=RIGHT)

        ttk.Separator(main_frame).pack(fill=X, pady=10)

        # 4. Các nút chức năng
        action_frame = ttk.Frame(main_frame)
        action_frame.pack(fill=X)
        action_frame.columnconfigure((0, 1, 2), weight=1) # Chia 3 cột

        # Nút Mở Link
        link_btn = ttk.Button(action_frame, text="🔗 Mở trên Amazon", bootstyle=(PRIMARY, OUTLINE), 
                              command=lambda u=product_data['product_url']: webbrowser.open_new(u))
        link_btn.grid(row=0, column=0, padx=5, sticky='ew')
        
        # Nút Check TM
        tm_btn = ttk.Button(action_frame, text="🛡️ Check TM", style='Pro.TButton', bootstyle=(WARNING, OUTLINE), 
                            command=lambda t=product_data['title']: self.show_trademark_window(prefill_text=t))
        tm_btn.grid(row=0, column=1, padx=5, sticky='ew')
        
        # Nút Phân tích Keyword
        kw_btn = ttk.Button(action_frame, text="📊 Phân tích Keyword", style='Pro.TButton', bootstyle=(INFO, OUTLINE), 
                            command=lambda t=product_data['title']: self.show_keyword_analyzer(t))
        kw_btn.grid(row=0, column=2, padx=5, sticky='ew')

        detail_win.lift()
        detail_win.focus_force()
    # --- Kết thúc cửa sổ chi tiết sản phẩm ---
    
    # --- Cập nhật cửa sổ Phân tích Keyword ---
    def show_keyword_analyzer(self,title):
        win=Toplevel(master=self.master, title="Phân Tích Keyword");
        win.geometry("600x550"); # Tăng chiều cao cho nút
        win.transient(self.master)
        
        mf=ttk.Frame(win); mf.pack(fill=BOTH,expand=True); mf.rowconfigure(0,weight=1); mf.columnconfigure(0,weight=1);
        cv=tk.Canvas(mf,highlightthickness=0,bg=Config.CARD_COLOR); sb=ttk.Scrollbar(mf,orient="vertical",command=cv.yview); 
        sf=ttk.Frame(cv,style='Card.TFrame',padding=15); sf.bind("<Configure>",lambda e:cv.configure(scrollregion=cv.bbox("all")));
        cv.create_window((0,0),window=sf,anchor="nw"); cv.configure(yscrollcommand=sb.set); cv.grid(row=0,column=0,sticky="nsew"); sb.grid(row=0,column=1,sticky="ns");
        
        ttk.Label(sf,text="Tiêu đề gốc:",font="-weight bold",style="Card.TLabel").pack(anchor='w'); 
        # Hiển thị tiêu đề trong Text để dễ copy
        title_widget = tk.Text(sf, height=3, wrap='word', relief='flat', font=('Segoe UI', 10), 
                             fg=Config.PRIMARY_TEXT, bg=Config.BG_COLOR, highlightthickness=0)
        title_widget.insert('1.0', title)
        title_widget.config(state='disabled')
        title_widget.pack(fill=X, pady=(0, 10))

        ttk.Separator(sf).pack(fill=X,pady=10); 
        words=[w for w in re.split(r'\W+',title.lower()) if len(w)>Config.MIN_WORD_LENGTH and w not in Config.STOP_WORDS]; 
        
        txt=tk.Text(sf,wrap='word',font=('Segoe UI',10),relief='flat',height=15,bg=Config.CARD_COLOR,fg=Config.PRIMARY_TEXT,highlightthickness=0); # Giảm height
        txt.pack(fill=X,expand=True);
        
        txt.insert(END,"Tần Suất Từ Đơn:\n","h2"); 
        [txt.insert(END,f"- {w.capitalize()}: {c} lần\n") for w,c in Counter(words).most_common(10)];
        
        # Tính và hiển thị cụm 2-3 từ
        phrases2 = [" ".join(words[i:i+2]) for i in range(len(words)-1)]
        phrases3 = [" ".join(words[i:i+3]) for i in range(len(words)-2)]
        common_phrases = Counter(phrases2 + phrases3).most_common(10) # Lấy top 10 cụm từ
        
        txt.insert(END,"\nCụm Từ Phổ Biến (2-3 từ):\n","h2"); 
        [txt.insert(END,f"- {p.title()}: {c} lần\n") for p,c in common_phrases if c > 1]; # Chỉ hiển thị nếu xuất hiện > 1 lần
        
        txt.tag_config("h2",font='-weight bold',foreground=Config.ACCENT_COLOR); 
        txt.config(state='disabled')
        
        # Thêm nút tìm kiếm
        search_frame = ttk.Frame(sf, style='Card.TFrame')
        search_frame.pack(fill=X, pady=(10, 0))
        search_frame.columnconfigure((0, 1), weight=1)

        trends_btn = ttk.Button(search_frame, text="Tìm trên Google Trends", bootstyle=(INFO, OUTLINE), 
                                command=lambda t=title: self.search_on_google_trends(t))
        trends_btn.grid(row=0, column=0, padx=(0, 5), sticky='ew')

        amazon_btn = ttk.Button(search_frame, text="Tìm trên Amazon", bootstyle=(SUCCESS, OUTLINE), 
                                command=lambda t=title: self.search_on_amazon(t))
        amazon_btn.grid(row=0, column=1, padx=(5, 0), sticky='ew')
        
        win.lift(); win.focus_force();

    def search_on_google_trends(self, text):
        if not text or text == "N/A": return
        query = urllib.parse.quote_plus(text)
        url = f"https://trends.google.com/trends/explore?q={query}"
        webbrowser.open_new(url)

    def search_on_amazon(self, text):
        if not text or text == "N/A": return
        query = urllib.parse.quote_plus(text)
        # Link tìm kiếm áo phông đơn giản trên Amazon
        url = f"https://www.amazon.com/s?k={query}&i=fashion-novelty&rh=n%3A7141123011%2Cn%3A7147441011%2Cn%3A12035955011" 
        webbrowser.open_new(url)
    # --- Kết thúc cập nhật Phân tích Keyword ---

    # SỬA LỖI YÊU THÍCH: Tối ưu hóa, chỉ cập nhật nút và lọc lại nếu cần
    def toggle_favorite(self,asin):
        p=next((p for p in self.cached_products if p['asin']==asin),None);
        if not p: return
        new_status=1-p.get('is_favorite',0);
        p['is_favorite']=new_status; # Cập nhật trạng thái trong cached_products

        # Cập nhật DB nền
        threading.Thread(target=self.db.toggle_favorite_status,args=(asin, new_status),daemon=True).start()

        # Cập nhật nút bấm trực tiếp
        button = self.fav_buttons.get(asin)
        if button and button.winfo_exists():
             button.configure(bootstyle=("warning") if new_status else (SECONDARY, OUTLINE))

        # Chỉ lọc và render lại nếu đang ở chế độ xem yêu thích
        if self.viewing_favorites:
            # Lọc lại danh sách all_products từ cached_products
            self.all_products = [prod for prod in self.cached_products if prod.get('is_favorite') == 1]
            # Sắp xếp và render lại trang hiện tại (hoặc trang đầu nếu cần)
            # Kiểm tra nếu trang hiện tại bị trống sau khi lọc
            start_index = (self.current_page - 1) * Config.PRODUCTS_PER_PAGE
            if start_index >= len(self.all_products) and self.current_page > 1:
                self.current_page -= 1 # Lùi về trang trước nếu trang hiện tại trống
            self.sort_products() # Hàm này sẽ gọi render_page

    def copy_to_clipboard(self,text,button=None): # Cho phép không truyền button (khi copy từ menu)
        if not text or text=="N/A": return;
        try:
            # Tối ưu hóa clipboard: Dùng self.master thay vì self
            self.master.clipboard_clear();
            self.master.clipboard_append(text);
            if button: # Chỉ đổi trạng thái nếu có button
                ot=button.cget("text"); button.config(text="Đã chép!",bootstyle=SUCCESS, state=DISABLED); self.after(2000,lambda:button.config(text=ot,bootstyle=(SECONDARY,OUTLINE), state=NORMAL) if button.winfo_exists() else None)
        except tk.TclError: print("Lỗi clipboard.")
    def _bind_mousewheel_recursive(self, w): w.bind("<MouseWheel>", self._on_mousewheel); [self._bind_mousewheel_recursive(c) for c in w.winfo_children()]

    # --- Sửa lỗi Twitter Trends ---
    def show_twitter_trends(self):
        try:
            if self.trends_window and self.trends_window.winfo_exists(): self.trends_window.lift(); self.trends_window.focus_force(); return
        except Exception: pass
        self.trends_window = Toplevel(master=self.master, title="Trends Twitter (US)");
        self.trends_window.geometry("500x400"); self.trends_window.transient(self.master);
        cols=("rank","trend","volume"); self.trends_tree=ttk.Treeview(self.trends_window, columns=cols, show='headings', bootstyle=PRIMARY); # Lưu tree vào self
        [self.trends_tree.heading(c, text=h) for c,h in zip(cols,("Hạng","Trend","Lượt Tweet"))];
        self.trends_tree.column("rank", width=60, anchor=CENTER); self.trends_tree.column("trend", width=300); self.trends_tree.column("volume", width=120, anchor=E);
        self.trends_tree.pack(fill=BOTH, expand=True, padx=10, pady=10);
        self._clear_treeview(self.trends_tree); self.trends_tree.insert("", END, values=("...", "Đang tải...", ""));

        # Thêm binding và menu
        self.trends_tree.bind("<Double-1>", self.on_trend_double_click)
        self.trends_menu = Menu(self.trends_window, tearoff=0)
        self.trends_menu.add_command(label="Sao chép Trend", command=self.copy_selected_trend)
        self.trends_menu.add_command(label="Tìm trên Twitter", command=self.search_selected_trend)
        self.trends_tree.bind("<Button-3>", self.show_trend_menu) # Nút chuột phải

        threading.Thread(target=self._fetch_twitter_trends, args=(self.trends_tree,), daemon=True).start()
        self.trends_window.lift(); self.trends_window.focus_force()

    def on_trend_double_click(self, event):
        self.search_selected_trend()

    def show_trend_menu(self, event):
        # Chọn dòng dưới con trỏ chuột trước khi hiện menu
        iid = self.trends_tree.identify_row(event.y)
        if iid:
            self.trends_tree.selection_set(iid)
            self.trends_menu.post(event.x_root, event.y_root)

    def get_selected_trend_text(self):
        selected_item = self.trends_tree.selection()
        if not selected_item: return None
        item = self.trends_tree.item(selected_item[0])
        if item and 'values' in item and len(item['values']) > 1:
            return item['values'][1] # Cột thứ 2 là tên trend
        return None

    def copy_selected_trend(self):
        trend_text = self.get_selected_trend_text()
        if trend_text:
            self.copy_to_clipboard(trend_text) # Dùng lại hàm copy chung
            print(f"Copied trend: {trend_text}")

    def search_selected_trend(self):
        trend_text = self.get_selected_trend_text()
        if trend_text:
            # Tạo URL an toàn
            query = urllib.parse.quote_plus(trend_text)
            url = f"https://twitter.com/search?q={query}&src=typed_query"
            webbrowser.open_new(url)
            print(f"Searching trend: {trend_text}")
    # --- Kết thúc sửa lỗi Twitter Trends ---

    def _fetch_twitter_trends(self, tree):
        try:
            with httpx.Client(timeout=15.0) as c: r=c.get("https://api.twitter.com/1.1/trends/place.json?id=23424977", headers={"Authorization": "Bearer AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs%3D1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA"}); r.raise_for_status(); data=r.json()
            trends = data[0].get('trends', []); valid = [t for t in trends if t.get('tweet_volume')]; sorted_t = sorted(valid, key=lambda x: x['tweet_volume'], reverse=True); [t.update({'vol_f': f"{t['tweet_volume']:,}"}) for t in sorted_t]; self.after(0, self._update_trends_ui, tree, sorted_t, None)
        except Exception as e: self.after(0, self._update_trends_ui, tree, [], f"Lỗi tải trends: {e}")
    def _update_trends_ui(self, tree, trends, error):
        if not tree.winfo_exists(): return; self._clear_treeview(tree);
        if error: messagebox.showerror("Lỗi Trends", error, parent=self.trends_window); tree.insert("", END, values=("Lỗi!", error, ""))
        elif trends: [tree.insert("", "end", values=(f"#{i}", t.get('name','N/A'), t.get('vol_f','N/A'))) for i, t in enumerate(trends[:50], 1)]
        else: tree.insert("", END, values=("!", "Không có data.", ""))

    # --- Sửa lỗi Phân Tích Niche ---
    def show_niche_analyzer_window(self):
        try:
            if self.niche_analyzer_win and self.niche_analyzer_win.winfo_exists(): self.niche_analyzer_win.lift(); self.niche_analyzer_win.focus_force(); return # Thêm focus
        except Exception: pass
        self.niche_analyzer_win = Toplevel(master=self.master, title="Phân Tích Niche");
        self.niche_analyzer_win.geometry("600x650"); # Tăng chiều cao cho biểu đồ
        self.niche_analyzer_win.transient(self.master);

        # Chia cửa sổ thành 2 phần: Bảng và Biểu đồ
        main_frame = ttk.Frame(self.niche_analyzer_win, padding=10)
        main_frame.pack(fill=BOTH, expand=True)
        main_frame.rowconfigure(2, weight=1) # Row 2 cho biểu đồ
        main_frame.columnconfigure(0, weight=1)

        top=ttk.Frame(main_frame); top.grid(row=0, column=0, sticky='ew', pady=(0, 5));
        ttk.Label(top, text="Top keywords từ 100 áo Mới + 100 áo Bán Chạy.", wraplength=480).pack(side=LEFT, fill=X, expand=True); # Tăng wraplength
        
        trf=ttk.Frame(main_frame); trf.grid(row=1, column=0, sticky='nsew', pady=(0,10)); # Row 1 cho bảng
        trf.rowconfigure(0, weight=1); trf.columnconfigure(0, weight=1);
        cols=("rank","keyword","count");
        # Lưu tree vào self để _update dùng được
        self.niche_tree=ttk.Treeview(trf, columns=cols, show='headings', bootstyle=PRIMARY, height=10); # Giới hạn chiều cao bảng
        [self.niche_tree.heading(c, text=h) for c,h in zip(cols,("Hạng","Keyword","Số lần"))];
        self.niche_tree.column("rank", width=60, anchor=CENTER); self.niche_tree.column("keyword", width=400); self.niche_tree.column("count", width=100, anchor=CENTER);
        sb=ttk.Scrollbar(trf, orient=VERTICAL, command=self.niche_tree.yview); self.niche_tree.configure(yscrollcommand=sb.set);
        self.niche_tree.grid(row=0, column=0, sticky='nsew'); sb.grid(row=0, column=1, sticky='ns');

        # Thêm menu chuột phải cho Niche Tree
        self.niche_menu = Menu(self.niche_analyzer_win, tearoff=0)
        self.niche_menu.add_command(label="Sao chép Keyword", command=self.copy_selected_niche_keyword)
        self.niche_tree.bind("<Button-3>", self.show_niche_menu)

        # Thêm Canvas cho biểu đồ
        chart_frame = ttk.Frame(main_frame, height=250) # Frame chứa biểu đồ
        chart_frame.grid(row=2, column=0, sticky='nsew')
        chart_frame.grid_propagate(False) # Ngăn co lại
        self.niche_chart_canvas = tk.Canvas(chart_frame, bg=Config.BG_COLOR, highlightthickness=0)
        self.niche_chart_canvas.pack(fill=BOTH, expand=True)
        
        # Truyền self.niche_tree vào command
        ref=ttk.Button(top, text="Tải Lại", bootstyle=(INFO, OUTLINE), command=lambda t=self.niche_tree: self._start_fetch_niche_analysis(t));
        ref.pack(side=RIGHT, padx=5);
        # Truyền self.niche_tree vào hàm chạy lần đầu
        self._start_fetch_niche_analysis(self.niche_tree)
        self.niche_analyzer_win.lift(); self.niche_analyzer_win.focus_force() # Thêm lift/focus

    def show_niche_menu(self, event):
        iid = self.niche_tree.identify_row(event.y)
        if iid:
            self.niche_tree.selection_set(iid)
            self.niche_menu.post(event.x_root, event.y_root)

    def get_selected_niche_keyword(self):
        selected_item = self.niche_tree.selection()
        if not selected_item: return None
        item = self.niche_tree.item(selected_item[0])
        if item and 'values' in item and len(item['values']) > 1:
            return item['values'][1] # Cột Keyword
        return None

    def copy_selected_niche_keyword(self):
        kw = self.get_selected_niche_keyword()
        if kw:
            self.copy_to_clipboard(kw)
            print(f"Copied niche keyword: {kw}")

    def _start_fetch_niche_analysis(self, tree):
        if not tree.winfo_exists(): return; self._clear_treeview(tree); tree.insert("", END, values=("...", "Đang phân tích...", ""));
        # Xóa biểu đồ cũ
        if hasattr(self, 'niche_chart_canvas') and self.niche_chart_canvas.winfo_exists():
            self.niche_chart_canvas.delete("all")
        threading.Thread(target=self._analyze_niches, args=(tree,), daemon=True).start() # Đổi tên hàm

    # Đổi tên hàm và cập nhật logic
    def _analyze_niches(self, tree):
        try:
            # Lấy top 100 Bestsellers
            bs = [p for p in self.cached_products if p.get('scan_type')=='bestseller'];
            bs_titles = [p['title'] for p in bs[:100]]
            
            # Lấy top 100 Newest
            newest = [p for p in self.cached_products if p.get('scan_type')=='newest'];
            newest_titles = [p['title'] for p in newest[:100]]
            
            # Gộp danh sách titles (dùng set để loại bỏ trùng lặp nếu muốn, nhưng ở đây gộp thẳng)
            combined_titles = bs_titles + newest_titles

            if not combined_titles:
                self.after(0, self._update_niche_analyzer_ui, tree, [], "Chưa có data 'Mới' hoặc 'Bán Chạy'.\nVui lòng chạy Quét trước.");
                return

            aw = []; [aw.append(w) for t in combined_titles for w in re.split(r'\W+', t.lower()) if len(w)>Config.MIN_WORD_LENGTH and w not in Config.STOP_WORDS]
            if not aw:
                self.after(0, self._update_niche_analyzer_ui, tree, [], "Không tìm thấy keyword.");
                return
                
            counts = Counter(aw).most_common(50);
            self.after(0, self._update_niche_analyzer_ui, tree, counts, None)
        except Exception as e:
            print(f"Lỗi niche: {e}");
            self.after(0, self._update_niche_analyzer_ui, tree, [], f"Lỗi: {e}")

    def _update_niche_analyzer_ui(self, tree, trends, error):
         # Sửa: Đảm bảo cửa sổ niche_analyzer_win tồn tại
        if not hasattr(self, 'niche_analyzer_win') or not self.niche_analyzer_win.winfo_exists(): return
        if not tree.winfo_exists(): return;
        self._clear_treeview(tree);
        
        # Đảm bảo canvas tồn tại
        if not hasattr(self, 'niche_chart_canvas') or not self.niche_chart_canvas.winfo_exists(): return
        self.niche_chart_canvas.delete("all")

        if error:
             # Sửa: Không dùng messagebox ở đây nữa, chỉ hiển thị lỗi trên tree
            tree.insert("", END, values=("Lỗi!", error, ""))
            # Hiển thị lỗi trên canvas luôn
            w = self.niche_chart_canvas.winfo_width() or 300
            h = self.niche_chart_canvas.winfo_height() or 100
            self.niche_chart_canvas.create_text(w/2, h/2, text=error, fill=Config.ERROR_COLOR, width=w-20, anchor='center')
        elif trends:
            [tree.insert("", END, values=(f"#{i}", kw.capitalize(), f"{c} lần")) for i, (kw, c) in enumerate(trends, 1)]
            # Vẽ biểu đồ
            self.after(100, lambda d=trends[:15]: self._draw_niche_chart(d)) # Delay nhẹ để canvas kịp vẽ
        else:
            tree.insert("", END, values=("!", "Không có data.", ""))
            w = self.niche_chart_canvas.winfo_width() or 300
            h = self.niche_chart_canvas.winfo_height() or 100
            self.niche_chart_canvas.create_text(w/2, h/2, text="Không có dữ liệu để vẽ biểu đồ.", fill=Config.SECONDARY_TEXT, width=w-20, anchor='center')

    def _draw_niche_chart(self, top_trends):
        """Vẽ biểu đồ cột ngang đơn giản cho top trends."""
        canvas = self.niche_chart_canvas
        canvas.delete("all")
        
        if not top_trends: return

        # Lấy kích thước canvas sau khi cửa sổ đã vẽ xong
        canvas.update_idletasks()
        width = canvas.winfo_width()
        height = canvas.winfo_height()
        
        if width < 50 or height < 50: # Kích thước quá nhỏ
             self.after(100, lambda d=top_trends: self._draw_niche_chart(d)) # Thử lại sau
             return

        padding = 20
        chart_height = height - 2 * padding
        chart_width = width - 2 * padding - 60 # Trừ thêm padding phải cho text count
        
        max_count = top_trends[0][1] if top_trends else 1
        bar_height = chart_height / len(top_trends) if len(top_trends) > 0 else chart_height # Tránh chia cho 0
        bar_spacing = bar_height * 0.2 # Khoảng cách giữa các cột
        actual_bar_height = bar_height * 0.8
        
        # Chọn màu gradient (ví dụ)
        color1_hex = Config.ACCENT_COLOR
        color2_hex = Config.SUCCESS_COLOR # Màu cuối
        
        # Chuyển hex sang RGB tuple (0-255)
        def hex_to_rgb(hex_color):
            hex_color = hex_color.lstrip('#')
            return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))

        # Nội suy màu
        def interpolate_color(color1, color2, factor):
            r1, g1, b1 = color1
            r2, g2, b2 = color2
            r = int(r1 + (r2 - r1) * factor)
            g = int(g1 + (g2 - g1) * factor)
            b = int(b1 + (b2 - b1) * factor)
            return f'#{r:02x}{g:02x}{b:02x}'

        rgb1 = hex_to_rgb(color1_hex)
        rgb2 = hex_to_rgb(color2_hex)

        for i, (keyword, count) in enumerate(top_trends):
            bar_width = (count / max_count) * chart_width if max_count > 0 else 0
            y1 = padding + i * bar_height + bar_spacing / 2
            y2 = y1 + actual_bar_height
            x1 = padding
            x2 = x1 + bar_width
            
            # Tính màu gradient cho cột hiện tại
            factor = i / (len(top_trends) -1) if len(top_trends) > 1 else 0
            bar_color = interpolate_color(rgb1, rgb2, factor)

            canvas.create_rectangle(x1, y1, x2, y2, fill=bar_color, outline="")
            
            # Hiển thị keyword (căn trái)
            canvas.create_text(x1 + 5, (y1 + y2) / 2, text=f"{keyword.capitalize()}", anchor='w', fill=Config.PRIMARY_TEXT, font=('Segoe UI', 9))
            
            # Hiển thị count (căn phải)
            canvas.create_text(width - padding - 5, (y1 + y2) / 2, text=f"{count}", anchor='e', fill=Config.SECONDARY_TEXT, font=('Segoe UI', 9))

    # --- Kết thúc sửa lỗi Phân Tích Niche ---

    # --- Các hàm TM window (đã có ở trên, giữ nguyên) ---
    def _update_tm_window_text(self, text):
        if hasattr(self, 'tm_text_in') and self.tm_text_in.winfo_exists(): self.tm_text_in.delete("1.0", END); self.tm_text_in.insert("1.0", text)
    def _tm_text_changed(self, event, cb, b_cols, s_cols):
        text = self.tm_text_in.get("1.0", END).strip(); is_bulk = '\n' in text or ',' in text; cols = b_cols if is_bulk else s_cols; cmd = self._handle_tm_bulk_check_thread if is_bulk else self._handle_tm_check_thread
        self.tm_tree.config(columns=cols); [self.tm_tree.heading(i, text=c) for i, c in enumerate(cols)]; cb.config(command=lambda: cmd(self.tm_text_in.get("1.0",END), self.tm_tree, cb))
        if is_bulk: self.tm_tree.column("Source", width=250, anchor=W); self.tm_tree.column("Keyword", width=120, anchor=W);
        else: self.tm_tree.column("Keyword", width=200, anchor=W); self.tm_tree.column("Status", width=100, anchor=CENTER);
    def _clear_treeview(self,tree):
        if tree.winfo_exists(): [tree.delete(i) for i in tree.get_children()]
    def _handle_tm_bulk_check_thread(self,text,tree,button):
        tl = [t.strip() for t in text.split('\n') if t.strip()] or [t.strip() for t in text.split(',') if t.strip()];
        if not tl: messagebox.showerror("Lỗi", "Nhập ít nhất 1 mục.", parent=self.tm_window); return
        self._clear_treeview(tree); tree.insert('',END,values=("Đang xử lý 0/...", *[""]*4),tags=('Low',)); button.config(state=DISABLED)
        threading.Thread(target=self._execute_tm_bulk_check,args=(tl,tree,button),daemon=True).start()
    def _execute_tm_bulk_check(self, tl, tree, button):
        all_r = []; opts={"class_25":self.check_class_25.get(),"class_general":self.check_class_general.get()}; total = len(tl)
        for i, item in enumerate(tl):
            if not item: continue; res = self.tm_service.check(item, opts); [all_r.append({'source': item[:50] + ('...' if len(item)>50 else ''), **r}) for r in res]; self.after(0, self._update_progress_tree, tree, i+1, total)
        self.after(0,self._update_tm_bulk_results, all_r, tree, button)
    def _update_progress_tree(self, tree, cur, total):
        if not tree.winfo_exists(): return; ch = tree.get_children();
        if ch: tree.delete(ch[0]);
        if cur < total: tree.insert('', 'end', values=(f"Đang xử lý {cur}/{total}...",*[""]*4), tags=('Low',))
    def _update_tm_bulk_results(self, all_r, tree, button):
        if not tree.winfo_exists(): return; ch = tree.get_children();
        if ch: tree.delete(ch[0])
        if not all_r: tree.insert('',END,values=("(Hoàn tất)","An toàn","N/A","N/A","Thấp"),tags=('Low',))
        else: sorted_r = sorted(all_r, key=lambda x: ('High','Medium','Low').index(x.get('risk', 'Low'))); [tree.insert('',END,values=(i.get('source',''), i.get('keyword','').title(), i.get('status',''), i.get('class',''), i.get('risk','')),tags=(i.get('risk','Low'),)) for i in sorted_r]
        button.config(state=NORMAL)
    def _handle_tm_check_thread(self, text, tree, button):
        if not text.strip(): return; self._clear_treeview(tree); tree.insert('',END,values=("Đang kiểm tra...", "","",""),tags=('Low',)); button.config(state=DISABLED)
        threading.Thread(target=self._execute_tm_check,args=(text,tree,button),daemon=True).start()
    def _execute_tm_check(self, text, tree, button):
        opts={"class_25":self.check_class_25.get(),"class_general":self.check_class_general.get()}; res=self.tm_service.check(text,opts); self.after(0,self._update_tm_results,res,tree,button)
    def _update_tm_results(self,res,tree,button):
        if not tree.winfo_exists(): return; self._clear_treeview(tree)
        if not res: tree.insert('',END,values=("(Không có rủi ro)","An toàn","N/A","Thấp"),tags=('Low',))
        else: [tree.insert('',END,values=(i.get('keyword','').title(),i.get('status',''),i.get('class',''),i.get('risk','')),tags=(i.get('risk','Low'),)) for i in res]
        button.config(state=NORMAL)
        
    def switch_user_and_restart(self):
        if messagebox.askyesno("Đổi License", "Khởi động lại?", parent=self.master):
            try: self.on_closing(); os.execl(sys.executable, sys.executable, *sys.argv)
            except Exception as e: print(f"Lỗi restart: {e}"); self.quit()

# ========================== MAIN ==========================
if __name__ == "__main__":
    try:
        if ENABLE_HIGH_DPI and os.name == 'nt':
             try: ctypes.windll.shcore.SetProcessDpiAwareness(1)
             except AttributeError:
                 try: ctypes.windll.user32.SetProcessDPIAware()
                 except AttributeError: print("Warning: Could not set DPI awareness.")

        style = Style(theme='superhero'); root = style.master
        # SỬA LỖI: Không withdraw root ở đây
        print("Initializing DB..."); db = DatabaseManager(Config.DATABASE_FILE); auth = None
        print("Starting license check...")
        dialog = LicenseDialog(parent_root=root); license_key = dialog.ask()
        if not license_key: print(" No valid license. Exiting."); root.destroy(); sys.exit(0)
        # SỬA LỖI: Không withdraw root ở đây nữa, vì MainApplication sẽ vẽ lên nó
        else: root.withdraw() # Chỉ withdraw SAU KHI dialog đóng
        print(" License OK. Initializing app UI...")
        app = MainApplication(master=root, db=db, auth=auth, license_key=license_key)
        # SỬA LỖI: Gán protocol cho root, sử dụng app.on_closing đã được khôi phục
        root.protocol("WM_DELETE_WINDOW", app.on_closing) 
        app.run() # Hàm run bây giờ sẽ hiện root và vẽ giao diện
        print(" Entering mainloop..."); root.mainloop(); print(" UI closed.") # Mainloop chạy trên root
    except Exception as e:
        import traceback; print(f" Unhandled exception: {e}"); traceback.print_exc()
        try: err_root = tk.Tk(); err_root.withdraw(); messagebox.showerror("Lỗi nghiêm trọng", f"Lỗi:\n{e}\n\nVui lòng khởi động lại.", parent=err_root); err_root.destroy()
        except Exception as e2: print(f"Could not show error messagebox: {e2}")
        sys.exit(1)

