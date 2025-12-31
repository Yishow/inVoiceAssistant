"""
AI 瀏覽器自動化模組

使用 AI 解析自然語言指令，控制瀏覽器執行發票申報操作
支援多種 AI 後端：Claude API、本地指令解析、Claude Code MCP
"""
import json
import re
import time
import datetime
from typing import Optional, Dict, Any, List, Callable
from dataclasses import dataclass, field
from enum import Enum

try:
    import anthropic
    HAS_ANTHROPIC = True
except ImportError:
    HAS_ANTHROPIC = False

from .browser_automation import EInvoiceAutomation, BrowserConfig
from .invoice_extractor import InvoiceData


class ActionType(Enum):
    """瀏覽器操作類型"""
    NAVIGATE = "navigate"
    CLICK = "click"
    TYPE = "type"
    WAIT = "wait"
    SCREENSHOT = "screenshot"
    LOGIN = "login"
    FILL_FORM = "fill_form"
    SUBMIT = "submit"
    SCROLL = "scroll"
    SELECT = "select"
    EXTRACT = "extract"
    CUSTOM_SCRIPT = "custom_script"


@dataclass
class BrowserAction:
    """瀏覽器操作指令"""
    action_type: ActionType
    target: Optional[str] = None  # CSS selector 或 XPath
    value: Optional[str] = None   # 輸入值或 URL
    description: str = ""         # 操作描述
    wait_after: float = 0.5       # 操作後等待時間
    options: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "action_type": self.action_type.value,
            "target": self.target,
            "value": self.value,
            "description": self.description,
            "wait_after": self.wait_after,
            "options": self.options
        }


@dataclass
class AutomationSession:
    """自動化會話狀態"""
    session_id: str
    status: str = "idle"  # idle, running, paused, completed, error
    current_step: int = 0
    total_steps: int = 0
    actions: List[BrowserAction] = field(default_factory=list)
    results: List[Dict[str, Any]] = field(default_factory=list)
    error_message: Optional[str] = None
    invoice_data: Optional[Dict[str, Any]] = None


class AICommandParser:
    """
    AI 指令解析器

    將自然語言指令轉換為瀏覽器操作序列
    """

    # 財政部相關網站
    KNOWN_SITES = {
        "einvoice": "https://www.einvoice.nat.gov.tw/",
        "電子發票": "https://www.einvoice.nat.gov.tw/",
        "etax": "https://tax.nat.gov.tw/",
        "營業稅": "https://tax.nat.gov.tw/",
        "財政部": "https://www.mof.gov.tw/",
    }

    # 常用操作模式
    COMMAND_PATTERNS = {
        r"(?:開啟|打開|前往|去|到|訪問)\s*(.+)": "navigate",
        r"(?:登入|登錄|signin|login)": "login",
        r"(?:輸入|填入|填寫|打)\s*(.+)\s*(?:到|在)\s*(.+)": "type",
        r"(?:點擊|點選|按|click)\s*(.+)": "click",
        r"(?:等待|wait)\s*(\d+)\s*秒?": "wait",
        r"(?:截圖|screenshot|擷取)": "screenshot",
        r"(?:提交|送出|submit)": "submit",
        r"(?:選擇|select)\s*(.+)": "select",
        r"(?:滾動|scroll)\s*(上|下|到底)": "scroll",
        r"(?:填寫發票|自動填表|填入發票資料)": "fill_form",
    }

    def __init__(self):
        self.context: Dict[str, Any] = {}

    def parse_command(self, command: str) -> List[BrowserAction]:
        """
        解析自然語言指令

        Args:
            command: 自然語言指令

        Returns:
            瀏覽器操作列表
        """
        actions = []
        command = command.strip().lower()

        # 嘗試匹配已知模式
        for pattern, action_type in self.COMMAND_PATTERNS.items():
            match = re.search(pattern, command, re.IGNORECASE)
            if match:
                action = self._create_action(action_type, match, command)
                if action:
                    actions.append(action)

        # 如果沒有匹配，返回一個通用操作
        if not actions:
            actions.append(BrowserAction(
                action_type=ActionType.CUSTOM_SCRIPT,
                description=command,
                options={"raw_command": command}
            ))

        return actions

    def _create_action(self, action_type: str, match: re.Match,
                       full_command: str) -> Optional[BrowserAction]:
        """根據匹配結果創建操作"""

        if action_type == "navigate":
            target = match.group(1) if match.groups() else ""
            url = self._resolve_url(target)
            return BrowserAction(
                action_type=ActionType.NAVIGATE,
                value=url,
                description=f"導航到 {url}"
            )

        elif action_type == "login":
            return BrowserAction(
                action_type=ActionType.LOGIN,
                description="執行登入操作"
            )

        elif action_type == "type":
            if len(match.groups()) >= 2:
                value, target = match.group(1), match.group(2)
                return BrowserAction(
                    action_type=ActionType.TYPE,
                    target=target,
                    value=value,
                    description=f"在 {target} 輸入 {value}"
                )

        elif action_type == "click":
            target = match.group(1) if match.groups() else ""
            return BrowserAction(
                action_type=ActionType.CLICK,
                target=target,
                description=f"點擊 {target}"
            )

        elif action_type == "wait":
            seconds = int(match.group(1)) if match.groups() else 1
            return BrowserAction(
                action_type=ActionType.WAIT,
                value=str(seconds),
                description=f"等待 {seconds} 秒"
            )

        elif action_type == "screenshot":
            return BrowserAction(
                action_type=ActionType.SCREENSHOT,
                description="擷取螢幕截圖"
            )

        elif action_type == "submit":
            return BrowserAction(
                action_type=ActionType.SUBMIT,
                description="提交表單"
            )

        elif action_type == "fill_form":
            return BrowserAction(
                action_type=ActionType.FILL_FORM,
                description="填寫發票表單"
            )

        return None

    def _resolve_url(self, target: str) -> str:
        """解析目標為 URL"""
        target_lower = target.lower()

        # 檢查是否是已知網站
        for keyword, url in self.KNOWN_SITES.items():
            if keyword in target_lower:
                return url

        # 如果已經是 URL
        if target.startswith(("http://", "https://")):
            return target

        # 嘗試構建 URL
        return f"https://{target}"


class ClaudeAutomationAgent:
    """
    Claude AI 自動化代理

    使用 Claude API 解析複雜指令並生成操作序列
    """

    SYSTEM_PROMPT = """你是一個瀏覽器自動化助手，專門協助用戶在台灣財政部電子發票平台進行發票申報操作。

你的任務是將用戶的自然語言指令轉換為具體的瀏覽器操作步驟。

## 可用的操作類型:
1. navigate - 導航到網址
2. click - 點擊元素（需提供 CSS selector 或元素描述）
3. type - 在輸入框輸入文字
4. wait - 等待指定秒數
5. screenshot - 截取螢幕
6. login - 執行登入（需要帳號密碼）
7. fill_form - 填寫發票表單
8. submit - 提交表單
9. scroll - 滾動頁面
10. select - 選擇下拉選項

## 財政部電子發票平台資訊:
- 首頁: https://www.einvoice.nat.gov.tw/
- 營業稅申報: https://tax.nat.gov.tw/
- 登入通常需要工商憑證或帳號密碼

## 輸出格式:
請以 JSON 陣列格式輸出操作步驟，每個步驟包含:
{
  "action_type": "操作類型",
  "target": "目標元素（CSS selector 或描述）",
  "value": "輸入值或 URL",
  "description": "步驟說明",
  "wait_after": 等待秒數
}

## 注意事項:
1. 對於敏感操作（如登入、提交），請確認用戶意圖
2. 如果指令不明確，請列出可能的操作選項
3. 考慮網頁載入時間，適當加入等待步驟
4. 財政部網站可能有驗證碼，需要人工介入

請根據用戶指令生成操作步驟。"""

    def __init__(self, api_key: Optional[str] = None):
        """
        初始化 Claude 代理

        Args:
            api_key: Anthropic API 金鑰（可從環境變數 ANTHROPIC_API_KEY 讀取）
        """
        if not HAS_ANTHROPIC:
            raise ImportError("請安裝 anthropic: pip install anthropic")

        self.client = anthropic.Anthropic(api_key=api_key)
        self.conversation_history: List[Dict[str, str]] = []

    def generate_actions(self, user_prompt: str,
                        invoice_data: Optional[InvoiceData] = None) -> List[BrowserAction]:
        """
        使用 Claude 生成操作序列

        Args:
            user_prompt: 用戶指令
            invoice_data: 可選的發票資料

        Returns:
            操作序列
        """
        # 構建完整提示
        context = ""
        if invoice_data:
            context = f"\n\n當前發票資料:\n{json.dumps(invoice_data.to_dict(), ensure_ascii=False, indent=2)}"

        full_prompt = user_prompt + context

        # 添加到對話歷史
        self.conversation_history.append({
            "role": "user",
            "content": full_prompt
        })

        # 呼叫 Claude API
        response = self.client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=2048,
            system=self.SYSTEM_PROMPT,
            messages=self.conversation_history
        )

        assistant_message = response.content[0].text

        # 保存回應
        self.conversation_history.append({
            "role": "assistant",
            "content": assistant_message
        })

        # 解析回應為操作
        return self._parse_response(assistant_message)

    def _parse_response(self, response: str) -> List[BrowserAction]:
        """解析 Claude 回應為操作列表"""
        actions = []

        # 嘗試提取 JSON
        json_match = re.search(r'\[[\s\S]*\]', response)
        if json_match:
            try:
                action_list = json.loads(json_match.group())
                for action_dict in action_list:
                    action_type = ActionType(action_dict.get("action_type", "custom_script"))
                    actions.append(BrowserAction(
                        action_type=action_type,
                        target=action_dict.get("target"),
                        value=action_dict.get("value"),
                        description=action_dict.get("description", ""),
                        wait_after=action_dict.get("wait_after", 0.5)
                    ))
            except (json.JSONDecodeError, ValueError) as e:
                # 如果 JSON 解析失敗，創建一個自定義操作
                actions.append(BrowserAction(
                    action_type=ActionType.CUSTOM_SCRIPT,
                    description=response,
                    options={"raw_response": response, "parse_error": str(e)}
                ))
        else:
            # 沒有找到 JSON，返回文字回應
            actions.append(BrowserAction(
                action_type=ActionType.CUSTOM_SCRIPT,
                description=response,
                options={"raw_response": response}
            ))

        return actions

    def clear_history(self):
        """清除對話歷史"""
        self.conversation_history = []


class AIBrowserController:
    """
    AI 瀏覽器控制器

    整合 AI 指令解析和瀏覽器自動化
    """

    def __init__(self,
                 use_claude: bool = False,
                 api_key: Optional[str] = None,
                 browser_config: Optional[BrowserConfig] = None):
        """
        初始化控制器

        Args:
            use_claude: 是否使用 Claude API
            api_key: Claude API 金鑰
            browser_config: 瀏覽器配置
        """
        self.browser = EInvoiceAutomation(browser_config)
        self.local_parser = AICommandParser()

        self.use_claude = use_claude
        self.claude_agent: Optional[ClaudeAutomationAgent] = None

        if use_claude:
            try:
                self.claude_agent = ClaudeAutomationAgent(api_key)
            except ImportError:
                print("警告: 無法使用 Claude API，將使用本地解析器")
                self.use_claude = False

        self.session: Optional[AutomationSession] = None
        self.action_handlers: Dict[ActionType, Callable] = self._setup_handlers()

    def _setup_handlers(self) -> Dict[ActionType, Callable]:
        """設置操作處理器"""
        return {
            ActionType.NAVIGATE: self._handle_navigate,
            ActionType.CLICK: self._handle_click,
            ActionType.TYPE: self._handle_type,
            ActionType.WAIT: self._handle_wait,
            ActionType.SCREENSHOT: self._handle_screenshot,
            ActionType.LOGIN: self._handle_login,
            ActionType.FILL_FORM: self._handle_fill_form,
            ActionType.SUBMIT: self._handle_submit,
            ActionType.SCROLL: self._handle_scroll,
            ActionType.SELECT: self._handle_select,
            ActionType.EXTRACT: self._handle_extract,
            ActionType.CUSTOM_SCRIPT: self._handle_custom_script,
        }

    def start_session(self, session_id: Optional[str] = None) -> AutomationSession:
        """啟動自動化會話"""
        import uuid
        self.session = AutomationSession(
            session_id=session_id or str(uuid.uuid4())[:8]
        )
        self.browser.start_browser()
        self.session.status = "running"
        return self.session

    def end_session(self):
        """結束會話"""
        if self.session:
            self.session.status = "completed"
        self.browser.close_browser()

    def process_prompt(self, prompt: str,
                       invoice_data: Optional[InvoiceData] = None) -> Dict[str, Any]:
        """
        處理用戶提示

        Args:
            prompt: 自然語言指令
            invoice_data: 發票資料

        Returns:
            執行結果
        """
        result = {
            "success": False,
            "prompt": prompt,
            "actions": [],
            "results": [],
            "message": ""
        }

        try:
            # 解析指令
            if self.use_claude and self.claude_agent:
                actions = self.claude_agent.generate_actions(prompt, invoice_data)
            else:
                actions = self.local_parser.parse_command(prompt)

            result["actions"] = [a.to_dict() for a in actions]

            # 確保瀏覽器已啟動
            if not self.browser.driver:
                self.start_session()

            # 執行操作
            for action in actions:
                action_result = self.execute_action(action, invoice_data)
                result["results"].append(action_result)

                if not action_result.get("success", False):
                    result["message"] = f"操作失敗: {action_result.get('error', '未知錯誤')}"
                    return result

            result["success"] = True
            result["message"] = f"成功執行 {len(actions)} 個操作"

        except Exception as e:
            result["message"] = f"執行錯誤: {str(e)}"

        return result

    def execute_action(self, action: BrowserAction,
                       invoice_data: Optional[InvoiceData] = None) -> Dict[str, Any]:
        """
        執行單個操作

        Args:
            action: 瀏覽器操作
            invoice_data: 發票資料

        Returns:
            執行結果
        """
        handler = self.action_handlers.get(action.action_type)

        if handler:
            result = handler(action, invoice_data)
        else:
            result = {
                "success": False,
                "error": f"不支援的操作類型: {action.action_type}"
            }

        # 操作後等待
        if action.wait_after > 0:
            time.sleep(action.wait_after)

        return result

    # 操作處理器實現
    def _handle_navigate(self, action: BrowserAction,
                         invoice_data: Optional[InvoiceData]) -> Dict[str, Any]:
        """處理導航操作"""
        try:
            self.browser.navigate_to(action.value)
            return {"success": True, "url": action.value}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _handle_click(self, action: BrowserAction,
                      invoice_data: Optional[InvoiceData]) -> Dict[str, Any]:
        """處理點擊操作"""
        try:
            from selenium.webdriver.common.by import By

            # 嘗試多種定位方式（使用更精確的選擇器）
            element = None
            selectors = [
                (By.CSS_SELECTOR, action.target),
                (By.XPATH, f"//button[normalize-space(.) = '{action.target}']"
                           f" | //a[normalize-space(.) = '{action.target}']"
                           f" | //input[@value = '{action.target}']"),
                (By.ID, action.target),
                (By.NAME, action.target),
            ]

            for by, selector in selectors:
                try:
                    element = self.browser.wait_for_element(by, selector, timeout=5)
                    break
                except Exception:
                    continue

            if element:
                self.browser.safe_click(element)
                return {"success": True, "target": action.target}
            else:
                return {"success": False, "error": f"找不到元素: {action.target}"}

        except Exception as e:
            return {"success": False, "error": str(e)}

    def _handle_type(self, action: BrowserAction,
                     invoice_data: Optional[InvoiceData]) -> Dict[str, Any]:
        """處理輸入操作"""
        try:
            from selenium.webdriver.common.by import By

            element = None
            selectors = [
                (By.CSS_SELECTOR, action.target),
                (By.ID, action.target),
                (By.NAME, action.target),
            ]

            for by, selector in selectors:
                try:
                    element = self.browser.wait_for_element(by, selector, timeout=5)
                    break
                except Exception:
                    continue

            if element:
                self.browser.safe_send_keys(element, action.value)
                return {"success": True, "target": action.target, "value": action.value}
            else:
                return {"success": False, "error": f"找不到輸入框: {action.target}"}

        except Exception as e:
            return {"success": False, "error": str(e)}

    def _handle_wait(self, action: BrowserAction,
                     invoice_data: Optional[InvoiceData]) -> Dict[str, Any]:
        """處理等待操作"""
        try:
            seconds = float(action.value) if action.value else 1
            time.sleep(seconds)
            return {"success": True, "waited": seconds}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _handle_screenshot(self, action: BrowserAction,
                           invoice_data: Optional[InvoiceData]) -> Dict[str, Any]:
        """處理截圖操作"""
        try:
            filename = action.value or f"screenshot_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            self.browser.take_screenshot(filename)
            return {"success": True, "filename": filename}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _handle_login(self, action: BrowserAction,
                      invoice_data: Optional[InvoiceData]) -> Dict[str, Any]:
        """處理登入操作"""
        # 登入需要額外的帳號密碼資訊
        options = action.options or {}
        username = options.get("username")
        password = options.get("password")

        if username and password:
            try:
                self.browser.login_with_account(username, password)
                return {"success": True, "message": "登入成功"}
            except Exception as e:
                return {"success": False, "error": str(e)}
        else:
            return {
                "success": False,
                "error": "需要提供帳號和密碼",
                "requires_input": True,
                "fields": ["username", "password"]
            }

    def _handle_fill_form(self, action: BrowserAction,
                          invoice_data: Optional[InvoiceData]) -> Dict[str, Any]:
        """處理填表操作"""
        if invoice_data:
            try:
                success = self.browser.fill_invoice_form(invoice_data)
                return {"success": success, "message": "表單填寫完成" if success else "填寫失敗"}
            except Exception as e:
                return {"success": False, "error": str(e)}
        else:
            return {"success": False, "error": "沒有發票資料可填寫"}

    def _handle_submit(self, action: BrowserAction,
                       invoice_data: Optional[InvoiceData]) -> Dict[str, Any]:
        """處理提交操作"""
        try:
            from selenium.webdriver.common.by import By

            # 嘗試找到提交按鈕
            submit_selectors = [
                "button[type='submit']",
                "input[type='submit']",
                ".submit-btn",
                "#submitBtn",
            ]

            for selector in submit_selectors:
                try:
                    element = self.browser.wait_for_element(By.CSS_SELECTOR, selector, timeout=3)
                    self.browser.safe_click(element)
                    return {"success": True, "message": "表單已提交"}
                except Exception:
                    continue

            return {"success": False, "error": "找不到提交按鈕"}

        except Exception as e:
            return {"success": False, "error": str(e)}

    def _handle_scroll(self, action: BrowserAction,
                       invoice_data: Optional[InvoiceData]) -> Dict[str, Any]:
        """處理滾動操作"""
        try:
            direction = action.value or "down"

            if direction == "up":
                self.browser.execute_script("window.scrollBy(0, -500);")
            elif direction == "down":
                self.browser.execute_script("window.scrollBy(0, 500);")
            elif direction in ("bottom", "到底"):
                self.browser.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            elif direction in ("top", "頂部"):
                self.browser.execute_script("window.scrollTo(0, 0);")

            return {"success": True, "direction": direction}

        except Exception as e:
            return {"success": False, "error": str(e)}

    def _handle_select(self, action: BrowserAction,
                       invoice_data: Optional[InvoiceData]) -> Dict[str, Any]:
        """處理下拉選擇操作"""
        try:
            from selenium.webdriver.common.by import By
            from selenium.webdriver.support.ui import Select

            element = self.browser.wait_for_element(By.CSS_SELECTOR, action.target, timeout=5)
            select = Select(element)

            # 嘗試用文字選擇
            try:
                select.select_by_visible_text(action.value)
            except Exception:
                # 嘗試用值選擇
                select.select_by_value(action.value)

            return {"success": True, "target": action.target, "value": action.value}

        except Exception as e:
            return {"success": False, "error": str(e)}

    def _handle_extract(self, action: BrowserAction,
                        invoice_data: Optional[InvoiceData]) -> Dict[str, Any]:
        """處理資料提取操作"""
        try:
            from selenium.webdriver.common.by import By

            elements = self.browser.driver.find_elements(By.CSS_SELECTOR, action.target)
            data = [el.text for el in elements]

            return {"success": True, "data": data}

        except Exception as e:
            return {"success": False, "error": str(e)}

    def _handle_custom_script(self, action: BrowserAction,
                              invoice_data: Optional[InvoiceData]) -> Dict[str, Any]:
        """處理自定義腳本"""
        # 自定義腳本需要返回給用戶讓他們決定如何處理
        return {
            "success": True,
            "type": "custom",
            "description": action.description,
            "options": action.options,
            "requires_user_action": True
        }


# 方便的工廠函數
def create_ai_controller(use_claude: bool = False,
                         api_key: Optional[str] = None,
                         headless: bool = False) -> AIBrowserController:
    """
    創建 AI 控制器

    Args:
        use_claude: 是否使用 Claude API
        api_key: API 金鑰
        headless: 是否使用無頭模式

    Returns:
        AIBrowserController 實例
    """
    config = BrowserConfig(headless=headless)
    return AIBrowserController(
        use_claude=use_claude,
        api_key=api_key,
        browser_config=config
    )
