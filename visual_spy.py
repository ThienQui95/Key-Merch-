# -*- coding: utf-8 -*-
import sys
import os
import pandas as pd
import threading
import time
import requests # <-- THÊM VÀO
from PyQt5 import QtWidgets, QtCore, QtGui
from PyQt5.QtWidgets import QInputDialog # <-- THÊM VÀO
from PyQt5.QtGui import QPixmap, QImage # Thêm QPixmap, QImage
from PyQt5.QtCore import QRunnable, QThreadPool, pyqtSignal, QObject # Thêm QRunnable, QThreadPool
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, TimeoutException, ElementClickInterceptedException, WebDriverException
from webdriver_manager.chrome import ChromeDriverManager
import urllib.request # Thêm urllib
import openpyxl # Thêm openpyxl (cho export Excel)

# ==========================================================
# Lớp Spy chính (Logic backend)
# ==========================================================
class VisualSpy(QtCore.QObject):
    log = QtCore.pyqtSignal(str)
    search_complete = QtCore.pyqtSignal(object) # Gửi DataFrame khi xong
    search_error = QtCore.pyqtSignal(str)
    progress_update = QtCore.pyqtSignal(int, int) # Signal cho progress bar (current, total)
    image_loaded = QtCore.pyqtSignal(int, QPixmap) # Signal gửi ảnh đã load (row_index, QPixmap)

    def __init__(self):
        super().__init__()
        self.driver = None
        self.running = False
        self.logged_in = False

    def _init_driver(self):
        try:
            options = webdriver.ChromeOptions()
            # options.add_argument('--headless') # Chạy ẩn - Tạm tắt để dễ debug
            options.add_argument('--disable-gpu')
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36") # User agent mới hơn
            options.add_experimental_option('excludeSwitches', ['enable-logging']) # Tắt bớt log của Chrome

            # Tự động cài hoặc cập nhật ChromeDriver
            try:
                 service = Service(ChromeDriverManager().install())
                 self.driver = webdriver.Chrome(service=service, options=options)
            except ValueError as ve:
                 if "Could not get version for Chrome" in str(ve):
                      self.log.emit("LỖI: Không tìm thấy Chrome hoặc ChromeDriver tương thích. Vui lòng cài đặt Google Chrome.")
                      self.search_error.emit("Không tìm thấy Chrome/ChromeDriver. Vui lòng cài Google Chrome.")
                      return False
                 else:
                      raise ve # Ném lại lỗi khác
            except WebDriverException as wde:
                 self.log.emit(f"Lỗi WebDriverException khi khởi tạo: {wde}")
                 self.search_error.emit(f"Lỗi WebDriverException: {wde}. Có thể do phiên bản Chrome/Driver không khớp.")
                 return False

            self.driver.set_page_load_timeout(60) # Tăng timeout load trang
            self.log.emit("WebDriver đã khởi tạo.")
            return True
        except Exception as e:
            self.log.emit(f"Lỗi không xác định khi khởi tạo WebDriver: {e}")
            self.search_error.emit(f"Lỗi không xác định khi khởi tạo WebDriver: {e}")
            return False

    def check_login(self, email, password, spy_instance=None): # spy_instance không dùng nhưng để tương thích worker cũ
        self.log.emit("Đang kiểm tra đăng nhập...")
        if not self._init_driver():
             self.log.emit("Không thể khởi tạo WebDriver để kiểm tra đăng nhập.")
             return # Lỗi driver thì dừng luôn

        try:
            self.driver.get("https://www.amazon.com/ap/signin") # Hoặc market khác nếu cần
            # --- Code đăng nhập chi tiết ---
            wait = WebDriverWait(self.driver, 10)

            # Điền email
            email_field = wait.until(EC.presence_of_element_located((By.ID, "ap_email")))
            email_field.send_keys(email)
            self.driver.find_element(By.ID, "continue").click()
            self.log.emit("Đã điền email.")

            # Điền password
            password_field = wait.until(EC.presence_of_element_located((By.ID, "ap_password")))
            password_field.send_keys(password)
            self.driver.find_element(By.ID, "signInSubmit").click()
            self.log.emit("Đã điền password và submit.")

            # Xử lý OTP/Captcha (Cần kiểm tra giao diện thực tế của Amazon)
            time.sleep(5) # Chờ xem có trang OTP/Captcha không

            if "Enter the code" in self.driver.page_source or "verification" in self.driver.page_source.lower():
                 self.log.emit("Amazon yêu cầu mã xác thực (OTP/Captcha). Vui lòng xác thực thủ công trong trình duyệt (nếu không headless).")
                 # Tạm dừng ở đây để người dùng nhập OTP nếu chạy không headless
                 # input("Nhấn Enter sau khi đã xác thực...") # Dòng này chỉ dùng khi debug ko headless
                 # Hoặc báo lỗi nếu chạy headless
                 if '--headless' in self.driver.options.arguments:
                      self.log.emit("Lỗi: Không thể tự động xác thực OTP/Captcha khi chạy headless.")
                      self.logged_in = False
                      return

            # Kiểm tra đăng nhập thành công (ví dụ: xem có tên user không)
            try:
                 wait.until(EC.presence_of_element_located((By.ID, "nav-link-accountList")))
                 account_link_text = self.driver.find_element(By.ID, "nav-link-accountList").text
                 if "Hello, sign in" not in account_link_text: # Nếu không còn chữ "sign in" là OK
                      self.logged_in = True
                      self.log.emit(f"Kiểm tra đăng nhập thành công với tài khoản: {account_link_text.split(',')[1].strip()}")
                 else:
                      self.log.emit("Đăng nhập thất bại. Sai email/password hoặc cần xác thực.")
                      self.logged_in = False
            except TimeoutException:
                 self.log.emit("Đăng nhập thất bại hoặc trang load quá lâu sau khi submit.")
                 self.logged_in = False


        except TimeoutException:
            self.log.emit("Lỗi: Trang đăng nhập load quá lâu.")
            self.logged_in = False
        except Exception as e:
            self.log.emit(f"Lỗi trong quá trình đăng nhập: {e}")
            self.logged_in = False
        finally:
             if self.driver:
                 self.driver.quit()
                 self.driver = None
                 self.log.emit("WebDriver đã đóng sau khi kiểm tra login.")

    def search_product(self, keywords, pages=1, start_page=1, sort_type="relevancerank", market="com", spy_instance=None):
        self.running = True
        if not self._init_driver():
            self.log.emit("Không thể khởi tạo WebDriver để tìm kiếm.")
            self.search_error.emit("Không thể khởi tạo WebDriver.")
            self.running = False # Đặt lại running flag
            # Emit search_complete với DataFrame rỗng để GUI biết là đã kết thúc (dù lỗi)
            self.search_complete.emit(pd.DataFrame())
            return

        all_products = []
        base_url = f"https://www.amazon.{market}"
        total_products_expected = 0 # Ước lượng tổng số sản phẩm (để tính progress)
        products_processed_count = 0 # Đếm sản phẩm đã xử lý

        try:
            # Ước lượng tổng số sản phẩm (lấy từ trang đầu tiên nếu có)
            try:
                 temp_url = f"{base_url}/s?k={keywords.replace(' ', '+')}&page={start_page}&s={sort_type}"
                 self.driver.get(temp_url)
                 WebDriverWait(self.driver, 15).until(EC.presence_of_element_located((By.XPATH, "//div[@data-component-type='s-search-result']")))
                 result_count_element = self.driver.find_element(By.XPATH, "//span[contains(text(), 'results for')]")
                 # Trích xuất số lượng từ text, ví dụ "1-48 of over 2,000 results for..."
                 # Đoạn code trích xuất số có thể phức tạp, tạm bỏ qua để đơn giản
                 total_products_expected = pages * 48 # Ước tính 48 sp/trang
                 self.log.emit(f"Ước tính có khoảng {total_products_expected} sản phẩm.")
            except Exception as e_count:
                 self.log.emit(f"Không thể ước tính tổng số sản phẩm: {e_count}")
                 total_products_expected = pages * 48 # Ước tính mặc định

            for page in range(start_page, start_page + pages):
                if not self.running:
                    self.log.emit("Đã dừng tìm kiếm theo yêu cầu.")
                    break

                current_page_start_index = (page - 1) * 48 # Ước tính index bắt đầu của trang

                self.log.emit(f"Đang lấy dữ liệu trang {page}...")
                search_url = f"{base_url}/s?k={keywords.replace(' ', '+')}&page={page}&s={sort_type}"
                self.driver.get(search_url)

                try:
                     # Chờ cho đến khi các thẻ chứa kết quả xuất hiện
                     WebDriverWait(self.driver, 20).until( # Tăng chờ lên 20s
                         EC.presence_of_all_elements_located((By.XPATH, "//div[@data-component-type='s-search-result']"))
                     )
                     self.log.emit("Đã tìm thấy các thẻ kết quả.")
                except TimeoutException:
                     self.log.emit(f"Không tìm thấy kết quả nào trên trang {page} hoặc trang load quá lâu.")
                     # Kiểm tra xem có phải trang CAPTCHA không
                     page_lower = self.driver.page_source.lower()
                     if "captcha" in page_lower or "robot check" in page_lower or "type the characters you see" in page_lower:
                         self.log.emit("LỖI: Amazon yêu cầu CAPTCHA. Không thể tiếp tục.")
                         self.search_error.emit("Amazon yêu cầu CAPTCHA. Vui lòng thử lại sau hoặc giảm tốc độ.")
                         break # Dừng hẳn vòng lặp
                     else:
                         self.log.emit("Có thể đã hết trang hoặc không có kết quả.")
                         continue # Bỏ qua trang này

                products = self.driver.find_elements(By.XPATH, "//div[@data-component-type='s-search-result']")
                self.log.emit(f"Tìm thấy {len(products)} sản phẩm trên trang {page}.")
                if not products: continue # Nếu không có sp nào thì sang trang tiếp


                for i, product in enumerate(products):
                    if not self.running: break # Kiểm tra dừng lần nữa
                    
                    products_processed_count += 1
                    # Cập nhật progress bar
                    self.progress_update.emit(products_processed_count, total_products_expected)

                    data = {
                        "asin": None,
                        "title": None,
                        "brand": None,
                        "price": None,
                        "bestseller_rank": None, # Sẽ lấy chi tiết sau
                        "image_url": None,
                        "product_url": None,
                        "reviews": None, # Thêm cột reviews
                        "rating": None, # Thêm cột rating
                        "sponsored": False # Thêm cột sponsored
                    }

                    try:
                        data["asin"] = product.get_attribute("data-asin")
                        if not data["asin"]: continue # Bỏ qua nếu không có ASIN
                    except Exception: continue # Lỗi cũng bỏ qua

                    # Kiểm tra sponsored
                    try:
                         product.find_element(By.XPATH, ".//span[contains(@class, 'sponsored')]")
                         data["sponsored"] = True
                    except NoSuchElementException: pass

                    try:
                        title_link_element = product.find_element(By.XPATH, ".//h2/a")
                        data["title"] = title_link_element.find_element(By.XPATH, "./span").text
                        data["product_url"] = title_link_element.get_attribute("href")
                        if data["product_url"] and not data["product_url"].startswith("http"):
                             data["product_url"] = base_url + data["product_url"]
                    except NoSuchElementException: pass
                    except Exception as e_title: self.log.emit(f"Warn [{data['asin']}]: Lỗi nhỏ khi lấy title: {e_title}")

                    # Lấy Brand
                    try:
                         brand_elements = product.find_elements(By.XPATH, ".//h5//span | .//div[contains(@class, 's-title-instructions-style')]//span[contains(@class,'a-size-base-plus')]")
                         if brand_elements:
                              data["brand"] = brand_elements[0].text
                         else: # Thử cách khác nếu cách trên không được
                              brand_elements = product.find_elements(By.XPATH, ".//span[@class='a-size-base-plus a-color-base a-text-normal']")
                              if brand_elements:
                                   data["brand"] = brand_elements[0].text

                    except Exception as e_brand: self.log.emit(f"Warn [{data['asin']}]: Lỗi nhỏ khi lấy brand: {e_brand}")


                    try:
                        price_whole = product.find_element(By.CLASS_NAME, "a-price-whole").text
                        price_fraction = product.find_element(By.CLASS_NAME, "a-price-fraction").text
                        price_symbol = product.find_element(By.CLASS_NAME, "a-price-symbol").text
                        data["price"] = f"{price_symbol}{price_whole}.{price_fraction}"
                    except NoSuchElementException: pass # Giá có thể không có
                    except Exception as e_price: self.log.emit(f"Warn [{data['asin']}]: Lỗi nhỏ khi lấy price: {e_price}")

                    # Lấy Rating và Reviews
                    try:
                         rating_review_element = product.find_element(By.XPATH, ".//div[@class='a-row a-size-small']/span[@aria-label]")
                         data["rating"] = rating_review_element.get_attribute("aria-label").split(" ")[0] # Lấy số đầu tiên
                         review_element = rating_review_element.find_element(By.XPATH, "./following-sibling::span[@aria-label]")
                         data["reviews"] = review_element.get_attribute("aria-label").replace(",", "") # Xóa dấu phẩy
                    except NoSuchElementException: pass # Có thể không có rating/review
                    except Exception as e_rating: self.log.emit(f"Warn [{data['asin']}]: Lỗi nhỏ khi lấy rating/review: {e_rating}")

                    # Lấy Best Seller Rank (chỉ lấy text nếu có)
                    try:
                        rank_element = product.find_element(By.XPATH, ".//span[contains(@id,'best-seller-label')]")
                        data["bestseller_rank"] = rank_element.text # Lấy cả cụm "Best Seller..."
                    except NoSuchElementException: pass
                    except Exception as e_rank: self.log.emit(f"Warn [{data['asin']}]: Lỗi nhỏ khi lấy rank: {e_rank}")

                    try:
                        img_element = product.find_element(By.XPATH, ".//img[@class='s-image']")
                        data["image_url"] = img_element.get_attribute("src")
                    except NoSuchElementException: pass
                    except Exception as e_img: self.log.emit(f"Warn [{data['asin']}]: Lỗi nhỏ khi lấy image: {e_img}")

                    all_products.append(data)
                    # self.log.emit(f"Đã lấy: {data['asin']} - {data['title'][:30]}...") # Log quá nhiều

                if not self.running: break # Dừng sớm nếu có yêu cầu
                self.log.emit(f"Hoàn thành trang {page}. Đã lấy {len(all_products)} sản phẩm.")
                # Nghỉ giữa các trang để tránh bị block
                sleep_time = random.uniform(2.5, 5.0) # Ngẫu nhiên từ 2.5 đến 5 giây
                self.log.emit(f"Nghỉ {sleep_time:.1f} giây...")
                time.sleep(sleep_time)


        except TimeoutException:
             self.log.emit("Lỗi: Trang tìm kiếm load quá lâu.")
             self.search_error.emit("Trang tìm kiếm load quá lâu.")
        except WebDriverException as wde:
             self.log.emit(f"Lỗi WebDriverException trong quá trình tìm kiếm: {wde}")
             self.search_error.emit(f"Lỗi WebDriverException: {wde}. Trình duyệt có thể đã bị đóng.")
        except Exception as e:
            import traceback
            tb_str = traceback.format_exc()
            self.log.emit(f"Lỗi nghiêm trọng xảy ra: {e}\n{tb_str}")
            self.search_error.emit(f"Lỗi nghiêm trọng: {e}")
        finally:
            if self.driver:
                try:
                     self.driver.quit()
                except Exception as e_quit:
                     self.log.emit(f"Lỗi khi đóng WebDriver: {e_quit}")
                self.driver = None
                self.log.emit("WebDriver đã đóng.")
            
            df = pd.DataFrame(all_products)
            self.search_complete.emit(df) # Gửi kết quả (có thể rỗng)
            self.running = False
            self.progress_update.emit(total_products_expected, total_products_expected) # Hoàn thành progress


    def stop(self):
        self.running = False
        self.log.emit("Nhận được yêu cầu dừng...")


# --- PHẦN GIAO DIỆN (TỪ RUN_APP.PY) ---

# Lớp Stream để chuyển hướng stdout (log) sang GUI
class Stream(QtCore.QObject):
    newText = QtCore.pyqtSignal(str)

    def write(self, text):
        # Đảm bảo emit trên main thread nếu cần
        QtCore.QMetaObject.invokeMethod(self, "emit_signal", QtCore.Qt.QueuedConnection, QtCore.Q_ARG(str, str(text)))

    @QtCore.pyqtSlot(str)
    def emit_signal(self, text):
        self.newText.emit(text)

    def flush(self):
        pass

# Worker để tải ảnh trong thread riêng
class ImageDownloader(QRunnable):
    def __init__(self, row_index, image_url):
        super().__init__()
        self.row_index = row_index
        self.image_url = image_url
        self.signals = WorkerSignals() # Dùng chung signal object

    def run(self):
        try:
            if not self.image_url or not self.image_url.startswith('http'):
                 # self.signals.log.emit(f"Warn [Row {self.row_index}]: URL ảnh không hợp lệ: {self.image_url}")
                 return # Bỏ qua nếu URL không hợp lệ

            # self.signals.log.emit(f"Đang tải ảnh hàng {self.row_index} từ {self.image_url}")
            with urllib.request.urlopen(self.image_url, timeout=10) as response: # Thêm timeout
                image_data = response.read()
                image = QImage()
                image.loadFromData(image_data)
                pixmap = QPixmap.fromImage(image).scaled(100, 100, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation) # Scale ảnh
                self.signals.finished.emit(self.row_index, pixmap)
                # self.signals.log.emit(f"Tải ảnh hàng {self.row_index} thành công.")
        except urllib.error.URLError as e:
             self.signals.log.emit(f"Lỗi mạng khi tải ảnh hàng {self.row_index}: {e}")
        except Exception as e:
            self.signals.log.emit(f"Lỗi khi tải ảnh hàng {self.row_index}: {e}")
            # Có thể emit lỗi nếu cần xử lý riêng
            # self.signals.error.emit(self.row_index, str(e))

# Signal object cho ImageDownloader
class WorkerSignals(QObject):
    finished = pyqtSignal(int, QPixmap)
    error = pyqtSignal(int, str)
    log = pyqtSignal(str)


# Lớp Worker để chạy tác vụ trong thread riêng (Giữ nguyên)
class Worker(QtCore.QObject):
    finished = QtCore.pyqtSignal(object)
    error = QtCore.pyqtSignal(tuple)
    log = QtCore.pyqtSignal(str) # Thêm signal log cho worker

    def __init__(self, fn, *args, **kwargs):
        super().__init__()
        self.fn = fn
        self.args = args
        self.kwargs = kwargs

    @QtCore.pyqtSlot()
    def run(self):
        try:
             spy_instance = self.kwargs.get('spy_instance')
             if spy_instance:
                 # Kết nối signal từ spy instance ra worker
                 spy_instance.log.connect(self.log.emit)
                 spy_instance.search_complete.connect(self.finished.emit)
                 spy_instance.search_error.connect(lambda msg: self.error.emit((Exception(msg), None)))
                 # Kết nối progress từ spy ra worker (nếu cần xử lý thêm ở worker)
                 # spy_instance.progress_update.connect(...) 

             # Chạy hàm chính
             self.fn(*self.args, **self.kwargs)
             # Kết quả/lỗi đã được xử lý qua signals connect ở trên, không cần emit lại finished/error ở đây nữa

        except Exception as e:
            import traceback
            tb_str = traceback.format_exc()
            self.log.emit(f"Worker Error: {e}\n{tb_str}") # Emit log lỗi
            self.error.emit((e, sys.exc_info()))


# Dialog Đăng nhập (Giữ nguyên)
class LoginDialog(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Login")
        layout = QtWidgets.QVBoxLayout(self)

        self.email_input = QtWidgets.QLineEdit()
        self.email_input.setPlaceholderText("Email")
        self.password_input = QtWidgets.QLineEdit()
        self.password_input.setPlaceholderText("Password")
        self.password_input.setEchoMode(QtWidgets.QLineEdit.Password)

        layout.addWidget(self.email_input)
        layout.addWidget(self.password_input)

        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel,
            QtCore.Qt.Horizontal, self
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_credentials(self):
        return self.email_input.text(), self.password_input.text()

# Cửa sổ chính
class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.spy = VisualSpy() # Tạo instance của VisualSpy ở đây
        self.thread = None
        self.worker = None
        self.df = pd.DataFrame()
        self.trademark_set = set() # Set để lưu TM từ tệp
        self.threadpool = QThreadPool() # Tạo thread pool để tải ảnh
        self.threadpool.setMaxThreadCount(10) # Giới hạn 10 thread tải ảnh cùng lúc
        self.image_cache = {} # Cache ảnh đã tải
        self.current_tm_violations = set() # Lưu các dòng đang bị tô màu đỏ TM

        self.init_ui()
        self.setup_connections()
        self.redirect_stdout()
        self.load_trademarks() # Tải TM khi khởi động
        self.update_log("Ứng dụng sẵn sàng.")
        # LƯU Ý: Không gọi check license ở đây

    def init_ui(self):
        self.setWindowTitle("Visual Spy Tool - Merch Amazon")
        self.setGeometry(50, 50, 1600, 950) # Tăng kích thước cửa sổ

        main_widget = QtWidgets.QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QtWidgets.QHBoxLayout(main_widget)

        # === Cột điều khiển (Bên trái) ===
        control_layout = QtWidgets.QVBoxLayout()
        control_layout.setSpacing(10)
        control_layout.setAlignment(QtCore.Qt.AlignTop) # Căn chỉnh lên trên

        # Form inputs GroupBox
        form_groupbox = QtWidgets.QGroupBox("Tìm kiếm")
        form_layout = QtWidgets.QGridLayout(form_groupbox) # Đặt layout vào groupbox

        form_layout.addWidget(QtWidgets.QLabel("Keywords:"), 0, 0)
        self.keyword_input = QtWidgets.QLineEdit()
        self.keyword_input.setPlaceholderText("Ví dụ: cat t-shirt")
        form_layout.addWidget(self.keyword_input, 0, 1)

        form_layout.addWidget(QtWidgets.QLabel("Pages:"), 1, 0)
        self.pages_input = QtWidgets.QSpinBox()
        self.pages_input.setRange(1, 100)
        self.pages_input.setValue(1)
        form_layout.addWidget(self.pages_input, 1, 1)

        form_layout.addWidget(QtWidgets.QLabel("Start Page:"), 2, 0)
        self.start_page_input = QtWidgets.QSpinBox()
        self.start_page_input.setRange(1, 400)
        self.start_page_input.setValue(1)
        form_layout.addWidget(self.start_page_input, 2, 1)

        form_layout.addWidget(QtWidgets.QLabel("Sort Type:"), 3, 0)
        self.sort_type_combo = QtWidgets.QComboBox()
        self.sort_type_combo.addItems([
            "relevancerank", "price-asc-rank", "price-desc-rank",
            "review-rank", "newest-rank", "featured-rank" # Thêm featured-rank
        ])
        form_layout.addWidget(self.sort_type_combo, 3, 1)

        form_layout.addWidget(QtWidgets.QLabel("Market:"), 4, 0)
        self.market_combo = QtWidgets.QComboBox()
        self.market_combo.addItems(["com", "de", "co.uk", "fr", "it", "es", "co.jp", "ca", "com.au"]) # Thêm thị trường
        form_layout.addWidget(self.market_combo, 4, 1)

        control_layout.addWidget(form_groupbox) # Thêm groupbox vào layout chính

        # Nút Search và Stop GroupBox
        action_groupbox = QtWidgets.QGroupBox("Hành động")
        action_layout = QtWidgets.QVBoxLayout(action_groupbox)

        search_button_layout = QtWidgets.QHBoxLayout()
        self.search_button = QtWidgets.QPushButton(QtGui.QIcon.fromTheme("edit-find"), " Tìm kiếm") # Thêm icon
        self.search_button.setStyleSheet("background-color: #4CAF50; color: white; padding: 8px; font-weight: bold;")
        self.stop_button = QtWidgets.QPushButton(QtGui.QIcon.fromTheme("process-stop"), " Dừng") # Thêm icon
        self.stop_button.setStyleSheet("background-color: #f44336; color: white; padding: 8px; font-weight: bold;")
        self.stop_button.setEnabled(False)
        search_button_layout.addWidget(self.search_button)
        search_button_layout.addWidget(self.stop_button)
        action_layout.addLayout(search_button_layout)

        # Progress bar
        self.progress_bar = QtWidgets.QProgressBar()
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat("Tiến độ: %p%")
        action_layout.addWidget(self.progress_bar)

        # Nút Check Login và Export
        self.check_login_button = QtWidgets.QPushButton(QtGui.QIcon.fromTheme("system-users"), " Kiểm tra Login")
        self.export_button = QtWidgets.QPushButton(QtGui.QIcon.fromTheme("document-save"), " Xuất Excel")
        action_layout.addWidget(self.check_login_button)
        action_layout.addWidget(self.export_button)

        control_layout.addWidget(action_groupbox)

        # === Khu vực Trademark (Bên trái, phía dưới) ===
        tm_groupbox = QtWidgets.QGroupBox("Kiểm tra Trademark")
        tm_layout = QtWidgets.QVBoxLayout(tm_groupbox)

        tm_input_layout = QtWidgets.QHBoxLayout()
        self.tm_input = QtWidgets.QLineEdit()
        self.tm_input.setPlaceholderText("Thêm TM thủ công...")
        self.add_tm_button = QtWidgets.QPushButton("Thêm")
        self.clear_tm_button = QtWidgets.QPushButton("Xóa hết") # Nút xóa TM list
        tm_input_layout.addWidget(self.tm_input)
        tm_input_layout.addWidget(self.add_tm_button)
        tm_input_layout.addWidget(self.clear_tm_button) # Thêm nút xóa

        tm_layout.addLayout(tm_input_layout)

        self.tm_list_widget = QtWidgets.QListWidget()
        self.tm_list_widget.setContextMenuPolicy(QtCore.Qt.CustomContextMenu) # Cho phép menu chuột phải
        self.tm_list_widget.customContextMenuRequested.connect(self.show_tm_context_menu) # Kết nối menu
        tm_layout.addWidget(self.tm_list_widget)

        tm_check_layout = QtWidgets.QHBoxLayout() # Layout cho nút check và clear highlight
        self.check_tm_button = QtWidgets.QPushButton(QtGui.QIcon.fromTheme("edit-find-replace"), " Check Trademark")
        self.check_tm_button.setStyleSheet("background-color: #008CBA; color: white; padding: 5px;")
        self.clear_highlight_button = QtWidgets.QPushButton("Clear Highlight") # Nút bỏ tô màu
        tm_check_layout.addWidget(self.check_tm_button)
        tm_check_layout.addWidget(self.clear_highlight_button)
        tm_layout.addLayout(tm_check_layout)


        control_layout.addWidget(tm_groupbox)
        control_layout.addStretch() # Đẩy mọi thứ lên trên


        control_widget = QtWidgets.QWidget()
        control_widget.setLayout(control_layout)
        control_widget.setMinimumWidth(380) # Đặt chiều rộng tối thiểu cột trái
        control_widget.setMaximumWidth(450) # Đặt chiều rộng tối đa

        # === Khu vực Dữ liệu (Bên phải) ===
        data_layout = QtWidgets.QVBoxLayout()

        # Bảng kết quả
        self.table_widget = QtWidgets.QTableWidget()
        self.table_widget.setColumnCount(10) # Thêm cột Reviews, Rating, Sponsored
        self.table_widget.setHorizontalHeaderLabels([
             "ASIN", "Title", "Brand", "Price", "Rank", "Reviews", "Rating", "Sponsored", "Image", "Link"
        ])
        # Điều chỉnh độ rộng cột
        self.table_widget.setColumnWidth(0, 100) # ASIN
        self.table_widget.setColumnWidth(1, 400) # Title
        self.table_widget.setColumnWidth(2, 150) # Brand
        self.table_widget.setColumnWidth(3, 80)  # Price
        self.table_widget.setColumnWidth(4, 120) # Rank
        self.table_widget.setColumnWidth(5, 70)  # Reviews
        self.table_widget.setColumnWidth(6, 60)  # Rating
        self.table_widget.setColumnWidth(7, 80) # Sponsored
        self.table_widget.setColumnWidth(8, 110) # Image (cho ảnh 100x100)
        # self.table_widget.setColumnWidth(9, 50) # Link (để nhỏ, dùng tooltip)
        self.table_widget.horizontalHeader().setSectionResizeMode(9, QtWidgets.QHeaderView.Stretch) # Link co giãn

        self.table_widget.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.table_widget.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.table_widget.setSortingEnabled(True) # Cho phép sort cột
        self.table_widget.verticalHeader().setDefaultSectionSize(105) # Tăng chiều cao hàng để vừa ảnh
        self.table_widget.verticalHeader().setVisible(False) # Ẩn header hàng (số thứ tự)
        self.table_widget.setShowGrid(True) # Hiện lưới
        self.table_widget.setAlternatingRowColors(True) # Màu xen kẽ
        self.table_widget.setStyleSheet("alternate-background-color: #f0f0f0;")
        self.table_widget.itemDoubleClicked.connect(self.open_link_in_browser) # Mở link khi double click

        data_layout.addWidget(self.table_widget)

        # Log console GroupBox
        log_groupbox = QtWidgets.QGroupBox("Log")
        log_layout = QtWidgets.QVBoxLayout(log_groupbox)
        self.log_text = QtWidgets.QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumHeight(200) # Giữ chiều cao log cố định
        log_layout.addWidget(self.log_text)
        data_layout.addWidget(log_groupbox)


        data_widget = QtWidgets.QWidget()
        data_widget.setLayout(data_layout)

        # === Splitter ===
        splitter = QtWidgets.QSplitter(QtCore.Qt.Horizontal)
        splitter.addWidget(control_widget)
        splitter.addWidget(data_widget)
        # splitter.setSizes([400, 1200]) # Tỉ lệ ban đầu

        main_layout.addWidget(splitter)

        # Kết nối signal từ spy instance chính tới GUI
        self.spy.log.connect(self.update_log)
        self.spy.progress_update.connect(self.update_progress_bar)
        self.spy.image_loaded.connect(self.update_table_image)


    def setup_connections(self):
        self.search_button.clicked.connect(self.start_search)
        self.stop_button.clicked.connect(self.stop_search)
        self.export_button.clicked.connect(self.export_to_excel)
        self.check_login_button.clicked.connect(self.check_login)
        self.check_tm_button.clicked.connect(self.check_trademark)
        self.clear_highlight_button.clicked.connect(self.clear_all_highlights) # Kết nối nút clear highlight

        # Kết nối nút Add/Clear TM
        self.add_tm_button.clicked.connect(self.add_trademark)
        self.tm_input.returnPressed.connect(self.add_trademark)
        self.clear_tm_button.clicked.connect(self.clear_trademark_list) # Kết nối nút xóa list TM

    def redirect_stdout(self):
        # Tạo stream và kết nối signal của nó với update_log
        self.stdout_stream = Stream()
        self.stdout_stream.newText.connect(self.update_log)
        sys.stdout = self.stdout_stream

        self.stderr_stream = Stream()
        self.stderr_stream.newText.connect(self.update_log)
        sys.stderr = self.stderr_stream


    def load_trademarks(self):
        try:
            # Lấy đường dẫn tuyệt đối của thư mục chứa file script (visual_spy.py)
            script_dir = os.path.dirname(os.path.abspath(__file__))
            # Tạo đường dẫn đầy đủ đến file "Check TM.txt"
            tm_file = os.path.join(script_dir, "Check TM.txt")

            if not os.path.exists(tm_file):
                self.update_log(f"LƯU Ý: Không tìm thấy tệp '{tm_file}'. Chỉ sử dụng TM thủ công.")
                return

            with open(tm_file, 'r', encoding='utf-8') as f:
                # Đọc, chuyển về chữ thường, và xoá khoảng trắng, bỏ qua dòng trống
                trademarks = [line.strip().lower() for line in f if line.strip()]

            self.trademark_set = set(trademarks)
            self.update_log(f"Đã tải {len(self.trademark_set)} trademarks từ '{tm_file}'.")

        except Exception as e:
            self.update_log(f"LỖI khi đọc tệp TM: {e}")

    def add_trademark(self):
        tm_text = self.tm_input.text().strip()
        if tm_text:
            # Kiểm tra xem TM đã tồn tại chưa (không phân biệt hoa thường khi add)
            existing_items = [self.tm_list_widget.item(i).text().lower() for i in range(self.tm_list_widget.count())]
            if tm_text.lower() not in existing_items:
                self.tm_list_widget.addItem(tm_text)
                self.update_log(f"Đã thêm TM thủ công: {tm_text}")
            else:
                 self.update_log(f"Trademark '{tm_text}' đã tồn tại trong danh sách.")
            self.tm_input.clear()

    def clear_trademark_list(self):
        self.tm_list_widget.clear()
        self.update_log("Đã xóa hết danh sách TM thủ công.")

    # --- Menu chuột phải cho danh sách TM ---
    def show_tm_context_menu(self, position):
        item = self.tm_list_widget.itemAt(position)
        if not item: return # Không có item nào ở vị trí đó

        menu = QtWidgets.QMenu()
        delete_action = menu.addAction("Xóa")
        action = menu.exec_(self.tm_list_widget.mapToGlobal(position))

        if action == delete_action:
            row = self.tm_list_widget.row(item)
            self.tm_list_widget.takeItem(row)
            self.update_log(f"Đã xóa TM: {item.text()}")

    # --- Hàm xóa highlight ---
    def clear_all_highlights(self):
         default_color = QtGui.QColor(QtCore.Qt.white) # Hoặc màu nền mặc định nếu có alternating colors
         is_alternating = self.table_widget.alternatingRowColors()
         alt_color = QtGui.QColor("#f0f0f0") # Màu xen kẽ

         for row in range(self.table_widget.rowCount()):
             bg_color = alt_color if is_alternating and row % 2 != 0 else default_color
             for col in range(self.table_widget.columnCount()):
                 item = self.table_widget.item(row, col)
                 if item:
                     item.setBackground(bg_color)
         self.current_tm_violations.clear() # Xóa bộ nhớ các dòng bị tô màu
         self.update_log("Đã xóa highlight.")

    def check_trademark(self):
        # Lấy danh sách TM từ QListWidget (do người dùng nhập thủ công)
        manual_tms = set(self.tm_list_widget.item(i).text().lower() for i in range(self.tm_list_widget.count()))

        # Kết hợp với danh sách TM từ tệp
        if not self.trademark_set and not manual_tms:
             self.update_log("Danh sách TM (từ tệp và thủ công) đều rỗng. Thử tải lại tệp...")
             self.load_trademarks() # Thử tải lại
             # Nếu vẫn rỗng thì thoát
             if not self.trademark_set and not manual_tms:
                self.update_log("Không thể kiểm tra, danh sách TM rỗng.")
                return

        combined_tms = self.trademark_set.union(manual_tms)

        if not combined_tms:
             self.update_log("Danh sách TM tổng hợp rỗng.")
             return

        self.update_log(f"Bắt đầu kiểm tra với {len(combined_tms)} trademarks (từ tệp + thủ công)...")

        # Xóa highlight cũ trước khi check mới
        self.clear_all_highlights()

        violation_color = QtGui.QColor(255, 153, 153) # Màu đỏ nhạt hơn
        found_count = 0

        for row in range(self.table_widget.rowCount()):
            title_item = self.table_widget.item(row, 1) # Cột Title
            brand_item = self.table_widget.item(row, 2) # Cột Brand

            if not title_item and not brand_item:
                continue # Bỏ qua nếu cả title và brand đều trống

            title_text = title_item.text().lower() if title_item else ""
            brand_text = brand_item.text().lower() if brand_item else ""

            found_violation = False
            violating_tm = "" # Lưu TM vi phạm để log
            for tm in combined_tms:
                if not tm: continue # Bỏ qua TM rỗng

                # Kiểm tra TM có phải là một từ đơn và nằm trong text như một từ riêng biệt không
                # Hoặc nếu TM có nhiều từ, kiểm tra xem nó có nằm trong text không
                # Bổ sung: Kiểm tra xem TM có trong ASIN không (cột 0)
                asin_item = self.table_widget.item(row, 0)
                asin_text = asin_item.text().lower() if asin_item else ""

                # Logic kiểm tra TM (có thể cần phức tạp hơn để tránh false positive)
                # Ví dụ đơn giản: kiểm tra " tm " hoặc "^tm " hoặc " tm$" hoặc "^tm$"
                # Hoặc chỉ đơn giản là 'in'
                if tm in title_text or tm in brand_text or tm in asin_text:
                    found_violation = True
                    violating_tm = tm
                    break # Tìm thấy 1 TM là đủ

            if found_violation:
                 # Tô màu cả hàng
                 for col in range(self.table_widget.columnCount()):
                      item = self.table_widget.item(row, col)
                      if item:
                           item.setBackground(violation_color)
                 self.current_tm_violations.add(row) # Lưu lại dòng bị tô màu
                 found_count += 1
                 # self.update_log(f"Phát hiện TM '{violating_tm}' ở hàng {row+1}") # Log quá nhiều

        self.update_log(f"Kiểm tra Trademark hoàn tất. Tìm thấy {found_count} sản phẩm có khả năng vi phạm.")


    def start_search(self):
        keyword = self.keyword_input.text().strip() # Xóa khoảng trắng thừa
        pages = self.pages_input.value()
        start_page = self.start_page_input.value()
        sort_type = self.sort_type_combo.currentText()
        market = self.market_combo.currentText()

        if not keyword:
            QtWidgets.QMessageBox.warning(self, "Thiếu thông tin", "Vui lòng nhập Keywords.")
            return

        # Hỏi lại nếu số trang lớn
        if pages > 10:
             reply = QtWidgets.QMessageBox.question(self, 'Xác nhận',
                                                 f"Bạn sắp quét {pages} trang. Quá trình này có thể mất nhiều thời gian và dễ bị Amazon chặn. Bạn có chắc chắn muốn tiếp tục?",
                                                 QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No, QtWidgets.QMessageBox.No)
             if reply == QtWidgets.QMessageBox.No:
                  return

        self.search_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.table_widget.setRowCount(0) # Xóa bảng cũ
        self.df = pd.DataFrame() # Reset DataFrame
        self.image_cache = {} # Xóa cache ảnh cũ
        self.progress_bar.setValue(0) # Reset progress bar
        self.clear_all_highlights() # Xóa highlight cũ
        self.update_log(f"Bắt đầu tìm kiếm '{keyword}' trên Amazon.{market}, sort='{sort_type}', trang {start_page} đến {start_page + pages - 1}...")

        self.thread = QtCore.QThread(self) # Chỉ định parent là self
        # Chạy hàm self.spy.search_product trong thread
        self.worker = Worker(self.spy.search_product,
                             keywords=keyword,
                             pages=pages,
                             start_page=start_page,
                             sort_type=sort_type,
                             market=market,
                             spy_instance=self.spy) # Truyền spy instance vào worker

        self.worker.moveToThread(self.thread)

        # Kết nối signals từ worker ra GUI slots
        self.worker.log.connect(self.update_log)
        self.worker.finished.connect(self.on_search_finished)
        self.worker.error.connect(self.on_search_error)
        # Kết nối progress từ spy instance (không phải worker) ra GUI slot
        self.spy.progress_update.connect(self.update_progress_bar)

        self.thread.started.connect(self.worker.run)
        # self.thread.finished.connect(self.cleanup_thread) # Cleanup khi thread thực sự xong
        self.thread.start()

    # --- Cập nhật progress bar ---
    @QtCore.pyqtSlot(int, int) # Đảm bảo chạy trên main thread
    def update_progress_bar(self, current, total):
        if total > 0:
            percent = int((current / total) * 100)
            self.progress_bar.setValue(percent)
            self.progress_bar.setFormat(f"Đang xử lý: {current}/{total} (%p%)")
        else:
            self.progress_bar.setValue(0)
            self.progress_bar.setFormat("Tiến độ: %p%")


    def on_search_finished(self, df_result):
        # Đảm bảo chạy trên main thread
        QtCore.QMetaObject.invokeMethod(self, "_handle_search_finished", QtCore.Qt.QueuedConnection, QtCore.Q_ARG(object, df_result))

    @QtCore.pyqtSlot(object) # Slot để nhận df từ signal
    def _handle_search_finished(self, df_result):
        if not isinstance(df_result, pd.DataFrame):
            self.update_log(f"Lỗi: Kết quả trả về không phải DataFrame: {type(df_result)}")
            df_result = pd.DataFrame() # Tạo df rỗng để tránh lỗi tiếp theo

        self.update_log("Tìm kiếm hoàn tất. Đang hiển thị dữ liệu...")
        self.df = df_result
        self.display_data(self.df)
        self.search_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.progress_bar.setValue(100) # Đặt 100% khi xong
        self.progress_bar.setFormat("Hoàn thành!")
        self.cleanup_thread() # Dọn dẹp thread
        self.update_log(f"Đã tìm thấy và hiển thị {len(self.df)} sản phẩm.")
        
        # Tự động check TM sau khi tìm kiếm xong (tùy chọn)
        # if not self.df.empty:
        #      self.check_trademark()


    def on_search_error(self, e_info):
         # Đảm bảo chạy trên main thread
        QtCore.QMetaObject.invokeMethod(self, "_handle_search_error", QtCore.Qt.QueuedConnection, QtCore.Q_ARG(tuple, e_info))

    @QtCore.pyqtSlot(tuple) # Slot để nhận error info
    def _handle_search_error(self, e_info):
        e, tb = e_info
        error_message = str(e) if e else "Lỗi không xác định"
        self.update_log(f"LỖI: {error_message}")
        if tb:
             import traceback
             self.update_log(f"Traceback: {''.join(traceback.format_tb(tb))}")
        else:
             self.update_log("Không có thông tin traceback.")

        QtWidgets.QMessageBox.critical(self, "Lỗi tìm kiếm", f"Đã xảy ra lỗi:\n{error_message}")

        self.search_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat("Lỗi xảy ra!")
        self.cleanup_thread() # Dọn dẹp thread


    def stop_search(self):
        if self.thread and self.thread.isRunning():
            self.spy.stop() # Gửi tín hiệu dừng cho spy
            self.update_log("Đang yêu cầu dừng (có thể mất vài giây)...")
            self.stop_button.setEnabled(False) # Vô hiệu hóa nút Stop ngay
            # Không terminate thread, chờ worker tự dừng và cleanup
        else:
             self.update_log("Không có tác vụ tìm kiếm nào đang chạy.")


    def cleanup_thread(self):
        if self.thread:
             if self.thread.isRunning():
                 self.thread.quit() # Yêu cầu thread dừng nhẹ nhàng
                 if not self.thread.wait(5000): # Chờ tối đa 5 giây
                      self.update_log("Cảnh báo: Worker thread không dừng kịp thời, buộc dừng.")
                      self.thread.terminate() # Buộc dừng nếu không phản hồi
                      self.thread.wait() # Chờ sau khi terminate
             self.thread = None
             self.worker = None
             self.update_log("Thread tìm kiếm đã dọn dẹp.")
        else:
             # self.update_log("Không có thread nào cần dọn dẹp.") # Log hơi thừa
             pass


    def display_data(self, df):
        self.table_widget.setSortingEnabled(False) # Tắt sort khi cập nhật data
        self.table_widget.setRowCount(len(df))

        # Đổi tên cột DF cho dễ dùng
        df.rename(columns={
             "asin": "ASIN", "title": "Title", "brand": "Brand", "price": "Price",
             "bestseller_rank": "Rank", "image_url": "Image", "product_url": "Link",
             "reviews": "Reviews", "rating": "Rating", "sponsored": "Sponsored"
        }, inplace=True, errors='ignore') # errors='ignore' nếu cột không tồn tại

        gui_columns = ["ASIN", "Title", "Brand", "Price", "Rank", "Reviews", "Rating", "Sponsored", "Image", "Link"]
        image_col_index = gui_columns.index("Image") # Lấy index cột Image
        link_col_index = gui_columns.index("Link")

        for row_idx, row_data in df.iterrows():
            for col_idx, col_name in enumerate(gui_columns):
                if col_name == "Image":
                     # Để trống ô Image, sẽ load ảnh sau
                     img_label = QtWidgets.QLabel()
                     img_label.setAlignment(QtCore.Qt.AlignCenter)
                     img_label.setToolTip("Đang tải...")
                     self.table_widget.setCellWidget(row_idx, col_idx, img_label)
                     # Bắt đầu tải ảnh trong thread pool
                     image_url = row_data.get(col_name, "")
                     if image_url and isinstance(image_url, str) and image_url.startswith('http'):
                          # Kiểm tra cache trước khi tải
                          if image_url in self.image_cache:
                               pixmap = self.image_cache[image_url]
                               img_label.setPixmap(pixmap)
                               img_label.setToolTip(image_url)
                          else:
                               worker = ImageDownloader(row_idx, image_url)
                               worker.signals.finished.connect(self.update_table_image)
                               worker.signals.log.connect(self.update_log) # Kết nối log của downloader
                               self.threadpool.start(worker)

                elif col_name == "Link":
                     link_url = row_data.get(col_name, "")
                     item = QtWidgets.QTableWidgetItem("Link") # Chỉ hiện chữ Link
                     item.setToolTip(link_url) # URL thật nằm trong tooltip
                     if link_url:
                          item.setForeground(QtGui.QColor('blue')) # Màu xanh cho link
                          # item.setFont(QtGui.QFont(self.table_widget.font().family(), self.table_widget.font().pointSize(), QtGui.QFont.Underline) ) # Gạch chân
                     self.table_widget.setItem(row_idx, col_idx, item)

                elif col_name == "Sponsored":
                     sponsored_val = row_data.get(col_name, False)
                     item = QtWidgets.QTableWidgetItem("✔️" if sponsored_val else "") # Dùng checkmark
                     item.setTextAlignment(QtCore.Qt.AlignCenter)
                     if sponsored_val: item.setForeground(QtGui.QColor('orange'))
                     self.table_widget.setItem(row_idx, col_idx, item)

                elif col_name in ["Reviews", "Rating", "Price"]:
                    # Căn phải cho số liệu
                    item_data = str(row_data.get(col_name, "")) if pd.notna(row_data.get(col_name)) else ""
                    item = QtWidgets.QTableWidgetItem(item_data)
                    # Cố gắng chuyển đổi sang số để sort đúng
                    try:
                        num_val = float(item_data.replace('$', '').replace('€', '').replace('£', '').replace(',',''))
                        item.setData(QtCore.Qt.EditRole, num_val) # Lưu dạng số để sort
                    except ValueError:
                         pass # Nếu không phải số thì thôi
                    item.setTextAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
                    self.table_widget.setItem(row_idx, col_idx, item)

                else:
                    item_data = str(row_data.get(col_name, "")) if pd.notna(row_data.get(col_name)) else ""
                    item = QtWidgets.QTableWidgetItem(item_data)
                    item.setToolTip(item_data) # Tooltip cho các ô text dài
                    self.table_widget.setItem(row_idx, col_idx, item)

        # self.table_widget.resizeRowsToContents() # Đã đặt chiều cao cố định
        self.table_widget.setSortingEnabled(True) # Bật lại sort

    # --- Slot nhận ảnh đã tải ---
    @QtCore.pyqtSlot(int, QPixmap)
    def update_table_image(self, row_index, pixmap):
         # Kiểm tra xem widget còn tồn tại không (do người dùng có thể search mới)
         if row_index < self.table_widget.rowCount():
              widget = self.table_widget.cellWidget(row_index, self.table_widget.columnCount() - 2) # Cột Image (áp chót)
              if isinstance(widget, QtWidgets.QLabel):
                   widget.setPixmap(pixmap)
                   # Lưu vào cache (lấy url từ tooltip cũ hoặc từ df nếu cần)
                   # Lấy URL từ DataFrame để làm key cache
                   try:
                        image_url = self.df.iloc[row_index]['Image']
                        if image_url:
                             self.image_cache[image_url] = pixmap
                             widget.setToolTip(image_url) # Cập nhật tooltip
                   except (IndexError, KeyError):
                        pass # Bỏ qua nếu không lấy được URL

    # --- Mở link khi double click ---
    def open_link_in_browser(self, item):
         col = item.column()
         # Kiểm tra xem có phải cột Link hoặc cột Title không
         link_col_index = self.table_widget.columnCount() - 1 # Cột cuối
         title_col_index = 1

         url = None
         if col == link_col_index:
             # Lấy link từ tooltip của cột Link
             url = item.toolTip()
         elif col == title_col_index:
              # Lấy link từ cột Link cùng hàng
              link_item = self.table_widget.item(item.row(), link_col_index)
              if link_item:
                   url = link_item.toolTip()

         if url and url.startswith("http"):
             try:
                 import webbrowser
                 webbrowser.open(url)
                 self.update_log(f"Đã mở link: {url}")
             except Exception as e:
                 self.update_log(f"Lỗi khi mở link: {e}")
                 QtWidgets.QMessageBox.warning(self, "Lỗi", f"Không thể mở link:\n{e}")
         elif url:
              self.update_log(f"Link không hợp lệ: {url}")


    def export_to_excel(self):
        if self.df.empty:
            QtWidgets.QMessageBox.warning(self, "Không có dữ liệu", "Chưa có dữ liệu để xuất.")
            return

        options = QtWidgets.QFileDialog.Options()
        # Đặt tên file mặc định
        default_name = f"visual_spy_results_{self.keyword_input.text()}.xlsx".replace(" ", "_").replace(":", "-")
        file_path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Lưu File Excel", default_name, "Excel Files (*.xlsx);;All Files (*)", options=options)

        if file_path:
            try:
                self.update_log(f"Đang chuẩn bị dữ liệu để xuất ra {file_path}...")
                
                # Tạo bản copy để không ảnh hưởng df gốc
                df_to_export = self.df.copy()
                
                # Bỏ cột Image URL đi nếu không cần
                # if 'Image' in df_to_export.columns:
                #     df_to_export = df_to_export.drop(columns=['Image'])
                    
                # Đổi tên cột lại cho thân thiện (tùy chọn)
                df_to_export.rename(columns={
                     "ASIN": "ASIN", "Title": "Tiêu đề", "Brand": "Thương hiệu", "Price": "Giá",
                     "Rank": "Rank Amazon", "Reviews": "Số Reviews", "Rating": "Đánh giá (sao)",
                     "Sponsored": "Được tài trợ", "Image": "Link Ảnh", "Link": "Link Sản phẩm"
                }, inplace=True, errors='ignore')

                # Ghi ra Excel
                with pd.ExcelWriter(file_path, engine='openpyxl') as writer:
                     df_to_export.to_excel(writer, index=False, sheet_name='Products')
                     # Tự động điều chỉnh độ rộng cột (tùy chọn, có thể chậm với file lớn)
                     worksheet = writer.sheets['Products']
                     for column_cells in worksheet.columns:
                          length = max(len(str(cell.value)) for cell in column_cells)
                          worksheet.column_dimensions[column_cells[0].column_letter].width = length + 2

                self.update_log(f"Xuất file Excel thành công!")
                # Hỏi có muốn mở file không
                reply = QtWidgets.QMessageBox.information(self, 'Hoàn thành',
                                                       f'Đã xuất thành công ra file:\n{file_path}\n\nBạn có muốn mở file này không?',
                                                       QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No, QtWidgets.QMessageBox.Yes)
                if reply == QtWidgets.QMessageBox.Yes:
                     try:
                          os.startfile(file_path) # Mở file trên Windows
                     except AttributeError: # Nếu không phải Windows
                          try:
                               import subprocess
                               opener ="open" if sys.platform == "darwin" else "xdg-open"
                               subprocess.call([opener, file_path])
                          except Exception as e_open:
                               self.update_log(f"Không thể tự mở file: {e_open}")


            except PermissionError:
                 self.update_log(f"Lỗi: Không có quyền ghi file vào đường dẫn đó hoặc file đang được mở.")
                 QtWidgets.QMessageBox.critical(self, "Lỗi quyền", f"Không thể ghi file Excel. File có thể đang được mở bởi chương trình khác hoặc bạn không có quyền ghi vào thư mục này.")
            except Exception as e:
                self.update_log(f"Lỗi khi xuất Excel: {e}")
                QtWidgets.QMessageBox.critical(self, "Lỗi", f"Xuất file Excel thất bại:\n{e}")

    def check_login(self):
        dialog = LoginDialog(self)
        if dialog.exec_() == QtWidgets.QDialog.Accepted:
            email, password = dialog.get_credentials()
            if not email or not password:
                self.update_log("Email hoặc mật khẩu không được để trống.")
                return

            self.update_log("Bắt đầu kiểm tra đăng nhập trong thread...")
            # Chạy check login trong thread
            self.thread = QtCore.QThread(self) # Chỉ định parent
            # Hàm self.spy.check_login KHÔNG CẦN spy_instance nữa
            self.worker = Worker(self.spy.check_login, email, password, spy_instance=self.spy) # Vẫn truyền spy_instance để connect signal
            self.worker.moveToThread(self.thread)
            # Kết nối log từ instance spy chính (self.spy), không phải từ worker
            # self.spy.log.connect(self.update_log) # Đã connect ở init_ui
            self.worker.finished.connect(self.on_check_login_finished) # Tạo hàm xử lý khi xong
            self.worker.error.connect(self.on_search_error) # Dùng chung hàm báo lỗi
            self.thread.started.connect(self.worker.run)
            self.thread.start()

    # Hàm mới để xử lý khi check_login xong
    def on_check_login_finished(self, result=None):
        # Hàm check_login không trả về gì, chỉ emit log
        self.update_log("Hoàn thành kiểm tra đăng nhập.")
        self.cleanup_thread()


    # Sửa hàm update_log để đảm bảo thread-safe
    @QtCore.pyqtSlot(str) # Đánh dấu là slot và nhận string
    def update_log(self, text):
        # Đảm bảo hàm này chỉ chạy trên main thread
        if threading.current_thread() is not threading.main_thread():
             # Nếu đang ở thread khác, gửi signal để main thread xử lý
             # Cần một signal riêng cho việc này hoặc dùng invokeMethod cẩn thận
             # Cách đơn giản nhất là để Stream class tự handle bằng invokeMethod
             # Chỉ cần đảm bảo Stream class emit signal đúng cách
             # print(f"Log from thread: {text}") # Debug xem có log từ thread không
             pass # Stream class sẽ lo việc emit lên main thread
        else:
            # Nếu đang ở main thread, cập nhật trực tiếp
            cursor = self.log_text.textCursor()
            cursor.movePosition(QtGui.QTextCursor.End)
            self.log_text.setTextCursor(cursor)
            self.log_text.insertPlainText(text.strip() + "\n")
            # Cuộn xuống dòng cuối cùng
            scrollbar = self.log_text.verticalScrollBar()
            scrollbar.setValue(scrollbar.maximum())

    def closeEvent(self, event):
        self.update_log("Đang đóng ứng dụng...")
        self.stop_search() # Cố gắng dừng thread tìm kiếm
        self.threadpool.clear() # Xóa các tác vụ tải ảnh còn lại
        self.threadpool.waitForDone(5000) # Chờ tối đa 5s cho các thread tải ảnh kết thúc

        # Chờ thread tìm kiếm kết thúc hẳn (nếu có)
        if self.thread and self.thread.isRunning():
             self.thread.quit()
             if not self.thread.wait(5000): # Chờ tối đa 5 giây
                 self.update_log("Cảnh báo: Worker thread tìm kiếm không dừng kịp thời.")
                 # self.thread.terminate() # Hạn chế dùng terminate
        self.cleanup_thread() # Dọn dẹp

        # Đóng WebDriver nếu còn sót lại (dù không nên)
        if self.spy.driver:
            try:
                self.spy.driver.quit()
                self.spy.driver = None
                self.update_log("Đã đóng WebDriver còn sót lại.")
            except Exception as e_quit:
                self.update_log(f"Lỗi khi đóng WebDriver sót lại: {e_quit}")

        self.update_log("Ứng dụng đã đóng.")
        event.accept()

    # <-- HÀM MỚI ĐỂ CHECK KEY -->
    def check_license_on_startup(self):
        # <-- ĐỊA CHỈ API CỦA BẠN (LẤY TỪ VERCEL) -->
        API_URL = "https://key-merch.vercel.app/api/check" # Đã sửa URL đúng

        # Hỏi key
        license_key, ok = QInputDialog.getText(self, "Xác thực bản quyền", "Vui lòng nhập License Key của bạn:")

        if not ok or not license_key:
            # Nếu người dùng bấm "Cancel" hoặc không nhập gì
            self.update_log("Cần có License Key để sử dụng.")
            return False

        self.update_log("Đang kiểm tra License Key...")

        try:
            # Gửi key lên server
            response = requests.post(API_URL, json={"key": license_key.strip()}, timeout=15) # strip() key
            response.raise_for_status() # Báo lỗi nếu server trả về 4xx hoặc 5xx

            # Nếu server trả về "OK" (status code 200)
            data = response.json()
            if data.get("status") == "success":
                self.update_log("Xác thực thành công! Chào mừng bạn.")
                return True
            else:
                # Trường hợp server trả về 200 nhưng không phải success (ít xảy ra)
                error_msg = data.get("message", "Phản hồi không hợp lệ từ server.")
                self.update_log(f"LỖI: {error_msg}")
                QtWidgets.QMessageBox.critical(self, "Lỗi xác thực", error_msg)
                return False

        except requests.exceptions.HTTPError as errh:
            # Xử lý lỗi HTTP (4xx, 5xx)
            error_detail = f"Lỗi HTTP {errh.response.status_code}" # Mặc định
            try:
                # Cố gắng lấy chi tiết lỗi từ JSON trả về
                error_detail = errh.response.json().get("detail", error_detail)
            except Exception: # Nếu không parse được JSON
                pass
            self.update_log(f"LỖI: {error_detail}")
            QtWidgets.QMessageBox.critical(self, "Lỗi xác thực", f"Key không hợp lệ hoặc đã hết hạn.\nChi tiết: {error_detail}")
            return False

        except requests.exceptions.RequestException as e:
            # Nếu không kết nối được server (mất mạng, sập server, timeout)
            self.update_log(f"LỖI: Không thể kết nối đến máy chủ xác thực. {e}")
            QtWidgets.QMessageBox.critical(self, "Lỗi kết nối", f"Không thể kết nối đến máy chủ xác thực. Vui lòng kiểm tra Internet.")
            return False

        except Exception as e: # Bắt các lỗi khác
            self.update_log(f"LỖI không xác định khi kiểm tra key: {e}")
            QtWidgets.QMessageBox.critical(self, "Lỗi không xác định", f"Đã xảy ra lỗi khi kiểm tra key:\n{e}")
            return False

# <-- SỬA KHỐI CODE CUỐI CÙNG NÀY -->
if __name__ == "__main__":
    # Kích hoạt chế độ DPI Scaling cho màn hình độ phân giải cao (nếu cần)
    if hasattr(QtCore.Qt, 'AA_EnableHighDpiScaling'):
        QtWidgets.QApplication.setAttribute(QtCore.Qt.AA_EnableHighDpiScaling, True)
    if hasattr(QtCore.Qt, 'AA_UseHighDpiPixmaps'):
        QtWidgets.QApplication.setAttribute(QtCore.Qt.AA_UseHighDpiPixmaps, True)

    app = QtWidgets.QApplication(sys.argv)
    
    # ---- Splash Screen (Tùy chọn) ----
    # splash_pix = QPixmap("path/to/your/splash_image.png") # Thay bằng ảnh của bạn
    # splash = QtWidgets.QSplashScreen(splash_pix, QtCore.Qt.WindowStaysOnTopHint)
    # splash.setMask(splash_pix.mask())
    # splash.show()
    # app.processEvents()
    # -----------------------------------

    main_win = MainWindow() # Tạo đối tượng MainWindow (bao gồm cả spy)

    # KIỂM TRA LICENSE TRƯỚC KHI HIỂN THỊ TOOL
    if main_win.check_license_on_startup():
        # Nếu key đúng, hiển thị tool
        # splash.finish(main_win) # Đóng splash screen khi main window hiện
        main_win.show()
        sys.exit(app.exec_())
    else:
        # Nếu key sai hoặc có lỗi, thoát luôn
        # splash.close() # Đóng splash screen nếu lỗi
        sys.exit()