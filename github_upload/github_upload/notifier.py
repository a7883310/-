import sys
import subprocess
from typing import Optional
from config import DASHBOARD_URL


def send_desktop_notification(title: str, message: str, app_name: str = "MacroWarRoom", url: Optional[str] = None) -> bool:
    """
    發送系統桌面彈窗推播通知 (支援 Windows 10/11 Toast, macOS, Linux)
    非阻塞式呼叫，確保 Streamlit 介面零延遲
    """
    if url is None:
        url = DASHBOARD_URL

    clean_title = title.replace("🚨", "[警報]").replace("🌐", "").replace("🔔", "").replace("🚀", "").strip()
    clean_msg = message.replace("🚨", "").replace("🚀", "").replace("⚖️", "").replace("👀", "").replace("🛡️", "").replace("【", "[").replace("】", "]").strip()

    # Windows 原生 PowerShell Toast 推播 (最穩定、支援繁體中文)
    if sys.platform.startswith("win"):
        try:
            ps_script = f"""
            [Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] > $null
            $Template = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent([Windows.UI.Notifications.ToastTemplateType]::ToastText02)
            $RawXml = [xml]$Template.GetXml()
            ($RawXml.GetElementsByTagName('text'))[0].AppendChild($RawXml.CreateTextNode('{clean_title}')) > $null
            ($RawXml.GetElementsByTagName('text'))[1].AppendChild($RawXml.CreateTextNode('{clean_msg}')) > $null
            $SerializedXml = New-Object Windows.Data.Xml.Dom.XmlDocument
            $SerializedXml.LoadXml($RawXml.OuterXml)
            $Toast = [Windows.UI.Notifications.ToastNotification]::new($SerializedXml)
            [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier('全球總經戰情室').Show($Toast)
            """
            subprocess.Popen(
                ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps_script],
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform.startswith("win") else 0
            )
            return True
        except Exception as e:
            print(f"[Windows Toast 失敗]: {e}")

    # macOS osascript
    elif sys.platform == "darwin":
        try:
            osa_cmd = f'display notification "{clean_msg}" with title "{clean_title}" subtitle "{app_name}"'
            subprocess.Popen(["osascript", "-e", osa_cmd])
            return True
        except Exception as e:
            print(f"[macOS 推播失敗]: {e}")

    # plyer 備援
    try:
        from plyer import notification
        notification.notify(title=clean_title, message=clean_msg, app_name=app_name, timeout=5)
        return True
    except Exception:
        pass

    return False


if __name__ == "__main__":
    send_desktop_notification(
        title="[測試戰報] 全球總經情報",
        message="評級：BUY (審慎進攻) | 信心分數: 60分。點擊開啟戰情室！"
    )
