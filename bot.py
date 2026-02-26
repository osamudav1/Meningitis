"""
နက်ပြ ဘော့တ် - Mode ၃ မျိုးနဲ့ အပြည့်အစုံ
Aiogram 3.17 ကိုသုံးထားသည်
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
    Message, ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton
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
            except:
                return self.get_default_data()
        return self.get_default_data()
    
    def save_data(self):
        with open(self.data_file, 'w', encoding='utf-8') as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)
    
    def get_default_data(self) -> Dict:
        return {
            "welcome": {
                "type": "text",
                "content": "**{mention} ကြိုဆိုပါတယ်** 🎉\n\nအောက်ပါခလုတ်များကို နှိပ်ပြီး သွားရောက်ကြည့်ရှုနိုင်ပါတယ်။",
                "buttons": []
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
    
    def get_button_by_name(self, name: str, parent_id: str = None) -> Optional[Dict]:
        if parent_id is None:
            for btn in self.data["buttons"]["main"]:
                if btn["name"] == name:
                    return btn
        else:
            for btn in self.data["buttons"]["submenus"].get(parent_id, []):
                if btn["name"] == name:
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
                    # Update orders
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
                elif direction == "⬅️":
                    # Already in main, can't go out
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
    def add_message_to_button(self, btn_id: str, msg_type: str, content: Any, buttons: List = None) -> Dict:
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

def create_inline_keyboard(buttons: List[Dict]) -> Optional[InlineKeyboardMarkup]:
    if not buttons:
        return None
    inline_buttons = []
    for btn in buttons:
        if "url" in btn:
            inline_buttons.append([InlineKeyboardButton(text=btn["text"], url=btn["url"])])
        else:
            inline_buttons.append([InlineKeyboardButton(text=btn["text"], callback_data="none")])
    return InlineKeyboardMarkup(inline_keyboard=inline_buttons)

def parse_buttons_text(buttons_text: str) -> List[Dict]:
    buttons = []
    if not buttons_text or buttons_text.lower() == "skip":
        return buttons
    
    parts = buttons_text.split(",")
    for part in parts:
        part = part.strip()
        if not part:
            continue
        if "|" in part:
            name, url = part.split("|", 1)
            buttons.append({"text": name.strip(), "url": url.strip()})
        else:
            buttons.append({"text": part, "callback": "none"})
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
    
    # Mode indicator
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

def get_back_keyboard():
    buttons = [[KeyboardButton(text="🔙 Back")]]
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
    waiting_message_buttons = State()
    waiting_welcome_text = State()
    waiting_welcome_photo = State()
    waiting_welcome_buttons = State()
    waiting_broadcast_text = State()
    waiting_broadcast_photo = State()
    waiting_broadcast_buttons = State()
    waiting_broadcast_confirm = State()

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
        except:
            pass
    
    # Get welcome
    welcome = bot_data.get_welcome()
    
    if welcome["type"] == "text":
        formatted = format_text(welcome["content"], user)
        await message.answer(
            formatted,
            reply_markup=get_main_menu_keyboard(user_id),
            reply_markup_inline=create_inline_keyboard(welcome.get("buttons", []))
        )
    elif welcome["type"] == "photo":
        caption = format_text(welcome["content"].get("caption", ""), user)
        await message.answer_photo(
            photo=welcome["content"]["file_id"],
            caption=caption,
            reply_markup=get_main_menu_keyboard(user_id),
            reply_markup_inline=create_inline_keyboard(welcome.get("buttons", []))
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
            "- ခလုတ်ခွဲအသစ်ထည့်ရန်"
        )
    elif message.text == "📝 Post Edit Mode":
        user_modes[user_id] = "post_edit"
        await message.answer(
            "📝 **Post Edit Mode**\n\n"
            "ခလုတ်တစ်ခုကိုနှိပ်ရင် အဲဒီခလုတ်အတွက် Message ထည့်လို့ရပါမယ်။\n"
            "- Text Message ထည့်ရန်\n"
            "- Photo Message ထည့်ရန်\n"
            "- Message များကြည့်ရန်"
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
    
    # Check in main
    for b in bot_data.get_main_buttons():
        if b["name"] == btn_name:
            btn = b
            break
    
    # Check in submenus
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
        await show_button_edit_menu(message, btn, state)
        return
    
    # ===== POST EDIT MODE =====
    if mode == "post_edit" and user_id == OWNER_ID:
        await show_post_edit_menu(message, btn, state)
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
# BUTTON EDIT MODE
# ============================

async def show_button_edit_menu(message: Message, btn: Dict, state: FSMContext):
    await state.update_data(current_button_id=btn["id"], current_button_name=btn["name"])
    
    buttons = [
        [KeyboardButton(text=f"✏️ Rename: {btn['name']}")],
        [KeyboardButton(text=f"🗑 Delete: {btn['name']}")],
        [KeyboardButton(text="➕ Add Sub Button")],
        [KeyboardButton(text="⬆️ Move Up"), KeyboardButton(text="⬇️ Move Down")],
        [KeyboardButton(text="⬅️ Move Out to Main")],
        [KeyboardButton(text="🔙 Back to Main")]
    ]
    
    await message.answer(
        f"**{btn['name']}** ကိုပြင်ရန်",
        reply_markup=ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)
    )

@dp.message(F.text.startswith("✏️ Rename:"))
async def rename_button_prompt(message: Message, state: FSMContext):
    user_id = message.from_user.id
    if user_id != OWNER_ID:
        return
    
    data = await state.get_data()
    btn_id = data.get("current_button_id")
    
    if btn_id:
        await state.update_data(rename_btn_id=btn_id)
        await message.answer("နာမည်အသစ်ကို ရိုက်ထည့်ပါ။")
        await state.set_state(BotStates.waiting_button_rename)

@dp.message(BotStates.waiting_button_rename)
async def process_rename(message: Message, state: FSMContext):
    data = await state.get_data()
    btn_id = data.get("rename_btn_id")
    
    if bot_data.rename_button(btn_id, message.text):
        await state.clear()
        await message.answer(
            f"✅ နာမည်ပြောင်းပြီးပါပြီ။",
            reply_markup=get_main_menu_keyboard(message.from_user.id)
        )
    else:
        await message.answer("❌ နာမည်ပြောင်းလို့မရပါ။")

@dp.message(F.text.startswith("🗑 Delete:"))
async def delete_button(message: Message, state: FSMContext):
    user_id = message.from_user.id
    if user_id != OWNER_ID:
        return
    
    data = await state.get_data()
    btn_id = data.get("current_button_id")
    
    if btn_id:
        bot_data.delete_button(btn_id)
        await state.clear()
        await message.answer(
            f"✅ ခလုတ်ဖျက်ပြီးပါပြီ။",
            reply_markup=get_main_menu_keyboard(user_id)
        )

@dp.message(F.text == "➕ Add Sub Button")
async def add_sub_button_prompt(message: Message, state: FSMContext):
    user_id = message.from_user.id
    if user_id != OWNER_ID:
        return
    
    data = await state.get_data()
    parent_id = data.get("current_button_id")
    
    if parent_id:
        await state.update_data(parent_id=parent_id)
        await message.answer("ခလုတ်ခွဲနာမည်အသစ်ကို ရိုက်ထည့်ပါ။")
        await state.set_state(BotStates.waiting_button_name)

@dp.message(F.text == "⬆️ Move Up")
async def move_button_up(message: Message, state: FSMContext):
    user_id = message.from_user.id
    if user_id != OWNER_ID:
        return
    
    data = await state.get_data()
    btn_id = data.get("current_button_id")
    
    if bot_data.move_button(btn_id, "⬆️"):
        await message.answer("✅ အပေါ်ကိုရွှေ့ပြီးပါပြီ။")
    else:
        await message.answer("❌ ရွှေ့လို့မရပါ။")

@dp.message(F.text == "⬇️ Move Down")
async def move_button_down(message: Message, state: FSMContext):
    user_id = message.from_user.id
    if user_id != OWNER_ID:
        return
    
    data = await state.get_data()
    btn_id = data.get("current_button_id")
    
    if bot_data.move_button(btn_id, "⬇️"):
        await message.answer("✅ အောက်ကိုရွှေ့ပြီးပါပြီ။")
    else:
        await message.answer("❌ ရွှေ့လို့မရပါ။")

@dp.message(F.text == "⬅️ Move Out to Main")
async def move_button_out(message: Message, state: FSMContext):
    user_id = message.from_user.id
    if user_id != OWNER_ID:
        return
    
    data = await state.get_data()
    btn_id = data.get("current_button_id")
    
    if bot_data.move_button(btn_id, "⬅️"):
        await message.answer("✅ Main Menu ကိုရွှေ့ပြီးပါပြီ။")
    else:
        await message.answer("❌ ရွှေ့လို့မရပါ။")

# ============================
# POST EDIT MODE
# ============================

async def show_post_edit_menu(message: Message, btn: Dict, state: FSMContext):
    await state.update_data(post_btn_id=btn["id"], post_btn_name=btn["name"])
    
    buttons = [
        [KeyboardButton(text="📝 Add Text Message")],
        [KeyboardButton(text="🖼 Add Photo Message")],
        [KeyboardButton(text="📋 View Messages")],
        [KeyboardButton(text="🔙 Back to Main")]
    ]
    
    await message.answer(
        f"**{btn['name']}** အတွက် Message ထည့်ရန်",
        reply_markup=ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)
    )

@dp.message(F.text == "📝 Add Text Message")
async def add_text_prompt(message: Message, state: FSMContext):
    await message.answer(
        "Message စာသားကို ရိုက်ထည့်ပါ။\n\n"
        "ပြီးရင် Inline Button ထည့်လို့ရပါမယ်။"
    )
    await state.set_state(BotStates.waiting_message_text)

@dp.message(F.text == "🖼 Add Photo Message")
async def add_photo_prompt(message: Message, state: FSMContext):
    await message.answer(
        "ဓာတ်ပုံကို ပို့ပါ။\n"
        "ဓာတ်ပုံနဲ့အတူ စာသားပါထည့်ချင်ရင် Caption မှာရေးပါ။\n\n"
        "ပြီးရင် Inline Button ထည့်လို့ရပါမယ်။"
    )
    await state.set_state(BotStates.waiting_message_photo)

@dp.message(BotStates.waiting_message_text)
async def process_text_message(message: Message, state: FSMContext):
    if message.text == "/cancel":
        await state.clear()
        await message.answer("ပယ်ဖျက်လိုက်သည်။")
        return
    
    await state.update_data(message_text=message.text)
    
    await message.answer(
        "Inline ခလုတ်တွေ ထည့်ချင်ရင် အောက်ပါပုံစံအတိုင်း ရိုက်ထည့်ပါ။\n"
        "မထည့်ချင်ရင် 'skip' လို့ရိုက်ပါ။\n\n"
        "ပုံစံ: ခလုတ်နာမည်|URL, ခလုတ်2|url2\n"
        "ဥပမာ: Channel|https://t.me/..., Group|https://t.me/..."
    )
    await state.set_state(BotStates.waiting_message_buttons)

@dp.message(BotStates.waiting_message_photo, F.photo)
async def process_photo_message(message: Message, state: FSMContext):
    photo = message.photo[-1]
    caption = message.caption or ""
    
    await state.update_data(
        message_photo=photo.file_id,
        message_caption=caption
    )
    
    await message.answer(
        "Inline ခလုတ်တွေ ထည့်ချင်ရင် အောက်ပါပုံစံအတိုင်း ရိုက်ထည့်ပါ။\n"
        "မထည့်ချင်ရင် 'skip' လို့ရိုက်ပါ။\n\n"
        "ပုံစံ: ခလုတ်နာမည်|URL, ခလုတ်2|url2\n"
        "ဥပမာ: Channel|https://t.me/..., Group|https://t.me/..."
    )
    await state.set_state(BotStates.waiting_message_buttons)

@dp.message(BotStates.waiting_message_buttons)
async def process_message_buttons(message: Message, state: FSMContext):
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
        # Send preview
        await message.answer("✅ Message ထည့်ပြီးပါပြီ။ အောက်ပါအတိုင်းပြမှာပါ။")
        await message.answer(
            data["message_text"],
            reply_markup=create_inline_keyboard(buttons)
        )
    elif "message_photo" in data:
        # Save photo message
        content = {
            "file_id": data["message_photo"],
            "caption": data.get("message_caption", "")
        }
        bot_data.add_message_to_button(btn_id, "photo", content, buttons)
        # Send preview
        await message.answer("✅ Message ထည့်ပြီးပါပြီ။ အောက်ပါအတိုင်းပြမှာပါ။")
        await message.answer_photo(
            photo=data["message_photo"],
            caption=data.get("message_caption", ""),
            reply_markup=create_inline_keyboard(buttons)
        )
    
    await state.clear()
    user_modes[message.from_user.id] = "main"
    await message.answer(
        "ပင်မမီနူး",
        reply_markup=get_main_menu_keyboard(message.from_user.id)
    )

@dp.message(F.text == "📋 View Messages")
async def view_messages(message: Message, state: FSMContext):
    data = await state.get_data()
    btn_id = data.get("post_btn_id")
    btn_name = data.get("post_btn_name")
    
    messages = bot_data.get_button_messages(btn_id)
    
    if not messages:
        await message.answer(f"{btn_name} အတွက် Message မရှိသေးပါ။")
        return
    
    text = f"**{btn_name}** အတွက် Message များ:\n\n"
    for i, msg in enumerate(messages, 1):
        msg_type = msg["type"]
        if msg_type == "text":
            preview = msg["content"][:50] + "..." if len(msg["content"]) > 50 else msg["content"]
        else:
            preview = f"[Photo] {msg['content'].get('caption', '')[:30]}..."
        btn_count = len(msg.get("buttons", []))
        text += f"{i}. {msg_type}: {preview} (ခလုတ် {btn_count} ခု)\n"
    
    await message.answer(text)

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
    btn_count = len(welcome.get("buttons", []))
    
    text = (
        f"**👋 Welcome Message Editor**\n\n"
        f"**လက်ရှိ:** {current_type}\n"
        f"**Inline ခလုတ်:** {btn_count} ခု\n\n"
        f"ဘာလုပ်ချင်ပါသလဲ?"
    )
    
    buttons = [
        [KeyboardButton(text="📝 Edit Welcome Text")],
        [KeyboardButton(text="🖼 Edit Welcome Photo")],
        [KeyboardButton(text="🔘 Add Inline Button")],
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

@dp.message(F.text == "🔘 Add Inline Button")
async def add_welcome_button(message: Message, state: FSMContext):
    await message.answer(
        "Welcome Message အောက်မှာထည့်မယ့် Inline Button ကို ရိုက်ထည့်ပါ။\n\n"
        "**URL ခလုတ်:** ခလုတ်နာမည်|URL\n"
        "ဥပမာ: Main Channel|https://t.me/...\n\n"
        "**သာမန်ခလုတ်:** ခလုတ်နာမည်\n"
        "ဥပမာ: Info\n\n"
        "ပြီးရင် 'done' လို့ရိုက်ပါ။"
    )
    await state.update_data(temp_buttons=[])
    await state.set_state(BotStates.waiting_welcome_buttons)

@dp.message(BotStates.waiting_welcome_buttons)
async def process_welcome_button(message: Message, state: FSMContext):
    data = await state.get_data()
    temp_buttons = data.get("temp_buttons", [])
    
    if message.text.lower() == "done":
        welcome = bot_data.get_welcome()
        bot_data.set_welcome(welcome["type"], welcome["content"], temp_buttons)
        await state.clear()
        await message.answer("✅ Inline ခလုတ်များ ထည့်ပြီးပါပြီ။")
        return
    
    if "|" in message.text:
        name, url = message.text.split("|", 1)
        temp_buttons.append({"text": name.strip(), "url": url.strip()})
        await message.answer(f"✅ '{name.strip()}' URL ခလုတ်ထည့်ပြီးပါပြီ။\nနောက်ထပ်ထည့်ချင်ရင် ဆက်ရိုက်ပါ။\nအကုန်ပြီးရင် 'done' ရိုက်ပါ။")
    else:
        temp_buttons.append({"text": message.text, "callback": "none"})
        await message.answer(f"✅ '{message.text}' ခလုတ်ထည့်ပြီးပါပြီ။\nနောက်ထပ်ထည့်ချင်ရင် ဆက်ရိုက်ပါ။\nအကုန်ပြီးရင် 'done' ရိုက်ပါ။")
    
    await state.update_data(temp_buttons=temp_buttons)

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
        await message.answer(f"✅ '{button_name}' ကို ပင်မမီနူးမှာထည့်ပြီးပါပြီ။")
    else:
        for btn in bot_data.get_main_buttons():
            if btn["name"] == message.text:
                bot_data.add_button(button_name, parent=btn["id"])
                await state.clear()
                await message.answer(f"✅ '{button_name}' ကို '{btn['name']}' အောက်မှာထည့်ပြီးပါပြီ။")
                return

# ============================
# BROADCAST
# ============================

@dp.message(F.text == "📢 Broadcast")
async def broadcast_menu(message: Message):
    user_id = message.from_user.id
    if user_id != OWNER_ID:
        return
    
    users_count = bot_data.get_users_count()
    
    buttons = [
        [KeyboardButton(text="📝 Send Text")],
        [KeyboardButton(text="🖼 Send Photo")],
        [KeyboardButton(text="🔙 Back")]
    ]
    
    await message.answer(
        f"**📢 Broadcast**\n\n"
        f"စုစုပေါင်းအသုံးပြုသူ: {users_count} ယောက်\n\n"
        f"ဘာပို့ချင်လဲ ရွေးပါ။",
        reply_markup=ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)
    )

@dp.message(F.text == "📝 Send Text")
async def broadcast_text_prompt(message: Message, state: FSMContext):
    await message.answer(
        "Broadcast ပို့မယ့် စာသားကို ရိုက်ထည့်ပါ။\n\n"
        "Macros များ: {mention}, {fullname}, {username}, {user_id}, {date}, {time}\n\n"
        "ပယ်ဖျက်ချင်ရင် /cancel ကိုသုံးပါ။"
    )
    await state.set_state(BotStates.waiting_broadcast_text)

@dp.message(F.text == "🖼 Send Photo")
async def broadcast_photo_prompt(message: Message, state: FSMContext):
    await message.answer(
        "Broadcast ပို့မယ့် ဓာတ်ပုံကို ပို့ပါ။\n"
        "ဓာတ်ပုံနဲ့အတူ စာသားပါထည့်ချင်ရင် Caption မှာရေးပါ။\n\n"
        "ပယ်ဖျက်ချင်ရင် /cancel ကိုသုံးပါ။"
    )
    await state.set_state(BotStates.waiting_broadcast_photo)

@dp.message(BotStates.waiting_broadcast_text)
async def process_broadcast_text(message: Message, state: FSMContext):
    if message.text == "/cancel":
        await state.clear()
        await message.answer("ပယ်ဖျက်လိုက်သည်။")
        return
    
    await state.update_data(broadcast_text=message.text)
    
    await message.answer(
        "Inline ခလုတ်တွေ ထည့်ချင်ရင် အောက်ပါပုံစံအတိုင်း ရိုက်ထည့်ပါ။\n"
        "မထည့်ချင်ရင် 'skip' လို့ရိုက်ပါ။\n\n"
        "ပုံစံ: ခလုတ်နာမည်|URL, ခလုတ်2|url2"
    )
    await state.set_state(BotStates.waiting_broadcast_buttons)

@dp.message(BotStates.waiting_broadcast_photo, F.photo)
async def process_broadcast_photo(message: Message, state: FSMContext):
    photo = message.photo[-1]
    caption = message.caption or ""
    
    await state.update_data(
        broadcast_photo=photo.file_id,
        broadcast_caption=caption
    )
    
    await message.answer(
        "Inline ခလုတ်တွေ ထည့်ချင်ရင် အောက်ပါပုံစံအတိုင်း ရိုက်ထည့်ပါ။\n"
        "မထည့်ချင်ရင် 'skip' လို့ရိုက်ပါ။\n\n"
        "ပုံစံ: ခလုတ်နာမည်|URL, ခလုတ်2|url2"
    )
    await state.set_state(BotStates.waiting_broadcast_buttons)

@dp.message(BotStates.waiting_broadcast_buttons)
async def process_broadcast_buttons(message: Message, state: FSMContext):
    data = await state.get_data()
    buttons = []
    
    if message.text.lower() != "skip":
        buttons = parse_buttons_text(message.text)
    
    await state.update_data(broadcast_buttons=buttons)
    
    # Show confirmation
    users_count = bot_data.get_users_count()
    
    if "broadcast_text" in data:
        preview = data["broadcast_text"][:100]
        msg_type = "Text"
    else:
        preview = f"[Photo] {data.get('broadcast_caption', '')[:100]}"
        msg_type = "Photo"
    
    confirm_text = (
        f"**📢 Broadcast အချက်အလက်များ**\n\n"
        f"**အမျိုးအစား:** {msg_type}\n"
        f"**လက်ခံသူဦးရေ:** {users_count} ယောက်\n"
        f"**ခလုတ်အရေအတွက်:** {len(buttons)} ခု\n\n"
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
    data = await state.get_data()
    users = bot_data.get_all_users()
    
    await message.answer(f"📢 Broadcast စတင်နေပါပြီ... လူ {len(users)} ယောက်ဆီပို့နေပါတယ်။")
    
    sent = 0
    failed = 0
    
    for i, user_id in enumerate(users):
        try:
            if "broadcast_text" in data:
                formatted = format_text(data["broadcast_text"], message.from_user)
                await bot.send_message(
                    user_id,
                    formatted,
                    reply_markup=create_inline_keyboard(data.get("broadcast_buttons", []))
                )
            else:
                caption = format_text(data.get("broadcast_caption", ""), message.from_user)
                await bot.send_photo(
                    user_id,
                    photo=data["broadcast_photo"],
                    caption=caption,
                    reply_markup=create_inline_keyboard(data.get("broadcast_buttons", []))
                )
            sent += 1
        except Exception as e:
            failed += 1
        
        # Rate limit
        if (i + 1) % 20 == 0:
            await asyncio.sleep(1)
    
    await state.clear()
    await message.answer(
        f"**✅ Broadcast ပြီးဆုံးပါပြီ**\n\n"
        f"စုစုပေါင်း: {len(users)} ယောက်\n"
        f"ပို့ပြီး: {sent} ယောက်\n"
        f"မအောင်မြင်: {failed} ယောက်"
    )

@dp.message(BotStates.waiting_broadcast_confirm, F.text == "❌ Cancel")
async def cancel_broadcast(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("❌ Broadcast ကို ပယ်ဖျက်လိုက်သည်။")

# ============================
# STATISTICS
# ============================

@dp.message(F.text == "📊 Statistics")
async def show_statistics(message: Message):
    user_id = message.from_user.id
    if user_id != OWNER_ID:
        return
    
    users = bot_data.get_all_users()
    buttons_count = len(bot_data.get_all_buttons())
    messages_count = 0
    for btn in bot_data.get_all_buttons():
        messages_count += len(btn.get("messages", []))
    
    welcome = bot_data.get_welcome()
    
    stats = (
        f"**📊 စာရင်းအင်းများ**\n\n"
        f"**👤 အသုံးပြုသူ**\n"
        f"စုစုပေါင်း: {len(users)} ယောက်\n\n"
        f"**🔧 ခလုတ်များ**\n"
        f"စုစုပေါင်း: {buttons_count} ခု\n\n"
        f"**📝 ပို့စ်များ**\n"
        f"စုစုပေါင်း: {messages_count} ခု\n\n"
        f"**👋 Welcome**\n"
        f"အမျိုးအစား: {welcome['type']}\n"
        f"Inline ခလုတ်: {len(welcome.get('buttons', []))} ခု"
    )
    
    await message.answer(stats)

# ============================
# BACK BUTTON
# ============================

@dp.message(F.text == "🔙 Back")
@dp.message(F.text == "🔙 Back to Main")
async def go_back(message: Message, state: FSMContext):
    user_id = message.from_user.id
    await state.clear()
    user_modes[user_id] = "main"
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
    await message.answer(
        "❌ လုပ်ဆောင်ချက်ကို ပယ်ဖျက်လိုက်သည်။",
        reply_markup=get_main_menu_keyboard(message.from_user.id)
    )

# ============================
# MAIN
# ============================

async def main():
    print("=" * 60)
    print("🤖 နက်ပြ ဘော့တ် - Mode ၃ မျိုး")
    print("=" * 60)
    print(f"👤 Owner ID: {OWNER_ID}")
    print(f"👥 Users: {bot_data.get_users_count()}")
    print(f"🔧 Buttons: {len(bot_data.get_all_buttons())}")
    print(f"📝 Messages: {sum(len(btn.get('messages', [])) for btn in bot_data.get_all_buttons())}")
    print("=" * 60)
    
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
