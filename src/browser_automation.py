"""
瀏覽器自動化模組 - Chrome 瀏覽器控制
用於自動登入財政部電子發票平台並填寫發票資料
"""
import time
import logging
from typing import Optional, TYPE_CHECKING
from dataclasses import dataclass

try:
    from selenium import webdriver
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.common.exceptions import (
        TimeoutException,
        ElementClickInterceptedException,
        ElementNotInteractableException,
    )
except ImportError:
    webdriver = None
    Service = None
    Options = None
    By = None
    WebDriverWait = None
    EC = None
    TimeoutException = None
    ElementClickInterceptedException = None
    ElementNotInteractableException = None

try:
    from webdriver_manager.chrome import ChromeDriverManager
except ImportError:
    ChromeDriverManager = None

from .invoice_extractor import InvoiceData

# For type hints only
if TYPE_CHECKING:
    from selenium.webdriver import Chrome


@dataclass
class BrowserConfig:
    """瀏覽器配置"""
    headless: bool = False  # 是否無頭模式
    window_width: int = 1920
    window_height: int = 1080
    implicit_wait: int = 10
    page_load_timeout: int = 30
    download_dir: Optional[str] = None


class BrowserAutomation:
    """
    瀏覽器自動化控制器

    用於控制 Chrome 瀏覽器自動完成發票申報作業
    """

    # 財政部電子發票整合服務平台
    EINVOICE_URL = "https://www.einvoice.nat.gov.tw/"

    # 營業稅電子申報繳稅系統
    ETAX_URL = "https://tax.nat.gov.tw/"

    def __init__(self, config: Optional[BrowserConfig] = None):
        """
        初始化瀏覽器自動化控制器

        Args:
            config: 瀏覽器配置
        """
        self._check_dependencies()
        self.config = config or BrowserConfig()
        self.driver: Optional["Chrome"] = None
        self.logger = logging.getLogger(__name__)

    def _check_dependencies(self):
        """檢查必要的套件"""
        if webdriver is None:
            raise ImportError("請安裝 selenium: pip install selenium")
        if ChromeDriverManager is None:
            raise ImportError("請安裝 webdriver-manager: pip install webdriver-manager")

    def start_browser(self) -> "Chrome":
        """
        啟動 Chrome 瀏覽器

        Returns:
            webdriver.Chrome: Chrome 瀏覽器實例
        """
        options = Options()

        # 基本設定
        if self.config.headless:
            options.add_argument("--headless=new")

        options.add_argument(f"--window-size={self.config.window_width},{self.config.window_height}")
        options.add_argument("--disable-gpu")
        
        # 安全警告：以下選項會降低瀏覽器安全隔離
        # --no-sandbox: 停用沙盒機制，僅應在受控環境（如 Docker 容器）中使用
        # --disable-dev-shm-usage: 停用 /dev/shm 使用，避免記憶體不足問題
        # 在生產環境中應謹慎評估這些選項的安全風險
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")

        # 避免被偵測為自動化
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option("useAutomationExtension", False)

        # 設定下載目錄
        if self.config.download_dir:
            prefs = {
                "download.default_directory": self.config.download_dir,
                "download.prompt_for_download": False,
            }
            options.add_experimental_option("prefs", prefs)

        # 啟動瀏覽器
        service = Service(ChromeDriverManager().install())
        self.driver = webdriver.Chrome(service=service, options=options)

        # 設定等待時間
        self.driver.implicitly_wait(self.config.implicit_wait)
        self.driver.set_page_load_timeout(self.config.page_load_timeout)

        return self.driver

    def close_browser(self):
        """關閉瀏覽器"""
        if self.driver:
            self.driver.quit()
            self.driver = None

    def navigate_to(self, url: str):
        """
        導航到指定網址

        Args:
            url: 目標網址
        """
        if not self.driver:
            self.start_browser()
        self.driver.get(url)

    def wait_for_element(
        self,
        by: By,
        value: str,
        timeout: int = 10,
        condition: str = "presence"
    ):
        """
        等待元素出現

        Args:
            by: 定位方式
            value: 定位值
            timeout: 超時時間（秒）
            condition: 等待條件 (presence, clickable, visible)

        Returns:
            找到的元素
        """
        wait = WebDriverWait(self.driver, timeout)

        conditions = {
            "presence": EC.presence_of_element_located,
            "clickable": EC.element_to_be_clickable,
            "visible": EC.visibility_of_element_located,
        }

        return wait.until(conditions[condition]((by, value)))

    def safe_click(self, element):
        """
        安全點擊元素
        
        Args:
            element: 要點擊的元素
        
        Raises:
            Exception: 如果點擊失敗且 JavaScript 點擊也失敗
        """
        try:
            element.click()
        except (ElementClickInterceptedException, ElementNotInteractableException) as e:
            # 如果一般點擊失敗（被遮蔽或無法互動），使用 JavaScript 點擊
            self.logger.warning(f"元素點擊被攔截，嘗試使用 JavaScript 點擊: {e}")
            self.driver.execute_script("arguments[0].click();", element)

    def safe_send_keys(self, element, text: str, clear_first: bool = True):
        """
        安全輸入文字

        Args:
            element: 目標元素
            text: 要輸入的文字
            clear_first: 是否先清空
        """
        if clear_first:
            element.clear()
        element.send_keys(text)

    def fill_invoice_form(self, invoice_data: InvoiceData) -> bool:
        """
        填寫發票表單

        這是一個範例方法，實際使用時需要根據目標網站的
        HTML 結構進行調整。

        Args:
            invoice_data: 發票資料

        Returns:
            bool: 是否填寫成功（所有關鍵欄位都成功填寫）
        """
        # 追蹤填寫成功的欄位
        filled_fields = []
        failed_fields = []
        
        try:
            # 注意：以下是範例代碼，實際的元素定位需要
            # 根據財政部網站的實際 HTML 結構進行調整

            # 填寫發票號碼（關鍵欄位）
            if invoice_data.invoice_number:
                try:
                    invoice_num_field = self.wait_for_element(
                        By.ID, "invoiceNumber", timeout=5
                    )
                    self.safe_send_keys(invoice_num_field, invoice_data.invoice_number)
                    filled_fields.append("invoice_number")
                except TimeoutException:
                    self.logger.warning("找不到發票號碼欄位")
                    failed_fields.append("invoice_number")

            # 填寫發票日期
            if invoice_data.invoice_date:
                try:
                    date_field = self.wait_for_element(
                        By.ID, "invoiceDate", timeout=5
                    )
                    self.safe_send_keys(date_field, invoice_data.invoice_date)
                    filled_fields.append("invoice_date")
                except TimeoutException:
                    self.logger.warning("找不到發票日期欄位")
                    failed_fields.append("invoice_date")

            # 填寫賣方統一編號
            if invoice_data.seller_id:
                try:
                    seller_id_field = self.wait_for_element(
                        By.ID, "sellerTaxId", timeout=5
                    )
                    self.safe_send_keys(seller_id_field, invoice_data.seller_id)
                    filled_fields.append("seller_id")
                except TimeoutException:
                    self.logger.warning("找不到賣方統編欄位")
                    failed_fields.append("seller_id")

            # 填寫買方統一編號
            if invoice_data.buyer_id:
                try:
                    buyer_id_field = self.wait_for_element(
                        By.ID, "buyerTaxId", timeout=5
                    )
                    self.safe_send_keys(buyer_id_field, invoice_data.buyer_id)
                    filled_fields.append("buyer_id")
                except TimeoutException:
                    self.logger.warning("找不到買方統編欄位")
                    failed_fields.append("buyer_id")

            # 填寫金額（關鍵欄位）
            if invoice_data.total_amount > 0:
                try:
                    amount_field = self.wait_for_element(
                        By.ID, "totalAmount", timeout=5
                    )
                    self.safe_send_keys(amount_field, str(invoice_data.total_amount))
                    filled_fields.append("total_amount")
                except TimeoutException:
                    self.logger.warning("找不到金額欄位")
                    failed_fields.append("total_amount")

            # 填寫稅額
            if invoice_data.tax_amount > 0:
                try:
                    tax_field = self.wait_for_element(
                        By.ID, "taxAmount", timeout=5
                    )
                    self.safe_send_keys(tax_field, str(invoice_data.tax_amount))
                    filled_fields.append("tax_amount")
                except TimeoutException:
                    self.logger.warning("找不到稅額欄位")
                    failed_fields.append("tax_amount")

            # 記錄填寫結果
            self.logger.info(f"成功填寫欄位: {filled_fields}")
            if failed_fields:
                self.logger.warning(f"無法填寫欄位: {failed_fields}")

            # 關鍵欄位：發票號碼和金額必須成功填寫
            critical_fields = ["invoice_number", "total_amount"]
            critical_failed = [f for f in critical_fields if f in failed_fields]
            
            if critical_failed:
                self.logger.error(f"關鍵欄位填寫失敗: {critical_failed}")
                return False

            return True

        except Exception as e:
            self.logger.error(f"填寫表單時發生錯誤: {e}", exc_info=True)
            return False

    def take_screenshot(self, filename: str):
        """
        擷取螢幕截圖

        Args:
            filename: 檔案名稱
        """
        if self.driver:
            self.driver.save_screenshot(filename)

    def get_page_source(self) -> str:
        """取得頁面原始碼"""
        return self.driver.page_source if self.driver else ""

    def execute_script(self, script: str, *args):
        """執行 JavaScript"""
        if self.driver:
            return self.driver.execute_script(script, *args)

    def switch_to_frame(self, frame_reference):
        """切換到 iframe"""
        if self.driver:
            self.driver.switch_to.frame(frame_reference)

    def switch_to_default_content(self):
        """切換回主頁面"""
        if self.driver:
            self.driver.switch_to.default_content()


class EInvoiceAutomation(BrowserAutomation):
    """
    電子發票平台自動化

    專門用於財政部電子發票整合服務平台的自動化操作
    """

    def __init__(self, config: Optional[BrowserConfig] = None):
        super().__init__(config)

    def open_einvoice_platform(self):
        """開啟電子發票平台"""
        self.navigate_to(self.EINVOICE_URL)
        time.sleep(2)  # 等待頁面載入

    def login_with_certificate(self):
        """
        使用憑證登入

        注意：需要電腦已插入工商憑證或自然人憑證
        """
        # 此功能需要實際測試和調整
        # 通常需要處理憑證選擇對話框
        raise NotImplementedError("憑證登入功能需要實際環境測試")

    def login_with_account(self, username: str, password: str):
        """
        使用帳號密碼登入

        Args:
            username: 使用者帳號
            password: 密碼
        """
        try:
            # 等待登入表單載入
            username_field = self.wait_for_element(
                By.NAME, "userId", timeout=10
            )
            password_field = self.wait_for_element(
                By.NAME, "password", timeout=10
            )

            # 輸入帳號密碼
            self.safe_send_keys(username_field, username)
            self.safe_send_keys(password_field, password)

            # 點擊登入按鈕
            login_button = self.wait_for_element(
                By.CSS_SELECTOR, "button[type='submit']", timeout=10
            )
            self.safe_click(login_button)

            # 等待登入完成
            time.sleep(3)

        except TimeoutException:
            print("登入頁面元素超時")
            raise

    def navigate_to_invoice_filing(self):
        """導航到發票申報頁面"""
        # 此方法需要根據實際網站結構調整
        raise NotImplementedError("需要根據實際網站結構實現")

    def fill_and_submit_invoice(self, invoice_data: InvoiceData) -> bool:
        """
        填寫並提交發票

        Args:
            invoice_data: 發票資料

        Returns:
            bool: 是否提交成功
        """
        # 填寫表單
        if not self.fill_invoice_form(invoice_data):
            return False

        # 此處添加提交邏輯
        # 注意：實際提交前應該有確認步驟

        return True


# 使用範例
if __name__ == "__main__":
    from .invoice_extractor import InvoiceData

    # 建立配置
    config = BrowserConfig(
        headless=False,  # 顯示瀏覽器視窗
        window_width=1920,
        window_height=1080,
    )

    # 建立自動化實例
    automation = EInvoiceAutomation(config)

    try:
        # 啟動瀏覽器
        automation.start_browser()

        # 開啟電子發票平台
        automation.open_einvoice_platform()

        # 等待使用者操作
        input("按 Enter 關閉瀏覽器...")

    finally:
        # 關閉瀏覽器
        automation.close_browser()
