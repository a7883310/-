"""
World Monitor MCP 官方即時情報連接器
連接端點: https://worldmonitor.app/mcp (Streamable HTTP / JSON-RPC 2.0)
支援 65 種全球地緣、航運、供應鏈與總經情報工具
"""

import json
import urllib.request
import ssl
from typing import Dict, Any, Optional
from config import WORLD_MONITOR_API_KEY


class WorldMonitorService:
    """World Monitor MCP 即時全球情報連接器"""

    def __init__(self, api_key: Optional[str] = None):
        self.endpoint = "https://worldmonitor.app/mcp"
        self.api_key = api_key or WORLD_MONITOR_API_KEY
        self.ssl_ctx = ssl.create_default_context()

    def list_available_tools(self) -> Dict[str, Any]:
        """查詢 World Monitor MCP 支援之工具清單 (公開端點)"""
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/list",
            "params": {}
        }
        try:
            req = urllib.request.Request(
                self.endpoint,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"}
            )
            with urllib.request.urlopen(req, timeout=6, context=self.ssl_ctx) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return data.get("result", {})
        except Exception as e:
            return {"error": str(e)}

    def call_intelligence_tool(self, tool_name: str, arguments: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """呼叫 World Monitor 情資工具 (需帶 X-WorldMonitor-Key)"""
        if not self.api_key:
            return {
                "status": "UNAUTHORIZED",
                "error": "未設定 WORLD_MONITOR_API_KEY (請至 https://worldmonitor.app 取得免費金鑰)",
                "tool": tool_name
            }

        payload = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": arguments or {}
            }
        }

        headers = {
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0",
            "X-WorldMonitor-Key": self.api_key,
            "Authorization": f"Bearer {self.api_key}"
        }

        try:
            req = urllib.request.Request(
                self.endpoint,
                data=json.dumps(payload).encode("utf-8"),
                headers=headers
            )
            with urllib.request.urlopen(req, timeout=8, context=self.ssl_ctx) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return {
                    "status": "SUCCESS",
                    "result": data.get("result", {}),
                    "tool": tool_name
                }
        except urllib.error.HTTPError as he:
            if he.code == 401:
                return {
                    "status": "UNAUTHORIZED",
                    "error": "World Monitor API Key 無效或已過期 (HTTP 401 Unauthorized)",
                    "tool": tool_name
                }
            return {"status": "HTTP_ERROR", "code": he.code, "error": str(he), "tool": tool_name}
        except Exception as e:
            return {"status": "ERROR", "error": str(e), "tool": tool_name}
