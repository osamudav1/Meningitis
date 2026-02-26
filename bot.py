"""
နက်ပြ ဘော့တ် - အပြည့်အစုံ
Aiogram 3.17 ကိုသုံးထားသည်
"""

import os
import json
import asyncio
import logging
import uuid
import re
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
# DATA STRUCTURES
# ============================

class BotData:
    """ဘော့တ်ဒေတာကို JSON မှာသိမ်းမယ်"""
    
    def __init__(self, data_file="bot_data.json"):
        self.data_file = data_file
        self.data = self.load_data()
        self.broadcast_queue = asyncio.Queue()
        self.broadcast_active = False
        self.user_stats = defaultdict(lambda: {"messages": 0, "joined": None})
    
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
        """မူလဒေတာဖွဲ့စည်းပုံ"""
        return {
            "welcome": {
                "messages": [
                    {
                        "id": "welcome1",
                        "type": "text",
                        "content": "**{mention} ကြိုဆိုပါတယ်** 🎉\n\nအောက်ပါခလုတ်များကို နှိပ်ပြီး သွားရောက်ကြည့်ရှုနိုင်ပါတယ်။",
                        "buttons": []
                    }
                ],
                "active": "welcome1"
            },
            "buttons": {
                "main": [
                    {"id": "btn1", "name": "📺 2D Anime", "parent": None, "order": 0, "messages": []},
                    {"id": "btn2", "name": "🎬 3D Anime", "parent": None, "order": 1, "messages": []},
                    {"id": "btn3", "name": "🍿 Anime Movies", "parent": None, "order": 2, "messages": []},
                    {"id": "btn4", "name": "📢 Main Channel", "parent": None, "order": 3, "messages": []},
                    {"id": "btn5", "name": "💬 Fan Chat", "parent": None, "order": 4, "messages": []},
                    {"id": "btn6", "name": "📞 Contact", "parent": None, "order": 5, "messages": []}
                ],
                "submenus": {},
                "all_buttons": {}
            },
            "users": []
        }
    
    def get_welcome_messages(self) -> List[Dict]:
        """Welcome messages အားလုံးရယူမယ်"""
        return self.data["welcome"]["messages"]
    
    def get_active_welcome(self) -> Dict:
        """လက်ရှိ Welcome message ရယူမယ်"""
        active_id = self.data["welcome"]["active"]
        for msg in self.data["welcome"]["messages"]:
            if msg["id"] == active_id:
                return msg
        return self.data["welcome"]["messages"][0]
    
    def add_welcome_message(self, msg_type: str, content: Any, buttons: List = None) -> Dict:
        """Welcome message အသစ်ထည့်မယ်"""
        msg_id = str(uuid.uuid4())[:8]
        message = {
            "id": msg_id,
            "type": msg_type,
            "content": content,
            "buttons": buttons or [],
            "created_at": datetime.now().isoformat()
        }
        self.data["welcome"]["messages"].append(message)
        self.save_data()
        return message
    
    def update_welcome_message(self, msg_id: str, updates: Dict):
        """Welcome message ကိုပြင်မယ်"""
        for i, msg in enumerate(self.data["welcome"]["messages"]):
            if msg["id"] == msg_id:
                self.data["welcome"]["messages"][i].update(updates)
                self.save_data()
                return True
        return False
    
    def delete_welcome_message(self, msg_id: str):
        """Welcome message ကိုဖျက်မယ်"""
        self.data["welcome"]["messages"] = [
            msg for msg in self.data["welcome"]["messages"] 
            if msg["id"] != msg_id
        ]
        if self.data["welcome"]["active"] == msg_id:
            if self.data["welcome"]["messages"]:
                self.data["welcome"]["active"] = self.data["welcome"]["messages"][0]["id"]
            else:
                # Create default if empty
                default = self.add_welcome_message("text", "**{mention} ကြိုဆိုပါတယ်** 🎉", [])
                self.data["welcome"]["active"] = default["id"]
        self.save_data()
    
    def set_active_welcome(self, msg_id: str):
        """Welcome message ကို active လုပ်မယ်"""
        self.data["welcome"]["active"] = msg_id
        self.save_data()
    
    def get_main_buttons(self) -> List[Dict]:
        """ပင်မမီနူးခလုတ်များရယူမယ် (order စီထား)"""
        buttons = self.data["buttons"]["main"]
        return sorted(buttons, key=lambda x: x.get("order", 0))
    
    def get_sub_buttons(self, parent_id: str) -> List[Dict]:
        """ခလုတ်ခွဲများရယူမယ်"""
        return self.data["buttons"]["submenus"].get(parent_id, [])
    
    def get_all_buttons(self) -> List[Dict]:
        """ခလုတ်အားလုံးရယူမယ်"""
        all_buttons = []
        all_buttons.extend(self.data["buttons"]["main"])
        for parent, buttons in self.data["buttons"]["submenus"].items():
            all_buttons.extend(buttons)
        return all_buttons
    
    def add_button(self, name: str, parent: str = None) -> Dict:
        """ခလုတ်အသစ်ထည့်မယ်"""
        btn_id = str(uuid.uuid4())[:8]
        
        if parent is None:
            # Main menu button
            order = len(self.data["buttons"]["main"])
            new_button = {
                "id": btn_id,
                "name": name,
                "parent": None,
                "order": order,
                "messages": []
            }
            self.data["buttons"]["main"].append(new_button)
        else:
            # Submenu button
            if parent not in self.data["buttons"]["submenus"]:
                self.data["buttons"]["submenus"][parent] = []
            new_button = {
                "id": btn_id,
                "name": name,
                "parent": parent,
                "messages": []
            }
            self.data["buttons"]["submenus"][parent].append(new_button)
        
        # Add to all_buttons for quick access
        self.data["buttons"]["all_buttons"][btn_id] = new_button
        self.save_data()
        return new_button
    
    def rename_button(self, btn_id: str, new_name: str):
        """ခလုတ်နာမည်ပြောင်းမယ်"""
        # Main menu မှာရှာမယ်
        for btn in self.data["buttons"]["main"]:
            if btn["id"] == btn_id:
                btn["name"] = new_name
                self.save_data()
                return True
        
        # Submenu တွေမှာရှာမယ်
        for parent, buttons in self.data["buttons"]["submenus"].items():
            for btn in buttons:
                if btn["id"] == btn_id:
                    btn["name"] = new_name
                    self.save_data()
                    return True
        return False
    
    def delete_button(self, btn_id: str):
        """ခလုတ်ကိုဖျက်မယ်"""
        # Main menu မှာရှာမယ်
        self.data["buttons"]["main"] = [
            btn for btn in self.data["buttons"]["main"] 
            if btn["id"] != btn_id
        ]
        
        # Submenu တွေမှာရှာမယ်
        for parent in list(self.data["buttons"]["submenus"].keys()):
            self.data["buttons"]["submenus"][parent] = [
                btn for btn in self.data["buttons"]["submenus"][parent]
                if btn["id"] != btn_id
            ]
            if not self.data["buttons"]["submenus"][parent]:
                del self.data["buttons"]["submenus"][parent]
        
        # Remove from all_buttons
        if btn_id in self.data["buttons"]["all_buttons"]:
            del self.data["buttons"]["all_buttons"][btn_id]
        
        self.save_data()
    
    def move_button(self, btn_id: str, direction: str):
        """ခလုတ်နေရာရွှေ့မယ် (⬆️ ⬇️ ⬅️ ➡️)"""
        # Main menu မှာရှာမယ်
        for i, btn in enumerate(self.data["buttons"]["main"]):
            if btn["id"] == btn_id:
                if direction == "⬆️" and i > 0:
                    # Swap with previous
                    self.data["buttons"]["main"][i]["order"], self.data["buttons"]["main"][i-1]["order"] = \
                        self.data["buttons"]["main"][i-1]["order"], self.data["buttons"]["main"][i]["order"]
                    self.data["buttons"]["main"][i], self.data["buttons"]["main"][i-1] = \
                        self.data["buttons"]["main"][i-1], self.data["buttons"]["main"][i]
                elif direction == "⬇️" and i < len(self.data["buttons"]["main"]) - 1:
                    # Swap with next
                    self.data["buttons"]["main"][i]["order"], self.data["buttons"]["main"][i+1]["order"] = \
                        self.data["buttons"]["main"][i+1]["order"], self.data["buttons"]["main"][i]["order"]
                    self.data["buttons"]["main"][i], self.data["buttons"]["main"][i+1] = \
                        self.data["buttons"]["main"][i+1], self.data["buttons"]["main"][i]
                self.save_data()
                return True
        
        # Submenu မှာရှာမယ်
        for parent, buttons in self.data["buttons"]["submenus"].items():
            for i, btn in enumerate(buttons):
                if btn["id"] == btn_id:
                    if direction == "⬆️" and i > 0:
                        buttons[i], buttons[i-1] = buttons[i-1], buttons[i]
                    elif direction == "⬇️" and i < len(buttons) - 1:
                        buttons[i], buttons[i+1] = buttons[i+1], buttons[i]
                    elif direction == "⬅️":
                        # Move to parent's level (become main menu)
                        btn["parent"] = None
                        btn["order"] = len(self.data["buttons"]["main"])
                        self.data["buttons"]["main"].append(btn)
                        buttons.pop(i)
                    elif direction == "➡️":
                        # Ask for target parent (handled in UI)
                        pass
                    self.save_data()
                    return True
        return False
    
    def get_button(self, btn_id: str) -> Optional[Dict]:
        """ခလုတ်တစ်ခုကိုရှာမယ်"""
        # Check all_buttons cache
        if btn_id in self.data["buttons"]["all_buttons"]:
            return self.data["buttons"]["all_buttons"][btn_id]
        
        # Main menu မှာရှာမယ်
        for btn in self.data["buttons"]["main"]:
            if btn["id"] == btn_id:
                self.data["buttons"]["all_buttons"][btn_id] = btn
                return btn
        
        # Submenu တွေမှာရှာမယ်
        for parent, buttons in self.data["buttons"]["submenus"].items():
            for btn in buttons:
                if btn["id"] == btn_id:
                    self.data["buttons"]["all_buttons"][btn_id] = btn
                    return btn
        return None
    
    def add_message_to_button(self, btn_id: str, msg_type: str, content: Any, buttons: List = None) -> Dict:
        """ခလုတ်တစ်ခုအတွက် Message ထည့်မယ်"""
        btn = self.get_button(btn_id)
        if btn:
            msg_id = str(uuid.uuid4())[:8]
            message = {
                "id": msg_id,
                "type": msg_type,
                "content": content,
                "buttons": buttons or [],
                "created_at": datetime.now().isoformat()
            }
            if "messages" not in btn:
                btn["messages"] = []
            btn["messages"].append(message)
            self.save_data()
            return message
        return None
    
    def update_button_message(self, btn_id: str, msg_id: str, updates: Dict):
        """ခလုတ်ရဲ့ Message ကိုပြင်မယ်"""
        btn = self.get_button(btn_id)
        if btn and "messages" in btn:
            for i, msg in enumerate(btn["messages"]):
                if msg["id"] == msg_id:
                    btn["messages"][i].update(updates)
                    self.save_data()
                    return True
        return False
    
    def delete_button_message(self, btn_id: str, msg_id: str):
        """ခလုတ်ရဲ့ Message ကိုဖျက်မယ်"""
        btn = self.get_button(btn_id)
        if btn and "messages" in btn:
            btn["messages"] = [msg for msg in btn["messages"] if msg["id"] != msg_id]
            self.save_data()
            return True
        return False
    
    def add_user(self, user_id: int, username: str = None, first_name: str = None):
        """အသုံးပြုသူအသစ်ထည့်မယ် (broadcast အတွက်)"""
        if user_id not in [u["id"] for u in self.data["users"]]:
            self.data["users"].append({
                "id": user_id,
                "username": username,
                "first_name": first_name,
                "joined_at": datetime.now().isoformat()
            })
            self.save_data()
    
    def get_all_users(self) -> List[int]:
        """အသုံးပြုသူအားလုံးရယူမယ်"""
        return [u["id"] for u in self.data["users"]]

# Initialize bot data
bot_data = BotData()

# ============================
# STATES
# ============================

class BotStates(StatesGroup):
    """ဘော့တ် State များ"""
    # Welcome message states
    waiting_welcome_text = State()
    waiting_welcome_photo = State()
    waiting_welcome_buttons = State()
    waiting_welcome_select = State()
    
    # Button editor states
    waiting_button_name = State()
    waiting_button_rename = State()
    waiting_button_select = State()
    waiting_parent_select = State()
    waiting_move_target = State()
    
    # Message editor states
    waiting_message_text = State()
    waiting_message_photo = State()
    waiting_message_video = State()
    waiting_message_document = State()
    waiting_message_buttons = State()
    waiting_message_select = State()
    
    # Broadcast states
    waiting_broadcast_text = State()
    waiting_broadcast_photo = State()
    waiting_broadcast_buttons = State()
    waiting_broadcast_confirm = State()

# ============================
# KEYBOARD BUILDERS
# ============================

def get_main_menu_keyboard(user_id: int = None):
    """ပင်မမီနူးခလုတ်များ"""
    buttons = []
    
    # Main menu buttons from data
    main_buttons = bot_data.get_main_buttons()
    row = []
    for i, btn in enumerate(main_buttons):
        row.append(KeyboardButton(text=btn["name"]))
        if (i + 1) % 2 == 0:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    
    # Admin buttons for owner
    if user_id and user_id == OWNER_ID:
        buttons.append([KeyboardButton(text="⚙️ Admin Panel")])
    
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

def get_admin_keyboard():
    """အက်မင်မီနူးခလုတ်များ"""
    buttons = [
        [KeyboardButton(text="🔧 Button Editor")],
        [KeyboardButton(text="📝 Post Editor")],
        [KeyboardButton(text="👋 Welcome Editor")],
        [KeyboardButton(text="📢 Broadcast")],
        [KeyboardButton(text="📊 Statistics")],
        [KeyboardButton(text="🏠 Main Menu")]
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

def get_button_editor_keyboard():
    """ခလုတ်တည်းဖြတ်ခန်းမီနူး"""
    buttons = [
        [KeyboardButton(text="➕ Add Button")],
        [KeyboardButton(text="✏️ Rename Button")],
        [KeyboardButton(text="🗑 Delete Button")],
        [KeyboardButton(text="📂 Enter Button")],
        [KeyboardButton(text="⬆️ ⬇️ Move Button")],
        [KeyboardButton(text="🏠 Main Menu")]
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

def get_message_editor_keyboard(has_messages: bool = False):
    """Message တည်းဖြတ်ခန်းမီနူး"""
    buttons = [
        [KeyboardButton(text="➕ Add Message")],
        [KeyboardButton(text="📝 View Messages")],
    ]
    if has_messages:
        buttons.append([KeyboardButton(text="✏️ Edit Message")])
        buttons.append([KeyboardButton(text="🗑 Delete Message")])
    buttons.append([KeyboardButton(text="🔙 Back")])
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

def get_welcome_editor_keyboard():
    """Welcome message တည်းဖြတ်ခန်းမီနူး"""
    buttons = [
        [KeyboardButton(text="➕ Add Welcome")],
        [KeyboardButton(text="📝 View Welcomes")],
        [KeyboardButton(text="✏️ Edit Welcome")],
        [KeyboardButton(text="🗑 Delete Welcome")],
        [KeyboardButton(text="✅ Set Active")],
        [KeyboardButton(text="🔙 Back")]
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

def get_buttons_list_keyboard(buttons_list: List[Dict], back_text: str = "🔙 Back", show_move: bool = False):
    """ခလုတ်စာရင်းကို ကီးဘုတ်အဖြစ်ပြမယ်"""
    keyboard = []
    row = []
    for i, btn in enumerate(buttons_list):
        text = btn["name"]
        if show_move:
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

def parse_buttons_text(buttons_text: str) -> List[Dict]:
    """Button တွေကို parse လုပ်မယ် (ပုံစံ: Button1|url1, Button2|url2)"""
    buttons = []
    if not buttons_text:
        return buttons
    
    parts = buttons_text.split(",")
    for part in parts:
        part = part.strip()
        if "|" in part:
            name, url = part.split("|", 1)
            buttons.append({
                "text": name.strip(),
                "url": url.strip()
            })
        else:
            buttons.append({
                "text": part.strip(),
                "callback": "none"
            })
    return buttons

def format_welcome_message(text: str, user) -> str:
    """Welcome message ကို format လုပ်မယ် (mention, user_id, etc)"""
    replacements = {
        "{mention}": user.first_name or "User",
        "{user_id}": str(user.id),
        "{username}": f"@{user.username}" if user.username else "",
        "{fullname}": f"{user.first_name} {user.last_name or ''}".strip(),
        "{date}": datetime.now().strftime("%Y-%m-%d"),
        "{time}": datetime.now().strftime("%H:%M:%S")
    }
    
    for key, value in replacements.items():
        text = text.replace(key, value)
    
    return text

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
            
            # Rate limiting: 20 messages per second
            if (i + 1) % chunk_size == 0:
                await asyncio.sleep(delay)
                
        except Exception as e:
            logger.error(f"Failed to send to {user_id}: {e}")
            failed += 1
    
    bot_data.broadcast_active = False
    return sent, failed, total

def create_inline_keyboard(buttons: List[Dict]) -> Optional[InlineKeyboardMarkup]:
    """Inline keyboard ဖန်တီးမယ်"""
    if not buttons:
        return None
    
    inline_buttons = []
    for btn in buttons:
        if "url" in btn:
            inline_buttons.append([InlineKeyboardButton(text=btn["text"], url=btn["url"])])
        else:
            inline_buttons.append([InlineKeyboardButton(text=btn["text"], callback_data=btn.get("callback", "none"))])
    
    return InlineKeyboardMarkup(inline_keyboard=inline_buttons)

# ============================
# HANDLERS - START & WELCOME
# ============================

@dp.message(CommandStart())
async def cmd_start(message: Message):
    """Start command handler"""
    user = message.from_user
    user_id = user.id
    
    # Add user to database for broadcast
    bot_data.add_user(user_id, user.username, user.first_name)
    
    # Get active welcome message
    welcome = bot_data.get_active_welcome()
    
    # Format message with user data
    if welcome["type"] == "text":
        formatted_text = format_welcome_message(welcome["content"], user)
        await message.answer(
            formatted_text,
            reply_markup=get_main_menu_keyboard(user_id),
            reply_markup_inline=create_inline_keyboard(welcome.get("buttons", []))
        )
    elif welcome["type"] == "photo":
        formatted_caption = format_welcome_message(welcome["content"].get("caption", ""), user)
        await message.answer_photo(
            photo=welcome["content"]["file_id"],
            caption=formatted_caption,
            reply_markup=get_main_menu_keyboard(user_id),
            reply_markup_inline=create_inline_keyboard(welcome.get("buttons", []))
        )

# ============================
# HANDLERS - MAIN MENU BUTTONS
# ============================

@dp.message(F.text.in_([btn["name"] for btn in bot_data.get_main_buttons()]))
async def handle_main_buttons(message: Message):
    """ပင်မမီနူးခလုတ်များကို နှိပ်တဲ့အခါ"""
    btn_name = message.text
    
    # Find button in data
    for btn in bot_data.get_main_buttons():
        if btn["name"] == btn_name:
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
            return

# ============================
# HANDLERS - SUB MENU BUTTONS
# ============================

@dp.message(F.text.in_([btn["name"] for parent in bot_data.data["buttons"]["submenus"].values() for btn in parent]))
async def handle_sub_buttons(message: Message):
    """ခလုတ်ခွဲများကို နှိပ်တဲ့အခါ"""
    btn_name = message.text
    
    # Find sub-button
    for parent, buttons in bot_data.data["buttons"]["submenus"].items():
        for btn in buttons:
            if btn["name"] == btn_name:
                if btn.get("messages"):
                    for msg in btn["messages"]:
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
                return

# ============================
# HANDLERS - BACK BUTTON
# ============================

@dp.message(F.text == "🔙 Back")
async def go_back(message: Message, state: FSMContext):
    """Back ခလုတ်"""
    data = await state.get_data()
    parent_id = data.get("parent_id")
    
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

# ============================
# HANDLERS - ADMIN PANEL
# ============================

@dp.message(F.text == "⚙️ Admin Panel")
async def admin_panel(message: Message):
    """Admin Panel"""
    if message.from_user.id != OWNER_ID:
        await message.answer("ဒီနေရာကို ဝင်ခွင့်မရှိပါ။")
        return
    
    await message.answer(
        "အက်မင်မီနူး",
        reply_markup=get_admin_keyboard()
    )

@dp.message(F.text == "🏠 Main Menu")
async def back_to_main(message: Message, state: FSMContext):
    """Main Menu ကိုပြန်သွားမယ်"""
    await state.clear()
    await message.answer(
        "ပင်မမီနူး",
        reply_markup=get_main_menu_keyboard(message.from_user.id)
    )

# ============================
# HANDLERS - WELCOME EDITOR
# ============================

@dp.message(F.text == "👋 Welcome Editor")
async def welcome_editor(message: Message):
    """Welcome Editor"""
    if message.from_user.id != OWNER_ID:
        return
    
    await message.answer(
        "Welcome Message တည်းဖြတ်ခန်း\n\n"
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
    await state.set_state(BotStates.waiting_welcome_select)

@dp.message(BotStates.waiting_welcome_select, F.text == "📝 Text")
async def add_welcome_text(message: Message, state: FSMContext):
    """Welcome text ထည့်မယ်"""
    await message.answer(
        "Welcome message အနေနဲ့ ပြချင်တဲ့ စာသားကို ရိုက်ထည့်ပါ။\n\n"
        "Macros များ:\n"
        "{mention} - အသုံးပြုသူအမည်\n"
        "{user_id} - User ID\n"
        "{username} - Username\n"
        "{date} - ယနေ့ရက်စွဲ\n\n"
        "ပယ်ဖျက်ချင်ရင် /cancel ကိုသုံးပါ။"
    )
    await state.set_state(BotStates.waiting_welcome_text)

@dp.message(BotStates.waiting_welcome_select, F.text == "🖼 Photo")
async def add_welcome_photo(message: Message, state: FSMContext):
    """Welcome photo ထည့်မယ်"""
    await message.answer(
        "Welcome message အနေနဲ့ ပြချင်တဲ့ ဓာတ်ပုံကို ပို့ပါ။\n"
        "ဓာတ်ပုံနဲ့အတူ စာသားပါထည့်ချင်ရင် Caption မှာရေးပါ။\n\n"
        "Macros များ: {mention}, {user_id}, {username}, {date}\n\n"
        "ပယ်ဖျက်ချင်ရင် /cancel ကိုသုံးပါ။"
    )
    await state.set_state(BotStates.waiting_welcome_photo)

@dp.message(BotStates.waiting_welcome_text)
async def process_welcome_text(message: Message, state: FSMContext):
    """Welcome text ရပြီးသိမ်းမယ်"""
    if message.text == "/cancel":
        await state.clear()
        await message.answer("လုပ်ဆောင်ချက်ကို ပယ်ဖျက်လိုက်သည်။")
        return
    
    await state.update_data(welcome_text=message.text)
    
    await message.answer(
        "Inline ခလုတ်တွေ ထည့်ချင်ရင် အောက်ပါပုံစံအတိုင်း ရိုက်ထည့်ပါ။\n"
        "မထည့်ချင်ရင် 'skip' လို့ရိုက်ပါ။\n\n"
        "ပုံစံ: Button Name|URL, Button2|url2\n"
        "ဥပမာ: Channel|https://t.me/channel, Group|https://t.me/group"
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
        "Inline ခလုတ်တွေ ထည့်ချင်ရင် အောက်ပါပုံစံအတိုင်း ရိုက်ထည့်ပါ။\n"
        "မထည့်ချင်ရင် 'skip' လို့ရိုက်ပါ။\n\n"
        "ပုံစံ: Button Name|URL, Button2|url2\n"
        "ဥပမာ: Channel|https://t.me/channel, Group|https://t.me/group"
    )
    await state.set_state(BotStates.waiting_welcome_buttons)

@dp.message(BotStates.waiting_welcome_buttons)
async def process_welcome_buttons(message: Message, state: FSMContext):
    """Welcome buttons သိမ်းမယ်"""
    data = await state.get_data()
    buttons = []
    
    if message.text.lower() != "skip":
        buttons = parse_buttons_text(message.text)
    
    if "welcome_text" in data:
        # Save text message
        bot_data.add_welcome_message(
            "text",
            data["welcome_text"],
            buttons
        )
    elif "welcome_photo" in data:
        # Save photo message
        bot_data.add_welcome_message(
            "photo",
            {
                "file_id": data["welcome_photo"],
                "caption": data.get("welcome_caption", "")
            },
            buttons
        )
    
    await state.clear()
    await message.answer(
        "Welcome message ထည့်ပြီးပါပြီ။",
        reply_markup=get_welcome_editor_keyboard()
    )

@dp.message(F.text == "📝 View Welcomes")
async def view_welcomes(message: Message):
    """Welcome messages အားလုံးကြည့်မယ်"""
    if message.from_user.id != OWNER_ID:
        return
    
    welcomes = bot_data.get_welcome_messages()
    active_id = bot_data.data["welcome"]["active"]
    
    if not welcomes:
        await message.answer("Welcome message မရှိသေးပါ။")
        return
    
    text = "**Welcome Messages များ**\n\n"
    for i, welcome in enumerate(welcomes, 1):
        active = "✅ " if welcome["id"] == active_id else ""
        msg_type = welcome["type"]
        preview = welcome["content"][:50] + "..." if welcome["type"] == "text" else "[Photo]"
        text += f"{active}{i}. {msg_type}: {preview}\n"
    
    # Show buttons to select
    await message.answer(
        text,
        reply_markup=get_buttons_list_keyboard(
            [{"name": f"{'✅ ' if w['id']==active_id else ''}{w['type']}"} for w in welcomes],
            "🔙 Back"
        )
    )

@dp.message(F.text == "✏️ Edit Welcome")
async def edit_welcome(message: Message, state: FSMContext):
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
    await state.set_state("waiting_edit_welcome")

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
    await state.set_state("waiting_delete_welcome")

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
    await state.set_state("waiting_set_active")

@dp.message(F.text, F.state == "waiting_edit_welcome")
async def process_edit_welcome(message: Message, state: FSMContext):
    """Edit welcome selection"""
    welcomes = bot_data.get_welcome_messages()
    for i, welcome in enumerate(welcomes):
        if f"{welcome['type']}" in message.text or str(i+1) in message.text:
            await state.update_data(edit_welcome_id=welcome["id"])
            await message.answer(
                "အသစ်ပြင်ချင်တဲ့ စာသားကို ရိုက်ထည့်ပါ။",
                reply_markup=get_media_type_keyboard()
            )
            await state.set_state("waiting_edit_content")
            return

@dp.message(F.text, F.state == "waiting_delete_welcome")
async def process_delete_welcome(message: Message, state: FSMContext):
    """Delete welcome confirmation"""
    welcomes = bot_data.get_welcome_messages()
    for i, welcome in enumerate(welcomes):
        if f"{welcome['type']}" in message.text or str(i+1) in message.text:
            bot_data.delete_welcome_message(welcome["id"])
            await state.clear()
            await message.answer(
                "Welcome message ဖျက်ပြီးပါပြီ။",
                reply_markup=get_welcome_editor_keyboard()
            )
            return

@dp.message(F.text, F.state == "waiting_set_active")
async def process_set_active(message: Message, state: FSMContext):
    """Set active welcome"""
    welcomes = bot_data.get_welcome_messages()
    for i, welcome in enumerate(welcomes):
        if f"{welcome['type']}" in message.text or str(i+1) in message.text:
            bot_data.set_active_welcome(welcome["id"])
            await state.clear()
            await message.answer(
                f"Welcome message '{welcome['type']}' ကို active လုပ်ပြီးပါပြီ။",
                reply_markup=get_welcome_editor_keyboard()
            )
            return

# ============================
# HANDLERS - BUTTON EDITOR
# ============================

@dp.message(F.text == "🔧 Button Editor")
async def button_editor(message: Message):
    """Button Editor"""
    if message.from_user.id != OWNER_ID:
        return
    
    await message.answer(
        "ခလုတ်တည်းဖြတ်ခန်း\n\n"
        "ဘာလုပ်ချင်ပါသလဲ?",
        reply_markup=get_button_editor_keyboard()
    )

@dp.message(F.text == "➕ Add Button")
async def add_button_prompt(message: Message, state: FSMContext):
    """ခလုတ်အသစ်ထည့်မယ်"""
    if message.from_user.id != OWNER_ID:
        return
    
    await message.answer(
        "ခလုတ်နာမည်အသစ်ကို ရိုက်ထည့်ပါ။\n\n"
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
    keyboard = get_buttons_list_keyboard(main_buttons, "➕ Main Menu (Top Level)")
    
    await message.answer(
        "ဒီခလုတ်ကို ဘယ်နေရာမှာထည့်ချင်လဲ?\n"
        "အပေါ်ဆုံးအဆင့်မှာထည့်ချင်ရင် 'Main Menu (Top Level)' ကိုနှိပ်ပါ။",
        reply_markup=keyboard
    )
    await state.set_state(BotStates.waiting_parent_select)

@dp.message(BotStates.waiting_parent_select)
async def select_parent(message: Message, state: FSMContext):
    """ဘယ်နေရာမှာထည့်မလဲရွေးမယ်"""
    data = await state.get_data()
    button_name = data.get("new_button_name")
    
    if message.text == "➕ Main Menu (Top Level)":
        bot_data.add_button(button_name, parent=None)
        await state.clear()
        await message.answer(
            f"'{button_name}' ကို ပင်မမီနူးမှာ ထည့်ပြီးပါပြီ။",
            reply_markup=get_button_editor_keyboard()
        )
    else:
        # Find parent button
        for btn in bot_data.get_main_buttons():
            if btn["name"] == message.text:
                bot_data.add_button(button_name, parent=btn["id"])
                await state.clear()
                await message.answer(
                    f"'{button_name}' ကို '{btn['name']}' အောက်မှာ ထည့်ပြီးပါပြီ။",
                    reply_markup=get_button_editor_keyboard()
                )
                return

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
        "ဘယ်ခလုတ်ကို နာမည်ပြောင်းချင်လဲ ရွေးပါ။",
        reply_markup=get_buttons_list_keyboard(all_buttons)
    )
    await state.set_state(BotStates.waiting_button_rename)

@dp.message(BotStates.waiting_button_rename)
async def process_rename_select(message: Message, state: FSMContext):
    """နာမည်ပြောင်းမယ့်ခလုတ်ကိုရွေးပြီး"""
    all_buttons = bot_data.get_all_buttons()
    for btn in all_buttons:
        if btn["name"] == message.text:
            await state.update_data(rename_btn_id=btn["id"])
            await message.answer("နာမည်အသစ်ကို ရိုက်ထည့်ပါ။")
            await state.set_state("waiting_new_name")
            return

@dp.message(F.text, F.state == "waiting_new_name")
async def process_rename(message: Message, state: FSMContext):
    """နာမည်အသစ်သိမ်းမယ်"""
    data = await state.get_data()
    btn_id = data.get("rename_btn_id")
    
    if bot_data.rename_button(btn_id, message.text):
        await state.clear()
        await message.answer(
            "ခလုတ်နာမည်ပြောင်းပြီးပါပြီ။",
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
        "ဘယ်ခလုတ်ကို ဖျက်ချင်လဲ ရွေးပါ။",
        reply_markup=get_buttons_list_keyboard(all_buttons)
    )
    await state.set_state("waiting_delete_button")

@dp.message(F.text, F.state == "waiting_delete_button")
async def process_delete_button(message: Message, state: FSMContext):
    """ခလုတ်ဖျက်မယ်"""
    all_buttons = bot_data.get_all_buttons()
    for btn in all_buttons:
        if btn["name"] == message.text:
            bot_data.delete_button(btn["id"])
            await state.clear()
            await message.answer(
                "ခလုတ်ဖျက်ပြီးပါပြီ။",
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
        "ဘယ်ခလုတ်အတွင်းကို ဝင်ချင်လဲ ရွေးပါ။",
        reply_markup=get_buttons_list_keyboard(all_buttons)
    )
    await state.set_state(BotStates.waiting_button_select)

@dp.message(BotStates.waiting_button_select)
async def process_enter_button(message: Message, state: FSMContext):
    """ရွေးထားတဲ့ခလုတ်အတွင်းကိုဝင်မယ်"""
    all_buttons = bot_data.get_all_buttons()
    for btn in all_buttons:
        if btn["name"] == message.text:
            sub_buttons = bot_data.get_sub_buttons(btn["id"])
            await state.update_data(current_button_id=btn["id"], parent_id=btn.get("parent"))
            await message.answer(
                f"{btn['name']} အတွင်းရှိခလုတ်များ",
                reply_markup=get_buttons_list_keyboard(
                    sub_buttons if sub_buttons else 
                    [{"name": "(ခလုတ်ခွဲမရှိသေး)"}],
                    "🔙 Back to Admin"
                )
            )
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
        "ဘယ်ခလုတ်ကို နေရာရွှေ့ချင်လဲ ရွေးပါ။",
        reply_markup=get_buttons_list_keyboard(all_buttons, show_move=True)
    )
    await state.set_state("waiting_move_button")

@dp.message(F.text, F.state == "waiting_move_button")
async def select_move_button(message: Message, state: FSMContext):
    """နေရာရွှေ့မယ့်ခလုတ်ရွေးပြီး"""
    all_buttons = bot_data.get_all_buttons()
    for btn in all_buttons:
        if btn["name"] in message.text:
            await state.update_data(move_btn_id=btn["id"])
            await message.answer(
                "ဘယ်ဘက်ကိုရွှေ့ချင်လဲ ရွေးပါ။\n\n"
                "⬆️ Up - အပေါ်ကိုရွှေ့\n"
                "⬇️ Down - အောက်ကိုရွှေ့\n"
                "⬅️ Out - အပေါ်အဆင့်ကိုရွှေ့\n"
                "➡️ Into - အောက်အဆင့်ကိုရွှေ့ (ခလုတ်တစ်ခုခုအောက်ကိုရွှေ့)",
                reply_markup=get_move_buttons_keyboard()
            )
            await state.set_state("waiting_move_direction")
            return

@dp.message(F.text, F.state == "waiting_move_direction")
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
            "ဘယ်ခလုတ်အောက်ကိုရွှေ့ချင်လဲ ရွေးပါ။",
            reply_markup=get_buttons_list_keyboard(all_buttons)
        )
        await state.set_state("waiting_move_target")
        return
    
    if bot_data.move_button(btn_id, message.text):
        await message.answer(
            "ခလုတ်နေရာရွှေ့ပြီးပါပြီ။",
            reply_markup=get_button_editor_keyboard()
        )
        await state.clear()
    else:
        await message.answer("နေရာရွှေ့လို့မရပါ။")

# ============================
# HANDLERS - POST EDITOR
# ============================

@dp.message(F.text == "📝 Post Editor")
async def post_editor(message: Message, state: FSMContext):
    """Post Editor"""
    if message.from_user.id != OWNER_ID:
        return
    
    all_buttons = bot_data.get_all_buttons()
    if not all_buttons:
        await message.answer("ခလုတ်မရှိသေးပါ။")
        return
    
    await message.answer(
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
            has_messages = bool(btn.get("messages"))
            await message.answer(
                f"**{btn['name']}** အတွက် ပို့စ်တည်းဖြတ်ခန်း",
                reply_markup=get_message_editor_keyboard(has_messages)
            )
            return

@dp.message(F.text == "➕ Add Message")
async def add_message_prompt(message: Message, state: FSMContext):
    """Message အသစ်ထည့်မယ်"""
    data = await state.get_data()
    btn_id = data.get("post_btn_id")
    
    if not btn_id:
        await message.answer("အရင်ဆုံး ခလုတ်တစ်ခုကို ရွေးပါ။")
        return
    
    await message.answer(
        "ဘယ်လိုအမျိုးအစား ထည့်ချင်လဲ?",
        reply_markup=get_media_type_keyboard()
    )
    await state.set_state("waiting_message_type")

@dp.message(F.text == "📝 Text", F.state == "waiting_message_type")
async def add_text_message_prompt(message: Message, state: FSMContext):
    """Text message ထည့်မယ်"""
    await message.answer(
        "ပို့စ်အနေနဲ့ ပြချင်တဲ့ စာသားကို ရိုက်ထည့်ပါ။\n\n"
        "ပယ်ဖျက်ချင်ရင် /cancel ကိုသုံးပါ။"
    )
    await state.set_state(BotStates.waiting_message_text)

@dp.message(F.text == "🖼 Photo", F.state == "waiting_message_type")
async def add_photo_message_prompt(message: Message, state: FSMContext):
    """Photo message ထည့်မယ်"""
    await message.answer(
        "ပို့စ်အနေနဲ့ ပြချင်တဲ့ ဓာတ်ပုံကို ပို့ပါ။\n"
        "ဓာတ်ပုံနဲ့အတူ စာသားပါထည့်ချင်ရင် Caption မှာရေးပါ။\n\n"
        "ပယ်ဖျက်ချင်ရင် /cancel ကိုသုံးပါ။"
    )
    await state.set_state(BotStates.waiting_message_photo)

@dp.message(BotStates.waiting_message_text)
async def process_text_message(message: Message, state: FSMContext):
    """Text message သိမ်းမယ်"""
    if message.text == "/cancel":
        await state.clear()
        await message.answer("လုပ်ဆောင်ချက်ကို ပယ်ဖျက်လိုက်သည်။")
        return
    
    await state.update_data(message_text=message.text)
    
    await message.answer(
        "Inline ခလုတ်တွေ ထည့်ချင်ရင် အောက်ပါပုံစံအတိုင်း ရိုက်ထည့်ပါ။\n"
        "မထည့်ချင်ရင် 'skip' လို့ရိုက်ပါ။\n\n"
        "ပုံစံ: Button Name|URL, Button2|url2\n"
        "ဥပမာ: Channel|https://t.me/channel, Group|https://t.me/group"
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
        "Inline ခလုတ်တွေ ထည့်ချင်ရင် အောက်ပါပုံစံအတိုင်း ရိုက်ထည့်ပါ။\n"
        "မထည့်ချင်ရင် 'skip' လို့ရိုက်ပါ။\n\n"
        "ပုံစံ: Button Name|URL, Button2|url2\n"
        "ဥပမာ: Channel|https://t.me/channel, Group|https://t.me/group"
    )
    await state.set_state(BotStates.waiting_message_buttons)

@dp.message(BotStates.waiting_message_buttons)
async def process_message_buttons(message: Message, state: FSMContext):
    """Message buttons သိမ်းမယ်"""
    data = await state.get_data()
    btn_id = data.get("post_btn_id")
    buttons = []
    
    if message.text.lower() != "skip":
        buttons = parse_buttons_text(message.text)
    
    if "message_text" in data:
        # Save text message
        bot_data.add_message_to_button(
            btn_id,
            "text",
            data["message_text"],
            buttons
        )
    elif "message_photo" in data:
        # Save photo message
        bot_data.add_message_to_button(
            btn_id,
            "photo",
            {
                "file_id": data["message_photo"],
                "caption": data.get("message_caption", "")
            },
            buttons
        )
    
    btn = bot_data.get_button(btn_id)
    await state.update_data(post_btn_id=btn_id, post_btn_name=btn["name"])
    
    await message.answer(
        "Message ထည့်ပြီးပါပြီ။",
        reply_markup=get_message_editor_keyboard(True)
    )

@dp.message(F.text == "📝 View Messages")
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
        preview = msg["content"][:50] + "..." if msg_type == "text" else "[Photo]"
        msg_text += f"{i}. {msg_type}: {preview}\n"
    
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
        "ဘယ် Message ကို ပြင်ချင်လဲ ရွေးပါ။",
        reply_markup=get_buttons_list_keyboard(msg_list)
    )
    await state.set_state("waiting_edit_message")

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
        "ဘယ် Message ကို ဖျက်ချင်လဲ ရွေးပါ။",
        reply_markup=get_buttons_list_keyboard(msg_list)
    )
    await state.set_state("waiting_delete_message")

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
    
    await message.answer(
        "Broadcast ပို့ရန်အတွက် အမျိုးအစားရွေးပါ။\n\n"
        "စုစုပေါင်းအသုံးပြုသူ: **{}** ယောက်".format(len(bot_data.get_all_users())),
        reply_markup=get_broadcast_keyboard()
    )

@dp.message(F.text == "📝 Send Text")
async def broadcast_text_prompt(message: Message, state: FSMContext):
    """Text broadcast"""
    if message.from_user.id != OWNER_ID:
        return
    
    await message.answer(
        "Broadcast ပို့မယ့် စာသားကို ရိုက်ထည့်ပါ။\n\n"
        "ပယ်ဖျက်ချင်ရင် /cancel ကိုသုံးပါ။"
    )
    await state.set_state(BotStates.waiting_broadcast_text)

@dp.message(F.text == "🖼 Send Photo")
async def broadcast_photo_prompt(message: Message, state: FSMContext):
    """Photo broadcast"""
    if message.from_user.id != OWNER_ID:
        return
    
    await message.answer(
        "Broadcast ပို့မယ့် ဓာတ်ပုံကို ပို့ပါ။\n"
        "ဓာတ်ပုံနဲ့အတူ စာသားပါထည့်ချင်ရင် Caption မှာရေးပါ။\n\n"
        "ပယ်ဖျက်ချင်ရင် /cancel ကိုသုံးပါ။"
    )
    await state.set_state(BotStates.waiting_broadcast_photo)

@dp.message(BotStates.waiting_broadcast_text)
async def process_broadcast_text(message: Message, state: FSMContext):
    """Process broadcast text"""
    if message.text == "/cancel":
        await state.clear()
        await message.answer("လုပ်ဆောင်ချက်ကို ပယ်ဖျက်လိုက်သည်။")
        return
    
    await state.update_data(broadcast_text=message.text)
    
    await message.answer(
        "Inline ခလုတ်တွေ ထည့်ချင်ရင် အောက်ပါပုံစံအတိုင်း ရိုက်ထည့်ပါ။\n"
        "မထည့်ချင်ရင် 'skip' လို့ရိုက်ပါ။\n\n"
        "ပုံစံ: Button Name|URL, Button2|url2\n"
        "ဥပမာ: Channel|https://t.me/channel, Group|https://t.me/group"
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
        "Inline ခလုတ်တွေ ထည့်ချင်ရင် အောက်ပါပုံစံအတိုင်း ရိုက်ထည့်ပါ။\n"
        "မထည့်ချင်ရင် 'skip' လို့ရိုက်ပါ။\n\n"
        "ပုံစံ: Button Name|URL, Button2|url2\n"
        "ဥပမာ: Channel|https://t.me/channel, Group|https://t.me/group"
    )
    await state.set_state(BotStates.waiting_broadcast_buttons)

@dp.message(BotStates.waiting_broadcast_buttons)
async def process_broadcast_buttons(message: Message, state: FSMContext):
    """Process broadcast buttons"""
    data = await state.get_data()
    buttons = []
    
    if message.text.lower() != "skip":
        buttons = parse_buttons_text(message.text)
    
    await state.update_data(broadcast_buttons=buttons)
    
    # Show confirmation
    users_count = len(bot_data.get_all_users())
    
    if "broadcast_text" in data:
        preview = data["broadcast_text"][:100]
        msg_type = "Text"
    else:
        preview = "[Photo] " + data.get("broadcast_caption", "")[:100]
        msg_type = "Photo"
    
    confirm_text = (
        f"**Broadcast အချက်အလက်များ**\n\n"
        f"အမျိုးအစား: {msg_type}\n"
        f"လက်ခံသူဦးရေ: {users_count} ယောက်\n"
        f"ခလုတ်အရေအတွက်: {len(buttons)} ခု\n\n"
        f"**စာသား:**\n{preview}\n\n"
        f"ပို့မှာသေချာပါသလား?"
    )
    
    await message.answer(
        confirm_text,
        reply_markup=get_confirmation_keyboard()
    )
    await state.set_state(BotStates.waiting_broadcast_confirm)

@dp.message(BotStates.waiting_broadcast_confirm, F.text == "✅ Confirm")
async def confirm_broadcast(message: Message, state: FSMContext):
    """Confirm and send broadcast"""
    data = await state.get_data()
    
    await message.answer("Broadcast စတင်နေပါပြီ... ခဏစောင့်ပါ။")
    
    if "broadcast_text" in data:
        # Text broadcast
        sent, failed, total = await send_broadcast(
            "text",
            data["broadcast_text"],
            data.get("broadcast_buttons", [])
        )
    else:
        # Photo broadcast
        sent, failed, total = await send_broadcast(
            "photo",
            {
                "file_id": data["broadcast_photo"],
                "caption": data.get("broadcast_caption", "")
            },
            data.get("broadcast_buttons", [])
        )
    
    await message.answer(
        f"**Broadcast ပြီးဆုံးပါပြီ**\n\n"
        f"စုစုပေါင်း: {total} ယောက်\n"
        f"ပို့ပြီး: {sent} ယောက်\n"
        f"မအောင်မြင်: {failed} ယောက်",
        reply_markup=get_admin_keyboard()
    )
    await state.clear()

@dp.message(BotStates.waiting_broadcast_confirm, F.text == "❌ Cancel")
async def cancel_broadcast(message: Message, state: FSMContext):
    """Cancel broadcast"""
    await state.clear()
    await message.answer(
        "Broadcast ကို ပယ်ဖျက်လိုက်သည်။",
        reply_markup=get_admin_keyboard()
    )

# ============================
# HANDLERS - STATISTICS
# ============================

@dp.message(F.text == "📊 Statistics")
async def show_statistics(message: Message):
    """Show statistics"""
    if message.from_user.id != OWNER_ID:
        return
    
    users = bot_data.get_all_users()
    buttons_count = len(bot_data.get_all_buttons())
    messages_count = sum(len(btn.get("messages", [])) for btn in bot_data.get_all_buttons())
    
    stats_text = (
        f"**📊 စာရင်းအင်းများ**\n\n"
        f"**အသုံးပြုသူများ**\n"
        f"စုစုပေါင်း: {len(users)} ယောက်\n\n"
        f"**ခလုတ်များ**\n"
        f"စုစုပေါင်း: {buttons_count} ခု\n\n"
        f"**ပို့စ်များ**\n"
        f"စုစုပေါင်း: {messages_count} ခု\n\n"
        f"**Welcome Messages**\n"
        f"စုစုပေါင်း: {len(bot_data.get_welcome_messages())} ခု\n"
        f"Active: {bot_data.get_active_welcome()['type']}"
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
        "လုပ်ဆောင်ချက်ကို ပယ်ဖျက်လိုက်သည်။",
        reply_markup=get_main_menu_keyboard(message.from_user.id)
    )

# ============================
# MAIN FUNCTION
# ============================

async def main():
    """Main function"""
    print("🤖 menu ဘော့တ် စတင်နေပါပြီ...")
    print(f"👤 Owner ID: {OWNER_ID}")
    print(f"📊 Users: {len(bot_data.get_all_users())}")
    print(f"🔧 Buttons: {len(bot_data.get_all_buttons())}")
    
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
