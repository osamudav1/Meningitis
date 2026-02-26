"""
နက်ပြ ဘော့တ် - အပြည့်အစုံ (MenuBuilderBot 2026 Features)
Aiogram 3.17 ကိုသုံးထားသည်
"""

import os
import json
import asyncio
import logging
import uuid
import re
import random
import string
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
from collections import defaultdict
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, F
from aiogram.types import (
    Message, CallbackQuery, ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile,
    InputMediaPhoto, InputMediaVideo, InputMediaDocument
)
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties

# Load environment variables
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
OWNER_ID = int(os.getenv("OWNER_ID", "0"))

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize bot and dispatcher
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# ============================
# DATA STRUCTURES (2026 Features)
# ============================

class BotData:
    """ဘော့တ်ဒေတာကို JSON မှာသိမ်းမယ် - 2026 Features အပြည့်"""
    
    def __init__(self, data_file="bot_data.json"):
        self.data_file = data_file
        self.data = self.load_data()
        self.broadcast_queue = asyncio.Queue()
        self.broadcast_active = False
        self.user_stats = defaultdict(lambda: {"messages": 0, "joined": None})
        self.new_users = []
        self.referral_stats = defaultdict(lambda: {"count": 0, "earnings": 0})
    
    def load_data(self) -> Dict:
        """JSON ဖိုင်ကနေဒေတာဖတ်မယ်"""
        if os.path.exists(self.data_file):
            try:
                with open(self.data_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                return self.get_default_data()
        return self.get_default_data()
    
    def save_data(self):
        """ဒေတာကို JSON မှာသိမ်းမယ်"""
        with open(self.data_file, 'w', encoding='utf-8') as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)
    
    def get_default_data(self) -> Dict:
        """မူလဒေတာဖွဲ့စည်းပုံ - 2026 Features"""
        return {
            "version": "2026.1",
            "welcome": {
                "messages": [
                    {
                        "id": "welcome1",
                        "type": "text",
                        "content": "**{mention} ကြိုဆိုပါတယ်** 🎉\n\nအောက်ပါခလုတ်များကို နှိပ်ပြီး သွားရောက်ကြည့်ရှုနိုင်ပါတယ်။",
                        "buttons": [],
                        "conditions": {
                            "subscription": [],
                            "balance": None,
                            "level": None
                        }
                    }
                ],
                "active": "welcome1",
                "random_mode": False
            },
            "buttons": {
                "main": [
                    {"id": "btn1", "name": "📺 2D Anime", "parent": None, "order": 0, "messages": [], "type": "menu", "conditions": {}},
                    {"id": "btn2", "name": "🎬 3D Anime", "parent": None, "order": 1, "messages": [], "type": "menu", "conditions": {}},
                    {"id": "btn3", "name": "🍿 Anime Movies", "parent": None, "order": 2, "messages": [], "type": "menu", "conditions": {}},
                    {"id": "btn4", "name": "📢 Main Channel", "parent": None, "order": 3, "messages": [], "type": "url", "url": "", "conditions": {}},
                    {"id": "btn5", "name": "💬 Fan Chat", "parent": None, "order": 4, "messages": [], "type": "url", "url": "", "conditions": {}},
                    {"id": "btn6", "name": "📞 Contact", "parent": None, "order": 5, "messages": [], "type": "text", "content": "Admin: @admin", "conditions": {}}
                ],
                "submenus": {},
                "all_buttons": {},
                "types": ["menu", "url", "text", "command", "share", "random", "admin", "back", "cancel"]
            },
            "users": [],
            "settings": {
                "new_user_notification": True,
                "notification_chat_id": OWNER_ID,
                "timezone": "Asia/Yangon",
                "language": "my",
                "captcha": False,
                "subscription_check": [],
                "bonus_enabled": False,
                "bonus_amount": 0,
                "referral_enabled": False,
                "referral_bonus": 0,
                "currency": "MMK",
                "payment_methods": ["telegram_stars", "usdt"]
            },
            "statistics": {
                "total_messages": 0,
                "total_buttons_click": 0,
                "daily_users": [],
                "hourly_stats": {}
            },
            "backup": {
                "last_backup": None,
                "auto_backup": False,
                "backup_interval": 24  # hours
            }
        }
    
    # ===== 2026 New Features =====
    
    # 1. Random Message Mode
    def set_random_mode(self, enabled: bool):
        """Random message mode ဖွင့်/ပိတ်"""
        self.data["welcome"]["random_mode"] = enabled
        self.save_data()
    
    def get_random_mode(self) -> bool:
        return self.data["welcome"]["random_mode"]
    
    # 2. Button Conditions
    def set_button_condition(self, btn_id: str, condition_type: str, value: Any):
        """ခလုတ်အတွက် Condition သတ်မှတ်မယ်"""
        btn = self.get_button(btn_id)
        if btn:
            if "conditions" not in btn:
                btn["conditions"] = {}
            btn["conditions"][condition_type] = value
            self.save_data()
            return True
        return False
    
    def check_button_condition(self, btn_id: str, user_id: int) -> bool:
        """ခလုတ် Condition စစ်ဆေးမယ်"""
        btn = self.get_button(btn_id)
        if not btn or not btn.get("conditions"):
            return True
        
        conditions = btn["conditions"]
        
        # Subscription check
        if "subscription" in conditions:
            # TODO: Check if user joined channels/groups
            pass
        
        # Balance check
        if "balance" in conditions:
            user_balance = self.get_user_balance(user_id)
            if user_balance < conditions["balance"]:
                return False
        
        # Level check
        if "level" in conditions:
            user_level = self.get_user_level(user_id)
            if user_level < conditions["level"]:
                return False
        
        return True
    
    # 3. Button Types
    def get_button_type(self, btn_id: str) -> str:
        """ခလုတ်အမျိုးအစားရယူမယ်"""
        btn = self.get_button(btn_id)
        return btn.get("type", "menu") if btn else "menu"
    
    def set_button_type(self, btn_id: str, btn_type: str, **kwargs):
        """ခလုတ်အမျိုးအစားသတ်မှတ်မယ်"""
        btn = self.get_button(btn_id)
        if btn and btn_type in self.data["buttons"]["types"]:
            btn["type"] = btn_type
            if btn_type == "url":
                btn["url"] = kwargs.get("url", "")
            elif btn_type == "command":
                btn["command"] = kwargs.get("command", "")
            elif btn_type == "text":
                btn["content"] = kwargs.get("content", "")
            elif btn_type == "admin":
                btn["admin_only"] = True
            self.save_data()
            return True
        return False
    
    # 4. Subscription Check
    def set_subscription_check(self, channels: List[str]):
        """Subscription check သတ်မှတ်မယ်"""
        self.data["settings"]["subscription_check"] = channels
        self.save_data()
    
    def check_subscription(self, user_id: int) -> Tuple[bool, List[str]]:
        """User က Channel/Group တွေမှာရှိလားစစ်မယ်"""
        not_joined = []
        channels = self.data["settings"]["subscription_check"]
        
        # TODO: Implement actual subscription check
        # This requires bot to be admin in those channels/groups
        
        return len(not_joined) == 0, not_joined
    
    # 5. Captcha
    def set_captcha(self, enabled: bool):
        """Captcha ဖွင့်/ပိတ်"""
        self.data["settings"]["captcha"] = enabled
        self.save_data()
    
    def generate_captcha(self) -> Tuple[str, str]:
        """Captcha ထုတ်မယ်"""
        captcha_text = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
        captcha_id = str(uuid.uuid4())[:8]
        return captcha_id, captcha_text
    
    # 6. Bonus System
    def set_bonus(self, enabled: bool, amount: int = 0):
        """Bonus system သတ်မှတ်မယ်"""
        self.data["settings"]["bonus_enabled"] = enabled
        self.data["settings"]["bonus_amount"] = amount
        self.save_data()
    
    def claim_bonus(self, user_id: int) -> bool:
        """Bonus ယူမယ်"""
        last_claim = self.user_stats[user_id].get("last_bonus")
        if last_claim:
            if datetime.now() - datetime.fromisoformat(last_claim) < timedelta(hours=24):
                return False
        
        self.user_stats[user_id]["last_bonus"] = datetime.now().isoformat()
        self.user_stats[user_id]["balance"] = self.user_stats[user_id].get("balance", 0) + self.data["settings"]["bonus_amount"]
        return True
    
    # 7. Referral System
    def set_referral(self, enabled: bool, bonus: int = 0):
        """Referral system သတ်မှတ်မယ်"""
        self.data["settings"]["referral_enabled"] = enabled
        self.data["settings"]["referral_bonus"] = bonus
        self.save_data()
    
    def add_referral(self, user_id: int, referrer_id: int):
        """Referral ထည့်မယ်"""
        self.referral_stats[referrer_id]["count"] += 1
        self.referral_stats[referrer_id]["earnings"] += self.data["settings"]["referral_bonus"]
        self.user_stats[referrer_id]["balance"] = self.user_stats[referrer_id].get("balance", 0) + self.data["settings"]["referral_bonus"]
    
    # 8. Navigation Buttons
    def add_navigation_buttons(self, btn_id: str, back_btn: bool = True, home_btn: bool = True):
        """Navigation buttons ထည့်မယ် (Back, Home)"""
        btn = self.get_button(btn_id)
        if btn:
            btn["navigation"] = {
                "back": back_btn,
                "home": home_btn
            }
            self.save_data()
    
    # 9. Payment Integration (Telegram Stars)
    def get_user_balance(self, user_id: int) -> int:
        """User balance ရယူမယ်"""
        return self.user_stats[user_id].get("balance", 0)
    
    def add_balance(self, user_id: int, amount: int):
        """Balance ထည့်မယ်"""
        self.user_stats[user_id]["balance"] = self.get_user_balance(user_id) + amount
    
    def withdraw_balance(self, user_id: int, amount: int, method: str) -> bool:
        """Balance ထုတ်မယ်"""
        if self.get_user_balance(user_id) >= amount:
            self.user_stats[user_id]["balance"] -= amount
            # TODO: Process withdrawal
            return True
        return False
    
    # 10. User Levels
    def get_user_level(self, user_id: int) -> int:
        """User level ရယူမယ်"""
        messages = self.user_stats[user_id].get("messages", 0)
        if messages < 10:
            return 1
        elif messages < 50:
            return 2
        elif messages < 100:
            return 3
        elif messages < 500:
            return 4
        else:
            return 5
    
    # 11. Data Export
    def export_data(self, format: str = "json") -> Dict:
        """ဒေတာ Export လုပ်မယ်"""
        if format == "json":
            return self.data
        elif format == "csv":
            # TODO: Convert to CSV
            pass
        return {}
    
    def import_data(self, data: Dict):
        """ဒေတာ Import လုပ်မယ်"""
        self.data = data
        self.save_data()
    
    # 12. Backup
    def create_backup(self) -> str:
        """Backup ဖန်တီးမယ်"""
        backup_id = str(uuid.uuid4())[:8]
        backup_data = {
            "id": backup_id,
            "created_at": datetime.now().isoformat(),
            "data": self.data
        }
        
        # Save backup to file
        with open(f"backup_{backup_id}.json", 'w', encoding='utf-8') as f:
            json.dump(backup_data, f, ensure_ascii=False, indent=2)
        
        self.data["backup"]["last_backup"] = datetime.now().isoformat()
        self.save_data()
        return backup_id
    
    def restore_backup(self, backup_id: str) -> bool:
        """Backup ကို Restore လုပ်မယ်"""
        try:
            with open(f"backup_{backup_id}.json", 'r', encoding='utf-8') as f:
                backup = json.load(f)
            self.data = backup["data"]
            self.save_data()
            return True
        except:
            return False
    
    # 13. Statistics Tracking
    def track_message(self, user_id: int):
        """Message statistics မှတ်မယ်"""
        self.user_stats[user_id]["messages"] = self.user_stats[user_id].get("messages", 0) + 1
        self.data["statistics"]["total_messages"] += 1
        
        # Daily stats
        today = datetime.now().strftime("%Y-%m-%d")
        if today not in self.data["statistics"]["daily_users"]:
            self.data["statistics"]["daily_users"].append(today)
    
    def track_button_click(self, btn_id: str):
        """Button click statistics မှတ်မယ်"""
        self.data["statistics"]["total_buttons_click"] += 1
    
    # 14. Multi-language
    def set_language(self, lang: str):
        """ဘာသာစကားသတ်မှတ်မယ်"""
        self.data["settings"]["language"] = lang
        self.save_data()
    
    def get_text(self, key: str, lang: str = None) -> str:
        """ဘာသာပြန်စာသားရယူမယ်"""
        if lang is None:
            lang = self.data["settings"]["language"]
        
        # TODO: Load translations from file
        translations = {
            "my": {
                "welcome": "ကြိုဆိုပါတယ်",
                "menu": "မီနူး",
                "back": "နောက်သို့",
                "cancel": "ပယ်ဖျက်ရန်"
            },
            "en": {
                "welcome": "Welcome",
                "menu": "Menu",
                "back": "Back",
                "cancel": "Cancel"
            }
        }
        
        return translations.get(lang, {}).get(key, key)
    
    # ===== Original Methods (Updated) =====
    
    def add_user(self, user_id: int, username: str = None, first_name: str = None, last_name: str = None):
        """အသုံးပြုသူအသစ်ထည့်မယ်"""
        is_new = False
        if user_id not in [u["id"] for u in self.data["users"]]:
            self.data["users"].append({
                "id": user_id,
                "username": username,
                "first_name": first_name,
                "last_name": last_name,
                "full_name": f"{first_name or ''} {last_name or ''}".strip(),
                "joined_at": datetime.now().isoformat(),
                "balance": 0,
                "level": 1,
                "referrals": 0,
                "last_active": datetime.now().isoformat()
            })
            self.save_data()
            is_new = True
        
        return self.get_user_info(user_id), is_new
    
    def get_user_info(self, user_id: int) -> Dict:
        """အသုံးပြုသူအချက်အလက်ရယူမယ်"""
        for user in self.data["users"]:
            if user["id"] == user_id:
                return user
        return {
            "id": user_id,
            "username": None,
            "first_name": None,
            "last_name": None,
            "full_name": None,
            "balance": 0,
            "level": 1
        }
    
    def get_all_users(self) -> List[int]:
        return [u["id"] for u in self.data["users"]]
    
    def get_users_count(self) -> int:
        return len(self.data["users"])
    
    # Welcome Messages
    def get_welcome_messages(self) -> List[Dict]:
        return self.data["welcome"]["messages"]
    
    def get_active_welcome(self) -> Dict:
        active_id = self.data["welcome"]["active"]
        if self.data["welcome"]["random_mode"]:
            return random.choice(self.data["welcome"]["messages"])
        for msg in self.data["welcome"]["messages"]:
            if msg["id"] == active_id:
                return msg
        return self.data["welcome"]["messages"][0]
    
    def add_welcome_message(self, msg_type: str, content: Any, buttons: List = None, conditions: Dict = None) -> Dict:
        msg_id = str(uuid.uuid4())[:8]
        message = {
            "id": msg_id,
            "type": msg_type,
            "content": content,
            "buttons": buttons or [],
            "conditions": conditions or {},
            "created_at": datetime.now().isoformat()
        }
        self.data["welcome"]["messages"].append(message)
        self.save_data()
        return message
    
    def update_welcome_message(self, msg_id: str, updates: Dict):
        for i, msg in enumerate(self.data["welcome"]["messages"]):
            if msg["id"] == msg_id:
                self.data["welcome"]["messages"][i].update(updates)
                self.save_data()
                return True
        return False
    
    def delete_welcome_message(self, msg_id: str):
        self.data["welcome"]["messages"] = [msg for msg in self.data["welcome"]["messages"] if msg["id"] != msg_id]
        if self.data["welcome"]["active"] == msg_id:
            if self.data["welcome"]["messages"]:
                self.data["welcome"]["active"] = self.data["welcome"]["messages"][0]["id"]
            else:
                default = self.add_welcome_message("text", "**{mention} ကြိုဆိုပါတယ်** 🎉", [])
                self.data["welcome"]["active"] = default["id"]
        self.save_data()
    
    def set_active_welcome(self, msg_id: str):
        self.data["welcome"]["active"] = msg_id
        self.save_data()
    
    # Button Management
    def get_main_buttons(self) -> List[Dict]:
        buttons = self.data["buttons"]["main"]
        return sorted(buttons, key=lambda x: x.get("order", 0))
    
    def get_sub_buttons(self, parent_id: str) -> List[Dict]:
        return self.data["buttons"]["submenus"].get(parent_id, [])
    
    def get_all_buttons(self) -> List[Dict]:
        all_buttons = []
        all_buttons.extend(self.data["buttons"]["main"])
        for parent, buttons in self.data["buttons"]["submenus"].items():
            all_buttons.extend(buttons)
        return all_buttons
    
    def get_button(self, btn_id: str) -> Optional[Dict]:
        if btn_id in self.data["buttons"]["all_buttons"]:
            return self.data["buttons"]["all_buttons"][btn_id]
        
        for btn in self.data["buttons"]["main"]:
            if btn["id"] == btn_id:
                self.data["buttons"]["all_buttons"][btn_id] = btn
                return btn
        
        for parent, buttons in self.data["buttons"]["submenus"].items():
            for btn in buttons:
                if btn["id"] == btn_id:
                    self.data["buttons"]["all_buttons"][btn_id] = btn
                    return btn
        return None
    
    def add_button(self, name: str, parent: str = None, btn_type: str = "menu", **kwargs) -> Dict:
        btn_id = str(uuid.uuid4())[:8]
        
        new_button = {
            "id": btn_id,
            "name": name,
            "parent": parent,
            "order": len(self.data["buttons"]["main"]) if parent is None else len(self.data["buttons"]["submenus"].get(parent, [])),
            "messages": [],
            "type": btn_type,
            "conditions": {}
        }
        
        if btn_type == "url":
            new_button["url"] = kwargs.get("url", "")
        elif btn_type == "command":
            new_button["command"] = kwargs.get("command", "")
        elif btn_type == "text":
            new_button["content"] = kwargs.get("content", "")
        elif btn_type == "admin":
            new_button["admin_only"] = True
        
        if parent is None:
            self.data["buttons"]["main"].append(new_button)
        else:
            if parent not in self.data["buttons"]["submenus"]:
                self.data["buttons"]["submenus"][parent] = []
            self.data["buttons"]["submenus"][parent].append(new_button)
        
        self.data["buttons"]["all_buttons"][btn_id] = new_button
        self.save_data()
        return new_button
    
    def rename_button(self, btn_id: str, new_name: str) -> bool:
        for btn in self.data["buttons"]["main"]:
            if btn["id"] == btn_id:
                btn["name"] = new_name
                self.save_data()
                return True
        
        for parent, buttons in self.data["buttons"]["submenus"].items():
            for btn in buttons:
                if btn["id"] == btn_id:
                    btn["name"] = new_name
                    self.save_data()
                    return True
        return False
    
    def delete_button(self, btn_id: str):
        self.data["buttons"]["main"] = [btn for btn in self.data["buttons"]["main"] if btn["id"] != btn_id]
        
        for parent in list(self.data["buttons"]["submenus"].keys()):
            self.data["buttons"]["submenus"][parent] = [btn for btn in self.data["buttons"]["submenus"][parent] if btn["id"] != btn_id]
            if not self.data["buttons"]["submenus"][parent]:
                del self.data["buttons"]["submenus"][parent]
        
        if btn_id in self.data["buttons"]["all_buttons"]:
            del self.data["buttons"]["all_buttons"][btn_id]
        
        self.save_data()
    
    def move_button(self, btn_id: str, direction: str) -> bool:
        # Main menu
        for i, btn in enumerate(self.data["buttons"]["main"]):
            if btn["id"] == btn_id:
                if direction == "⬆️" and i > 0:
                    self.data["buttons"]["main"][i]["order"], self.data["buttons"]["main"][i-1]["order"] = \
                        self.data["buttons"]["main"][i-1]["order"], self.data["buttons"]["main"][i]["order"]
                    self.data["buttons"]["main"][i], self.data["buttons"]["main"][i-1] = \
                        self.data["buttons"]["main"][i-1], self.data["buttons"]["main"][i]
                elif direction == "⬇️" and i < len(self.data["buttons"]["main"]) - 1:
                    self.data["buttons"]["main"][i]["order"], self.data["buttons"]["main"][i+1]["order"] = \
                        self.data["buttons"]["main"][i+1]["order"], self.data["buttons"]["main"][i]["order"]
                    self.data["buttons"]["main"][i], self.data["buttons"]["main"][i+1] = \
                        self.data["buttons"]["main"][i+1], self.data["buttons"]["main"][i]
                self.save_data()
                return True
        
        # Submenu
        for parent, buttons in self.data["buttons"]["submenus"].items():
            for i, btn in enumerate(buttons):
                if btn["id"] == btn_id:
                    if direction == "⬆️" and i > 0:
                        buttons[i], buttons[i-1] = buttons[i-1], buttons[i]
                    elif direction == "⬇️" and i < len(buttons) - 1:
                        buttons[i], buttons[i+1] = buttons[i+1], buttons[i]
                    elif direction == "⬅️":
                        btn["parent"] = None
                        btn["order"] = len(self.data["buttons"]["main"])
                        self.data["buttons"]["main"].append(btn)
                        buttons.pop(i)
                    self.save_data()
                    return True
        return False
    
    # Message Management
    def add_message_to_button(self, btn_id: str, msg_type: str, content: Any, buttons: List = None, conditions: Dict = None) -> Optional[Dict]:
        btn = self.get_button(btn_id)
        if btn:
            msg_id = str(uuid.uuid4())[:8]
            message = {
                "id": msg_id,
                "type": msg_type,
                "content": content,
                "buttons": buttons or [],
                "conditions": conditions or {},
                "created_at": datetime.now().isoformat()
            }
            if "messages" not in btn:
                btn["messages"] = []
            btn["messages"].append(message)
            self.data["buttons"]["all_buttons"][btn_id] = btn
            self.save_data()
            return message
        return None
    
    def get_button_messages(self, btn_id: str) -> List[Dict]:
        btn = self.get_button(btn_id)
        return btn.get("messages", []) if btn else []
    
    def update_button_message(self, btn_id: str, msg_id: str, updates: Dict) -> bool:
        btn = self.get_button(btn_id)
        if btn and "messages" in btn:
            for i, msg in enumerate(btn["messages"]):
                if msg["id"] == msg_id:
                    btn["messages"][i].update(updates)
                    self.save_data()
                    return True
        return False
    
    def delete_button_message(self, btn_id: str, msg_id: str) -> bool:
        btn = self.get_button(btn_id)
        if btn and "messages" in btn:
            btn["messages"] = [msg for msg in btn["messages"] if msg["id"] != msg_id]
            self.save_data()
            return True
        return False

# Initialize bot data
bot_data = BotData()

# ============================
# FORMATTER FUNCTIONS
# ============================

def format_user_text(text: str, user, user_info: Dict = None) -> str:
    """စာသားကို format လုပ်မယ် (2026 Macros)"""
    if user_info is None:
        user_info = bot_data.get_user_info(user.id)
    
    full_name = user_info.get("full_name", "") or f"{user.first_name or ''} {user.last_name or ''}".strip()
    
    # 2026 Macros အသစ်များ
    replacements = {
        # Basic
        "{mention}": user.first_name or "User",
        "{fullname}": full_name,
        "{first_name}": user.first_name or "",
        "{last_name}": user.last_name or "",
        "{username}": f"@{user.username}" if user.username else "",
        "{user_id}": str(user.id),
        
        # Date & Time
        "{date}": datetime.now().strftime("%Y-%m-%d"),
        "{time}": datetime.now().strftime("%H:%M:%S"),
        "{datetime}": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "{day}": datetime.now().strftime("%A"),
        "{month}": datetime.now().strftime("%B"),
        "{year}": datetime.now().strftime("%Y"),
        
        # User Stats
        "{balance}": str(user_info.get("balance", 0)),
        "{level}": str(bot_data.get_user_level(user.id)),
        "{messages}": str(bot_data.user_stats[user.id].get("messages", 0)),
        "{referrals}": str(bot_data.referral_stats[user.id].get("count", 0)),
        
        # Random
        "{random}": str(random.randint(1, 100)),
        "{random_id}": str(uuid.uuid4())[:8],
        
        # Bot Info
        "{total_users}": str(bot_data.get_users_count()),
        "{total_buttons}": str(len(bot_data.get_all_buttons())),
        "{version}": bot_data.data["version"]
    }
    
    for key, value in replacements.items():
        text = text.replace(key, value)
    
    return text

def create_inline_keyboard(buttons: List[Dict]) -> Optional[InlineKeyboardMarkup]:
    """Inline keyboard ဖန်တီးမယ်"""
    if not buttons:
        return None
    
    inline_buttons = []
    for btn in buttons:
        if "url" in btn:
            inline_buttons.append([InlineKeyboardButton(text=btn["text"], url=btn["url"])])
        elif "callback" in btn:
            inline_buttons.append([InlineKeyboardButton(text=btn["text"], callback_data=btn["callback"])])
        elif "switch_inline_query" in btn:
            inline_buttons.append([InlineKeyboardButton(text=btn["text"], switch_inline_query=btn.get("query", ""))])
        elif "switch_inline_query_current_chat" in btn:
            inline_buttons.append([InlineKeyboardButton(text=btn["text"], switch_inline_query_current_chat=btn.get("query", ""))])
        elif "pay" in btn:
            inline_buttons.append([InlineKeyboardButton(text=btn["text"], pay=True)])
        else:
            inline_buttons.append([InlineKeyboardButton(text=btn["text"], callback_data="none")])
    
    return InlineKeyboardMarkup(inline_keyboard=inline_buttons)

def parse_buttons_text(buttons_text: str) -> List[Dict]:
    """Button တွေကို parse လုပ်မယ် (2026 Format)"""
    buttons = []
    if not buttons_text or buttons_text.lower() == "skip":
        return buttons
    
    # Support for multiple formats
    # 1. Button|url
    # 2. Button|callback:data
    # 3. Button|switch:query
    # 4. Button (simple callback)
    
    parts = buttons_text.split(",")
    for part in parts:
        part = part.strip()
        if not part:
            continue
        
        if "|" in part:
            name, value = part.split("|", 1)
            name = name.strip()
            value = value.strip()
            
            if value.startswith("http"):
                buttons.append({"text": name, "url": value})
            elif value.startswith("callback:"):
                buttons.append({"text": name, "callback": value[9:]})
            elif value.startswith("switch:"):
                buttons.append({"text": name, "switch_inline_query": value[7:]})
            elif value.startswith("chat:"):
                buttons.append({"text": name, "switch_inline_query_current_chat": value[5:]})
            elif value == "pay":
                buttons.append({"text": name, "pay": True})
            else:
                buttons.append({"text": name, "callback": value})
        else:
            buttons.append({"text": part, "callback": "none"})
    
    return buttons

# ============================
# KEYBOARD BUILDERS (2026)
# ============================

def get_main_menu_keyboard(user_id: int = None):
    """ပင်မမီနူးခလုတ်များ"""
    buttons = []
    
    # Main menu buttons from data
    main_buttons = bot_data.get_main_buttons()
    row = []
    for i, btn in enumerate(main_buttons):
        # Check conditions
        if user_id and not bot_data.check_button_condition(btn["id"], user_id):
            continue
        
        # Admin only check
        if btn.get("type") == "admin" and user_id != OWNER_ID:
            continue
        
        row.append(KeyboardButton(text=btn["name"]))
        if (i + 1) % 2 == 0:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    
    # Navigation buttons
    nav_row = []
    if bot_data.data["settings"]["language"] == "my":
        nav_row.append(KeyboardButton(text="🔙 နောက်သို့"))
        nav_row.append(KeyboardButton(text="🏠 ပင်မ"))
    else:
        nav_row.append(KeyboardButton(text="🔙 Back"))
        nav_row.append(KeyboardButton(text="🏠 Home"))
    buttons.append(nav_row)
    
    # Admin buttons for owner
    if user_id and user_id == OWNER_ID:
        buttons.append([KeyboardButton(text="⚙️ Admin Panel")])
    
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

def get_admin_keyboard():
    """အက်မင်မီနူးခလုတ်များ - 2026 Features"""
    buttons = [
        [KeyboardButton(text="🔧 Button Editor")],
        [KeyboardButton(text="📝 Post Editor")],
        [KeyboardButton(text="👋 Welcome Editor")],
        [KeyboardButton(text="📢 Broadcast")],
        [KeyboardButton(text="📊 Statistics")],
        [KeyboardButton(text="⚙️ Settings")],
        [KeyboardButton(text="💰 Payments")],
        [KeyboardButton(text="👥 Users")],
        [KeyboardButton(text="🔐 Subscription Check")],
        [KeyboardButton(text="🎁 Bonus System")],
        [KeyboardButton(text="🤝 Referrals")],
        [KeyboardButton(text="📦 Backup/Restore")],
        [KeyboardButton(text="🌐 Language")],
        [KeyboardButton(text="🏠 Main Menu")]
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

def get_button_editor_keyboard():
    """ခလုတ်တည်းဖြတ်ခန်းမီနူး - 2026"""
    buttons = [
        [KeyboardButton(text="➕ Add Button")],
        [KeyboardButton(text="✏️ Rename Button")],
        [KeyboardButton(text="🗑 Delete Button")],
        [KeyboardButton(text="📂 Enter Button")],
        [KeyboardButton(text="⬆️ ⬇️ Move Button")],
        [KeyboardButton(text="🔧 Set Button Type")],
        [KeyboardButton(text="🔐 Set Conditions")],
        [KeyboardButton(text="🏠 Main Menu")]
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

def get_button_type_keyboard():
    """ခလုတ်အမျိုးအစားရွေးရန်"""
    buttons = [
        [KeyboardButton(text="📋 Menu Button")],
        [KeyboardButton(text="🔗 URL Button")],
        [KeyboardButton(text="📝 Text Button")],
        [KeyboardButton(text="🔄 Command Button")],
        [KeyboardButton(text="📤 Share Button")],
        [KeyboardButton(text="🎲 Random Button")],
        [KeyboardButton(text="👤 Admin Only")],
        [KeyboardButton(text="🔙 Back")]
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

def get_conditions_keyboard():
    """Condition သတ်မှတ်ရန်ကီးဘုတ်"""
    buttons = [
        [KeyboardButton(text="🔐 Subscription Check")],
        [KeyboardButton(text="💰 Balance Check")],
        [KeyboardButton(text="📊 Level Check")],
        [KeyboardButton(text="✅ Clear Conditions")],
        [KeyboardButton(text="🔙 Back")]
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

def get_settings_keyboard():
    """ဆက်တင်မီနူး"""
    settings = bot_data.data["settings"]
    buttons = [
        [KeyboardButton(text=f"🔄 New User Notification: {'✅' if settings['new_user_notification'] else '❌'}")],
        [KeyboardButton(text=f"🎲 Random Welcome: {'✅' if settings.get('random_welcome', False) else '❌'}")],
        [KeyboardButton(text=f"🔐 Captcha: {'✅' if settings['captcha'] else '❌'}")],
        [KeyboardButton(text=f"🎁 Bonus: {'✅' if settings['bonus_enabled'] else '❌'}")],
        [KeyboardButton(text=f"🤝 Referrals: {'✅' if settings['referral_enabled'] else '❌'}")],
        [KeyboardButton(text="🌐 Change Language")],
        [KeyboardButton(text="⏰ Set Timezone")],
        [KeyboardButton(text="🔙 Back")]
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

def get_payment_keyboard():
    """ငွေပေးချေမှုမီနူး"""
    buttons = [
        [KeyboardButton(text="⭐ Telegram Stars")],
        [KeyboardButton(text="💎 USDT (TRC20)")],
        [KeyboardButton(text="💳 Withdraw")],
        [KeyboardButton(text="📊 Balance")],
        [KeyboardButton(text="🔙 Back")]
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

def get_backup_keyboard():
    """Backup/Restore မီနူး"""
    buttons = [
        [KeyboardButton(text="📦 Create Backup")],
        [KeyboardButton(text="📂 Restore Backup")],
        [KeyboardButton(text="📋 List Backups")],
        [KeyboardButton(text="⚙️ Auto Backup Settings")],
        [KeyboardButton(text="🔙 Back")]
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

def get_language_keyboard():
    """ဘာသာစကားရွေးရန်ကီးဘုတ်"""
    buttons = [
        [KeyboardButton(text="🇲🇲 မြန်မာ")],
        [KeyboardButton(text="🇬🇧 English")],
        [KeyboardButton(text="🇹🇭 ไทย")],
        [KeyboardButton(text="🇱🇦 ລາວ")],
        [KeyboardButton(text="🇨🇳 中文")],
        [KeyboardButton(text="🇯🇵 日本語")],
        [KeyboardButton(text="🇰🇷 한국어")],
        [KeyboardButton(text="🔙 Back")]
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

def get_move_buttons_keyboard():
    """နေရာရွှေ့ရန်ခလုတ်များ"""
    buttons = [
        [KeyboardButton(text="⬆️ Up"), KeyboardButton(text="⬇️ Down")],
        [KeyboardButton(text="⬅️ Out (to Main)"), KeyboardButton(text="➡️ Into (submenu)")],
        [KeyboardButton(text="🔙 Back")]
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

def get_message_editor_keyboard(btn_id: str = None):
    """Message တည်းဖြတ်ခန်းမီနူး"""
    buttons = [
        [KeyboardButton(text="📝 Add Text Message")],
        [KeyboardButton(text="🖼 Add Photo Message")],
        [KeyboardButton(text="🎥 Add Video Message")],
        [KeyboardButton(text="📎 Add Document Message")],
    ]
    
    if btn_id:
        messages = bot_data.get_button_messages(btn_id)
        if messages:
            buttons.append([KeyboardButton(text="📋 View Messages")])
            buttons.append([KeyboardButton(text="✏️ Edit Message")])
            buttons.append([KeyboardButton(text="🗑 Delete Message")])
            buttons.append([KeyboardButton(text="🎲 Random Message Mode")])
    
    buttons.append([KeyboardButton(text="🔙 Back")])
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

def get_welcome_editor_keyboard():
    """Welcome message တည်းဖြတ်ခန်းမီနူး"""
    buttons = [
        [KeyboardButton(text="➕ Add Welcome")],
        [KeyboardButton(text="📋 View Welcomes")],
        [KeyboardButton(text="✏️ Edit Welcome")],
        [KeyboardButton(text="🗑 Delete Welcome")],
        [KeyboardButton(text="✅ Set Active")],
        [KeyboardButton(text="🎲 Random Mode")],
        [KeyboardButton(text="🔙 Back")]
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

def get_buttons_list_keyboard(buttons_list: List[Dict], back_text: str = "🔙 Back", show_numbers: bool = False):
    """ခလုတ်စာရင်းကို ကီးဘုတ်အဖြစ်ပြမယ်"""
    keyboard = []
    row = []
    for i, btn in enumerate(buttons_list):
        text = btn["name"]
        if btn.get("type") == "admin":
            text = "👤 " + text
        if show_numbers:
            text = f"{i+1}. {text}"
        row.append(KeyboardButton(text=text))
        if (i + 1) % 2 == 0:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    keyboard.append([KeyboardButton(text=back_text)])
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

def get_media_type_keyboard():
    """မီဒီယာအမျိုးအစားရွေးရန်"""
    buttons = [
        [KeyboardButton(text="📝 Text")],
        [KeyboardButton(text="🖼 Photo")],
        [KeyboardButton(text="🎥 Video")],
        [KeyboardButton(text="📎 Document")],
        [KeyboardButton(text="🔙 Back")]
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

def get_broadcast_keyboard():
    """Broadcast မီနူး"""
    buttons = [
        [KeyboardButton(text="📝 Send Text")],
        [KeyboardButton(text="🖼 Send Photo")],
        [KeyboardButton(text="🎥 Send Video")],
        [KeyboardButton(text="📎 Send Document")],
        [KeyboardButton(text="🔙 Back")]
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

def get_confirmation_keyboard():
    """အတည်ပြုရန်ခလုတ်များ"""
    buttons = [
        [KeyboardButton(text="✅ Confirm"), KeyboardButton(text="❌ Cancel")]
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

# ============================
# BROADCAST FUNCTION
# ============================

async def send_broadcast(
    message_type: str,
    content: Any,
    buttons: List = None,
    delay: float = 1.0,
    chunk_size: int = 20
):
    """Broadcast ပို့မယ် (spam မဖြစ်အောင် delay ခံမယ်)"""
    users = bot_data.get_all_users()
    total = len(users)
    sent = 0
    failed = 0
    
    bot_data.broadcast_active = True
    
    for i, user_id in enumerate(users):
        if not bot_data.broadcast_active:
            break
        
        try:
            if message_type == "text":
                await bot.send_message(
                    user_id,
                    content,
                    reply_markup=create_inline_keyboard(buttons) if buttons else None
                )
            elif message_type == "photo":
                await bot.send_photo(
                    user_id,
                    photo=content["file_id"],
                    caption=content.get("caption", ""),
                    reply_markup=create_inline_keyboard(buttons) if buttons else None
                )
            elif message_type == "video":
                await bot.send_video(
                    user_id,
                    video=content["file_id"],
                    caption=content.get("caption", ""),
                    reply_markup=create_inline_keyboard(buttons) if buttons else None
                )
            elif message_type == "document":
                await bot.send_document(
                    user_id,
                    document=content["file_id"],
                    caption=content.get("caption", ""),
                    reply_markup=create_inline_keyboard(buttons) if buttons else None
                )
            sent += 1
            
            # Track statistics
            bot_data.track_message(user_id)
            
            # Rate limiting
            if (i + 1) % chunk_size == 0:
                await asyncio.sleep(delay)
                
        except Exception as e:
            logger.error(f"Failed to send to {user_id}: {e}")
            failed += 1
    
    bot_data.broadcast_active = False
    return sent, failed, total

# ============================
# STATES
# ============================

class BotStates(StatesGroup):
    """ဘော့တ် State များ - 2026"""
    # Welcome message states
    waiting_welcome_type = State()
    waiting_welcome_text = State()
    waiting_welcome_photo = State()
    waiting_welcome_video = State()
    waiting_welcome_document = State()
    waiting_welcome_buttons = State()
    waiting_welcome_select = State()
    waiting_welcome_edit = State()
    waiting_welcome_delete = State()
    waiting_welcome_set_active = State()
    waiting_welcome_conditions = State()
    
    # Button editor states
    waiting_button_name = State()
    waiting_button_rename_select = State()
    waiting_button_rename = State()
    waiting_button_delete_select = State()
    waiting_button_enter_select = State()
    waiting_button_move_select = State()
    waiting_button_move_direction = State()
    waiting_button_move_target = State()
    waiting_parent_select = State()
    waiting_button_type = State()
    waiting_button_url = State()
    waiting_button_command = State()
    waiting_button_text = State()
    waiting_button_conditions = State()
    waiting_condition_value = State()
    
    # Message editor states
    waiting_message_type = State()
    waiting_message_text = State()
    waiting_message_photo = State()
    waiting_message_video = State()
    waiting_message_document = State()
    waiting_message_buttons = State()
    waiting_message_select = State()
    waiting_message_edit_select = State()
    waiting_message_edit_text = State()
    waiting_message_delete_select = State()
    waiting_message_conditions = State()
    
    # Broadcast states
    waiting_broadcast_type = State()
    waiting_broadcast_text = State()
    waiting_broadcast_photo = State()
    waiting_broadcast_video = State()
    waiting_broadcast_document = State()
    waiting_broadcast_buttons = State()
    waiting_broadcast_confirm = State()
    
    # Payment states
    waiting_payment_amount = State()
    waiting_withdraw_amount = State()
    waiting_withdraw_address = State()
    
    # Settings states
    waiting_timezone = State()
    waiting_captcha_text = State()
    waiting_bonus_amount = State()
    waiting_referral_bonus = State()
    waiting_subscription_channel = State()

# ============================
# HANDLERS - START & WELCOME
# ============================

@dp.message(CommandStart())
async def cmd_start(message: Message):
    """Start command handler - 2026 Version"""
    user = message.from_user
    user_id = user.id
    
    # Track start
    bot_data.track_message(user_id)
    
    # Add user to database and check if new
    user_info, is_new = bot_data.add_user(
        user_id, 
        user.username, 
        user.first_name, 
        user.last_name
    )
    
    # Send new user notification to owner
    if is_new and bot_data.data["settings"]["new_user_notification"]:
        try:
            total_users = bot_data.get_users_count()
            notification = (
                f"**👤 အသုံးပြုသူအသစ်**\n\n"
                f"**User:** {format_user_text('{fullname}', user, user_info)}\n"
                f"**Username:** {format_user_text('{username}', user, user_info)}\n"
                f"**User ID:** `{user_id}`\n"
                f"**Level:** {bot_data.get_user_level(user_id)}\n"
                f"**Joined:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
                f"**စုစုပေါင်း:** {total_users} ယောက်"
            )
            await bot.send_message(
                bot_data.data["settings"]["notification_chat_id"],
                notification
            )
        except Exception as e:
            logger.error(f"Failed to send notification: {e}")
    
    # Check captcha if enabled
    if bot_data.data["settings"]["captcha"]:
        captcha_id, captcha_text = bot_data.generate_captcha()
        # TODO: Store captcha in state
        await message.answer(
            f"**🔐 Captcha Verification**\n\nPlease enter: `{captcha_text}`"
        )
        return
    
    # Check subscription if enabled
    if bot_data.data["settings"]["subscription_check"]:
        ok, not_joined = await check_subscription(user_id)
        if not ok:
            channels_text = "\n".join([f"• {ch}" for ch in not_joined])
            await message.answer(
                f"**🔐 ကျေးဇူးပြု၍ အောက်ပါ Channel များကို Join ပါ**\n\n{channels_text}\n\n"
                f"Join ပြီးရင် /start ကိုထပ်နှိပ်ပါ။"
            )
            return
    
    # Get active welcome message
    welcome = bot_data.get_active_welcome()
    
    # Check welcome conditions
    if not check_conditions(welcome.get("conditions", {}), user_id):
        welcome = bot_data.get_welcome_messages()[0]
    
    # Format message with user data
    if welcome["type"] == "text":
        formatted_text = format_user_text(welcome["content"], user, user_info)
        await message.answer(
            formatted_text,
            reply_markup=get_main_menu_keyboard(user_id),
            reply_markup_inline=create_inline_keyboard(welcome.get("buttons", []))
        )
    elif welcome["type"] == "photo":
        formatted_caption = format_user_text(welcome["content"].get("caption", ""), user, user_info)
        await message.answer_photo(
            photo=welcome["content"]["file_id"],
            caption=formatted_caption,
            reply_markup=get_main_menu_keyboard(user_id),
            reply_markup_inline=create_inline_keyboard(welcome.get("buttons", []))
        )
    elif welcome["type"] == "video":
        formatted_caption = format_user_text(welcome["content"].get("caption", ""), user, user_info)
        await message.answer_video(
            video=welcome["content"]["file_id"],
            caption=formatted_caption,
            reply_markup=get_main_menu_keyboard(user_id),
            reply_markup_inline=create_inline_keyboard(welcome.get("buttons", []))
        )

async def check_subscription(user_id: int) -> Tuple[bool, List[str]]:
    """Check if user joined required channels"""
    # TODO: Implement actual subscription check
    return True, []

def check_conditions(conditions: Dict, user_id: int) -> bool:
    """Check if user meets conditions"""
    # TODO: Implement condition checking
    return True

# ============================
# HANDLERS - MAIN MENU BUTTONS
# ============================

@dp.message(F.text.in_([btn["name"] for btn in bot_data.get_main_buttons()]))
async def handle_main_buttons(message: Message):
    """ပင်မမီနူးခလုတ်များကို နှိပ်တဲ့အခါ"""
    btn_name = message.text
    user_id = message.from_user.id
    
    # Find button in data
    for btn in bot_data.get_main_buttons():
        if btn["name"] == btn_name:
            # Track click
            bot_data.track_button_click(btn["id"])
            
            # Check conditions
            if not bot_data.check_button_condition(btn["id"], user_id):
                await message.answer("❌ ဒီခလုတ်ကို သုံးခွင့်မရှိပါ။")
                return
            
            # Handle by type
            btn_type = btn.get("type", "menu")
            
            if btn_type == "menu":
                # Check if button has sub-buttons
                sub_buttons = bot_data.get_sub_buttons(btn["id"])
                if sub_buttons:
                    # Show sub-menu
                    await message.answer(
                        f"{btn_name} အမျိုးအစားများ",
                        reply_markup=get_buttons_list_keyboard(sub_buttons)
                    )
                elif btn.get("messages"):
                    # Show messages
                    for msg in btn["messages"]:
                        if check_conditions(msg.get("conditions", {}), user_id):
                            if msg["type"] == "text":
                                await message.answer(
                                    msg["content"],
                                    reply_markup=create_inline_keyboard(msg.get("buttons", []))
                                )
                            elif msg["type"] == "photo":
                                await message.answer_photo(
                                    photo=msg["content"]["file_id"],
                                    caption=msg["content"].get("caption", ""),
                                    reply_markup=create_inline_keyboard(msg.get("buttons", []))
                                )
                else:
                    await message.answer(f"{btn_name} အတွက် ပို့စ်မရှိသေးပါ။")
            
            elif btn_type == "url":
                if btn.get("url"):
                    keyboard = InlineKeyboardMarkup(
                        inline_keyboard=[[InlineKeyboardButton(text=btn_name, url=btn["url"])]]
                    )
                    await message.answer("🔗 လင့်ခ်ဖွင့်ရန် အောက်ပါခလုတ်ကိုနှိပ်ပါ။", reply_markup=keyboard)
                else:
                    await message.answer("❌ URL မသတ်မှတ်ရသေးပါ။")
            
            elif btn_type == "text":
                if btn.get("content"):
                    await message.answer(btn["content"])
                else:
                    await message.answer("❌ စာသားမသတ်မှတ်ရသေးပါ။")
            
            elif btn_type == "command":
                if btn.get("command"):
                    # Execute command
                    cmd = btn["command"]
                    if cmd == "/start":
                        await cmd_start(message)
                    # TODO: Handle other commands
            
            elif btn_type == "random":
                if btn.get("messages"):
                    msg = random.choice(btn["messages"])
                    if msg["type"] == "text":
                        await message.answer(msg["content"])
                    elif msg["type"] == "photo":
                        await message.answer_photo(photo=msg["content"]["file_id"])
            
            elif btn_type == "admin" and user_id != OWNER_ID:
                await message.answer("❌ ဒီခလုတ်ကို သုံးခွင့်မရှိပါ။")
            
            return

# ============================
# HANDLERS - NAVIGATION BUTTONS
# ============================

@dp.message(F.text.in_(["🔙 နောက်သို့", "🔙 Back"]))
async def go_back(message: Message, state: FSMContext):
    """Back ခလုတ်"""
    data = await state.get_data()
    parent_id = data.get("parent_id")
    previous_menu = data.get("previous_menu")
    
    if previous_menu == "post_editor":
        btn_id = data.get("post_btn_id")
        if btn_id:
            await message.answer(
                f"**{data.get('post_btn_name')}** အတွက် ပို့စ်တည်းဖြတ်ခန်း",
                reply_markup=get_message_editor_keyboard(btn_id)
            )
            await state.update_data(previous_menu=None)
            return
    
    if parent_id:
        parent_btn = bot_data.get_button(parent_id)
        if parent_btn:
            sub_buttons = bot_data.get_sub_buttons(parent_id)
            if sub_buttons:
                await message.answer(
                    f"{parent_btn['name']} အမျိုးအစားများ",
                    reply_markup=get_buttons_list_keyboard(sub_buttons)
                )
            else:
                await message.answer(
                    "ပင်မမီနူး",
                    reply_markup=get_main_menu_keyboard(message.from_user.id)
                )
            await state.update_data(parent_id=parent_btn.get("parent"))
        else:
            await message.answer(
                "ပင်မမီနူး",
                reply_markup=get_main_menu_keyboard(message.from_user.id)
            )
            await state.clear()
    else:
        await message.answer(
            "ပင်မမီနူး",
            reply_markup=get_main_menu_keyboard(message.from_user.id)
        )
        await state.clear()

@dp.message(F.text.in_(["🏠 ပင်မ", "🏠 Home"]))
async def go_home(message: Message, state: FSMContext):
    """Home ခလုတ် - Main Menu ကိုပြန်သွားမယ်"""
    await state.clear()
    await message.answer(
        "ပင်မမီနူး",
        reply_markup=get_main_menu_keyboard(message.from_user.id)
    )

# ============================
# HANDLERS - ADMIN PANEL
# ============================

@dp.message(F.text == "⚙️ Admin Panel")
async def admin_panel(message: Message):
    """Admin Panel"""
    if message.from_user.id != OWNER_ID:
        await message.answer("❌ ဒီနေရာကို ဝင်ခွင့်မရှိပါ။")
        return
    
    await message.answer(
        "**⚙️ အက်မင်မီနူး (2026)**\n\n"
        "ဘာလုပ်ချင်ပါသလဲ?",
        reply_markup=get_admin_keyboard()
    )

# ============================
# HANDLERS - SETTINGS
# ============================

@dp.message(F.text == "⚙️ Settings")
async def settings_menu(message: Message):
    """Settings menu"""
    if message.from_user.id != OWNER_ID:
        return
    
    await message.answer(
        "**⚙️ ဆက်တင်များ**",
        reply_markup=get_settings_keyboard()
    )

@dp.message(F.text.startswith("🔄 New User Notification:"))
async def toggle_notification(message: Message):
    """Toggle new user notification"""
    if message.from_user.id != OWNER_ID:
        return
    
    bot_data.data["settings"]["new_user_notification"] = not bot_data.data["settings"]["new_user_notification"]
    bot_data.save_data()
    
    await message.answer(
        f"✅ New User Notification ကို {'ON' if bot_data.data['settings']['new_user_notification'] else 'OFF'} လုပ်ပြီးပါပြီ။",
        reply_markup=get_settings_keyboard()
    )

@dp.message(F.text.startswith("🎲 Random Welcome:"))
async def toggle_random_welcome(message: Message):
    """Toggle random welcome mode"""
    if message.from_user.id != OWNER_ID:
        return
    
    current = bot_data.data["settings"].get("random_welcome", False)
    bot_data.data["settings"]["random_welcome"] = not current
    bot_data.save_data()
    
    await message.answer(
        f"✅ Random Welcome Mode ကို {'ON' if not current else 'OFF'} လုပ်ပြီးပါပြီ။",
        reply_markup=get_settings_keyboard()
    )

@dp.message(F.text.startswith("🔐 Captcha:"))
async def toggle_captcha(message: Message):
    """Toggle captcha"""
    if message.from_user.id != OWNER_ID:
        return
    
    bot_data.data["settings"]["captcha"] = not bot_data.data["settings"]["captcha"]
    bot_data.save_data()
    
    await message.answer(
        f"✅ Captcha ကို {'ON' if bot_data.data['settings']['captcha'] else 'OFF'} လုပ်ပြီးပါပြီ။",
        reply_markup=get_settings_keyboard()
    )

@dp.message(F.text.startswith("🎁 Bonus:"))
async def toggle_bonus(message: Message):
    """Toggle bonus system"""
    if message.from_user.id != OWNER_ID:
        return
    
    bot_data.data["settings"]["bonus_enabled"] = not bot_data.data["settings"]["bonus_enabled"]
    bot_data.save_data()
    
    await message.answer(
        f"✅ Bonus System ကို {'ON' if bot_data.data['settings']['bonus_enabled'] else 'OFF'} လုပ်ပြီးပါပြီ။\n\n"
        f"Bonus ပမာဏသတ်မှတ်ရန် /set_bonus [ပမာဏ] ကိုသုံးပါ။",
        reply_markup=get_settings_keyboard()
    )

@dp.message(F.text.startswith("🤝 Referrals:"))
async def toggle_referrals(message: Message):
    """Toggle referral system"""
    if message.from_user.id != OWNER_ID:
        return
    
    bot_data.data["settings"]["referral_enabled"] = not bot_data.data["settings"]["referral_enabled"]
    bot_data.save_data()
    
    await message.answer(
        f"✅ Referral System ကို {'ON' if bot_data.data['settings']['referral_enabled'] else 'OFF'} လုပ်ပြီးပါပြီ။\n\n"
        f"Referral Bonus သတ်မှတ်ရန် /set_referral [ပမာဏ] ကိုသုံးပါ။",
        reply_markup=get_settings_keyboard()
    )

@dp.message(Command("set_bonus"))
async def set_bonus(message: Message):
    """Set bonus amount"""
    if message.from_user.id != OWNER_ID:
        return
    
    try:
        amount = int(message.text.split()[1])
        bot_data.data["settings"]["bonus_amount"] = amount
        bot_data.save_data()
        await message.answer(f"✅ Bonus ပမာဏကို {amount} သတ်မှတ်ပြီးပါပြီ။")
    except:
        await message.answer("❌ ပုံစံမှားနေပါတယ်။ /set_bonus [ပမာဏ]")

@dp.message(Command("set_referral"))
async def set_referral(message: Message):
    """Set referral bonus"""
    if message.from_user.id != OWNER_ID:
        return
    
    try:
        amount = int(message.text.split()[1])
        bot_data.data["settings"]["referral_bonus"] = amount
        bot_data.save_data()
        await message.answer(f"✅ Referral Bonus ပမာဏကို {amount} သတ်မှတ်ပြီးပါပြီ။")
    except:
        await message.answer("❌ ပုံစံမှားနေပါတယ်။ /set_referral [ပမာဏ]")

# ============================
# HANDLERS - LANGUAGE
# ============================

@dp.message(F.text == "🌐 Change Language")
async def language_menu(message: Message):
    """Language selection menu"""
    if message.from_user.id != OWNER_ID:
        return
    
    await message.answer(
        "**🌐 ဘာသာစကားရွေးချယ်ပါ**\n\n"
        "Select Language:",
        reply_markup=get_language_keyboard()
    )

@dp.message(F.text.in_(["🇲🇲 မြန်မာ", "🇬🇧 English", "🇹🇭 ไทย", "🇱🇦 ລາວ", "🇨🇳 中文", "🇯🇵 日本語", "🇰🇷 한국어"]))
async def set_language(message: Message):
    """Set bot language"""
    if message.from_user.id != OWNER_ID:
        return
    
    lang_map = {
        "🇲🇲 မြန်မာ": "my",
        "🇬🇧 English": "en",
        "🇹🇭 ไทย": "th",
        "🇱🇦 ລາວ": "lo",
        "🇨🇳 中文": "zh",
        "🇯🇵 日本語": "ja",
        "🇰🇷 한국어": "ko"
    }
    
    lang_code = lang_map.get(message.text, "en")
    bot_data.set_language(lang_code)
    
    await message.answer(
        f"✅ ဘာသာစကားကို {message.text} သို့ပြောင်းပြီးပါပြီ။",
        reply_markup=get_settings_keyboard()
    )

# ============================
# HANDLERS - PAYMENTS
# ============================

@dp.message(F.text == "💰 Payments")
async def payments_menu(message: Message):
    """Payments menu"""
    if message.from_user.id != OWNER_ID:
        return
    
    balance = bot_data.get_user_balance(OWNER_ID)
    
    await message.answer(
        f"**💰 ငွေပေးချေမှုစနစ်**\n\n"
        f"**လက်ကျန်:** {balance} {bot_data.data['settings']['currency']}\n\n"
        f"ငွေဖြည့်ရန် အောက်ပါနည်းလမ်းများကို ရွေးချယ်ပါ။",
        reply_markup=get_payment_keyboard()
    )

@dp.message(F.text == "⭐ Telegram Stars")
async def buy_stars(message: Message, state: FSMContext):
    """Buy with Telegram Stars"""
    if message.from_user.id != OWNER_ID:
        return
    
    await message.answer(
        "**⭐ Telegram Stars ဖြင့်ဝယ်ယူရန်**\n\n"
        "ငွေပမာဏ ရိုက်ထည့်ပါ။ (1 Star = 1 ယူနစ်)"
    )
    await state.set_state(BotStates.waiting_payment_amount)

@dp.message(BotStates.waiting_payment_amount)
async def process_stars_payment(message: Message, state: FSMContext):
    """Process stars payment"""
    if message.from_user.id != OWNER_ID:
        return
    
    try:
        amount = int(message.text)
        # TODO: Implement Telegram Stars payment
        bot_data.add_balance(OWNER_ID, amount)
        await message.answer(
            f"✅ ငွေဖြည့်ပြီးပါပြီ။\n"
            f"လက်ကျန်: {bot_data.get_user_balance(OWNER_ID)}"
        )
        await state.clear()
    except:
        await message.answer("❌ နံပါတ်မှန်မှန်ရိုက်ထည့်ပါ။")

@dp.message(F.text == "💳 Withdraw")
async def withdraw_menu(message: Message, state: FSMContext):
    """Withdraw balance"""
    if message.from_user.id != OWNER_ID:
        return
    
    balance = bot_data.get_user_balance(OWNER_ID)
    
    await message.answer(
        f"**💳 ငွေထုတ်ရန်**\n\n"
        f"**လက်ကျန်:** {balance}\n\n"
        f"ထုတ်ယူလိုသော ပမာဏ ရိုက်ထည့်ပါ။"
    )
    await state.set_state(BotStates.waiting_withdraw_amount)

@dp.message(BotStates.waiting_withdraw_amount)
async def process_withdraw_amount(message: Message, state: FSMContext):
    """Process withdraw amount"""
    if message.from_user.id != OWNER_ID:
        return
    
    try:
        amount = int(message.text)
        await state.update_data(withdraw_amount=amount)
        await message.answer(
            "ငွေလက်ခံမည့် USDT (TRC20) လိပ်စာ ရိုက်ထည့်ပါ။"
        )
        await state.set_state(BotStates.waiting_withdraw_address)
    except:
        await message.answer("❌ နံပါတ်မှန်မှန်ရိုက်ထည့်ပါ။")

@dp.message(BotStates.waiting_withdraw_address)
async def process_withdraw_address(message: Message, state: FSMContext):
    """Process withdraw address"""
    if message.from_user.id != OWNER_ID:
        return
    
    address = message.text
    data = await state.get_data()
    amount = data.get("withdraw_amount")
    
    if bot_data.withdraw_balance(OWNER_ID, amount, "usdt"):
        await message.answer(
            f"✅ ငွေထုတ်ယူမှု အောင်မြင်ပါသည်။\n"
            f"ပမာဏ: {amount}\n"
            f"လိပ်စာ: {address}\n\n"
            f"လက်ကျန်အသစ်: {bot_data.get_user_balance(OWNER_ID)}"
        )
    else:
        await message.answer("❌ ငွေထုတ်ယူမှု မအောင်မြင်ပါ။ လက်ကျန်ငွေ မလုံလောက်ပါ။")
    
    await state.clear()

@dp.message(F.text == "📊 Balance")
async def show_balance(message: Message):
    """Show user balance"""
    if message.from_user.id != OWNER_ID:
        return
    
    balance = bot_data.get_user_balance(OWNER_ID)
    
    await message.answer(
        f"**📊 လက်ကျန်ငွေ**\n\n"
        f"**စုစုပေါင်း:** {balance} {bot_data.data['settings']['currency']}\n\n"
        f"**ငွေသွင်းရန်:** /deposit\n"
        f"**ငွေထုတ်ရန်:** /withdraw"
    )

# ============================
# HANDLERS - BACKUP/RESTORE
# ============================

@dp.message(F.text == "📦 Backup/Restore")
async def backup_menu(message: Message):
    """Backup/Restore menu"""
    if message.from_user.id != OWNER_ID:
        return
    
    last_backup = bot_data.data["backup"]["last_backup"] or "မရှိသေး"
    
    await message.answer(
        f"**📦 Backup & Restore**\n\n"
        f"**နောက်ဆုံး Backup:** {last_backup}\n"
        f"**Auto Backup:** {'ON' if bot_data.data['backup']['auto_backup'] else 'OFF'}\n"
        f"**Backup Interval:** {bot_data.data['backup']['backup_interval']} နာရီ\n\n"
        f"ဘာလုပ်ချင်ပါသလဲ?",
        reply_markup=get_backup_keyboard()
    )

@dp.message(F.text == "📦 Create Backup")
async def create_backup(message: Message):
    """Create backup"""
    if message.from_user.id != OWNER_ID:
        return
    
    backup_id = bot_data.create_backup()
    
    await message.answer(
        f"✅ Backup ဖန်တီးပြီးပါပြီ။\n"
        f"**Backup ID:** `{backup_id}`\n"
        f"**အချိန်:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    )

@dp.message(F.text == "📂 Restore Backup")
async def restore_backup_prompt(message: Message, state: FSMContext):
    """Restore backup prompt"""
    if message.from_user.id != OWNER_ID:
        return
    
    await message.answer(
        "**Backup ID** ကို ရိုက်ထည့်ပါ။\n\n"
        "ပယ်ဖျက်ချင်ရင် /cancel ကိုသုံးပါ။"
    )
    await state.set_state("waiting_backup_id")

@dp.message(F.text == "📋 List Backups")
async def list_backups(message: Message):
    """List all backups"""
    if message.from_user.id != OWNER_ID:
        return
    
    import glob
    backups = glob.glob("backup_*.json")
    
    if not backups:
        await message.answer("❌ Backup မရှိသေးပါ။")
        return
    
    text = "**📋 Backup များ**\n\n"
    for backup in sorted(backups, reverse=True)[:10]:
        try:
            with open(backup, 'r', encoding='utf-8') as f:
                data = json.load(f)
            text += f"• `{data['id']}` - {data['created_at']}\n"
        except:
            pass
    
    await message.answer(text)

@dp.message(F.text == "⚙️ Auto Backup Settings")
async def auto_backup_settings(message: Message):
    """Auto backup settings"""
    if message.from_user.id != OWNER_ID:
        return
    
    bot_data.data["backup"]["auto_backup"] = not bot_data.data["backup"]["auto_backup"]
    bot_data.save_data()
    
    await message.answer(
        f"✅ Auto Backup ကို {'ON' if bot_data.data['backup']['auto_backup'] else 'OFF'} လုပ်ပြီးပါပြီ။"
    )

# ============================
# HANDLERS - SUBSCRIPTION CHECK
# ============================

@dp.message(F.text == "🔐 Subscription Check")
async def subscription_menu(message: Message, state: FSMContext):
    """Subscription check settings"""
    if message.from_user.id != OWNER_ID:
        return
    
    channels = bot_data.data["settings"]["subscription_check"]
    channels_text = "\n".join([f"• {ch}" for ch in channels]) if channels else "မရှိသေး"
    
    await message.answer(
        f"**🔐 Subscription Check**\n\n"
        f"**စစ်ဆေးရန် Channel/Group များ:**\n{channels_text}\n\n"
        f"အသစ်ထည့်ရန် /add_channel [link]\n"
        f"ဖျက်ရန် /remove_channel [link]"
    )

@dp.message(Command("add_channel"))
async def add_channel(message: Message):
    """Add channel to subscription check"""
    if message.from_user.id != OWNER_ID:
        return
    
    try:
        channel = message.text.split()[1]
        channels = bot_data.data["settings"]["subscription_check"]
        if channel not in channels:
            channels.append(channel)
            bot_data.save_data()
            await message.answer(f"✅ Channel ထည့်ပြီးပါပြီ။")
        else:
            await message.answer("❌ Channel ရှိပြီးသားပါ။")
    except:
        await message.answer("❌ ပုံစံမှားနေပါတယ်။ /add_channel [link]")

@dp.message(Command("remove_channel"))
async def remove_channel(message: Message):
    """Remove channel from subscription check"""
    if message.from_user.id != OWNER_ID:
        return
    
    try:
        channel = message.text.split()[1]
        channels = bot_data.data["settings"]["subscription_check"]
        if channel in channels:
            channels.remove(channel)
            bot_data.save_data()
            await message.answer(f"✅ Channel ဖျက်ပြီးပါပြီ။")
        else:
            await message.answer("❌ Channel မရှိပါ။")
    except:
        await message.answer("❌ ပုံစံမှားနေပါတယ်။ /remove_channel [link]")

# ============================
# HANDLERS - USERS
# ============================

@dp.message(F.text == "👥 Users")
async def users_menu(message: Message):
    """Users management menu"""
    if message.from_user.id != OWNER_ID:
        return
    
    users = bot_data.get_all_users()
    active_today = len(bot_data.data["statistics"]["daily_users"])
    
    await message.answer(
        f"**👥 အသုံးပြုသူများ**\n\n"
        f"**စုစုပေါင်း:** {len(users)} ယောက်\n"
        f"**ယနေ့အသုံးပြုသူ:** {active_today} ယောက်\n"
        f"**စုစုပေါင်း Messages:** {bot_data.data['statistics']['total_messages']}\n\n"
        f"အသုံးပြုသူစာရင်းကြည့်ရန် /users_list\n"
        f"အသုံးပြုသူအချက်အလက်ကြည့်ရန် /user [id]"
    )

@dp.message(Command("users_list"))
async def users_list(message: Message):
    """List all users"""
    if message.from_user.id != OWNER_ID:
        return
    
    users = bot_data.get_all_users()
    text = "**👥 အသုံးပြုသူများ**\n\n"
    
    for i, user_id in enumerate(users[:50], 1):
        user_info = bot_data.get_user_info(user_id)
        text += f"{i}. {user_info.get('full_name', 'N/A')} - `{user_id}`\n"
    
    if len(users) > 50:
        text += f"\n...နောက်ထပ် {len(users) - 50} ယောက်"
    
    await message.answer(text)

@dp.message(Command("user"))
async def user_info(message: Message):
    """Show user info"""
    if message.from_user.id != OWNER_ID:
        return
    
    try:
        user_id = int(message.text.split()[1])
        user_info = bot_data.get_user_info(user_id)
        
        text = (
            f"**👤 အသုံးပြုသူအချက်အလက်**\n\n"
            f"**ID:** `{user_id}`\n"
            f"**အမည်:** {user_info.get('full_name', 'N/A')}\n"
            f"**Username:** {user_info.get('username', 'N/A')}\n"
            f"**Level:** {bot_data.get_user_level(user_id)}\n"
            f"**Balance:** {user_info.get('balance', 0)}\n"
            f"**Messages:** {bot_data.user_stats[user_id].get('messages', 0)}\n"
            f"**Joined:** {user_info.get('joined_at', 'N/A')}"
        )
        
        await message.answer(text)
    except:
        await message.answer("❌ ပုံစံမှားနေပါတယ်။ /user [user_id]")

# ============================
# HANDLERS - BUTTON EDITOR (2026)
# ============================

@dp.message(F.text == "🔧 Button Editor")
async def button_editor(message: Message):
    """Button Editor - 2026"""
    if message.from_user.id != OWNER_ID:
        return
    
    await message.answer(
        "**🔧 ခလုတ်တည်းဖြတ်ခန်း (2026)**\n\n"
        "ဘာလုပ်ချင်ပါသလဲ?",
        reply_markup=get_button_editor_keyboard()
    )

@dp.message(F.text == "➕ Add Button")
async def add_button_prompt(message: Message, state: FSMContext):
    """ခလုတ်အသစ်ထည့်မယ်"""
    if message.from_user.id != OWNER_ID:
        return
    
    await message.answer(
        "**ခလုတ်နာမည်အသစ်ကို ရိုက်ထည့်ပါ။**\n\n"
        "ပယ်ဖျက်ချင်ရင် /cancel ကိုသုံးပါ။"
    )
    await state.set_state(BotStates.waiting_button_name)

@dp.message(BotStates.waiting_button_name)
async def process_button_name(message: Message, state: FSMContext):
    """ခလုတ်နာမည်ရပြီးသိမ်းမယ်"""
    if message.text == "/cancel":
        await state.clear()
        await message.answer("လုပ်ဆောင်ချက်ကို ပယ်ဖျက်လိုက်သည်။")
        return
    
    await state.update_data(new_button_name=message.text)
    
    # Ask where to add
    main_buttons = bot_data.get_main_buttons()
    keyboard_buttons = [[KeyboardButton(text="📋 Main Menu (Top Level)")]]
    
    for btn in main_buttons:
        keyboard_buttons.append([KeyboardButton(text=btn["name"])])
    
    keyboard_buttons.append([KeyboardButton(text="🔙 Cancel")])
    
    await message.answer(
        "**ဒီခလုတ်ကို ဘယ်နေရာမှာထည့်ချင်လဲ?**\n\n"
        "• အပေါ်ဆုံးအဆင့်မှာထည့်ချင်ရင် 'Main Menu (Top Level)' ကိုနှိပ်ပါ။\n"
        "• ခလုတ်တစ်ခုခုအောက်မှာထည့်ချင်ရင် အဲဒီခလုတ်ကိုနှိပ်ပါ။",
        reply_markup=ReplyKeyboardMarkup(keyboard=keyboard_buttons, resize_keyboard=True)
    )
    await state.set_state(BotStates.waiting_parent_select)

@dp.message(BotStates.waiting_parent_select)
async def select_parent(message: Message, state: FSMContext):
    """ဘယ်နေရာမှာထည့်မလဲရွေးမယ်"""
    data = await state.get_data()
    button_name = data.get("new_button_name")
    
    if message.text == "🔙 Cancel":
        await state.clear()
        await message.answer(
            "လုပ်ဆောင်ချက်ကို ပယ်ဖျက်လိုက်သည်။",
            reply_markup=get_button_editor_keyboard()
        )
        return
    
    if message.text == "📋 Main Menu (Top Level)":
        # Ask for button type
        await state.update_data(parent=None)
        await message.answer(
            "**ခလုတ်အမျိုးအစားရွေးချယ်ပါ။**",
            reply_markup=get_button_type_keyboard()
        )
        await state.set_state(BotStates.waiting_button_type)
    else:
        # Find parent button
        for btn in bot_data.get_main_buttons():
            if btn["name"] == message.text:
                await state.update_data(parent=btn["id"])
                await message.answer(
                    "**ခလုတ်အမျိုးအစားရွေးချယ်ပါ။**",
                    reply_markup=get_button_type_keyboard()
                )
                await state.set_state(BotStates.waiting_button_type)
                return

@dp.message(BotStates.waiting_button_type)
async def select_button_type(message: Message, state: FSMContext):
    """ခလုတ်အမျိုးအစားရွေးမယ်"""
    data = await state.get_data()
    button_name = data.get("new_button_name")
    parent = data.get("parent")
    
    type_map = {
        "📋 Menu Button": "menu",
        "🔗 URL Button": "url",
        "📝 Text Button": "text",
        "🔄 Command Button": "command",
        "📤 Share Button": "share",
        "🎲 Random Button": "random",
        "👤 Admin Only": "admin"
    }
    
    btn_type = type_map.get(message.text)
    
    if not btn_type:
        await message.answer("❌ မှားယွင်းသောရွေးချယ်မှုပါ။")
        return
    
    await state.update_data(btn_type=btn_type)
    
    if btn_type == "url":
        await message.answer(
            "**URL လင့်ခ်ကို ရိုက်ထည့်ပါ။**\n\n"
            "ဥပမာ: https://t.me/yourchannel"
        )
        await state.set_state(BotStates.waiting_button_url)
    
    elif btn_type == "command":
        await message.answer(
            "**Command ကို ရိုက်ထည့်ပါ။**\n\n"
            "ဥပမာ: /start, /help"
        )
        await state.set_state(BotStates.waiting_button_command)
    
    elif btn_type == "text":
        await message.answer(
            "**စာသားကို ရိုက်ထည့်ပါ။**"
        )
        await state.set_state(BotStates.waiting_button_text)
    
    else:
        # Create button without extra data
        bot_data.add_button(button_name, parent, btn_type)
        await state.clear()
        await message.answer(
            f"✅ **'{button_name}'** ခလုတ်ကို ထည့်ပြီးပါပြီ။",
            reply_markup=get_button_editor_keyboard()
        )

@dp.message(BotStates.waiting_button_url)
async def process_button_url(message: Message, state: FSMContext):
    """Process button URL"""
    data = await state.get_data()
    button_name = data.get("new_button_name")
    parent = data.get("parent")
    btn_type = data.get("btn_type")
    url = message.text
    
    bot_data.add_button(button_name, parent, btn_type, url=url)
    await state.clear()
    await message.answer(
        f"✅ **'{button_name}'** URL ခလုတ်ကို ထည့်ပြီးပါပြီ။",
        reply_markup=get_button_editor_keyboard()
    )

@dp.message(BotStates.waiting_button_command)
async def process_button_command(message: Message, state: FSMContext):
    """Process button command"""
    data = await state.get_data()
    button_name = data.get("new_button_name")
    parent = data.get("parent")
    btn_type = data.get("btn_type")
    command = message.text
    
    bot_data.add_button(button_name, parent, btn_type, command=command)
    await state.clear()
    await message.answer(
        f"✅ **'{button_name}'** Command ခလုတ်ကို ထည့်ပြီးပါပြီ။",
        reply_markup=get_button_editor_keyboard()
    )

@dp.message(BotStates.waiting_button_text)
async def process_button_text(message: Message, state: FSMContext):
    """Process button text"""
    data = await state.get_data()
    button_name = data.get("new_button_name")
    parent = data.get("parent")
    btn_type = data.get("btn_type")
    text = message.text
    
    bot_data.add_button(button_name, parent, btn_type, content=text)
    await state.clear()
    await message.answer(
        f"✅ **'{button_name}'** Text ခလုတ်ကို ထည့်ပြီးပါပြီ။",
        reply_markup=get_button_editor_keyboard()
    )

@dp.message(F.text == "✏️ Rename Button")
async def rename_button_prompt(message: Message, state: FSMContext):
    """ခလုတ်နာမည်ပြောင်းမယ်"""
    if message.from_user.id != OWNER_ID:
        return
    
    all_buttons = bot_data.get_all_buttons()
    if not all_buttons:
        await message.answer("ခလုတ်မရှိသေးပါ။")
        return
    
    await message.answer(
        "**ဘယ်ခလုတ်ကို နာမည်ပြောင်းချင်လဲ ရွေးပါ။**",
        reply_markup=get_buttons_list_keyboard(all_buttons)
    )
    await state.set_state(BotStates.waiting_button_rename_select)

@dp.message(BotStates.waiting_button_rename_select)
async def process_rename_select(message: Message, state: FSMContext):
    """နာမည်ပြောင်းမယ့်ခလုတ်ကိုရွေးပြီး"""
    all_buttons = bot_data.get_all_buttons()
    for btn in all_buttons:
        if btn["name"] == message.text:
            await state.update_data(rename_btn_id=btn["id"])
            await message.answer(
                f"**'{btn['name']}'** အတွက် နာမည်အသစ်ကို ရိုက်ထည့်ပါ။"
            )
            await state.set_state(BotStates.waiting_button_rename)
            return

@dp.message(BotStates.waiting_button_rename)
async def process_rename(message: Message, state: FSMContext):
    """နာမည်အသစ်သိမ်းမယ်"""
    data = await state.get_data()
    btn_id = data.get("rename_btn_id")
    
    if bot_data.rename_button(btn_id, message.text):
        await state.clear()
        await message.answer(
            f"✅ ခလုတ်နာမည်ကို **'{message.text}'** သို့ ပြောင်းပြီးပါပြီ။",
            reply_markup=get_button_editor_keyboard()
        )

@dp.message(F.text == "🗑 Delete Button")
async def delete_button_prompt(message: Message, state: FSMContext):
    """ခလုတ်ဖျက်မယ်"""
    if message.from_user.id != OWNER_ID:
        return
    
    all_buttons = bot_data.get_all_buttons()
    if not all_buttons:
        await message.answer("ခလုတ်မရှိသေးပါ။")
        return
    
    await message.answer(
        "**ဘယ်ခလုတ်ကို ဖျက်ချင်လဲ ရွေးပါ။**",
        reply_markup=get_buttons_list_keyboard(all_buttons)
    )
    await state.set_state(BotStates.waiting_button_delete_select)

@dp.message(BotStates.waiting_button_delete_select)
async def process_delete_button(message: Message, state: FSMContext):
    """ခလုတ်ဖျက်မယ်"""
    all_buttons = bot_data.get_all_buttons()
    for btn in all_buttons:
        if btn["name"] == message.text:
            bot_data.delete_button(btn["id"])
            await state.clear()
            await message.answer(
                f"✅ **'{btn['name']}'** ခလုတ်ကို ဖျက်ပြီးပါပြီ။",
                reply_markup=get_button_editor_keyboard()
            )
            return

@dp.message(F.text == "📂 Enter Button")
async def enter_button_prompt(message: Message, state: FSMContext):
    """ခလုတ်အတွင်းထဲဝင်မယ်"""
    if message.from_user.id != OWNER_ID:
        return
    
    all_buttons = bot_data.get_all_buttons()
    if not all_buttons:
        await message.answer("ခလုတ်မရှိသေးပါ။")
        return
    
    await message.answer(
        "**ဘယ်ခလုတ်အတွင်းကို ဝင်ချင်လဲ ရွေးပါ။**",
        reply_markup=get_buttons_list_keyboard(all_buttons)
    )
    await state.set_state(BotStates.waiting_button_enter_select)

@dp.message(BotStates.waiting_button_enter_select)
async def process_enter_button(message: Message, state: FSMContext):
    """ရွေးထားတဲ့ခလုတ်အတွင်းကိုဝင်မယ်"""
    all_buttons = bot_data.get_all_buttons()
    for btn in all_buttons:
        if btn["name"] == message.text:
            sub_buttons = bot_data.get_sub_buttons(btn["id"])
            await state.update_data(current_button_id=btn["id"], parent_id=btn.get("parent"))
            
            if sub_buttons:
                text = f"**{btn['name']}** အတွင်းရှိခလုတ်ခွဲများ"
                reply_markup = get_buttons_list_keyboard(sub_buttons, "🔙 Back to Admin")
            else:
                text = f"**{btn['name']}** အတွင်း၌ ခလုတ်ခွဲမရှိသေးပါ။"
                reply_markup = ReplyKeyboardMarkup(
                    keyboard=[[KeyboardButton(text="➕ Add Sub Button")], [KeyboardButton(text="🔙 Back to Admin")]],
                    resize_keyboard=True
                )
            
            await message.answer(text, reply_markup=reply_markup)
            return

@dp.message(F.text == "⬆️ ⬇️ Move Button")
async def move_button_prompt(message: Message, state: FSMContext):
    """ခလုတ်နေရာရွှေ့မယ်"""
    if message.from_user.id != OWNER_ID:
        return
    
    all_buttons = bot_data.get_all_buttons()
    if not all_buttons:
        await message.answer("ခလုတ်မရှိသေးပါ။")
        return
    
    await message.answer(
        "**ဘယ်ခလုတ်ကို နေရာရွှေ့ချင်လဲ ရွေးပါ။**",
        reply_markup=get_buttons_list_keyboard(all_buttons, show_numbers=True)
    )
    await state.set_state(BotStates.waiting_button_move_select)

@dp.message(BotStates.waiting_button_move_select)
async def select_move_button(message: Message, state: FSMContext):
    """နေရာရွှေ့မယ့်ခလုတ်ရွေးပြီး"""
    all_buttons = bot_data.get_all_buttons()
    for btn in all_buttons:
        if btn["name"] in message.text:
            await state.update_data(move_btn_id=btn["id"])
            await message.answer(
                "**ဘယ်ဘက်ကိုရွှေ့ချင်လဲ ရွေးပါ။**\n\n"
                "⬆️ **Up** - အပေါ်ကိုရွှေ့\n"
                "⬇️ **Down** - အောက်ကိုရွှေ့\n"
                "⬅️ **Out** - အပေါ်အဆင့်ကိုရွှေ့\n"
                "➡️ **Into** - အောက်အဆင့်ကိုရွှေ့",
                reply_markup=get_move_buttons_keyboard()
            )
            await state.set_state(BotStates.waiting_button_move_direction)
            return

@dp.message(BotStates.waiting_button_move_direction)
async def process_move_direction(message: Message, state: FSMContext):
    """နေရာရွှေ့မယ်"""
    data = await state.get_data()
    btn_id = data.get("move_btn_id")
    
    if message.text == "🔙 Back":
        await state.clear()
        await message.answer(
            "ခလုတ်တည်းဖြတ်ခန်း",
            reply_markup=get_button_editor_keyboard()
        )
        return
    
    if message.text == "➡️ Into (submenu)":
        # Show list of possible parents
        all_buttons = bot_data.get_all_buttons()
        await message.answer(
            "**ဘယ်ခလုတ်အောက်ကိုရွှေ့ချင်လဲ ရွေးပါ။**",
            reply_markup=get_buttons_list_keyboard(all_buttons)
        )
        await state.set_state(BotStates.waiting_button_move_target)
        return
    
    if bot_data.move_button(btn_id, message.text):
        await message.answer(
            "✅ ခလုတ်နေရာရွှေ့ပြီးပါပြီ။",
            reply_markup=get_button_editor_keyboard()
        )
        await state.clear()
    else:
        await message.answer("❌ နေရာရွှေ့လို့မရပါ။")

@dp.message(F.text == "🔧 Set Button Type")
async def set_button_type_prompt(message: Message, state: FSMContext):
    """ခလုတ်အမျိုးအစားပြောင်းမယ်"""
    if message.from_user.id != OWNER_ID:
        return
    
    all_buttons = bot_data.get_all_buttons()
    if not all_buttons:
        await message.answer("ခလုတ်မရှိသေးပါ။")
        return
    
    await message.answer(
        "**ဘယ်ခလုတ်ရဲ့ အမျိုးအစားကို ပြောင်းချင်လဲ ရွေးပါ။**",
        reply_markup=get_buttons_list_keyboard(all_buttons)
    )
    await state.set_state("waiting_button_type_select")

@dp.message(F.text == "🔐 Set Conditions")
async def set_conditions_prompt(message: Message, state: FSMContext):
    """ခလုတ် Condition သတ်မှတ်မယ်"""
    if message.from_user.id != OWNER_ID:
        return
    
    all_buttons = bot_data.get_all_buttons()
    if not all_buttons:
        await message.answer("ခလုတ်မရှိသေးပါ။")
        return
    
    await message.answer(
        "**ဘယ်ခလုတ်အတွက် Condition သတ်မှတ်ချင်လဲ ရွေးပါ။**",
        reply_markup=get_buttons_list_keyboard(all_buttons)
    )
    await state.set_state("waiting_conditions_button")

# ============================
# HANDLERS - POST EDITOR (2026)
# ============================

@dp.message(F.text == "📝 Post Editor")
async def post_editor(message: Message, state: FSMContext):
    """Post Editor - 2026"""
    if message.from_user.id != OWNER_ID:
        return
    
    all_buttons = bot_data.get_all_buttons()
    if not all_buttons:
        await message.answer("ခလုတ်မရှိသေးပါ။")
        return
    
    await message.answer(
        "**📝 ပို့စ်တည်းဖြတ်ခန်း (2026)**\n\n"
        "ဘယ်ခလုတ်အတွက် ပို့စ်ထည့်ချင်လဲ ရွေးပါ။",
        reply_markup=get_buttons_list_keyboard(all_buttons)
    )
    await state.set_state(BotStates.waiting_message_select)

@dp.message(BotStates.waiting_message_select)
async def select_button_for_post(message: Message, state: FSMContext):
    """ပို့စ်ထည့်မယ့်ခလုတ်ကိုရွေးပြီး"""
    all_buttons = bot_data.get_all_buttons()
    for btn in all_buttons:
        if btn["name"] == message.text:
            await state.update_data(
                post_btn_id=btn["id"],
                post_btn_name=btn["name"]
            )
            await message.answer(
                f"**{btn['name']}** အတွက် ပို့စ်တည်းဖြတ်ခန်း",
                reply_markup=get_message_editor_keyboard(btn["id"])
            )
            return

@dp.message(F.text == "📝 Add Text Message")
async def add_text_message_prompt(message: Message, state: FSMContext):
    """Text message ထည့်မယ်"""
    data = await state.get_data()
    btn_id = data.get("post_btn_id")
    
    if not btn_id:
        await message.answer("အရင်ဆုံး ခလုတ်တစ်ခုကို ရွေးပါ။")
        return
    
    await message.answer(
        "**ပို့စ်အနေနဲ့ ပြချင်တဲ့ စာသားကို ရိုက်ထည့်ပါ။**\n\n"
        "**Macros များ:** {mention}, {fullname}, {username}, {user_id}, {date}, {time}, {random}\n\n"
        "ပယ်ဖျက်ချင်ရင် /cancel ကိုသုံးပါ။"
    )
    await state.set_state(BotStates.waiting_message_text)

@dp.message(F.text == "🖼 Add Photo Message")
async def add_photo_message_prompt(message: Message, state: FSMContext):
    """Photo message ထည့်မယ်"""
    data = await state.get_data()
    btn_id = data.get("post_btn_id")
    
    if not btn_id:
        await message.answer("အရင်ဆုံး ခလုတ်တစ်ခုကို ရွေးပါ။")
        return
    
    await message.answer(
        "**ပို့စ်အနေနဲ့ ပြချင်တဲ့ ဓာတ်ပုံကို ပို့ပါ။**\n"
        "ဓာတ်ပုံနဲ့အတူ စာသားပါထည့်ချင်ရင် Caption မှာရေးပါ။\n\n"
        "**Macros များ:** {mention}, {fullname}, {username}, {user_id}, {date}, {time}\n\n"
        "ပယ်ဖျက်ချင်ရင် /cancel ကိုသုံးပါ။"
    )
    await state.set_state(BotStates.waiting_message_photo)

@dp.message(F.text == "🎥 Add Video Message")
async def add_video_message_prompt(message: Message, state: FSMContext):
    """Video message ထည့်မယ်"""
    data = await state.get_data()
    btn_id = data.get("post_btn_id")
    
    if not btn_id:
        await message.answer("အရင်ဆုံး ခလုတ်တစ်ခုကို ရွေးပါ။")
        return
    
    await message.answer(
        "**ပို့စ်အနေနဲ့ ပြချင်တဲ့ ဗီဒီယိုကို ပို့ပါ။**\n"
        "ဗီဒီယိုနဲ့အတူ စာသားပါထည့်ချင်ရင် Caption မှာရေးပါ။\n\n"
        "ပယ်ဖျက်ချင်ရင် /cancel ကိုသုံးပါ။"
    )
    await state.set_state(BotStates.waiting_message_video)

@dp.message(F.text == "📎 Add Document Message")
async def add_document_message_prompt(message: Message, state: FSMContext):
    """Document message ထည့်မယ်"""
    data = await state.get_data()
    btn_id = data.get("post_btn_id")
    
    if not btn_id:
        await message.answer("အရင်ဆုံး ခလုတ်တစ်ခုကို ရွေးပါ။")
        return
    
    await message.answer(
        "**ပို့စ်အနေနဲ့ ပြချင်တဲ့ ဖိုင်ကို ပို့ပါ။**\n"
        "ဖိုင်နဲ့အတူ စာသားပါထည့်ချင်ရင် Caption မှာရေးပါ။\n\n"
        "ပယ်ဖျက်ချင်ရင် /cancel ကိုသုံးပါ။"
    )
    await state.set_state(BotStates.waiting_message_document)

@dp.message(BotStates.waiting_message_text)
async def process_text_message(message: Message, state: FSMContext):
    """Text message သိမ်းမယ်"""
    if message.text == "/cancel":
        await state.clear()
        await message.answer("လုပ်ဆောင်ချက်ကို ပယ်ဖျက်လိုက်သည်။")
        return
    
    await state.update_data(message_text=message.text)
    
    await message.answer(
        "**Inline ခလုတ်တွေ ထည့်လို့ရပါတယ်။**\n\n"
        "ခလုတ်တစ်ခုချင်းစီကို အောက်ပါအတိုင်း ရိုက်ထည့်ပါ။\n\n"
        "**URL ခလုတ်:** `နာမည်|URL`\n"
        "**Callback ခလုတ်:** `နာမည်|callback:data`\n"
        "**Switch ခလုတ်:** `နာမည်|switch:query`\n"
        "**Pay ခလုတ်:** `နာမည်|pay`\n\n"
        "ခလုတ်တစ်ခုထည့်ပြီးရင် Enter နှိပ်ပါ။\n"
        "အကုန်ပြီးရင် `done` လို့ရိုက်ပါ။"
    )
    await state.set_state(BotStates.waiting_message_buttons)

@dp.message(BotStates.waiting_message_photo, F.photo)
async def process_photo_message(message: Message, state: FSMContext):
    """Photo message သိမ်းမယ်"""
    photo = message.photo[-1]
    caption = message.caption or ""
    
    await state.update_data(
        message_photo=photo.file_id,
        message_caption=caption
    )
    
    await message.answer(
        "**Inline ခလုတ်တွေ ထည့်လို့ရပါတယ်။**\n\n"
        "ခလုတ်တစ်ခုချင်းစီကို အောက်ပါအတိုင်း ရိုက်ထည့်ပါ။\n\n"
        "**URL ခလုတ်:** `နာမည်|URL`\n"
        "**Callback ခလုတ်:** `နာမည်|callback:data`\n\n"
        "ခလုတ်တစ်ခုထည့်ပြီးရင် Enter နှိပ်ပါ။\n"
        "အကုန်ပြီးရင် `done` လို့ရိုက်ပါ။"
    )
    await state.set_state(BotStates.waiting_message_buttons)

@dp.message(BotStates.waiting_message_video, F.video)
async def process_video_message(message: Message, state: FSMContext):
    """Video message သိမ်းမယ်"""
    video = message.video
    caption = message.caption or ""
    
    await state.update_data(
        message_video=video.file_id,
        message_caption=caption
    )
    
    await message.answer(
        "**Inline ခလုတ်တွေ ထည့်လို့ရပါတယ်။**\n\n"
        "ခလုတ်တစ်ခုချင်းစီကို အောက်ပါအတိုင်း ရိုက်ထည့်ပါ။\n\n"
        "**URL ခလုတ်:** `နာမည်|URL`\n"
        "**Callback ခလုတ်:** `နာမည်|callback:data`\n\n"
        "ခလုတ်တစ်ခုထည့်ပြီးရင် Enter နှိပ်ပါ။\n"
        "အကုန်ပြီးရင် `done` လို့ရိုက်ပါ။"
    )
    await state.set_state(BotStates.waiting_message_buttons)

@dp.message(BotStates.waiting_message_document, F.document)
async def process_document_message(message: Message, state: FSMContext):
    """Document message သိမ်းမယ်"""
    document = message.document
    caption = message.caption or ""
    
    await state.update_data(
        message_document=document.file_id,
        message_caption=caption
    )
    
    await message.answer(
        "**Inline ခလုတ်တွေ ထည့်လို့ရပါတယ်။**\n\n"
        "ခလုတ်တစ်ခုချင်းစီကို အောက်ပါအတိုင်း ရိုက်ထည့်ပါ။\n\n"
        "**URL ခလုတ်:** `နာမည်|URL`\n"
        "**Callback ခလုတ်:** `နာမည်|callback:data`\n\n"
        "ခလုတ်တစ်ခုထည့်ပြီးရင် Enter နှိပ်ပါ။\n"
        "အကုန်ပြီးရင် `done` လို့ရိုက်ပါ။"
    )
    await state.set_state(BotStates.waiting_message_buttons)

@dp.message(BotStates.waiting_message_buttons)
async def process_message_buttons(message: Message, state: FSMContext):
    """Message buttons သိမ်းမယ်"""
    data = await state.get_data()
    btn_id = data.get("post_btn_id")
    
    if message.text.lower() == "done":
        buttons = data.get("temp_buttons", [])
        
        if "message_text" in data:
            bot_data.add_message_to_button(
                btn_id,
                "text",
                data["message_text"],
                buttons
            )
        elif "message_photo" in data:
            bot_data.add_message_to_button(
                btn_id,
                "photo",
                {
                    "file_id": data["message_photo"],
                    "caption": data.get("message_caption", "")
                },
                buttons
            )
        elif "message_video" in data:
            bot_data.add_message_to_button(
                btn_id,
                "video",
                {
                    "file_id": data["message_video"],
                    "caption": data.get("message_caption", "")
                },
                buttons
            )
        elif "message_document" in data:
            bot_data.add_message_to_button(
                btn_id,
                "document",
                {
                    "file_id": data["message_document"],
                    "caption": data.get("message_caption", "")
                },
                buttons
            )
        
        await state.update_data(previous_menu="post_editor")
        btn = bot_data.get_button(btn_id)
        await message.answer(
            "✅ **Message ထည့်ပြီးပါပြီ။**",
            reply_markup=get_message_editor_keyboard(btn_id)
        )
        return
    
    # Add button to temp list
    temp_buttons = data.get("temp_buttons", [])
    button = parse_buttons_text(message.text)
    if button:
        temp_buttons.extend(button)
        await state.update_data(temp_buttons=temp_buttons)
        await message.answer(f"✅ ခလုတ် '{message.text}' ကို ထည့်ပြီးပါပြီ။\nနောက်ထပ်ထည့်ချင်ရင် ဆက်ရိုက်ပါ။\nအကုန်ပြီးရင် `done` လို့ရိုက်ပါ။")
    else:
        await message.answer("❌ ခလုတ်ပုံစံမှားနေပါတယ်။ ထပ်ရိုက်ပါ။")

@dp.message(F.text == "📋 View Messages")
async def view_messages(message: Message, state: FSMContext):
    """Messages တွေကြည့်မယ်"""
    data = await state.get_data()
    btn_id = data.get("post_btn_id")
    btn = bot_data.get_button(btn_id)
    
    if not btn or not btn.get("messages"):
        await message.answer("ဒီခလုတ်အတွက် ပို့စ်မရှိသေးပါ။")
        return
    
    msg_text = f"**{btn['name']}** အတွက် ပို့စ်များ:\n\n"
    for i, msg in enumerate(btn["messages"], 1):
        msg_type = msg["type"]
        if msg_type == "text":
            preview = msg["content"][:50] + "..." if len(msg["content"]) > 50 else msg["content"]
        else:
            preview = f"[{msg_type}] " + (msg["content"].get("caption", "")[:30] + "..." if msg["content"].get("caption") else "")
        buttons_count = len(msg.get("buttons", []))
        conditions = "🔐" if msg.get("conditions") else ""
        msg_text += f"{i}. **{msg_type}** {conditions}: {preview} (ခလုတ် {buttons_count} ခု)\n"
    
    await message.answer(msg_text)

@dp.message(F.text == "✏️ Edit Message")
async def edit_message_prompt(message: Message, state: FSMContext):
    """Message ပြင်မယ်"""
    data = await state.get_data()
    btn_id = data.get("post_btn_id")
    btn = bot_data.get_button(btn_id)
    
    if not btn or not btn.get("messages"):
        await message.answer("ဒီခလုတ်အတွက် ပို့စ်မရှိသေးပါ။")
        return
    
    # Show messages list
    msg_list = []
    for i, msg in enumerate(btn["messages"], 1):
        msg_list.append({"name": f"{i}. {msg['type']}"})
    
    await message.answer(
        "**ဘယ် Message ကို ပြင်ချင်လဲ ရွေးပါ။**",
        reply_markup=get_buttons_list_keyboard(msg_list)
    )
    await state.set_state(BotStates.waiting_message_edit_select)

@dp.message(F.text == "🗑 Delete Message")
async def delete_message_prompt(message: Message, state: FSMContext):
    """Message ဖျက်မယ်"""
    data = await state.get_data()
    btn_id = data.get("post_btn_id")
    btn = bot_data.get_button(btn_id)
    
    if not btn or not btn.get("messages"):
        await message.answer("ဒီခလုတ်အတွက် ပို့စ်မရှိသေးပါ။")
        return
    
    # Show messages list
    msg_list = []
    for i, msg in enumerate(btn["messages"], 1):
        msg_list.append({"name": f"{i}. {msg['type']}"})
    
    await message.answer(
        "**ဘယ် Message ကို ဖျက်ချင်လဲ ရွေးပါ။**",
        reply_markup=get_buttons_list_keyboard(msg_list)
    )
    await state.set_state(BotStates.waiting_message_delete_select)

@dp.message(F.text == "🎲 Random Message Mode")
async def random_message_mode(message: Message, state: FSMContext):
    """Random message mode ဖွင့်/ပိတ်"""
    data = await state.get_data()
    btn_id = data.get("post_btn_id")
    btn = bot_data.get_button(btn_id)
    
    if not btn:
        return
    
    # Toggle random mode for this button
    current = btn.get("random_mode", False)
    btn["random_mode"] = not current
    
    if btn["random_mode"]:
        # If turning on, set button type to random
        btn["type"] = "random"
    
    bot_data.save_data()
    
    await message.answer(
        f"✅ Random Message Mode ကို {'ON' if not current else 'OFF'} လုပ်ပြီးပါပြီ။"
    )

# ============================
# HANDLERS - WELCOME EDITOR (2026)
# ============================

@dp.message(F.text == "👋 Welcome Editor")
async def welcome_editor(message: Message):
    """Welcome Editor - 2026"""
    if message.from_user.id != OWNER_ID:
        return
    
    await message.answer(
        "**👋 Welcome Message တည်းဖြတ်ခန်း (2026)**\n\n"
        "ဘာလုပ်ချင်ပါသလဲ?",
        reply_markup=get_welcome_editor_keyboard()
    )

@dp.message(F.text == "➕ Add Welcome")
async def add_welcome(message: Message, state: FSMContext):
    """Welcome message အသစ်ထည့်မယ်"""
    if message.from_user.id != OWNER_ID:
        return
    
    await message.answer(
        "Welcome message အနေနဲ့ ဘယ်လိုအမျိုးအစားထည့်ချင်လဲ?",
        reply_markup=get_media_type_keyboard()
    )
    await state.set_state(BotStates.waiting_welcome_type)

@dp.message(BotStates.waiting_welcome_type, F.text == "📝 Text")
async def add_welcome_text(message: Message, state: FSMContext):
    """Welcome text ထည့်မယ်"""
    await message.answer(
        "**Welcome message အနေနဲ့ ပြချင်တဲ့ စာသားကို ရိုက်ထည့်ပါ။**\n\n"
        "**Macros များ (2026):**\n"
        "• `{{mention}}` - အသုံးပြုသူအမည်\n"
        "• `{{fullname}}` - အမည်အပြည့်အစုံ\n"
        "• `{{username}}` - ယူဆာနိမ်\n"
        "• `{{user_id}}` - ယူဆာအိုင်ဒီ\n"
        "• `{{balance}}` - လက်ကျန်ငွေ\n"
        "• `{{level}}` - အဆင့်\n"
        "• `{{messages}}` - ပို့စ်အရေအတွက်\n"
        "• `{{referrals}}` - Referral အရေအတွက်\n"
        "• `{{date}}` - ယနေ့ရက်စွဲ\n"
        "• `{{time}}` - ယခုအချိန်\n"
        "• `{{random}}` - ကျပန်းနံပါတ်\n\n"
        "ပယ်ဖျက်ချင်ရင် /cancel ကိုသုံးပါ။"
    )
    await state.set_state(BotStates.waiting_welcome_text)

@dp.message(BotStates.waiting_welcome_type, F.text == "🖼 Photo")
async def add_welcome_photo(message: Message, state: FSMContext):
    """Welcome photo ထည့်မယ်"""
    await message.answer(
        "**Welcome message အနေနဲ့ ပြချင်တဲ့ ဓာတ်ပုံကို ပို့ပါ။**\n\n"
        "ဓာတ်ပုံနဲ့အတူ စာသားပါထည့်ချင်ရင် Caption မှာရေးပါ။\n\n"
        "**Macros များ:** {mention}, {fullname}, {username}, {user_id}, {balance}, {level}, {date}, {time}\n\n"
        "ပယ်ဖျက်ချင်ရင် /cancel ကိုသုံးပါ။"
    )
    await state.set_state(BotStates.waiting_welcome_photo)

@dp.message(BotStates.waiting_welcome_type, F.text == "🎥 Video")
async def add_welcome_video(message: Message, state: FSMContext):
    """Welcome video ထည့်မယ်"""
    await message.answer(
        "**Welcome message အနေနဲ့ ပြချင်တဲ့ ဗီဒီယိုကို ပို့ပါ။**\n\n"
        "ဗီဒီယိုနဲ့အတူ စာသားပါထည့်ချင်ရင် Caption မှာရေးပါ။\n\n"
        "ပယ်ဖျက်ချင်ရင် /cancel ကိုသုံးပါ။"
    )
    await state.set_state(BotStates.waiting_welcome_video)

@dp.message(BotStates.waiting_welcome_text)
async def process_welcome_text(message: Message, state: FSMContext):
    """Welcome text ရပြီးသိမ်းမယ်"""
    if message.text == "/cancel":
        await state.clear()
        await message.answer("လုပ်ဆောင်ချက်ကို ပယ်ဖျက်လိုက်သည်။")
        return
    
    await state.update_data(welcome_text=message.text)
    
    await message.answer(
        "**Inline ခလုတ်တွေ ထည့်လို့ရပါတယ်။**\n\n"
        "ခလုတ်တစ်ခုချင်းစီကို အောက်ပါအတိုင်း ရိုက်ထည့်ပါ။\n\n"
        "**URL ခလုတ်:** `နာမည်|URL`\n"
        "**Callback ခလုတ်:** `နာမည်|callback:data`\n\n"
        "ခလုတ်တစ်ခုထည့်ပြီးရင် Enter နှိပ်ပါ။\n"
        "အကုန်ပြီးရင် `done` လို့ရိုက်ပါ။"
    )
    await state.set_state(BotStates.waiting_welcome_buttons)

@dp.message(BotStates.waiting_welcome_photo, F.photo)
async def process_welcome_photo(message: Message, state: FSMContext):
    """Welcome photo ရပြီးသိမ်းမယ်"""
    photo = message.photo[-1]
    caption = message.caption or ""
    
    await state.update_data(
        welcome_photo=photo.file_id,
        welcome_caption=caption
    )
    
    await message.answer(
        "**Inline ခလုတ်တွေ ထည့်လို့ရပါတယ်။**\n\n"
        "ခလုတ်တစ်ခုချင်းစီကို အောက်ပါအတိုင်း ရိုက်ထည့်ပါ။\n\n"
        "**URL ခလုတ်:** `နာမည်|URL`\n"
        "**Callback ခလုတ်:** `နာမည်|callback:data`\n\n"
        "ခလုတ်တစ်ခုထည့်ပြီးရင် Enter နှိပ်ပါ။\n"
        "အကုန်ပြီးရင် `done` လို့ရိုက်ပါ။"
    )
    await state.set_state(BotStates.waiting_welcome_buttons)

@dp.message(BotStates.waiting_welcome_video, F.video)
async def process_welcome_video(message: Message, state: FSMContext):
    """Welcome video ရပြီးသိမ်းမယ်"""
    video = message.video
    caption = message.caption or ""
    
    await state.update_data(
        welcome_video=video.file_id,
        welcome_caption=caption
    )
    
    await message.answer(
        "**Inline ခလုတ်တွေ ထည့်လို့ရပါတယ်။**\n\n"
        "ခလုတ်တစ်ခုချင်းစီကို အောက်ပါအတိုင်း ရိုက်ထည့်ပါ။\n\n"
        "**URL ခလုတ်:** `နာမည်|URL`\n"
        "**Callback ခလုတ်:** `နာမည်|callback:data`\n\n"
        "ခလုတ်တစ်ခုထည့်ပြီးရင် Enter နှိပ်ပါ။\n"
        "အကုန်ပြီးရင် `done` လို့ရိုက်ပါ။"
    )
    await state.set_state(BotStates.waiting_welcome_buttons)

@dp.message(BotStates.waiting_welcome_buttons)
async def process_welcome_buttons(message: Message, state: FSMContext):
    """Welcome buttons သိမ်းမယ်"""
    data = await state.get_data()
    
    if message.text.lower() == "done":
        buttons = data.get("temp_buttons", [])
        
        if "welcome_text" in data:
            bot_data.add_welcome_message(
                "text",
                data["welcome_text"],
                buttons
            )
        elif "welcome_photo" in data:
            bot_data.add_welcome_message(
                "photo",
                {
                    "file_id": data["welcome_photo"],
                    "caption": data.get("welcome_caption", "")
                },
                buttons
            )
        elif "welcome_video" in data:
            bot_data.add_welcome_message(
                "video",
                {
                    "file_id": data["welcome_video"],
                    "caption": data.get("welcome_caption", "")
                },
                buttons
            )
        
        await state.clear()
        await message.answer(
            "✅ **Welcome message ထည့်ပြီးပါပြီ။**",
            reply_markup=get_welcome_editor_keyboard()
        )
        return
    
    # Add button to temp list
    temp_buttons = data.get("temp_buttons", [])
    button = parse_buttons_text(message.text)
    if button:
        temp_buttons.extend(button)
        await state.update_data(temp_buttons=temp_buttons)
        await message.answer(f"✅ ခလုတ် '{message.text}' ကို ထည့်ပြီးပါပြီ။\nနောက်ထပ်ထည့်ချင်ရင် ဆက်ရိုက်ပါ။\nအကုန်ပြီးရင် `done` လို့ရိုက်ပါ။")
    else:
        await message.answer("❌ ခလုတ်ပုံစံမှားနေပါတယ်။ ထပ်ရိုက်ပါ။")

@dp.message(F.text == "📋 View Welcomes")
async def view_welcomes(message: Message):
    """Welcome messages အားလုံးကြည့်မယ်"""
    if message.from_user.id != OWNER_ID:
        return
    
    welcomes = bot_data.get_welcome_messages()
    active_id = bot_data.data["welcome"]["active"]
    random_mode = bot_data.get_random_mode()
    
    if not welcomes:
        await message.answer("Welcome message မရှိသေးပါ။")
        return
    
    text = f"**📋 Welcome Messages များ** (Random: {'✅' if random_mode else '❌'})\n\n"
    for i, welcome in enumerate(welcomes, 1):
        active = "✅ " if welcome["id"] == active_id else ""
        msg_type = welcome["type"]
        if welcome["type"] == "text":
            preview = welcome["content"][:50] + "..." if len(welcome["content"]) > 50 else welcome["content"]
        else:
            preview = f"[{msg_type}] " + (welcome["content"].get("caption", "")[:30] + "..." if welcome["content"].get("caption") else "")
        buttons_count = len(welcome.get("buttons", []))
        conditions = "🔐" if welcome.get("conditions") else ""
        text += f"{active}{i}. **{msg_type}** {conditions}: {preview} (ခလုတ် {buttons_count} ခု)\n"
    
    await message.answer(text)

@dp.message(F.text == "🎲 Random Mode")
async def toggle_random_welcome(message: Message):
    """Toggle random welcome mode"""
    if message.from_user.id != OWNER_ID:
        return
    
    current = bot_data.get_random_mode()
    bot_data.set_random_mode(not current)
    
    await message.answer(
        f"✅ Random Welcome Mode ကို {'ON' if not current else 'OFF'} လုပ်ပြီးပါပြီ။",
        reply_markup=get_welcome_editor_keyboard()
    )

@dp.message(F.text == "✏️ Edit Welcome")
async def edit_welcome_prompt(message: Message, state: FSMContext):
    """Welcome message ပြင်မယ်"""
    if message.from_user.id != OWNER_ID:
        return
    
    welcomes = bot_data.get_welcome_messages()
    if not welcomes:
        await message.answer("Welcome message မရှိသေးပါ။")
        return
    
    await message.answer(
        "ဘယ် Welcome message ကို ပြင်ချင်လဲ ရွေးပါ။",
        reply_markup=get_buttons_list_keyboard(welcomes)
    )
    await state.set_state(BotStates.waiting_welcome_edit)

@dp.message(F.text == "🗑 Delete Welcome")
async def delete_welcome_prompt(message: Message, state: FSMContext):
    """Welcome message ဖျက်မယ်"""
    if message.from_user.id != OWNER_ID:
        return
    
    welcomes = bot_data.get_welcome_messages()
    if len(welcomes) <= 1:
        await message.answer("အနည်းဆုံး Welcome message တစ်ခု ရှိရပါမယ်။")
        return
    
    await message.answer(
        "ဘယ် Welcome message ကို ဖျက်ချင်လဲ ရွေးပါ။",
        reply_markup=get_buttons_list_keyboard(welcomes)
    )
    await state.set_state(BotStates.waiting_welcome_delete)

@dp.message(F.text == "✅ Set Active")
async def set_active_prompt(message: Message, state: FSMContext):
    """Welcome message ကို active လုပ်မယ်"""
    if message.from_user.id != OWNER_ID:
        return
    
    welcomes = bot_data.get_welcome_messages()
    await message.answer(
        "ဘယ် Welcome message ကို active လုပ်ချင်လဲ ရွေးပါ။",
        reply_markup=get_buttons_list_keyboard(welcomes)
    )
    await state.set_state(BotStates.waiting_welcome_set_active)

# ============================
# HANDLERS - BROADCAST
# ============================

@dp.message(F.text == "📢 Broadcast")
async def broadcast_menu(message: Message):
    """Broadcast menu"""
    if message.from_user.id != OWNER_ID:
        return
    
    if bot_data.broadcast_active:
        await message.answer("Broadcast လုပ်နေဆဲဖြစ်ပါတယ်။ ခဏစောင့်ပါ။")
        return
    
    users_count = bot_data.get_users_count()
    await message.answer(
        f"**📢 Broadcast ပို့ရန်**\n\n"
        f"စုစုပေါင်းအသုံးပြုသူ: **{users_count}** ယောက်\n\n"
        f"ဘယ်လိုအမျိုးအစား ထည့်ချင်လဲ?",
        reply_markup=get_broadcast_keyboard()
    )

@dp.message(F.text == "📝 Send Text")
async def broadcast_text_prompt(message: Message, state: FSMContext):
    """Text broadcast"""
    if message.from_user.id != OWNER_ID:
        return
    
    await message.answer(
        "**Broadcast ပို့မယ့် စာသားကို ရိုက်ထည့်ပါ။**\n\n"
        "**Macros များ:** {mention}, {fullname}, {username}, {user_id}, {date}, {time}, {random}\n\n"
        "ပယ်ဖျက်ချင်ရင် /cancel ကိုသုံးပါ။"
    )
    await state.set_state(BotStates.waiting_broadcast_text)

@dp.message(F.text == "🖼 Send Photo")
async def broadcast_photo_prompt(message: Message, state: FSMContext):
    """Photo broadcast"""
    if message.from_user.id != OWNER_ID:
        return
    
    await message.answer(
        "**Broadcast ပို့မယ့် ဓာတ်ပုံကို ပို့ပါ။**\n"
        "ဓာတ်ပုံနဲ့အတူ စာသားပါထည့်ချင်ရင် Caption မှာရေးပါ။\n\n"
        "ပယ်ဖျက်ချင်ရင် /cancel ကိုသုံးပါ။"
    )
    await state.set_state(BotStates.waiting_broadcast_photo)

@dp.message(F.text == "🎥 Send Video")
async def broadcast_video_prompt(message: Message, state: FSMContext):
    """Video broadcast"""
    if message.from_user.id != OWNER_ID:
        return
    
    await message.answer(
        "**Broadcast ပို့မယ့် ဗီဒီယိုကို ပို့ပါ။**\n"
        "ဗီဒီယိုနဲ့အတူ စာသားပါထည့်ချင်ရင် Caption မှာရေးပါ။\n\n"
        "ပယ်ဖျက်ချင်ရင် /cancel ကိုသုံးပါ။"
    )
    await state.set_state(BotStates.waiting_broadcast_video)

@dp.message(F.text == "📎 Send Document")
async def broadcast_document_prompt(message: Message, state: FSMContext):
    """Document broadcast"""
    if message.from_user.id != OWNER_ID:
        return
    
    await message.answer(
        "**Broadcast ပို့မယ့် ဖိုင်ကို ပို့ပါ။**\n"
        "ဖိုင်နဲ့အတူ စာသားပါထည့်ချင်ရင် Caption မှာရေးပါ။\n\n"
        "ပယ်ဖျက်ချင်ရင် /cancel ကိုသုံးပါ။"
    )
    await state.set_state(BotStates.waiting_broadcast_document)

@dp.message(BotStates.waiting_broadcast_text)
async def process_broadcast_text(message: Message, state: FSMContext):
    """Process broadcast text"""
    if message.text == "/cancel":
        await state.clear()
        await message.answer("လုပ်ဆောင်ချက်ကို ပယ်ဖျက်လိုက်သည်။")
        return
    
    await state.update_data(broadcast_text=message.text)
    
    await message.answer(
        "**Inline ခလုတ်တွေ ထည့်လို့ရပါတယ်။**\n\n"
        "ခလုတ်တစ်ခုချင်းစီကို အောက်ပါအတိုင်း ရိုက်ထည့်ပါ။\n\n"
        "**URL ခလုတ်:** `နာမည်|URL`\n"
        "**Callback ခလုတ်:** `နာမည်|callback:data`\n\n"
        "ခလုတ်တစ်ခုထည့်ပြီးရင် Enter နှိပ်ပါ။\n"
        "အကုန်ပြီးရင် `done` လို့ရိုက်ပါ။"
    )
    await state.set_state(BotStates.waiting_broadcast_buttons)

@dp.message(BotStates.waiting_broadcast_photo, F.photo)
async def process_broadcast_photo(message: Message, state: FSMContext):
    """Process broadcast photo"""
    photo = message.photo[-1]
    caption = message.caption or ""
    
    await state.update_data(
        broadcast_photo=photo.file_id,
        broadcast_caption=caption
    )
    
    await message.answer(
        "**Inline ခလုတ်တွေ ထည့်လို့ရပါတယ်။**\n\n"
        "ခလုတ်တစ်ခုချင်းစီကို အောက်ပါအတိုင်း ရိုက်ထည့်ပါ။\n\n"
        "**URL ခလုတ်:** `နာမည်|URL`\n"
        "**Callback ခလုတ်:** `နာမည်|callback:data`\n\n"
        "ခလုတ်တစ်ခုထည့်ပြီးရင် Enter နှိပ်ပါ။\n"
        "အကုန်ပြီးရင် `done` လို့ရိုက်ပါ။"
    )
    await state.set_state(BotStates.waiting_broadcast_buttons)

@dp.message(BotStates.waiting_broadcast_video, F.video)
async def process_broadcast_video(message: Message, state: FSMContext):
    """Process broadcast video"""
    video = message.video
    caption = message.caption or ""
    
    await state.update_data(
        broadcast_video=video.file_id,
        broadcast_caption=caption
    )
    
    await message.answer(
        "**Inline ခလုတ်တွေ ထည့်လို့ရပါတယ်။**\n\n"
        "ခလုတ်တစ်ခုချင်းစီကို အောက်ပါအတိုင်း ရိုက်ထည့်ပါ။\n\n"
        "**URL ခလုတ်:** `နာမည်|URL`\n"
        "**Callback ခလုတ်:** `နာမည်|callback:data`\n\n"
        "ခလုတ်တစ်ခုထည့်ပြီးရင် Enter နှိပ်ပါ။\n"
        "အကုန်ပြီးရင် `done` လို့ရိုက်ပါ။"
    )
    await state.set_state(BotStates.waiting_broadcast_buttons)

@dp.message(BotStates.waiting_broadcast_document, F.document)
async def process_broadcast_document(message: Message, state: FSMContext):
    """Process broadcast document"""
    document = message.document
    caption = message.caption or ""
    
    await state.update_data(
        broadcast_document=document.file_id,
        broadcast_caption=caption
    )
    
    await message.answer(
        "**Inline ခလုတ်တွေ ထည့်လို့ရပါတယ်။**\n\n"
        "ခလုတ်တစ်ခုချင်းစီကို အောက်ပါအတိုင်း ရိုက်ထည့်ပါ။\n\n"
        "**URL ခလုတ်:** `နာမည်|URL`\n"
        "**Callback ခလုတ်:** `နာမည်|callback:data`\n\n"
        "ခလုတ်တစ်ခုထည့်ပြီးရင် Enter နှိပ်ပါ။\n"
        "အကုန်ပြီးရင် `done` လို့ရိုက်ပါ။"
    )
    await state.set_state(BotStates.waiting_broadcast_buttons)

@dp.message(BotStates.waiting_broadcast_buttons)
async def process_broadcast_buttons(message: Message, state: FSMContext):
    """Process broadcast buttons"""
    data = await state.get_data()
    
    if message.text.lower() == "done":
        buttons = data.get("temp_buttons", [])
        
        # Show confirmation
        users_count = bot_data.get_users_count()
        
        if "broadcast_text" in data:
            preview = data["broadcast_text"][:100]
            msg_type = "Text"
        elif "broadcast_photo" in data:
            preview = "[Photo] " + data.get("broadcast_caption", "")[:100]
            msg_type = "Photo"
        elif "broadcast_video" in data:
            preview = "[Video] " + data.get("broadcast_caption", "")[:100]
            msg_type = "Video"
        elif "broadcast_document" in data:
            preview = "[Document] " + data.get("broadcast_caption", "")[:100]
            msg_type = "Document"
        else:
            preview = ""
            msg_type = "Unknown"
        
        confirm_text = (
            f"**📢 Broadcast အချက်အလက်များ**\n\n"
            f"**အမျိုးအစား:** {msg_type}\n"
            f"**လက်ခံသူဦးရေ:** {users_count} ယောက်\n"
            f"**ခလုတ်အရေအတွက်:** {len(buttons)} ခု\n\n"
            f"**စာသား:**\n{preview}\n\n"
            f"**ပို့မှာသေချာပါသလား?**"
        )
        
        await state.update_data(broadcast_buttons=buttons)
        await message.answer(
            confirm_text,
            reply_markup=get_confirmation_keyboard()
        )
        await state.set_state(BotStates.waiting_broadcast_confirm)
        return
    
    # Add button to temp list
    temp_buttons = data.get("temp_buttons", [])
    button = parse_buttons_text(message.text)
    if button:
        temp_buttons.extend(button)
        await state.update_data(temp_buttons=temp_buttons)
        await message.answer(f"✅ ခလုတ် '{message.text}' ကို ထည့်ပြီးပါပြီ။\nနောက်ထပ်ထည့်ချင်ရင် ဆက်ရိုက်ပါ။\nအကုန်ပြီးရင် `done` လို့ရိုက်ပါ။")
    else:
        await message.answer("❌ ခလုတ်ပုံစံမှားနေပါတယ်။ ထပ်ရိုက်ပါ။")

@dp.message(BotStates.waiting_broadcast_confirm, F.text == "✅ Confirm")
async def confirm_broadcast(message: Message, state: FSMContext):
    """Confirm and send broadcast"""
    data = await state.get_data()
    
    await message.answer("📢 Broadcast စတင်နေပါပြီ... ခဏစောင့်ပါ။")
    
    if "broadcast_text" in data:
        sent, failed, total = await send_broadcast(
            "text",
            data["broadcast_text"],
            data.get("broadcast_buttons", [])
        )
    elif "broadcast_photo" in data:
        sent, failed, total = await send_broadcast(
            "photo",
            {
                "file_id": data["broadcast_photo"],
                "caption": data.get("broadcast_caption", "")
            },
            data.get("broadcast_buttons", [])
        )
    elif "broadcast_video" in data:
        sent, failed, total = await send_broadcast(
            "video",
            {
                "file_id": data["broadcast_video"],
                "caption": data.get("broadcast_caption", "")
            },
            data.get("broadcast_buttons", [])
        )
    elif "broadcast_document" in data:
        sent, failed, total = await send_broadcast(
            "document",
            {
                "file_id": data["broadcast_document"],
                "caption": data.get("broadcast_caption", "")
            },
            data.get("broadcast_buttons", [])
        )
    
    await message.answer(
        f"**✅ Broadcast ပြီးဆုံးပါပြီ**\n\n"
        f"**စုစုပေါင်း:** {total} ယောက်\n"
        f"**ပို့ပြီး:** {sent} ယောက်\n"
        f"**မအောင်မြင်:** {failed} ယောက်",
        reply_markup=get_admin_keyboard()
    )
    await state.clear()

@dp.message(BotStates.waiting_broadcast_confirm, F.text == "❌ Cancel")
async def cancel_broadcast(message: Message, state: FSMContext):
    """Cancel broadcast"""
    await state.clear()
    await message.answer(
        "❌ Broadcast ကို ပယ်ဖျက်လိုက်သည်။",
        reply_markup=get_admin_keyboard()
    )

# ============================
# HANDLERS - STATISTICS
# ============================

@dp.message(F.text == "📊 Statistics")
async def show_statistics(message: Message):
    """Show statistics - 2026"""
    if message.from_user.id != OWNER_ID:
        return
    
    users = bot_data.get_all_users()
    buttons_count = len(bot_data.get_all_buttons())
    messages_count = sum(len(btn.get("messages", [])) for btn in bot_data.get_all_buttons())
    welcomes_count = len(bot_data.get_welcome_messages())
    active_welcome = bot_data.get_active_welcome()
    
    # Calculate levels distribution
    level_counts = defaultdict(int)
    for user_id in users:
        level = bot_data.get_user_level(user_id)
        level_counts[level] += 1
    
    levels_text = "\n".join([f"  Level {lvl}: {count} ယောက်" for lvl, count in sorted(level_counts.items())])
    
    stats_text = (
        f"**📊 စာရင်းအင်းများ (2026)**\n\n"
        f"**👤 အသုံးပြုသူများ**\n"
        f"စုစုပေါင်း: {len(users)} ယောက်\n"
        f"ယနေ့အသုံးပြုသူ: {len(bot_data.data['statistics']['daily_users'])} ယောက်\n\n"
        f"**📊 အဆင့်အလိုက်**\n{levels_text}\n\n"
        f"**🔧 ခလုတ်များ**\n"
        f"စုစုပေါင်း: {buttons_count} ခု\n"
        f"စုစုပေါင်းနှိပ်မှု: {bot_data.data['statistics']['total_buttons_click']} ကြိမ်\n\n"
        f"**📝 ပို့စ်များ**\n"
        f"စုစုပေါင်း: {messages_count} ခု\n"
        f"စုစုပေါင်း Messages: {bot_data.data['statistics']['total_messages']}\n\n"
        f"**👋 Welcome Messages**\n"
        f"စုစုပေါင်း: {welcomes_count} ခု\n"
        f"Active: {active_welcome['type']}\n"
        f"Random Mode: {'ON' if bot_data.get_random_mode() else 'OFF'}"
    )
    
    await message.answer(stats_text)

# ============================
# CANCEL HANDLER
# ============================

@dp.message(Command("cancel"))
async def cancel_command(message: Message, state: FSMContext):
    """Cancel current operation"""
    current_state = await state.get_state()
    if current_state is None:
        return
    
    await state.clear()
    await message.answer(
        "❌ လုပ်ဆောင်ချက်ကို ပယ်ဖျက်လိုက်သည်။",
        reply_markup=get_main_menu_keyboard(message.from_user.id)
    )

# ============================
# CALLBACK QUERY HANDLER
# ============================

@dp.callback_query()
async def handle_callback(callback: CallbackQuery):
    """Handle inline button callbacks"""
    await callback.answer()
    
    data = callback.data
    user_id = callback.from_user.id
    
    if data == "none":
        return
    
    elif data == "back":
        await callback.message.delete()
        await callback.message.answer(
            "ပင်မမီနူး",
            reply_markup=get_main_menu_keyboard(user_id)
        )
    
    elif data.startswith("level_"):
        level = data.split("_")[1]
        await callback.message.answer(f"သင်သည် Level {level} ဖြစ်ပါသည်။")

# ============================
# MAIN FUNCTION
# ============================

async def main():
    """Main function"""
    print("=" * 60)
    print("🤖 နက်ပြ ဘော့တ် - MenuBuilderBot 2026 Edition")
    print("=" * 60)
    print(f"👤 Owner ID: {OWNER_ID}")
    print(f"📊 Users: {bot_data.get_users_count()}")
    print(f"🔧 Buttons: {len(bot_data.get_all_buttons())}")
    print(f"📝 Messages: {sum(len(btn.get('messages', [])) for btn in bot_data.get_all_buttons())}")
    print(f"🎲 Random Mode: {'ON' if bot_data.get_random_mode() else 'OFF'}")
    print(f"🌐 Language: {bot_data.data['settings']['language']}")
    print("=" * 60)
    
    # Start auto backup if enabled
    if bot_data.data["backup"]["auto_backup"]:
        asyncio.create_task(auto_backup())
    
    await dp.start_polling(bot)

async def auto_backup():
    """Auto backup task"""
    while True:
        await asyncio.sleep(bot_data.data["backup"]["backup_interval"] * 3600)
        backup_id = bot_data.create_backup()
        logger.info(f"Auto backup created: {backup_id}")

if __name__ == "__main__":
    asyncio.run(main())
