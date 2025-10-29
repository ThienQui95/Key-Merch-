#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
This launcher ADDS a Redbubble Trends button to the main app (Merch Spy Pro)
AND directly integrates the Redbubble Panel functionality (from rb_panel.py).

This file REPLACES integrate_redbubble_panel.py and rb_panel.py.
The Redbubble panel is now launched as a Toplevel window within the main app,
not as a separate subprocess.

Usage:
    python visual_spy_launcher.py
"""
import os
import sys
import tkinter as tk
from tkinter import messagebox, Menu, Text

# Import the existing app and its components (no edits to original files required)
try:
    import visual_spy as vs
except Exception as e:
    raise RuntimeError(f"Không thể import visual_spy.py: {e}")

# Safe import: ttkbootstrap may already be used by visual_spy
try:
    from ttkbootstrap import Style, ttk, Window, Toplevel
    from ttkbootstrap.constants import *
except Exception as e:
    raise RuntimeError(f"Thiếu ttkbootstrap (pip install ttkbootstrap): {e}")

# Imports for Redbubble Panel (Tích hợp từ rb_panel.py)
import requests
from bs4 import BeautifulSoup
import webbrowser
import threading
import random
from typing import List, Tuple

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# ===== Redbubble Panel Config (Tích hợp từ rb_panel.py) =====
RB_APP_TITLE = "RB Trend Spy V3.9"
RB_TREND_URL = "https://redbubble.dabu.ro/redbubble-popular-tags"
RB_RED_COLOR_PRIMARY = "#e01b2f" # Màu đỏ của Redbubble
RB_TOP_10_TEXT_COLOR = "#ffc107" # Màu vàng (warning)

# ===== Redbubble Panel Functions (Tích hợp từ rb_panel.py) =====

def rb_random_user_agent():
    """Đổi tên từ random_user_agent để tránh xung đột"""
    uas = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_5) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0 Safari/537.36",
    ]
    return random.choice(uas)

def rb_fetch_trends_from_external():
    """Đổi tên từ fetch_trends_from_external và cập nhật hằng số"""
    print(f"Đang fetch trends từ trang thứ ba: {RB_TREND_URL}")
    
    headers = {
        "User-Agent": rb_random_user_agent(),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://www.google.com/",
    }
    
    trends_list: List[Tuple[str, str, str, int]] = []
    
    try:
        with requests.Session() as s:
            r = s.get(RB_TREND_URL, headers=headers, timeout=15)
            r.raise_for_status()
        
        soup = BeautifulSoup(r.text, 'html.parser')
        
        table = soup.find("table")
        if not table:
            return [], "Lỗi: Không tìm thấy <table> nào. Cấu trúc trang có thể đã thay đổi."
            
        rows = table.find_all("tr")
        if not rows or len(rows) < 2:
            return [], "Lỗi: Tìm thấy bảng nhưng không có hàng dữ liệu (tr) nào."

        print(f"Debug: Tìm thấy {len(rows)} hàng. Bắt đầu lặp (bỏ qua hàng 0 - header)...")

        for i, row in enumerate(rows[1:]):
            cols = row.find_all("td")
            if len(cols) >= 5:
                try:
                    results_count = cols[2].text.strip().replace(',', '')
                    link_tag = cols[4].find("a")
                    if not link_tag: continue
                    keyword = link_tag.text.strip()
                    rb_link = link_tag.get("href", "N/A")
                    if keyword and rb_link:
                        trends_list.append((keyword, results_count, rb_link, i + 1))
                except Exception as e:
                    print(f"Debug (Hàng {i+1}): Bỏ qua hàng lỗi: {e}")
                    continue
            
        if not trends_list:
            return [], "Lỗi: Tìm thấy bảng nhưng không thể trích xuất dữ liệu. Cấu trúc cột (td) có thể đã thay đổi."
            
        return trends_list, f"Tìm thấy {len(trends_list)} trends."
        
    except requests.RequestException as e:
        print(f"Lỗi mạng: {e}")
        return [], f"Lỗi: {e}"
    except Exception as e:
        print(f"Lỗi không xác định: {e}")
        return [], f"Lỗi: {e}"

# ===== Redbubble Panel GUI (Tích hợp từ rb_panel.py) =====

class RedbubblePanel(ttk.Frame):
    """
    Đây là lớp 'App' từ rb_panel.py, đổi tên thành RedbubblePanel
    và kế thừa từ ttk.Frame để tuân thủ theme.
    """
    def __init__(self, master):
        super().__init__(master)
        self.master = master
        self.pack(fill="both", expand=True)
        # Không set title/geometry ở đây, vì master là Toplevel sẽ làm việc đó
        
        self.trends: List[Tuple[str, str, str, int]] = []
        self.sort_state = ('STT', False)
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", self.filter_trends)
        
        self.niche_filter = tk.StringVar(value="All")
        
        self.col_names = {
            "STT": "STT",
            "Keyword": "Keyword (Từ khóa)",
            "Results": "Results (Số kết quả)",
            "Niche": "Độ Cạnh Tranh"
        }
        self.context_menu = None
        self._build_ui()

    def _build_ui(self):
        control_frame = ttk.Frame(self); control_frame.pack(fill="x", padx=10, pady=8)
        
        action_buttons_frame = ttk.Frame(control_frame)
        action_buttons_frame.pack(side="left")
        
        self.fetch_btn = ttk.Button(action_buttons_frame, text="🔥 Quét Trends Mới Nhất", command=self.on_fetch, bootstyle="danger")
        self.fetch_btn.pack(side="left", padx=(0,4))
        
        self.copy_btn = ttk.Button(action_buttons_frame, text="Copy Keyword", command=self.on_copy_selected, bootstyle="info-outline")
        self.copy_btn.pack(side="left", padx=4)
        
        filter_search_frame = ttk.Frame(control_frame)
        filter_search_frame.pack(side="right", fill="x", expand=True, padx=(10, 0))

        search_subframe = ttk.Frame(filter_search_frame)
        search_subframe.pack(fill="x", pady=(0, 5))
        ttk.Label(search_subframe, text="Tìm kiếm:").pack(side="left", padx=(0, 5))
        search_entry = ttk.Entry(search_subframe, textvariable=self.search_var)
        search_entry.pack(side="left", fill="x", expand=True, padx=5)
        clear_btn = ttk.Button(search_subframe, text="Xóa", command=lambda: self.search_var.set(""), bootstyle="secondary-outline")
        clear_btn.pack(side="left")

        niche_filter_frame = ttk.Frame(filter_search_frame)
        niche_filter_frame.pack(fill="x")
        ttk.Label(niche_filter_frame, text="Lọc Niche:").pack(side="left", padx=(0, 10))
        
        self.filter_all_btn = ttk.Radiobutton(niche_filter_frame, text="Tất Cả", variable=self.niche_filter, value="All", command=self.filter_trends, bootstyle="toolbutton-outline")
        self.filter_all_btn.pack(side="left", padx=2)
        self.filter_good_btn = ttk.Radiobutton(niche_filter_frame, text="Tốt", variable=self.niche_filter, value="Good", command=self.filter_trends, bootstyle="toolbutton-outline")
        self.filter_good_btn.pack(side="left", padx=2)
        self.filter_medium_btn = ttk.Radiobutton(niche_filter_frame, text="Trung Bình", variable=self.niche_filter, value="Medium", command=self.filter_trends, bootstyle="toolbutton-outline")
        self.filter_medium_btn.pack(side="left", padx=2)
        self.filter_high_btn = ttk.Radiobutton(niche_filter_frame, text="Cao", variable=self.niche_filter, value="High", command=self.filter_trends, bootstyle="toolbutton-outline")
        self.filter_high_btn.pack(side="left", padx=2)
        self.niche_filter.set("All")

        body = ttk.Frame(self); body.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        
        # SỬ DỤNG STYLE "RB.Treeview" ĐÃ ĐỊNH NGHĨA TRONG main() ĐỂ TRÁNH XUNG ĐỘT
        self.tree = ttk.Treeview(body, columns=("STT", "Keyword", "Results", "Niche"), show="headings", style="RB.Treeview")
        
        self.tree.heading("STT", text=self.col_names["STT"], command=lambda: self.sort_column("STT"))
        self.tree.heading("Keyword", text=self.col_names["Keyword"], command=lambda: self.sort_column("Keyword"))
        self.tree.heading("Results", text=self.col_names["Results"], command=lambda: self.sort_column("Results"))
        self.tree.heading("Niche", text=self.col_names["Niche"], command=lambda: self.sort_column("Niche"))
        
        self.tree.column("STT", width=50, anchor="center")
        self.tree.column("Keyword", width=350)
        self.tree.column("Results", width=120, anchor="center")
        self.tree.column("Niche", width=120, anchor="center")
        
        self.tree.pack(side="left", fill="both", expand=True)
        sb = ttk.Scrollbar(body, orient="vertical", command=self.tree.yview); sb.pack(side="right", fill="y")
        self.tree.configure(yscrollcommand=sb.set)
        
        self.tree.bind("<Double-1>", self.on_double_click_open)
        self.tree.bind("<Button-3>", self.show_context_menu)
        self._create_context_menu()
        
        self.tree.tag_configure('top10_text', foreground=RB_TOP_10_TEXT_COLOR)
        self.tree.tag_configure('Good', foreground='#28a745')
        self.tree.tag_configure('Medium', foreground='#ffc107')
        self.tree.tag_configure('High', foreground='#dc3545')

        self.status = tk.StringVar(value="Sẵn sàng (Nhấn đúp hoặc chuột phải vào hàng để xem tùy chọn)")
        ttk.Label(self, textvariable=self.status).pack(side="bottom", fill="x", padx=10, pady=(0, 8))

    def set_status(self, s):
        print(s)
        self.status.set(s)

    def on_fetch(self):
        self.search_var.set("")
        self.niche_filter.set("All")
        for i in self.tree.get_children(): self.tree.delete(i)
        self.trends.clear()
        self.set_status(f"Đang tải trends...")
        self.fetch_btn.config(state="disabled")
        threading.Thread(target=self._fetch_thread, daemon=True).start()

    def _fetch_thread(self):
        try:
            # Sử dụng hàm đã đổi tên
            items, message = rb_fetch_trends_from_external() 
            self.trends = items
            self.sort_state = ('STT', False)
            self.master.after(0, lambda: self.set_status(message))
            self.master.after(0, self._populate)
        except Exception as e:
            self.master.after(0, lambda: self.set_status(f"Lỗi thread: {e}"))  # noqa: F821
        finally:
            self.master.after(0, lambda: self.fetch_btn.config(state="normal"))
            self.master.after(0, lambda: self.sort_column("STT"))

    def _get_niche_info(self, comp_str):
        try:
            comp_int = int(comp_str)
        except ValueError:
            return "N/A", ""
            
        if comp_int == 0:
            return "N/A", ""
        elif comp_int <= 1000:
            return "Tốt (Ít Cạnh Tranh)", "Good"
        elif comp_int <= 5000:
            return "Trung bình", "Medium"
        else:
            return "Cao (Nhiều Cạnh Tranh)", "High"

    def _populate(self):
        search_term = self.search_var.get().lower()
        active_niche_filter = self.niche_filter.get()
        
        for i in self.tree.get_children():
            self.tree.delete(i)
        
        display_index = 0
        
        for i, (name, comp_str, link, stt) in enumerate(self.trends):
            if search_term and search_term not in name.lower():
                continue
            
            niche_text, niche_tag = self._get_niche_info(comp_str)

            if active_niche_filter != "All" and niche_tag != active_niche_filter:
                continue

            all_tags = [niche_tag] if niche_tag else []
            if display_index < 10:
                all_tags.append('top10_text')
            
            self.tree.insert("", "end", iid=i, values=(stt, name, comp_str, niche_text), tags=all_tags)
            display_index += 1
        
        if display_index > 0:
            try:
                first_item = self.tree.get_children()[0]
                self.tree.selection_set(first_item)
                self.tree.focus(first_item)
            except Exception: pass

    def sort_column(self, col):
        current_col, is_reversed = self.sort_state
        if col == current_col: is_reversed = not is_reversed
        else: is_reversed = False
        self.sort_state = (col, is_reversed)
        
        arrow = ' ▼' if is_reversed else ' ▲'
        for c in self.col_names: self.tree.heading(c, text=self.col_names[c])
        self.tree.heading(col, text=self.col_names[col] + arrow)
        
        if col == "Keyword": self.trends.sort(key=lambda item: item[0].lower(), reverse=is_reversed)
        elif col == "Results" or col == "Niche": self.trends.sort(key=lambda item: int(item[1]) if item[1].isdigit() else 0, reverse=is_reversed)
        elif col == "STT": self.trends.sort(key=lambda item: item[3], reverse=is_reversed)
            
        self.set_status(f"Đã sắp xếp theo {col} ({'Giảm dần' if is_reversed else 'Tăng dần'})")
        self._populate()

    def filter_trends(self, *args):
        self._populate()

    def _get_selected(self):
        selected_iid = self.tree.focus()
        if not selected_iid:
            messagebox.showwarning("Chưa chọn", "Vui lòng chọn một trend từ danh sách.", parent=self.master)
            return None
        try:
            index = int(selected_iid)
            return self.trends[index]
        except (ValueError, IndexError):
            messagebox.showerror("Lỗi", "Không thể tìm thấy dữ liệu cho trend đã chọn.", parent=self.master)
            return None

    def on_double_click_open(self, event):
        try:
            item_iid = self.tree.identify_row(event.y)
            if not item_iid: return
            index = int(item_iid)
            selected_trend = self.trends[index]
            name, comp, url, _ = selected_trend
            if url != "N/A": webbrowser.open_new(url)
            else: self.set_status("Lỗi: Không tìm thấy link Redbubble cho trend này.")
        except (ValueError, IndexError, AttributeError):
            self.set_status("Lỗi: Không thể mở trend đã chọn.")
    
    def _create_context_menu(self):
        self.context_menu = Menu(self.tree, tearoff=0)
        self.context_menu.add_command(label="🔗 Mở trên Redbubble", command=self.on_open_selected_link)
        self.context_menu.add_command(label="📋 Copy Keyword", command=self.on_copy_selected)

    def show_context_menu(self, event):
        iid = self.tree.identify_row(event.y)
        if iid:
            self.tree.selection_set(iid)
            self.tree.focus(iid)
            self.context_menu.post(event.x_root, event.y_root)

    def on_open_selected_link(self):
        selected_trend = self._get_selected()
        if selected_trend:
            name, comp, url, _ = selected_trend
            if url != "N/A": webbrowser.open_new(url)
            else: self.set_status("Lỗi: Không tìm thấy link Redbubble cho trend này.")

    def on_copy_selected(self):
        selected_trend = self._get_selected()
        if selected_trend:
            name, comp, url, _ = selected_trend
            try:
                self.master.clipboard_clear()
                self.master.clipboard_append(name)
                self.set_status(f"Đã copy: '{name}'")
            except tk.TclError:
                self.set_status("Lỗi: Không thể copy vào clipboard.")


# ===== Logic Tích Hợp (Từ integrate_redbubble_panel.py) =====

def _find_sidebar_frame(root_frame: tk.Widget):
    """
    Heuristic to find the left sidebar frame created by visual_spy's _build_main_layout().
    We look for the label 'Merch Spy Pro' and use its parent as the sidebar.
    """
    for child in root_frame.winfo_children():
        try:
            for sub in child.winfo_children():
                if isinstance(sub, ttk.Label) and getattr(sub, "cget", lambda *_: "")("text") == "Merch Spy Pro":
                    return sub.master
        except Exception:
            pass
        try:
            found = _find_sidebar_frame(child)
            if found:
                return found
        except Exception:
            pass
    return None

# Biến toàn cục để theo dõi cửa sổ RB Panel
_rb_panel_window = None
_rb_panel_root = None # Lưu trữ root window để làm parent cho Toplevel

def _launch_rb_panel():
    """
    (VIẾT LẠI) Mở cửa sổ Redbubble Panel (Toplevel) thay vì subprocess.
    Chỉ cho phép mở 1 cửa sổ tại một thời điểm.
    """
    global _rb_panel_window, _rb_panel_root
    
    if not _rb_panel_root:
        messagebox.showerror("Lỗi", "Ứng dụng chính chưa được khởi tạo.")
        return

    try:
        # Nếu cửa sổ đã tồn tại và đang chạy, mang nó lên phía trước
        if _rb_panel_window and _rb_panel_window.winfo_exists():
            _rb_panel_window.lift()
            _rb_panel_window.focus_force()
            return
    except Exception:
        pass # Cửa sổ có thể đã bị hủy
    
    try:
        # Tạo cửa sổ Toplevel mới
        _rb_panel_window = Toplevel(master=_rb_panel_root)
        _rb_panel_window.title(RB_APP_TITLE)
        _rb_panel_window.geometry("900x700")
        
        # Tạo frame panel (lớp RedbubblePanel) bên trong Toplevel
        panel_frame = RedbubblePanel(master=_rb_panel_window)
        
        _rb_panel_window.transient(_rb_panel_root)
        
        # Khi đóng Toplevel, set _rb_panel_window về None
        def on_rb_close():
            global _rb_panel_window
            _rb_panel_window.destroy()
            _rb_panel_window = None
        
        _rb_panel_window.protocol("WM_DELETE_WINDOW", on_rb_close)

    except Exception as e:
        messagebox.showerror("Lỗi", f"Không mở được Redbubble Panel:\n{e}", parent=_rb_panel_root)


class PatchedMainApplication(vs.MainApplication):
    """
    Extends the original MainApplication to ADD a Redbubble Trends button
    after the base UI is constructed.
    """
    def _add_redbubble_button(self):
        sidebar = _find_sidebar_frame(self)
        if not sidebar:
            host = self
        else:
            host = sidebar

        try:
            btn = ttk.Button(
                host,
                text="🔴 Redbubble Trends",
                bootstyle=(INFO, OUTLINE),
                command=_launch_rb_panel, # Gọi hàm _launch_rb_panel đã viết lại
            )
            btn.pack(fill=tk.X, padx=10, pady=5)
            try:
                # Giữ nguyên Tooltip nếu có
                vs.CreateToolTip(btn, "Mở bảng xu hướng/tag Redbubble (module tích hợp)")
            except Exception:
                pass
        except Exception as e:
            print(f"[Integrate] Không thể thêm nút Redbubble: {e}")

    # Override the layout hook to add our button AFTER the base builds
    def _build_main_layout(self):
        super()._build_main_layout()
        # Thêm nút của chúng ta sau khi UI gốc đã được xây dựng
        self._add_redbubble_button()


def main():
    # Mirror the startup sequence from visual_spy.__main__
    try:
        if getattr(vs, "ENABLE_HIGH_DPI", False) and os.name == 'nt':
            import ctypes
            try:
                ctypes.windll.shcore.SetProcessDpiAwareness(1)
            except AttributeError:
                try:
                    ctypes.windll.user32.SetProcessDPIAware()
                except AttributeError:
                    print("Warning: Could not set DPI awareness.")
    except Exception:
        pass

    style = Style(theme='superhero')
    root = style.master
    
    # --- TÍCH HỢP ---
    # Lưu root window để Toplevel của RB Panel có thể tham chiếu
    global _rb_panel_root
    _rb_panel_root = root
    
    # Thêm style cho RB Panel (từ rb_panel.py)
    style.configure('danger.TButton', background=RB_RED_COLOR_PRIMARY, foreground='white', font=("-weight bold"))
    # Các style 'info.Outline.TButton', 'success.Outline.TButton', 'secondary.Outline.TButton'
    # có thể đã tồn tại hoặc được định nghĩa trong visual_spy.py. 
    # Thêm chúng ở đây để đảm bảo chúng tồn tại.
    style.configure('info.Outline.TButton', bordercolor='#17a2b8', foreground='#17a2b8')
    style.configure('success.Outline.TButton', bordercolor='#28a745', foreground='#28a745')
    style.configure('secondary.Outline.TButton', bordercolor='#6c757d', foreground='#6c757d')
    
    # Thêm style cho RadioButton của RB Panel
    style.configure('Outline.Toolbutton', font=('Segoe UI', 10))
    style.map('Outline.Toolbutton',
              foreground=[('!selected', '#6c757d'), ('selected', 'white')],
              background=[('selected', '#6c757d')])

    # Định nghĩa style Treeview riêng cho RB Panel để tránh xung đột
    # với Treeview của visual_spy (nếu có)
    style.configure('RB.Treeview', rowheight=35, font=('Segoe UI', 11))
    style.configure('RB.Treeview.Heading', background=RB_RED_COLOR_PRIMARY, foreground='white', font=("-weight bold", 12))
    # --- KẾT THÚC TÍCH HỢP STYLE ---


    print("Initializing DB...")
    db = vs.DatabaseManager(vs.Config.DATABASE_FILE)
    auth = None

    print("Starting license check...")
    dialog = vs.LicenseDialog(parent_root=root)
    license_key = dialog.ask()
    if not license_key:
        print(" No valid license. Exiting.")
        root.destroy()
        sys.exit(0)
    else:
        try:
            root.withdraw()
        except Exception:
            pass

    print(" License OK. Initializing app UI...")
    # Sử dụng PatchedMainApplication để thêm nút
    app = PatchedMainApplication(master=root, db=db, auth=auth, license_key=license_key)

    try:
        root.protocol("WM_DELETE_WINDOW", app.on_closing)
    except Exception:
        pass

    app.run()
    print(" Entering mainloop...")
    root.mainloop()
    print(" UI closed.")

if __name__ == "__main__":
    main()