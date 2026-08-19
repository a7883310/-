import os
import json
import hashlib
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from config import DATA_DIR, get_tw_now_str

WHITELIST_FILE = DATA_DIR / "access_whitelist.json"
DEFAULT_ADMIN_PWD = "a7883310"


def generate_user_token(passcode: str) -> str:
    """計算用戶專屬安全授權 Token (SHA-256)"""
    return hashlib.sha256(f"warroom_token_{passcode}_2026".encode()).hexdigest()[:20]


class AccessWhitelistService:
    """
    全球總經與投資戰情室：外來用戶存取白名單與邀請碼控管中樞
    - 1. 支援多用戶白名單 (姓名、通行碼、角色、授權狀態)
    - 2. 支援一鍵生成專屬免密邀請連結 (?auth=TOKEN)
    - 3. 支援後台隨時新增、停用、廢止任何外來訪客權限
    - 4. 本地與雲端雙向持久化存檔
    """

    def __init__(self):
        self._ensure_whitelist_file()

    def _ensure_whitelist_file(self):
        """確保白名單資料庫存在，預設包含管理員"""
        if not WHITELIST_FILE.exists():
            initial_data = {
                "master_admin_pwd": DEFAULT_ADMIN_PWD,
                "whitelist": [
                    {
                        "id": "admin_master",
                        "name": "站長管理員 (您自己)",
                        "passcode": DEFAULT_ADMIN_PWD,
                        "token": generate_user_token(DEFAULT_ADMIN_PWD),
                        "role": "admin",
                        "created_at": get_tw_now_str("%Y-%m-%d"),
                        "note": "站長最高管理權限",
                        "enabled": True
                    }
                ]
            }
            self._save_raw(initial_data)

    def _load_raw(self) -> Dict[str, Any]:
        try:
            if WHITELIST_FILE.exists():
                with open(WHITELIST_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception:
            pass
        return {
            "master_admin_pwd": DEFAULT_ADMIN_PWD,
            "whitelist": [
                {
                    "id": "admin_master",
                    "name": "站長管理員 (您自己)",
                    "passcode": DEFAULT_ADMIN_PWD,
                    "token": generate_user_token(DEFAULT_ADMIN_PWD),
                    "role": "admin",
                    "created_at": get_tw_now_str("%Y-%m-%d"),
                    "note": "站長最高管理權限",
                    "enabled": True
                }
            ]
        }

    def _save_raw(self, data: Dict[str, Any]) -> bool:
        try:
            with open(WHITELIST_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            print(f"[白名單存檔失敗]: {e}")
            return False

    def get_whitelist(self) -> List[Dict[str, Any]]:
        """獲取所有白名單用戶清單"""
        data = self._load_raw()
        return data.get("whitelist", [])

    def add_user(self, name: str, passcode: str, note: str = "外來授權用戶", role: str = "viewer") -> Tuple[bool, str]:
        """新增一名外來用戶至白名單"""
        data = self._load_raw()
        users = data.get("whitelist", [])

        passcode = passcode.strip()
        name = name.strip()
        if not passcode or not name:
            return False, "用戶姓名與通行碼不得為空！"

        # 檢查通行碼是否重複
        for u in users:
            if u["passcode"] == passcode:
                return False, f"通行碼已被【{u['name']}】使用，請設定其他通行碼！"

        new_user = {
            "id": f"user_{hashlib.md5((name + passcode).encode()).hexdigest()[:8]}",
            "name": name,
            "passcode": passcode,
            "token": generate_user_token(passcode),
            "role": role,
            "created_at": get_tw_now_str("%Y-%m-%d %H:%M"),
            "note": note,
            "enabled": True
        }
        users.append(new_user)
        data["whitelist"] = users
        self._save_raw(data)
        return True, f"成功將【{name}】加入白名單！通行碼為：{passcode}"

    def remove_user(self, user_id: str) -> Tuple[bool, str]:
        """從白名單移除/廢止一名用戶"""
        data = self._load_raw()
        users = data.get("whitelist", [])
        
        # 保護管理員不得被刪除
        if user_id == "admin_master":
            return False, "無法刪除站長管理員帳號！"

        filtered = [u for u in users if u.get("id") != user_id]
        if len(filtered) == len(users):
            return False, "找不到指定的白名單用戶！"

        data["whitelist"] = filtered
        self._save_raw(data)
        return True, "已成功廢止該用戶之存取權限！"

    def toggle_user_status(self, user_id: str, enabled: bool) -> bool:
        """啟用或停用用戶"""
        data = self._load_raw()
        users = data.get("whitelist", [])
        for u in users:
            if u.get("id") == user_id:
                u["enabled"] = enabled
                self._save_raw(data)
                return True
        return False

    def validate_access(self, code_or_token: str) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """
        驗證輸入之通行碼或 URL Token 是否在白名單內
        回傳: (是否通過, 匹配之用戶資料)
        """
        if not code_or_token:
            return False, None

        raw = code_or_token.strip()
        data = self._load_raw()
        users = data.get("whitelist", [])
        master_pwd = str(data.get("master_admin_pwd", DEFAULT_ADMIN_PWD))

        # 1. 站長密鑰比對
        if raw == master_pwd or raw == generate_user_token(master_pwd):
            return True, {
                "id": "admin_master",
                "name": "站長管理員",
                "role": "admin",
                "token": generate_user_token(master_pwd)
            }

        # 2. 白名單逐一比對
        for u in users:
            if not u.get("enabled", True):
                continue
            if raw == u.get("passcode") or raw == u.get("token"):
                return True, u

        return False, None
