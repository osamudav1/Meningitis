"""
Telegram Anime/Movie Bot - Aiogram Version
Screenshot အတိုင်း အသေးစိတ်ကျကျ - Full Code
"""

import asyncio
import json
import os
from datetime import datetime
from typing import Dict, List, Any, Optional

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton,
    FSInputFile, InputMediaPhoto, InputMediaVideo
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
import logging

# ==================== CONFIGURATION ====================
BOT_TOKEN = "YOUR_BOT_TOKEN_HERE"  # @BotFather ကရတဲ့ Token
OWNER_ID = 123456789  # သင့် Telegram User ID
ADMIN_IDS = [123456789]  # Admin များရဲ့ ID

# ==================== LOGGING ====================
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ==================== DATA FILES ====================
DATA_DIR = "bot_data"
os.makedirs(DATA_DIR, exist_ok=True)

WELCOMES_FILE = os.path.join(DATA_DIR, "welcomes.json")
POSTS_FILE = os.path.join(DATA_DIR, "posts.json")
BUTTONS_FILE = os.path.join(DATA_DIR, "buttons.json")
SETTINGS_FILE = os.path.join(DATA_DIR, "settings.json")

# ==================== DATA CLASSES ====================
class ButtonType:
    URL = "url"
    POPUP = "popup"
    COMMAND = "command"
    CALLBACK = "callback"

class Button:
    def __init__(self, text: str, button_type: str, data: str, order: int = 0):
        self.text = text
        self.type = button_type
        self.data = data
        self.order = order
    
    def to_dict(self):
        return {
            "text": self.text,
            "type": self.type,
            "data": self.data,
            "order": self.order
        }
    
    @classmethod
    def from_dict(cls, data):
        return cls(
            text=data.get("text", ""),
            button_type=data.get("type", ButtonType.CALLBACK),
            data=data.get("data", ""),
            order=data.get("order", 0)
        )

class Message:
    def __init__(self, id: str, text: str = "", media: str = None, media_type: str = None):
        self.id = id
        self.text = text
        self.media = media  # file_id or path
        self.media_type = media_type  # photo/video
        self.buttons = []  # List[Button]
        self.created_at = datetime.now().isoformat()
        self.updated_at = datetime.now().isoformat()
    
    def to_dict(self):
        return {
            "id": self.id,
            "text": self.text,
            "media": self.media,
            "media_type": self.media_type,
            "buttons": [b.to_dict() for b in self.buttons],
            "created_at": self.created_at,
            "updated_at": self.updated_at
        }
    
    @classmethod
    def from_dict(cls, data):
        msg = cls(
            id=data.get("id", ""),
            text=data.get("text", ""),
            media=data.get("media"),
            media_type=data.get("media_type")
        )
        msg.buttons = [Button.from_dict(b) for b in data.get("buttons", [])]
        msg.created_at = data.get("created_at", datetime.now().isoformat())
        msg.updated_at = data.get("updated_at", datetime.now().isoformat())
        return msg

# ==================== DATABASE MANAGER ====================
class Database:
    def __init__(self):
        self.welcomes = self._load(WELCOMES_FILE, {"messages": [], "active": None})
        self.posts = self._load(POSTS_FILE, {"messages": {}, "categories": {}})
        self.buttons = self._load(BUTTONS_FILE, {"main_menu": [], "inline_buttons": {}})
        self.settings = self._load(SETTINGS_FILE, {
            "editing_mode": False,
            "current_editor": None,
            "current_message": None,
            "temp_data": {}
        })
    
    def _load(self, filename, default):
        if os.path.exists(filename):
            with open(filename, 'r', encoding='utf-8') as f:
                return json.load(f)
        return default
    
    def _save(self, filename, data):
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
    
    def save_all(self):
        self._save(WELCOMES_FILE, self.welcomes)
        self._save(POSTS_FILE, self.posts)
        self._save(BUTTONS_FILE, self.buttons)
        self._save(SETTINGS_FILE, self.settings)
    
    # Welcome Methods
    def get_welcomes(self):
        return self.welcomes["messages"]
    
    def add_welcome(self, text: str):
        welcome = {
            "id": str(len(self.welcomes["messages"]) + 1),
            "text": text,
            "created_at": datetime.now().isoformat()
        }
        self.welcomes["messages"].append(welcome)
        if not self.welcomes["active"]:
            self.welcomes["active"] = welcome["id"]
        self.save_all()
        return welcome
    
    def get_active_welcome(self):
        if self.welcomes["active"]:
            for w in self.welcomes["messages"]:
                if w["id"] == self.welcomes["active"]:
                    return w["text"]
        return "မင်္ဂလာပါ {mention}!\nAnime Bot ကိုကြိုဆိုပါတယ်။"
    
    # Posts Methods
    def get_posts(self):
        return {k: Message.from_dict(v) for k, v in self.posts["messages"].items()}
    
    def get_post(self, post_id: str):
        if post_id in self.posts["messages"]:
            return Message.from_dict(self.posts["messages"][post_id])
        return None
    
    def add_post(self, message: Message):
        self.posts["messages"][message.id] = message.to_dict()
        self.save_all()
    
    def update_post(self, post_id: str, **kwargs):
        if post_id in self.posts["messages"]:
            for key, value in kwargs.items():
                if key == "buttons":
                    self.posts["messages"][post_id][key] = [b.to_dict() for b in value]
                else:
                    self.posts["messages"][post_id][key] = value
            self.posts["messages"][post_id]["updated_at"] = datetime.now().isoformat()
            self.save_all()
    
    def delete_post(self, post_id: str):
        if post_id in self.posts["messages"]:
            del self.posts["messages"][post_id]
            self.save_all()
    
    # Buttons Methods
    def get_main_menu(self):
        return [Button.from_dict(b) for b in self.buttons["main_menu"]]
    
    def add_main_menu_button(self, button: Button):
        self.buttons["main_menu"].append(button.to_dict())
        self.save_all()
    
    def get_inline_buttons(self, message_id: str):
        if message_id in self.buttons["inline_buttons"]:
            return [Button.from_dict(b) for b in self.buttons["inline_buttons"][message_id]]
        return []

db = Database()

# ==================== FSM STATES ====================
class BotStates(StatesGroup):
    # Welcome Editor
    adding_welcome = State()
    editing_welcome = State()
    
    # Posts Editor
    adding_post = State()
    editing_post = State()
    waiting_post_text = State()
    waiting_post_media = State()
    
    # Buttons Editor
    adding_button = State()
    editing_button = State()
    waiting_button_name = State()
    waiting_button_type = State()
    waiting_button_url = State()
    waiting_button_popup = State()
    waiting_button_command = State()
    
    # Settings
    admin_mode = State()
    editing_mode = State()

# ==================== INIT BOT ====================
bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# ==================== KEYBOARD BUILDERS ====================
def build_main_menu():
    """ပင်မ Menu တည်ဆောက်မယ်"""
    keyboard = []
    buttons = db.get_main_menu()
    
    # 2 Columns နဲ့ပြမယ်
    row = []
    for i, btn in enumerate(buttons):
        row.append(InlineKeyboardButton(
            text=btn.text,
            callback_data=f"menu_{btn.data}" if btn.type == ButtonType.CALLBACK else btn.data
        ))
        if len(row) == 2 or i == len(buttons) - 1:
            keyboard.append(row)
            row = []
    
    # Admin Button (Owner/Admin အတွက်)
    keyboard.append([InlineKeyboardButton(text="⚙️ Admin", callback_data="admin_panel")])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def build_admin_panel():
    """Admin Panel တည်ဆောက်မယ်"""
    keyboard = [
        [InlineKeyboardButton(text="📝 Posts Editor", callback_data="posts_editor")],
        [InlineKeyboardButton(text="🔘 Buttons Editor", callback_data="buttons_editor")],
        [InlineKeyboardButton(text="💬 Welcome Editor", callback_data="welcome_editor")],
        [InlineKeyboardButton(text="⚖️ Balance", callback_data="balance")],
        [InlineKeyboardButton(text="👤 Owner", callback_data="owner_settings")],
        [InlineKeyboardButton(text="🔙 Main Menu", callback_data="back_main")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def build_posts_editor():
    """Posts Editor တည်ဆောက်မယ်"""
    keyboard = []
    posts = db.get_posts()
    
    # Post တွေကို 2 Column နဲ့ပြမယ်
    row = []
    for i, (post_id, post) in enumerate(posts.items()):
        row.append(InlineKeyboardButton(
            text=post.text[:15] + "..." if len(post.text) > 15 else post.text,
            callback_data=f"edit_post_{post_id}"
        ))
        if len(row) == 2 or i == len(posts) - 1:
            keyboard.append(row)
            row = []
    
    # Control Buttons
    keyboard.extend([
        [InlineKeyboardButton(text="➕ Add Message", callback_data="add_post")],
        [InlineKeyboardButton(text="📄 Pagination (10)", callback_data="pagination")],
        [
            InlineKeyboardButton(text="🔘 Buttons Editor", callback_data="buttons_editor"),
            InlineKeyboardButton(text="⏹️ Stop Editor", callback_data="stop_editor")
        ]
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def build_message_settings(post_id: str):
    """Message Settings တည်ဆောက်မယ်"""
    post = db.get_post(post_id)
    
    keyboard = []
    
    # Inline Buttons တွေပြမယ်
    if post and post.buttons:
        row = []
        for i, btn in enumerate(post.buttons):
            btn_text = f"{btn.text} "
            if btn.type == ButtonType.URL:
                btn_text += "[u]"
            elif btn.type == ButtonType.POPUP:
                btn_text += "[p]"
            elif btn.type == ButtonType.COMMAND:
                btn_text += "[c]"
            
            row.append(InlineKeyboardButton(
                text=btn_text,
                callback_data=f"edit_button_{post_id}_{i}"
            ))
            if len(row) == 2 or i == len(post.buttons) - 1:
                keyboard.append(row)
                row = []
    
    # Button Management
    keyboard.extend([
        [
            InlineKeyboardButton(text="✏️ Edit", callback_data=f"edit_msg_{post_id}"),
            InlineKeyboardButton(text="🗑️ Del", callback_data=f"del_msg_{post_id}"),
            InlineKeyboardButton(text="📋 More", callback_data=f"more_msg_{post_id}"),
            InlineKeyboardButton(text="➕ Add", callback_data=f"add_button_{post_id}")
        ],
        [InlineKeyboardButton(text="🖼️ Media Variable", callback_data=f"media_{post_id}")],
        [InlineKeyboardButton(text="🔗 Links Preview", callback_data=f"links_{post_id}")],
        [InlineKeyboardButton(text="⏹️ Exit Message Settings", callback_data="back_posts")]
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def build_button_type_selector(post_id: str):
    """Button Type ရွေးချယ်ရန်"""
    keyboard = [
        [InlineKeyboardButton(text="🔗 URL or Share", callback_data=f"btn_url_{post_id}")],
        [InlineKeyboardButton(text="🪟 Pop-up Window", callback_data=f"btn_popup_{post_id}")],
        [InlineKeyboardButton(text="⚡ Command", callback_data=f"btn_cmd_{post_id}")],
        [InlineKeyboardButton(text="❌ Cancel", callback_data=f"cancel_btn_{post_id}")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def build_welcome_editor():
    """Welcome Editor တည်ဆောက်မယ်"""
    keyboard = [
        [InlineKeyboardButton(text="➕ Add Welcome", callback_data="add_welcome")],
        [InlineKeyboardButton(text="👁️ View Welcomes", callback_data="view_welcomes")],
        [InlineKeyboardButton(text="✏️ Edit Welcome", callback_data="edit_welcome")],
        [InlineKeyboardButton(text="🗑️ Delete Welcome", callback_data="delete_welcome")],
        [InlineKeyboardButton(text="✅ Set Active", callback_data="set_active_welcome")],
        [InlineKeyboardButton(text="🔙 Back", callback_data="back_admin")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

# ==================== HANDLERS ====================

@dp.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    """/start command - User စတင်အသုံးပြုချိန်"""
    user_mention = message.from_user.mention_html()
    welcome_text = db.get_active_welcome().format(mention=user_mention)
    
    await message.answer(
        text=welcome_text,
        reply_markup=build_main_menu(),
        parse_mode="HTML"
    )

@dp.callback_query(F.data == "admin_panel")
async def admin_panel(callback: CallbackQuery, state: FSMContext):
    """Admin Panel ကိုပြမယ်"""
    if callback.from_user.id not in ADMIN_IDS and callback.from_user.id != OWNER_ID:
        await callback.answer("သင်သည် Admin မဟုတ်ပါ။", show_alert=True)
        return
    
    await callback.message.edit_text(
        text="👑 **Admin Panel**\n\nအောက်ပါ Menu များမှ ရွေးချယ်ပါ။",
        reply_markup=build_admin_panel(),
        parse_mode="Markdown"
    )
    await callback.answer()

# ==================== POSTS EDITOR ====================

@dp.callback_query(F.data == "posts_editor")
async def posts_editor(callback: CallbackQuery, state: FSMContext):
    """Posts Editor ကိုပြမယ်"""
    await callback.message.edit_text(
        text="📝 **Posts Editor**\nYou are in Messages Editing mode.\n\nအောက်ပါ Message များကို ရွေးချယ်ပါ။",
        reply_markup=build_posts_editor(),
        parse_mode="Markdown"
    )
    await callback.answer()

@dp.callback_query(F.data == "add_post")
async def add_post_start(callback: CallbackQuery, state: FSMContext):
    """Message အသစ်ထည့်ရန်"""
    await callback.message.edit_text(
        text="➕ **Adding new Message**\n\nEnter New Message.\n\nYou can also <Forward> text from another chat or channel.",
        parse_mode="HTML"
    )
    await state.set_state(BotStates.waiting_post_text)
    await callback.answer()

@dp.message(BotStates.waiting_post_text)
async def add_post_text(message: Message, state: FSMContext):
    """Message စာသားရရှိချိန်"""
    post_id = f"post_{datetime.now().strftime('%Y%m%d%H%M%S')}"
    new_post = Message(id=post_id, text=message.text)
    db.add_post(new_post)
    
    await state.clear()
    await message.answer(
        text=f"✅ Message ထည့်ပြီးပါပြီ။\n\n**{message.text[:50]}**",
        reply_markup=build_posts_editor(),
        parse_mode="Markdown"
    )

@dp.callback_query(F.data.startswith("edit_post_"))
async def edit_post(callback: CallbackQuery, state: FSMContext):
    """Post တစ်ခုကို ပြင်ဆင်မယ်"""
    post_id = callback.data.replace("edit_post_", "")
    
    # Post data ကို settings မှာ ယာယီသိမ်းမယ်
    db.settings["current_message"] = post_id
    db.save_all()
    
    post = db.get_post(post_id)
    if not post:
        await callback.answer("Message မတွေ့ပါ။", show_alert=True)
        return
    
    # Post အချက်အလက်ပြမယ်
    display_text = f"**{post.text[:50]}**\n\n"
    if post.buttons:
        display_text += "Button များ:\n"
        for btn in post.buttons:
            btn_type = "🔗" if btn.type == ButtonType.URL else "🪟" if btn.type == ButtonType.POPUP else "⚡"
            display_text += f"{btn_type} {btn.text}\n"
    
    await callback.message.edit_text(
        text=display_text,
        reply_markup=build_message_settings(post_id),
        parse_mode="Markdown"
    )
    await callback.answer()

@dp.callback_query(F.data.startswith("add_button_"))
async def add_button_start(callback: CallbackQuery, state: FSMContext):
    """Button အသစ်ထည့်ရန်"""
    post_id = callback.data.replace("add_button_", "")
    
    await state.update_data(current_post=post_id)
    await callback.message.edit_text(
        text="Choose the MODE of Inline button:",
        reply_markup=build_button_type_selector(post_id)
    )
    await callback.answer()

@dp.callback_query(F.data.startswith("btn_url_"))
async def add_url_button(callback: CallbackQuery, state: FSMContext):
    """URL Button ထည့်မယ်"""
    post_id = callback.data.replace("btn_url_", "")
    await state.update_data(button_type=ButtonType.URL, post_id=post_id)
    
    await callback.message.edit_text(
        text="**Button Mode: URL or Share**\n\n"
             "Enter data for the URL/SHARE-button.\n\n"
             "For example to create <Share> button with the link:\n"
             "Share\n"
             "https://t.me/share/url?url=t.me/YourBot\n\n"
             "Data shall go in TWO LINES:\n"
             "BUTTON TITLE\n"
             "URL/Share address",
        parse_mode="Markdown"
    )
    await state.set_state(BotStates.waiting_button_url)
    await callback.answer()

@dp.message(BotStates.waiting_button_url)
async def process_url_button(message: Message, state: FSMContext):
    """URL Button Data ရရှိချိန်"""
    lines = message.text.strip().split('\n')
    if len(lines) < 2:
        await message.answer("ကျေးဇူးပြု၍ ပုံစံမှန်မှန်ထည့်ပါ။\nLine1: Button Name\nLine2: URL")
        return
    
    button_name = lines[0].strip()
    url = lines[1].strip()
    
    data = await state.get_data()
    post_id = data.get('post_id')
    
    post = db.get_post(post_id)
    if post:
        new_button = Button(text=button_name, button_type=ButtonType.URL, data=url)
        post.buttons.append(new_button)
        db.update_post(post_id, buttons=post.buttons)
        
        # Success Message
        await message.answer(
            text=f"✅ **Inline button successfully added!**\n\n"
                 f"[+] {button_name} [u]\n\n"
                 f"You can check its URL if you want to, and/or continue adding buttons.",
            parse_mode="Markdown"
        )
        
        # Message Settings ကိုပြန်ပြမယ်
        await message.answer(
            text="You are in the Message Settings mode.",
            reply_markup=build_message_settings(post_id)
        )
    
    await state.clear()

@dp.callback_query(F.data.startswith("btn_popup_"))
async def add_popup_button(callback: CallbackQuery, state: FSMContext):
    """Pop-up Window Button ထည့်မယ်"""
    post_id = callback.data.replace("btn_popup_", "")
    await state.update_data(button_type=ButtonType.POPUP, post_id=post_id)
    
    await callback.message.edit_text(
        text="**Button Mode: Pop-up Window**\n\n"
             "Enter data for the button with POP-UP WINDOW.\n\n"
             "Telegram limitation for this type of messages is 200 symbols.\n\n"
             "Data may go in SEVERAL LINES:\n"
             "BUTTON TITLE\n"
             "First line of the message\n"
             "Second line of the message",
        parse_mode="Markdown"
    )
    await state.set_state(BotStates.waiting_button_popup)
    await callback.answer()

@dp.message(BotStates.waiting_button_popup)
async def process_popup_button(message: Message, state: FSMContext):
    """Pop-up Button Data ရရှိချိန်"""
    lines = message.text.strip().split('\n')
    if len(lines) < 2:
        await message.answer("ကျေးဇူးပြု၍ ပုံစံမှန်မှန်ထည့်ပါ။\nLine1: Button Name\nLine2+: Pop-up Message")
        return
    
    button_name = lines[0].strip()
    popup_text = '\n'.join(lines[1:]).strip()
    
    if len(popup_text) > 200:
        await message.answer(f"Pop-up Message သည် စာလုံးရေ ၂၀၀ ထက်မပိုရပါ။ (လက်ရှိ: {len(popup_text)} လုံး)")
        return
    
    data = await state.get_data()
    post_id = data.get('post_id')
    
    post = db.get_post(post_id)
    if post:
        new_button = Button(text=button_name, button_type=ButtonType.POPUP, data=popup_text)
        post.buttons.append(new_button)
        db.update_post(post_id, buttons=post.buttons)
        
        await message.answer(
            text=f"✅ **Inline button successfully added!**\n\n"
                 f"[+] {button_name} [p]",
            parse_mode="Markdown"
        )
        
        await message.answer(
            text="You are in the Message Settings mode.",
            reply_markup=build_message_settings(post_id)
        )
    
    await state.clear()

@dp.callback_query(F.data.startswith("btn_cmd_"))
async def add_command_button(callback: CallbackQuery, state: FSMContext):
    """Command Button ထည့်မယ်"""
    post_id = callback.data.replace("btn_cmd_", "")
    await state.update_data(button_type=ButtonType.COMMAND, post_id=post_id)
    
    await callback.message.edit_text(
        text="**Button Mode: Command**\n\n"
             "Enter data for COMMAND button.\n\n"
             "Data shall go in TWO LINES:\n"
             "BUTTON TITLE\n"
             "Command (e.g., /back, /start, /help)",
        parse_mode="Markdown"
    )
    await state.set_state(BotStates.waiting_button_command)
    await callback.answer()

@dp.message(BotStates.waiting_button_command)
async def process_command_button(message: Message, state: FSMContext):
    """Command Button Data ရရှိချိန်"""
    lines = message.text.strip().split('\n')
    if len(lines) < 2:
        await message.answer("ကျေးဇူးပြု၍ ပုံစံမှန်မှန်ထည့်ပါ။\nLine1: Button Name\nLine2: Command")
        return
    
    button_name = lines[0].strip()
    command = lines[1].strip()
    
    data = await state.get_data()
    post_id = data.get('post_id')
    
    post = db.get_post(post_id)
    if post:
        new_button = Button(text=button_name, button_type=ButtonType.COMMAND, data=command)
        post.buttons.append(new_button)
        db.update_post(post_id, buttons=post.buttons)
        
        await message.answer(
            text=f"✅ **Inline button successfully added!**\n\n"
                 f"[+] {button_name} [c]",
            parse_mode="Markdown"
        )
        
        await message.answer(
            text="You are in the Message Settings mode.",
            reply_markup=build_message_settings(post_id)
        )
    
    await state.clear()

# ==================== BUTTONS EDITOR ====================

@dp.callback_query(F.data == "buttons_editor")
async def buttons_editor(callback: CallbackQuery, state: FSMContext):
    """Buttons Editor ကိုပြမယ်"""
    keyboard = []
    buttons = db.get_main_menu()
    
    row = []
    for i, btn in enumerate(buttons):
        row.append(InlineKeyboardButton(
            text=btn.text,
            callback_data=f"edit_main_btn_{i}"
        ))
        if len(row) == 2 or i == len(buttons) - 1:
            keyboard.append(row)
            row = []
    
    keyboard.extend([
        [InlineKeyboardButton(text="➕ Add Button", callback_data="add_main_button")],
        [
            InlineKeyboardButton(text="⏹️ Stop Editor", callback_data="back_main"),
            InlineKeyboardButton(text="📝 Posts Editor", callback_data="posts_editor")
        ]
    ])
    
    await callback.message.edit_text(
        text="🔘 **Buttons Editor**\nYou are in Button Editing mode.\n\nအောက်ပါ Button များကို စီမံနိုင်ပါသည်။",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard),
        parse_mode="Markdown"
    )
    await callback.answer()

@dp.callback_query(F.data == "add_main_button")
async def add_main_button(callback: CallbackQuery, state: FSMContext):
    """Main Menu Button အသစ်ထည့်မယ်"""
    await callback.message.edit_text(
        text="➕ **Adding new button**\n\nEnter a Name for the new button.\n\nPress < > Cancel> if you change your mind.",
        parse_mode="Markdown"
    )
    await state.set_state(BotStates.waiting_button_name)
    await callback.answer()

@dp.message(BotStates.waiting_button_name)
async def process_main_button_name(message: Message, state: FSMContext):
    """Main Menu Button Name ရရှိချိန်"""
    button_name = message.text.strip()
    
    new_button = Button(text=button_name, button_type=ButtonType.CALLBACK, data=f"category_{button_name.lower()}")
    db.add_main_menu_button(new_button)
    
    await message.answer(
        text=f"✅ Button '{button_name}' ကိုထည့်ပြီးပါပြီ။",
        reply_markup=build_main_menu()
    )
    await state.clear()

# ==================== WELCOME EDITOR ====================

@dp.callback_query(F.data == "welcome_editor")
async def welcome_editor(callback: CallbackQuery, state: FSMContext):
    """Welcome Editor ကိုပြမယ်"""
    await callback.message.edit_text(
        text="💬 **Welcome Editor**\n\nWelcome Message များကို စီမံနိုင်ပါသည်။",
        reply_markup=build_welcome_editor(),
        parse_mode="Markdown"
    )
    await callback.answer()

@dp.callback_query(F.data == "add_welcome")
async def add_welcome_start(callback: CallbackQuery, state: FSMContext):
    """Welcome Message အသစ်ထည့်ရန်"""
    await callback.message.edit_text(
        text="➕ **Add New Welcome**\n\nEnter Welcome Message text.\n\nUse {mention} for user mention.",
        parse_mode="Markdown"
    )
    await state.set_state(BotStates.adding_welcome)
    await callback.answer()

@dp.message(BotStates.adding_welcome)
async def add_welcome_text(message: Message, state: FSMContext):
    """Welcome Message ရရှိချိန်"""
    welcome = db.add_welcome(message.text)
    
    await message.answer(
        text=f"✅ Welcome Message ထည့်ပြီးပါပြီ။ (ID: {welcome['id']})",
        reply_markup=build_welcome_editor()
    )
    await state.clear()

# ==================== VIEW POSTS ====================

@dp.callback_query(F.data.startswith("menu_"))
async def handle_menu_click(callback: CallbackQuery, state: FSMContext):
    """Main Menu ကို နှိပ်တဲ့အခါ"""
    category = callback.data.replace("menu_", "")
    
    # Category အောက်က Post တွေကိုပြမယ်
    posts = db.get_posts()
    category_posts = [p for p in posts.values() if category.lower() in p.text.lower()]
    
    if not category_posts:
        await callback.answer("ဤအမျိုးအစားတွင် ဇာတ်ကားမရှိသေးပါ။")
        return
    
    # ပထမဆုံး Post ကိုပြမယ်
    post = category_posts[0]
    
    # Inline Keyboard တည်ဆောက်မယ်
    keyboard = []
    row = []
    for i, btn in enumerate(post.buttons[:4]):  # 4 buttons max
        if btn.type == ButtonType.URL:
            row.append(InlineKeyboardButton(text=btn.text, url=btn.data))
        elif btn.type == ButtonType.POPUP:
            row.append(InlineKeyboardButton(text=btn.text, callback_data=f"popup_{post.id}_{i}"))
        elif btn.type == ButtonType.COMMAND:
            row.append(InlineKeyboardButton(text=btn.text, callback_data=btn.data))
        
        if len(row) == 2 or i == min(len(post.buttons), 4) - 1:
            keyboard.append(row)
            row = []
    
    # Back Button
    keyboard.append([InlineKeyboardButton(text="🔙 Back", callback_data="back_main")])
    
    if post.media and post.media_type == "photo":
        await callback.message.answer_photo(
            photo=post.media,
            caption=post.text,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
        )
    elif post.media and post.media_type == "video":
        await callback.message.answer_video(
            video=post.media,
            caption=post.text,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
        )
    else:
        await callback.message.answer(
            text=post.text,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
        )
    
    await callback.answer()

@dp.callback_query(F.data.startswith("popup_"))
async def handle_popup(callback: CallbackQuery, state: FSMContext):
    """Pop-up Window Button နှိပ်တဲ့အခါ"""
    parts = callback.data.split('_')
    post_id = parts[1]
    btn_index = int(parts[2])
    
    post = db.get_post(post_id)
    if post and btn_index < len(post.buttons):
        btn = post.buttons[btn_index]
        if btn.type == ButtonType.POPUP:
            await callback.answer(btn.data, show_alert=True)
    
    await callback.answer()

@dp.callback_query(F.data == "back_main")
async def back_to_main(callback: CallbackQuery, state: FSMContext):
    """Main Menu ကိုပြန်သွားမယ်"""
    user_mention = callback.from_user.mention_html()
    welcome_text = db.get_active_welcome().format(mention=user_mention)
    
    await callback.message.edit_text(
        text=welcome_text,
        reply_markup=build_main_menu(),
        parse_mode="HTML"
    )
    await callback.answer()

@dp.callback_query(F.data == "back_admin")
async def back_to_admin(callback: CallbackQuery, state: FSMContext):
    """Admin Panel ကိုပြန်သွားမယ်"""
    await admin_panel(callback, state)

@dp.callback_query(F.data == "back_posts")
async def back_to_posts(callback: CallbackQuery, state: FSMContext):
    """Posts Editor ကိုပြန်သွားမယ်"""
    await posts_editor(callback, state)

@dp.callback_query(F.data == "stop_editor")
async def stop_editor(callback: CallbackQuery, state: FSMContext):
    """Editor ကိုရပ်ပြီး Main Menu ပြန်သွားမယ်"""
    db.settings["editing_mode"] = False
    db.settings["current_editor"] = None
    db.settings["current_message"] = None
    db.save_all()
    
    await back_to_main(callback, state)

# ==================== ERROR HANDLER ====================
@dp.errors()
async def errors_handler(update: Update, exception: Exception):
    logger.error(f"Update {update} caused error {exception}")
    return True

# ==================== MAIN FUNCTION ====================
async def main():
    """Bot ကိုစတင်မယ်"""
    logger.info("Starting bot...")
    
    # Default Main Menu Buttons (အကယ်၍မရှိသေးရင်)
    if not db.get_main_menu():
        default_buttons = ["🎬 Movies", "📺 Anime", "🎥 Trailers", "📞 Contact"]
        for btn_text in default_buttons:
            db.add_main_menu_button(Button(
                text=btn_text,
                button_type=ButtonType.CALLBACK,
                data=f"category_{btn_text.lower()}"
            ))
    
    # Default Welcome Message
    if not db.welcomes["messages"]:
        db.add_welcome("မင်္ဂလာပါ {mention}!\n\nAnime Japan ကိုကြိုဆိုပါတယ်။\nအောက်က Menu လေးတွေကနေ ရွေးကြည့်နော်။")
    
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
