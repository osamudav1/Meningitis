"""
နက်ပြ ဘော့တ် - အပြည့်အစုံ (Welcome Message with 2-Row Buttons)
"""

import os
import json
import asyncio
import logging
import uuid
from typing import Dict, List, Any, Optional
from datetime import datetime
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, F
from aiogram.types import (
    Message, 
    CallbackQuery,  # ✅ ဒီမှာ CallbackQuery ကို ထည့်ထားပါတယ်
    ReplyKeyboardMarkup, 
    KeyboardButton,
    InlineKeyboardMarkup, 
    InlineKeyboardButton
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
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize bot and dispatcher
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# ============================
# MODES
# ============================

user_modes = {}  # {user_id: "main" or "button_edit" or "post_edit"}

# ============================
# DATA STRUCTURES
# ============================

class BotData:
    def __init__(self, data_file="bot_data.json"):
        self.data_file = data_file
        self.data = self.load_data()
        self.current_editing = {}  # {user_id: {"button_id": "...", "parent_id": "..."}}
    
    def load_data(self) -> Dict:
        if os.path.exists(self.data_file):
            try:
                with open(self.data_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error loading data: {e}")
                return self.get_default_data()
        return self.get_default_data()
    
    def save_data(self):
        try:
            with open(self.data_file, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Error saving data: {e}")
    
    def get_default_data(self) -> Dict:
        return {
            "welcome": {
                "type": "text",
                "content": "**{mention} ကြိုဆိုပါတယ်** 🎉\n\nအောက်ပါခလုတ်များကို နှိပ်ပြီး သွားရောက်ကြည့်ရှုနိုင်ပါတယ်။",
                "buttons": [
                    # Row 1
                    [
                        {"text": "📢 Main Channel", "url": "https://t.me/yourchannel"},
                        {"text": "💬 Fan Chat", "url": "https://t.me/yourgroup"}
                    ],
                    # Row 2
                    [
                        {"text": "📺 2D Anime", "callback": "2d_anime"},
                        {"text": "🎬 3D Anime", "callback": "3d_anime"}
                    ]
                ]
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
                "submenus": {}
            },
            "users": []
        }
    
    # User management
    def add_user(self, user_id: int, username: str = None, first_name: str = None):
        if user_id not in [u["id"] for u in self.data["users"]]:
            self.data["users"].append({
                "id": user_id,
                "username": username,
                "first_name": first_name,
                "joined_at": datetime.now().isoformat()
            })
            self.save_data()
            return True
        return False
    
    def get_all_users(self) -> List[int]:
        return [u["id"] for u in self.data["users"]]
    
    def get_users_count(self) -> int:
        return len(self.data["users"])
    
    # Welcome message
    def get_welcome(self) -> Dict:
        return self.data["welcome"]
    
    def set_welcome(self, msg_type: str, content: Any, buttons: List = None):
        self.data["welcome"] = {
            "type": msg_type,
            "content": content,
            "buttons": buttons or []
        }
        self.save_data()
    
    # Buttons
    def get_main_buttons(self) -> List[Dict]:
        return sorted(self.data["buttons"]["main"], key=lambda x: x.get("order", 0))
    
    def get_sub_buttons(self, parent_id: str) -> List[Dict]:
        return self.data["buttons"]["submenus"].get(parent_id, [])
    
    def get_all_buttons(self) -> List[Dict]:
        all_buttons = self.get_main_buttons().copy()
        for parent, buttons in self.data["buttons"]["submenus"].items():
            all_buttons.extend(buttons)
        return all_buttons
    
    def get_button(self, btn_id: str) -> Optional[Dict]:
        for btn in self.data["buttons"]["main"]:
            if btn["id"] == btn_id:
                return btn
        for parent, buttons in self.data["buttons"]["submenus"].items():
            for btn in buttons:
                if btn["id"] == btn_id:
                    return btn
        return None
    
    def add_button(self, name: str, parent: str = None) -> Dict:
        btn_id = str(uuid.uuid4())[:8]
        
        if parent is None:
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
            if parent not in self.data["buttons"]["submenus"]:
                self.data["buttons"]["submenus"][parent] = []
            new_button = {
                "id": btn_id,
                "name": name,
                "parent": parent,
                "messages": []
            }
            self.data["buttons"]["submenus"][parent].append(new_button)
        
        self.save_data()
        return new_button
    
    def rename_button(self, btn_id: str, new_name: str) -> bool:
        btn = self.get_button(btn_id)
        if btn:
            btn["name"] = new_name
            self.save_data()
            return True
        return False
    
    def delete_button(self, btn_id: str):
        # Remove from main
        self.data["buttons"]["main"] = [btn for btn in self.data["buttons"]["main"] if btn["id"] != btn_id]
        
        # Remove from submenus
        for parent in list(self.data["buttons"]["submenus"].keys()):
            self.data["buttons"]["submenus"][parent] = [btn for btn in self.data["buttons"]["submenus"][parent] if btn["id"] != btn_id]
            if not self.data["buttons"]["submenus"][parent]:
                del self.data["buttons"]["submenus"][parent]
        
        self.save_data()
    
    def move_button(self, btn_id: str, direction: str) -> bool:
        # Main menu
        for i, btn in enumerate(self.data["buttons"]["main"]):
            if btn["id"] == btn_id:
                if direction == "⬆️" and i > 0:
                    self.data["buttons"]["main"][i], self.data["buttons"]["main"][i-1] = \
                        self.data["buttons"]["main"][i-1], self.data["buttons"]["main"][i]
                    for j, b in enumerate(self.data["buttons"]["main"]):
                        b["order"] = j
                    self.save_data()
                    return True
                elif direction == "⬇️" and i < len(self.data["buttons"]["main"]) - 1:
                    self.data["buttons"]["main"][i], self.data["buttons"]["main"][i+1] = \
                        self.data["buttons"]["main"][i+1], self.data["buttons"]["main"][i]
                    for j, b in enumerate(self.data["buttons"]["main"]):
                        b["order"] = j
                    self.save_data()
                    return True
                return False
        
        # Submenu
        for parent, buttons in self.data["buttons"]["submenus"].items():
            for i, btn in enumerate(buttons):
                if btn["id"] == btn_id:
                    if direction == "⬆️" and i > 0:
                        buttons[i], buttons[i-1] = buttons[i-1], buttons[i]
                        self.save_data()
                        return True
                    elif direction == "⬇️" and i < len(buttons) - 1:
                        buttons[i], buttons[i+1] = buttons[i+1], buttons[i]
                        self.save_data()
                        return True
                    elif direction == "⬅️":
                        # Move to main menu
                        btn["parent"] = None
                        btn["order"] = len(self.data["buttons"]["main"])
                        self.data["buttons"]["main"].append(btn)
                        buttons.pop(i)
                        if not buttons:
                            del self.data["buttons"]["submenus"][parent]
                        self.save_data()
                        return True
        return False
    
    # Messages
    def add_message_to_button(self, btn_id: str, msg_type: str, content: Any, buttons: List = None) -> Optional[Dict]:
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
    
    def get_button_messages(self, btn_id: str) -> List[Dict]:
        btn = self.get_button(btn_id)
        return btn.get("messages", []) if btn else []
    
    def delete_message(self, btn_id: str, msg_id: str) -> bool:
        btn = self.get_button(btn_id)
        if btn and "messages" in btn:
            btn["messages"] = [msg for msg in btn["messages"] if msg["id"] != msg_id]
            self.save_data()
            return True
        return False
    
    def update_message_buttons(self, btn_id: str, msg_id: str, buttons: List[Dict]) -> bool:
        btn = self.get_button(btn_id)
        if btn and "messages" in btn:
            for msg in btn["messages"]:
                if msg["id"] == msg_id:
                    msg["buttons"] = buttons
                    self.save_data()
                    return True
        return False

# Initialize
bot_data = BotData()

# ============================
# FORMATTER
# ============================

def format_text(text: str, user) -> str:
    replacements = {
        "{mention}": user.first_name or "User",
        "{user_id}": str(user.id),
        "{username}": f"@{user.username}" if user.username else "",
        "{fullname}": f"{user.first_name or ''} {user.last_name or ''}".strip(),
        "{date}": datetime.now().strftime("%Y-%m-%d"),
        "{time}": datetime.now().strftime("%H:%M:%S")
    }
    for key, value in replacements.items():
        text = text.replace(key, value)
    return text

def create_inline_keyboard(buttons: List) -> Optional[InlineKeyboardMarkup]:
    """Create inline keyboard with 2 rows support"""
    if not buttons:
        return None
    
    inline_buttons = []
    
    # If buttons is a list of lists (2 rows)
    if isinstance(buttons, list) and len(buttons) > 0 and isinstance(buttons[0], list):
        for row in buttons:
            row_buttons = []
            for btn in row:
                if "url" in btn:
                    row_buttons.append(InlineKeyboardButton(text=btn["text"], url=btn["url"]))
                elif "callback" in btn:
                    row_buttons.append(InlineKeyboardButton(text=btn["text"], callback_data=btn["callback"]))
                else:
                    row_buttons.append(InlineKeyboardButton(text=btn["text"], callback_data="none"))
            inline_buttons.append(row_buttons)
    else:
        # Old format (single list)
        for btn in buttons:
            if "url" in btn:
                inline_buttons.append([InlineKeyboardButton(text=btn["text"], url=btn["url"])])
            elif "callback" in btn:
                inline_buttons.append([InlineKeyboardButton(text=btn["text"], callback_data=btn["callback"])])
            else:
                inline_buttons.append([InlineKeyboardButton(text=btn["text"], callback_data="none")])
    
    return InlineKeyboardMarkup(inline_keyboard=inline_buttons)

def parse_buttons_text(buttons_text: str) -> List:
    """Parse buttons text - supports multiple rows with --- separator"""
    buttons = []
    if not buttons_text or buttons_text.lower() == "skip":
        return buttons
    
    # Split by --- for multiple rows
    rows = buttons_text.split("---")
    
    for row in rows:
        row = row.strip()
        if not row:
            continue
        
        row_buttons = []
        parts = row.split(",")
        for part in parts:
            part = part.strip()
            if not part:
                continue
            if "|" in part:
                name, value = part.split("|", 1)
                name = name.strip()
                value = value.strip()
                if value.startswith("http"):
                    row_buttons.append({"text": name, "url": value})
                else:
                    row_buttons.append({"text": name, "callback": value})
            else:
                row_buttons.append({"text": part, "callback": "none"})
        
        if row_buttons:
            buttons.append(row_buttons)
    
    return buttons

# ============================
# KEYBOARDS
# ============================

def get_main_menu_keyboard(user_id: int = None):
    buttons = []
    main_buttons = bot_data.get_main_buttons()
    
    row = []
    for i, btn in enumerate(main_buttons):
        row.append(KeyboardButton(text=btn["name"]))
        if (i + 1) % 2 == 0:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    
    # Mode buttons for owner
    if user_id == OWNER_ID:
        mode = user_modes.get(user_id, "main")
        if mode == "main":
            mode_text = "⚙️ Main Mode"
        elif mode == "button_edit":
            mode_text = "🔧 Button Edit Mode"
        else:
            mode_text = "📝 Post Edit Mode"
        
        buttons.append([KeyboardButton(text=mode_text)])
        buttons.append([
            KeyboardButton(text="➕ Add Button"),
            KeyboardButton(text="👋 Welcome Editor")
        ])
    
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

def get_edit_buttons_keyboard():
    """ခလုတ်တစ်ခုကိုနှိပ်ရင် ပြမယ့်ခလုတ်တွေ"""
    buttons = [
        [KeyboardButton(text="⬅️"), KeyboardButton(text="⬇️"), 
         KeyboardButton(text="⬆️"), KeyboardButton(text="➡️"), KeyboardButton(text="*️⃣")],
        [KeyboardButton(text="⏹ Stop Edit")]
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

def get_post_edit_buttons_keyboard():
    """Post Edit Mode မှာ ပြမယ့်ခလုတ်တွေ"""
    buttons = [
        [KeyboardButton(text="➕ Add Message")],
        [KeyboardButton(text="➕ Add Question")],
        [KeyboardButton(text="⏹ Stop Editor")]
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

def get_message_edit_buttons_keyboard():
    """Message တစ်ခုကိုနှိပ်ရင် ပြမယ့်ခလုတ်တွေ"""
    buttons = [
        [KeyboardButton(text="⬅️"), KeyboardButton(text="⬇️"), 
         KeyboardButton(text="⬆️"), KeyboardButton(text="➡️"), KeyboardButton(text="*️⃣")],
        [KeyboardButton(text="⏹ Stop Editor")]
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

def get_confirmation_keyboard():
    buttons = [[KeyboardButton(text="✅ Confirm"), KeyboardButton(text="❌ Cancel")]]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

# ============================
# STATES
# ============================

class BotStates(StatesGroup):
    waiting_button_name = State()
    waiting_button_rename = State()
    waiting_parent_select = State()
    waiting_message_text = State()
    waiting_message_photo = State()
    waiting_question = State()
    waiting_inline_button = State()
    waiting_welcome_text = State()
    waiting_welcome_photo = State()
    waiting_welcome_buttons = State()

# ============================
# HANDLERS - START
# ============================

@dp.message(CommandStart())
async def cmd_start(message: Message):
    user = message.from_user
    user_id = user.id
    
    # Add user
    is_new = bot_data.add_user(user_id, user.username, user.first_name)
    
    # Reset mode
    user_modes[user_id] = "main"
    
    # Send notification to owner if new user
    if is_new and user_id != OWNER_ID:
        try:
            total = bot_data.get_users_count()
            await bot.send_message(
                OWNER_ID,
                f"**👤 အသုံးပြုသူအသစ်**\n\n"
                f"**အမည်:** {format_text('{fullname}', user)}\n"
                f"**Username:** {format_text('{username}', user)}\n"
                f"**User ID:** `{user_id}`\n"
                f"**စုစုပေါင်း:** {total} ယောက်"
            )
        except Exception as e:
            logger.error(f"Failed to send notification: {e}")
    
    # Get welcome
    welcome = bot_data.get_welcome()
    
    # Format message with user data
    if welcome["type"] == "text":
        formatted = format_text(welcome["content"], user)
        await message.answer(
            formatted,
            reply_markup=get_main_menu_keyboard(user_id),
            reply_markup=create_inline_keyboard(welcome.get("buttons", []))
        )
    elif welcome["type"] == "photo":
        caption = format_text(welcome["content"].get("caption", ""), user)
        await message.answer_photo(
            photo=welcome["content"]["file_id"],
            caption=caption,
            reply_markup=get_main_menu_keyboard(user_id),
            reply_markup=create_inline_keyboard(welcome.get("buttons", []))
        )

# ============================
# HANDLERS - MODE TOGGLE
# ============================

@dp.message(F.text.in_(["⚙️ Main Mode", "🔧 Button Edit Mode", "📝 Post Edit Mode"]))
async def toggle_mode(message: Message):
    user_id = message.from_user.id
    if user_id != OWNER_ID:
        return
    
    if message.text == "⚙️ Main Mode":
        user_modes[user_id] = "main"
        await message.answer("⚙️ Main Mode ကိုပြောင်းပြီးပါပြီ။")
    elif message.text == "🔧 Button Edit Mode":
        user_modes[user_id] = "button_edit"
        await message.answer(
            "🔧 **Button Edit Mode**\n\n"
            "ခလုတ်တစ်ခုကိုနှိပ်ရင် အဲဒီခလုတ်ကို ပြင်လို့ရပါမယ်။\n"
            "- နာမည်ပြောင်းရန်\n"
            "- ဖျက်ရန်\n"
            "- ခလုတ်ခွဲအသစ်ထည့်ရန်\n"
            "- နေရာရွှေ့ရန်\n"
            "- Inline Button ထည့်ရန်"
        )
    elif message.text == "📝 Post Edit Mode":
        user_modes[user_id] = "post_edit"
        await message.answer(
            "📝 **Post Edit Mode**\n\n"
            "ခလုတ်တစ်ခုကိုနှိပ်ရင် အဲဒီခလုတ်အတွက် Message တွေကိုပြမယ်။\n"
            "- Add Message နှိပ်ပြီး Message အသစ်ထည့်လို့ရ\n"
            "- Add Question နှိပ်ပြီး Question ထည့်လို့ရ\n"
            "- Message တစ်ခုကိုနှိပ်ရင် အဲဒီ Message ကိုပြင်လို့ရ"
        )
    
    await message.answer("မီနူးပြန်ပြသည်", reply_markup=get_main_menu_keyboard(user_id))

# ============================
# HANDLERS - MAIN MENU BUTTONS
# ============================

@dp.message(F.text.in_([btn["name"] for btn in bot_data.get_all_buttons()]))
async def handle_all_buttons(message: Message, state: FSMContext):
    user_id = message.from_user.id
    btn_name = message.text
    mode = user_modes.get(user_id, "main")
    
    # Find button
    btn = None
    parent_id = None
    
    for b in bot_data.get_main_buttons():
        if b["name"] == btn_name:
            btn = b
            break
    
    if not btn:
        for parent, buttons in bot_data.data["buttons"]["submenus"].items():
            for b in buttons:
                if b["name"] == btn_name:
                    btn = b
                    parent_id = parent
                    break
            if btn:
                break
    
    if not btn:
        return
    
    # ===== BUTTON EDIT MODE =====
    if mode == "button_edit" and user_id == OWNER_ID:
        await state.update_data(editing_button_id=btn["id"], editing_button_name=btn["name"])
        
        text = f"🔧 Editing button: «{btn['name']}»"
        await message.answer(
            text,
            reply_markup=get_edit_buttons_keyboard()
        )
        return
    
    # ===== POST EDIT MODE =====
    if mode == "post_edit" and user_id == OWNER_ID:
        await state.update_data(current_button_id=btn["id"], current_button_name=btn["name"])
        
        text = f"**{btn['name']}** အတွက် Messages"
        await message.answer(
            text,
            reply_markup=get_post_edit_buttons_keyboard()
        )
        return
    
    # ===== NORMAL MODE =====
    # Check if has subbuttons
    sub_buttons = bot_data.get_sub_buttons(btn["id"])
    if sub_buttons:
        await show_submenu(message, btn, sub_buttons)
        return
    
    # Show messages
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
            elif msg["type"] == "question":
                await message.answer(
                    f"❓ {msg['content']}",
                    reply_markup=create_inline_keyboard(msg.get("buttons", []))
                )
    else:
        await message.answer(f"{btn_name} - ပို့စ်မရှိသေး")

async def show_submenu(message: Message, parent_btn: Dict, sub_buttons: List[Dict]):
    buttons = []
    row = []
    for i, btn in enumerate(sub_buttons):
        row.append(KeyboardButton(text=btn["name"]))
        if (i + 1) % 2 == 0:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    buttons.append([KeyboardButton(text="🔙 Back")])
    
    await message.answer(
        f"{parent_btn['name']} အမျိုးအစားများ",
        reply_markup=ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)
    )

# ============================
# BUTTON EDIT MODE HANDLERS
# ============================

@dp.message(F.text.in_(["⬅️", "⬇️", "⬆️", "➡️"]), F.state == "*")
async def handle_button_move(message: Message, state: FSMContext):
    user_id = message.from_user.id
    if user_id != OWNER_ID:
        return
    
    direction = message.text
    data = await state.get_data()
    btn_id = data.get("editing_button_id")
    
    if not btn_id:
        await message.answer("❌ ခလုတ်မတွေ့ပါ။")
        return
    
    if direction == "➡️":
        # Show list of possible parent buttons
        main_buttons = bot_data.get_main_buttons()
        buttons = []
        for btn in main_buttons:
            if btn["id"] != btn_id:
                buttons.append([KeyboardButton(text=btn["name"])])
        buttons.append([KeyboardButton(text="❌ Cancel")])
        
        await state.update_data(move_target_id=btn_id)
        await message.answer(
            "ဒီခလုတ်ကို ဘယ်ခလုတ်အောက်ကိုရွှေ့ချင်လဲ ရွေးပါ။",
            reply_markup=ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)
        )
        await state.set_state("waiting_move_target")
    else:
        if bot_data.move_button(btn_id, direction):
            btn = bot_data.get_button(btn_id)
            if btn:
                text = f"🔧 Editing button: «{btn['name']}»\n\n✅ နေရာရွှေ့ပြီးပါပြီ။"
                await message.answer(
                    text,
                    reply_markup=get_edit_buttons_keyboard()
                )
        else:
            await message.answer("❌ ရွှေ့လို့မရပါ။")

@dp.message(F.state == "waiting_move_target")
async def process_move_target(message: Message, state: FSMContext):
    data = await state.get_data()
    btn_id = data.get("move_target_id")
    target_name = message.text
    
    if target_name == "❌ Cancel":
        await state.clear()
        await message.answer("ပယ်ဖျက်လိုက်သည်။")
        return
    
    # Find target button
    for btn in bot_data.get_main_buttons():
        if btn["name"] == target_name:
            # Move button under target
            btn_data = bot_data.get_button(btn_id)
            if btn_data:
                # Remove from current location
                bot_data.delete_button(btn_id)
                # Add under target
                bot_data.add_button(btn_data["name"], parent=btn["id"])
                
                await message.answer(
                    f"✅ '{btn_data['name']}' ကို '{btn['name']}' အောက်ကိုရွှေ့ပြီးပါပြီ။",
                    reply_markup=get_edit_buttons_keyboard()
                )
                await state.clear()
                return
    
    await message.answer("❌ ခလုတ်မတွေ့ပါ။")

@dp.message(F.text == "*️⃣", F.state == "*")
async def add_inline_button_to_button(message: Message, state: FSMContext):
    user_id = message.from_user.id
    if user_id != OWNER_ID:
        return
    
    data = await state.get_data()
    btn_id = data.get("editing_button_id")
    
    if btn_id:
        await state.update_data(inline_target_button=btn_id)
        await message.answer(
            "**Inline Button ထည့်ရန်**\n\n"
            "ပုံစံ: ခလုတ်နာမည်|URL\n"
            "ဥပမာ: `Main Channel|https://t.me/...`\n\n"
            "ဒါမှမဟုတ်: ခလုတ်နာမည်|callback:data\n"
            "ဥပမာ: `Info|callback:info`\n\n"
            "**၂ တန်းထည့်ချင်ရင်:** တန်းတစ်ခုစီကို --- နဲ့ခြားပါ။\n"
            "ဥပမာ: `Button1|url1, Button2|url2 --- Button3|url3, Button4|url4`\n\n"
            "ခလုတ်တစ်ခုထည့်ပြီးရင် Enter နှိပ်ပါ။\n"
            "အကုန်ပြီးရင် `done` လို့ရိုက်ပါ။"
        )
        await state.update_data(temp_buttons=[])
        await state.set_state(BotStates.waiting_inline_button)

# ============================
# POST EDIT MODE HANDLERS
# ============================

@dp.message(F.text == "➕ Add Message", F.state == "*")
async def add_message_prompt(message: Message, state: FSMContext):
    data = await state.get_data()
    btn_id = data.get("current_button_id")
    
    if not btn_id:
        await message.answer("ခလုတ်မတွေ့ပါ။")
        return
    
    await state.update_data(adding_to_button=btn_id)
    await message.answer(
        "Message စာသားကို ရိုက်ထည့်ပါ။\n\n"
        "ပြီးရင် Preview ပြပြီး Inline Button ထည့်လို့ရပါမယ်။"
    )
    await state.set_state(BotStates.waiting_message_text)

@dp.message(F.text == "➕ Add Question", F.state == "*")
async def add_question_prompt(message: Message, state: FSMContext):
    data = await state.get_data()
    btn_id = data.get("current_button_id")
    
    if not btn_id:
        await message.answer("ခလုတ်မတွေ့ပါ။")
        return
    
    await state.update_data(adding_to_button=btn_id)
    await message.answer(
        "Question မေးခွန်းကို ရိုက်ထည့်ပါ။"
    )
    await state.set_state(BotStates.waiting_question)

@dp.message(BotStates.waiting_question)
async def process_question(message: Message, state: FSMContext):
    data = await state.get_data()
    btn_id = data.get("adding_to_button")
    
    bot_data.add_message_to_button(btn_id, "question", message.text)
    await state.clear()
    
    btn = bot_data.get_button(btn_id)
    await message.answer(
        f"✅ Question ထည့်ပြီးပါပြီ။",
        reply_markup=get_post_edit_buttons_keyboard()
    )

@dp.message(BotStates.waiting_message_text)
async def process_message_text(message: Message, state: FSMContext):
    if message.text == "/cancel":
        await state.clear()
        await message.answer("ပယ်ဖျက်လိုက်သည်။")
        return
    
    data = await state.get_data()
    btn_id = data.get("adding_to_button")
    
    # Save message
    msg = bot_data.add_message_to_button(btn_id, "text", message.text)
    
    if msg:
        await state.update_data(current_message_id=msg["id"])
        
        # Send preview
        await message.answer("**Preview:**")
        await message.answer(message.text)
        
        # Show edit buttons
        await message.answer(
            "⬅️ ⬇️ ⬆️ ➡️  *️⃣",
            reply_markup=get_message_edit_buttons_keyboard()
        )
    else:
        await message.answer("❌ Message ထည့်မရပါ။")

@dp.message(F.photo, F.state == BotStates.waiting_message_text)
async def process_message_photo(message: Message, state: FSMContext):
    data = await state.get_data()
    btn_id = data.get("adding_to_button")
    photo = message.photo[-1]
    caption = message.caption or ""
    
    content = {"file_id": photo.file_id, "caption": caption}
    msg = bot_data.add_message_to_button(btn_id, "photo", content)
    
    if msg:
        await state.update_data(current_message_id=msg["id"])
        
        # Send preview
        await message.answer("**Preview:**")
        await message.answer_photo(photo=photo.file_id, caption=caption)
        
        # Show edit buttons
        await message.answer(
            "⬅️ ⬇️ ⬆️ ➡️  *️⃣",
            reply_markup=get_message_edit_buttons_keyboard()
        )
    else:
        await message.answer("❌ Message ထည့်မရပါ။")

# ============================
# MESSAGE EDIT HANDLERS
# ============================

@dp.message(F.text == "*️⃣", F.state == "*")
async def add_inline_to_message(message: Message, state: FSMContext):
    data = await state.get_data()
    msg_id = data.get("current_message_id")
    btn_id = data.get("current_button_id") or data.get("adding_to_button")
    
    if msg_id and btn_id:
        await state.update_data(inline_message_id=msg_id, inline_button_id=btn_id)
        await message.answer(
            "**Inline Button ထည့်ရန်**\n\n"
            "ပုံစံ: ခလုတ်နာမည်|URL\n"
            "ဥပမာ: `Main Channel|https://t.me/...`\n\n"
            "ဒါမှမဟုတ်: ခလုတ်နာမည်|callback:data\n"
            "ဥပမာ: `Info|callback:info`\n\n"
            "**၂ တန်းထည့်ချင်ရင်:** တန်းတစ်ခုစီကို --- နဲ့ခြားပါ။\n"
            "ဥပမာ: `Button1|url1, Button2|url2 --- Button3|url3, Button4|url4`\n\n"
            "ခလုတ်တစ်ခုထည့်ပြီးရင် Enter နှိပ်ပါ။\n"
            "အကုန်ပြီးရင် `done` လို့ရိုက်ပါ။"
        )
        await state.update_data(temp_buttons=[])
        await state.set_state(BotStates.waiting_inline_button)

@dp.message(BotStates.waiting_inline_button)
async def process_inline_button(message: Message, state: FSMContext):
    data = await state.get_data()
    temp_buttons = data.get("temp_buttons", [])
    
    if message.text.lower() == "done":
        msg_id = data.get("inline_message_id")
        btn_id = data.get("inline_button_id") or data.get("inline_target_button")
        
        if msg_id and btn_id:
            bot_data.update_message_buttons(btn_id, msg_id, temp_buttons)
            
            # Show final preview
            btn = bot_data.get_button(btn_id)
            if btn:
                for msg in btn.get("messages", []):
                    if msg["id"] == msg_id:
                        if msg["type"] == "text":
                            await message.answer("**Final Preview:**")
                            await message.answer(
                                msg["content"],
                                reply_markup=create_inline_keyboard(temp_buttons)
                            )
                        elif msg["type"] == "photo":
                            await message.answer("**Final Preview:**")
                            await message.answer_photo(
                                photo=msg["content"]["file_id"],
                                caption=msg["content"].get("caption", ""),
                                reply_markup=create_inline_keyboard(temp_buttons)
                            )
        
        await state.clear()
        await message.answer(
            "✅ Inline ခလုတ်များ ထည့်ပြီးပါပြီ။",
            reply_markup=get_main_menu_keyboard(message.from_user.id)
        )
        return
    
    # Parse and add button(s)
    new_buttons = parse_buttons_text(message.text)
    if new_buttons:
        if isinstance(new_buttons[0], list):
            # Multiple rows
            temp_buttons.extend(new_buttons)
            await message.answer(f"✅ {sum(len(row) for row in new_buttons)} ခလုတ် ထည့်ပြီးပါပြီ။")
        else:
            # Single row
            temp_buttons.append(new_buttons)
            await message.answer(f"✅ {len(new_buttons)} ခလုတ် ထည့်ပြီးပါပြီ။")
    else:
        await message.answer("❌ ခလုတ်ပုံစံမှားနေပါတယ်။")
    
    await state.update_data(temp_buttons=temp_buttons)
    await message.answer("နောက်ထပ်ထည့်ချင်ရင် ဆက်ရိုက်ပါ။\nအကုန်ပြီးရင် `done` ရိုက်ပါ။")

# ============================
# STOP EDITORS
# ============================

@dp.message(F.text == "⏹ Stop Edit")
async def stop_button_edit(message: Message, state: FSMContext):
    user_id = message.from_user.id
    await state.clear()
    user_modes[user_id] = "button_edit"
    await message.answer(
        "Button Edit Mode ကိုပြန်ရောက်ပါပြီ။",
        reply_markup=get_main_menu_keyboard(user_id)
    )

@dp.message(F.text == "⏹ Stop Editor")
async def stop_post_edit(message: Message, state: FSMContext):
    user_id = message.from_user.id
    await state.clear()
    user_modes[user_id] = "post_edit"
    await message.answer(
        "Post Edit Mode ကိုပြန်ရောက်ပါပြီ။",
        reply_markup=get_main_menu_keyboard(user_id)
    )

# ============================
# WELCOME EDITOR
# ============================

@dp.message(F.text == "👋 Welcome Editor")
async def welcome_editor(message: Message, state: FSMContext):
    user_id = message.from_user.id
    if user_id != OWNER_ID:
        return
    
    welcome = bot_data.get_welcome()
    current_type = welcome["type"]
    
    # Count buttons
    btn_count = 0
    if welcome.get("buttons"):
        if isinstance(welcome["buttons"][0], list):
            btn_count = sum(len(row) for row in welcome["buttons"])
        else:
            btn_count = len(welcome["buttons"])
    
    text = (
        f"**👋 Welcome Message Editor**\n\n"
        f"**လက်ရှိ:** {current_type}\n"
        f"**Inline ခလုတ်:** {btn_count} ခု\n\n"
        f"ဘာလုပ်ချင်ပါသလဲ?"
    )
    
    buttons = [
        [KeyboardButton(text="📝 Edit Welcome Text")],
        [KeyboardButton(text="🖼 Edit Welcome Photo")],
        [KeyboardButton(text="🔘 Add/Edit Inline Buttons")],
        [KeyboardButton(text="👁 Preview Welcome")],
        [KeyboardButton(text="🔙 Back")]
    ]
    
    await message.answer(text, reply_markup=ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True))

@dp.message(F.text == "📝 Edit Welcome Text")
async def edit_welcome_text(message: Message, state: FSMContext):
    await message.answer(
        "Welcome Message စာသားအသစ်ကို ရိုက်ထည့်ပါ။\n\n"
        "**Macros များ:**\n"
        "{mention} - အသုံးပြုသူအမည်\n"
        "{user_id} - User ID\n"
        "{username} - Username\n"
        "{fullname} - အမည်အပြည့်\n"
        "{date} - ယနေ့ရက်စွဲ\n"
        "{time} - ယခုအချိန်"
    )
    await state.set_state(BotStates.waiting_welcome_text)

@dp.message(BotStates.waiting_welcome_text)
async def process_welcome_text(message: Message, state: FSMContext):
    welcome = bot_data.get_welcome()
    bot_data.set_welcome("text", message.text, welcome.get("buttons", []))
    await state.clear()
    await message.answer("✅ Welcome Message ပြောင်းပြီးပါပြီ။")
    await message.answer(format_text(message.text, message.from_user))

@dp.message(F.text == "🖼 Edit Welcome Photo")
async def edit_welcome_photo(message: Message, state: FSMContext):
    await message.answer(
        "Welcome အတွက် ဓာတ်ပုံအသစ်ကို ပို့ပါ။\n"
        "ဓာတ်ပုံနဲ့အတူ စာသားပါထည့်ချင်ရင် Caption မှာရေးပါ။"
    )
    await state.set_state(BotStates.waiting_welcome_photo)

@dp.message(BotStates.waiting_welcome_photo, F.photo)
async def process_welcome_photo(message: Message, state: FSMContext):
    photo = message.photo[-1]
    caption = message.caption or ""
    content = {"file_id": photo.file_id, "caption": caption}
    
    welcome = bot_data.get_welcome()
    bot_data.set_welcome("photo", content, welcome.get("buttons", []))
    await state.clear()
    await message.answer("✅ Welcome Photo ပြောင်းပြီးပါပြီ။")
    await message.answer_photo(photo=photo.file_id, caption=caption)

@dp.message(F.text == "🔘 Add/Edit Inline Buttons")
async def edit_welcome_buttons(message: Message, state: FSMContext):
    await message.answer(
        "**Welcome Message အတွက် Inline Button များထည့်ရန်**\n\n"
        "**ပုံစံ:** ခလုတ်နာမည်|URL\n"
        "ဥပမာ: `Main Channel|https://t.me/...`\n\n"
        "**Callback ခလုတ်:** ခလုတ်နာမည်|callback:data\n"
        "ဥပမာ: `Info|callback:info`\n\n"
        "**၂ တန်းထည့်ချင်ရင်:** တန်းတစ်ခုစီကို --- နဲ့ခြားပါ။\n"
        "ဥပမာ: `Button1|url1, Button2|url2 --- Button3|url3, Button4|url4`\n\n"
        "ခလုတ်တစ်ခုထည့်ပြီးရင် Enter နှိပ်ပါ။\n"
        "အကုန်ပြီးရင် `done` လို့ရိုက်ပါ။"
    )
    await state.update_data(temp_buttons=[])
    await state.set_state(BotStates.waiting_welcome_buttons)

@dp.message(BotStates.waiting_welcome_buttons)
async def process_welcome_buttons(message: Message, state: FSMContext):
    data = await state.get_data()
    temp_buttons = data.get("temp_buttons", [])
    
    if message.text.lower() == "done":
        welcome = bot_data.get_welcome()
        bot_data.set_welcome(welcome["type"], welcome["content"], temp_buttons)
        await state.clear()
        await message.answer("✅ Inline ခလုတ်များ ထည့်ပြီးပါပြီ။")
        return
    
    # Parse and add button(s)
    new_buttons = parse_buttons_text(message.text)
    if new_buttons:
        if isinstance(new_buttons[0], list):
            # Multiple rows
            temp_buttons.extend(new_buttons)
            await message.answer(f"✅ {sum(len(row) for row in new_buttons)} ခလုတ် ထည့်ပြီးပါပြီ။")
        else:
            # Single row
            temp_buttons.append(new_buttons)
            await message.answer(f"✅ {len(new_buttons)} ခလုတ် ထည့်ပြီးပါပြီ။")
    else:
        await message.answer("❌ ခလုတ်ပုံစံမှားနေပါတယ်။")
    
    await state.update_data(temp_buttons=temp_buttons)
    await message.answer("နောက်ထပ်ထည့်ချင်ရင် ဆက်ရိုက်ပါ။\nအကုန်ပြီးရင် `done` ရိုက်ပါ။")

@dp.message(F.text == "👁 Preview Welcome")
async def preview_welcome(message: Message):
    user = message.from_user
    welcome = bot_data.get_welcome()
    
    if welcome["type"] == "text":
        formatted = format_text(welcome["content"], user)
        await message.answer(
            formatted,
            reply_markup=create_inline_keyboard(welcome.get("buttons", []))
        )
    else:
        caption = format_text(welcome["content"].get("caption", ""), user)
        await message.answer_photo(
            photo=welcome["content"]["file_id"],
            caption=caption,
            reply_markup=create_inline_keyboard(welcome.get("buttons", []))
        )

# ============================
# ADD BUTTON
# ============================

@dp.message(F.text == "➕ Add Button")
async def add_button_prompt(message: Message, state: FSMContext):
    user_id = message.from_user.id
    if user_id != OWNER_ID:
        return
    
    await message.answer(
        "ခလုတ်နာမည်အသစ်ကို ရိုက်ထည့်ပါ။\n\n"
        "ပယ်ဖျက်ချင်ရင် /cancel ကိုသုံးပါ။"
    )
    await state.set_state(BotStates.waiting_button_name)

@dp.message(BotStates.waiting_button_name)
async def process_add_button_name(message: Message, state: FSMContext):
    if message.text == "/cancel":
        await state.clear()
        await message.answer("ပယ်ဖျက်လိုက်သည်။")
        return
    
    await state.update_data(new_button_name=message.text)
    
    # Ask where to add
    buttons = [[KeyboardButton(text="📋 Main Menu (Top Level)")]]
    for btn in bot_data.get_main_buttons():
        buttons.append([KeyboardButton(text=btn["name"])])
    buttons.append([KeyboardButton(text="❌ Cancel")])
    
    await message.answer(
        "ဒီခလုတ်ကို ဘယ်နေရာမှာထည့်ချင်လဲ?\n\n"
        "- Main Menu မှာထည့်ချင်ရင် 'Main Menu' ကိုနှိပ်ပါ။\n"
        "- ခလုတ်တစ်ခုအောက်မှာထည့်ချင်ရင် အဲဒီခလုတ်ကိုနှိပ်ပါ။",
        reply_markup=ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)
    )
    await state.set_state(BotStates.waiting_parent_select)

@dp.message(BotStates.waiting_parent_select)
async def select_parent(message: Message, state: FSMContext):
    data = await state.get_data()
    button_name = data.get("new_button_name")
    
    if message.text == "❌ Cancel":
        await state.clear()
        await message.answer("ပယ်ဖျက်လိုက်သည်။")
        return
    
    if message.text == "📋 Main Menu (Top Level)":
        bot_data.add_button(button_name, parent=None)
        await state.clear()
        
        # Go back to button edit mode
        user_modes[message.from_user.id] = "button_edit"
        await message.answer(
            f"✅ '{button_name}' ကို ပင်မမီနူးမှာထည့်ပြီးပါပြီ။",
            reply_markup=get_main_menu_keyboard(message.from_user.id)
        )
    else:
        for btn in bot_data.get_main_buttons():
            if btn["name"] == message.text:
                bot_data.add_button(button_name, parent=btn["id"])
                await state.clear()
                
                # Go back to button edit mode
                user_modes[message.from_user.id] = "button_edit"
                await message.answer(
                    f"✅ '{button_name}' ကို '{btn['name']}' အောက်မှာထည့်ပြီးပါပြီ။",
                    reply_markup=get_main_menu_keyboard(message.from_user.id)
                )
                return

# ============================
# BACK BUTTON
# ============================

@dp.message(F.text == "🔙 Back")
async def go_back(message: Message, state: FSMContext):
    user_id = message.from_user.id
    mode = user_modes.get(user_id, "main")
    
    if mode == "post_edit":
        # Go back to post edit main menu
        await message.answer(
            "Post Edit Mode",
            reply_markup=get_post_edit_buttons_keyboard()
        )
    else:
        await state.clear()
        await message.answer(
            "ပင်မမီနူး",
            reply_markup=get_main_menu_keyboard(user_id)
        )

# ============================
# CANCEL HANDLER
# ============================

@dp.message(Command("cancel"))
async def cancel_command(message: Message, state: FSMContext):
    await state.clear()
    user_modes[message.from_user.id] = "main"
    await message.answer(
        "❌ လုပ်ဆောင်ချက်ကို ပယ်ဖျက်လိုက်သည်။",
        reply_markup=get_main_menu_keyboard(message.from_user.id)
    )

# ============================
# CALLBACK QUERY HANDLER
# ============================

@dp.callback_query()
async def handle_callback(callback: CallbackQuery):
    await callback.answer()
    
    data = callback.data
    if data == "none":
        return
    
    if data == "2d_anime":
        await callback.message.answer("၂D Anime စာရင်း")
    elif data == "3d_anime":
        await callback.message.answer("၃D Anime စာရင်း")
    else:
        await callback.message.answer(f"Callback: {data}")

# ============================
# MAIN
# ============================

async def main():
    print("=" * 60)
    print("🤖 နက်ပြ ဘော့တ် - Welcome Message with 2-Row Buttons")
    print("=" * 60)
    print(f"👤 Owner ID: {OWNER_ID}")
    print(f"👥 Users: {bot_data.get_users_count()}")
    print(f"🔧 Buttons: {len(bot_data.get_all_buttons())}")
    print(f"📝 Messages: {sum(len(btn.get('messages', [])) for btn in bot_data.get_all_buttons())}")
    print("=" * 60)
    
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
