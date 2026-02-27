import asyncio
import logging
from datetime import datetime
from typing import Union
import sqlite3
import random
import json
from contextlib import contextmanager

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ==================== CONFIGURATION ====================
BOT_TOKEN = "YOUR_BOT_TOKEN_HERE"
OWNER_ID = 123456789  # Replace with your Telegram ID
GROUP_ID = -100123456789  # Replace with your Group ID

# ==================== DATABASE ====================
class Database:
    def __init__(self, db_name="bot_data.db"):
        self.db_name = db_name
        self.init_db()
    
    @contextmanager
    def get_connection(self):
        conn = sqlite3.connect(self.db_name)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()
    
    def init_db(self):
        with self.get_connection() as conn:
            # Users table
            conn.execute('''CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                full_name TEXT,
                balance INTEGER DEFAULT 0,
                total_invite INTEGER DEFAULT 0,
                invite_limit INTEGER DEFAULT 100,
                last_game_amount INTEGER DEFAULT 0,
                last_game_time TEXT,
                phone TEXT,
                kpay_name TEXT,
                join_date TEXT
            )''')
            
            # Game settings table
            conn.execute('''CREATE TABLE IF NOT EXISTS game_settings (
                id INTEGER PRIMARY KEY CHECK (id=1),
                total_amount INTEGER DEFAULT 0,
                current_amount INTEGER DEFAULT 0,
                game_active INTEGER DEFAULT 0
            )''')
            
            # Game winners table
            conn.execute('''CREATE TABLE IF NOT EXISTS game_winners (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                username TEXT,
                full_name TEXT,
                amount INTEGER,
                win_time TEXT
            )''')
            
            # Force channels table
            conn.execute('''CREATE TABLE IF NOT EXISTS force_channels (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                channel_id TEXT UNIQUE,
                channel_name TEXT,
                channel_link TEXT,
                added_date TEXT
            )''')
            
            # Insert default game settings
            conn.execute("INSERT OR IGNORE INTO game_settings (id) VALUES (1)")

# ==================== FSM STATES ====================
class AdminStates(StatesGroup):
    waiting_for_amount = State()
    waiting_for_channel_link = State()
    waiting_for_channel_name = State()
    waiting_for_withdraw_name = State()
    waiting_for_withdraw_phone = State()

class UserStates(StatesGroup):
    waiting_for_withdraw_info = State()

# ==================== INITIALIZE ====================
db = Database()
bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# ==================== MAIN MENU KEYBOARD ====================
def main_menu_keyboard():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🎲 ကံစမ်းမည်", callback_data="play_game"),
            InlineKeyboardButton(text="💰 ထုတ်ယူရန်", callback_data="withdraw")
        ],
        [
            InlineKeyboardButton(text="📊 My Info", callback_data="my_info"),
            InlineKeyboardButton(text="👥 Invite", callback_data="invite")
        ]
    ])
    return keyboard

# ==================== CHANNEL CHECK ====================
async def check_channels(user_id: int) -> tuple[bool, list]:
    """Check if user joined all force channels"""
    with db.get_connection() as conn:
        channels = conn.execute("SELECT * FROM force_channels").fetchall()
    
    not_joined = []
    for channel in channels:
        try:
            member = await bot.get_chat_member(chat_id=channel['channel_id'], user_id=user_id)
            if member.status in ['left', 'kicked']:
                not_joined.append(channel)
        except:
            not_joined.append(channel)
    
    return len(not_joined) == 0, not_joined

def get_force_channels_keyboard(channels):
    """Create keyboard for force channels"""
    keyboard = []
    for channel in channels:
        if channel['channel_link']:
            keyboard.append([InlineKeyboardButton(
                text=f"📢 Join {channel['channel_name']}", 
                url=channel['channel_link']
            )])
    
    keyboard.append([InlineKeyboardButton(
        text="🔄 Check Again", 
        callback_data="check_join"
    )])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

# ==================== START COMMAND ====================
@dp.message(Command("start"))
async def cmd_start(message: Message):
    user_id = message.from_user.id
    username = message.from_user.username or "No username"
    full_name = message.from_user.full_name
    
    # Add user to database if not exists
    with db.get_connection() as conn:
        user = conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()
        if not user:
            conn.execute(
                "INSERT INTO users (user_id, username, full_name, join_date) VALUES (?, ?, ?, ?)",
                (user_id, username, full_name, datetime.now().isoformat())
            )
    
    # Check force channels
    joined, not_joined = await check_channels(user_id)
    
    if not joined:
        keyboard = get_force_channels_keyboard(not_joined)
        await message.answer(
            "🔒 ကျေးဇူးပြု၍ အောက်ပါ Channel များကို Join ပေးပါ။",
            reply_markup=keyboard
        )
        return
    
    # Show main menu
    await message.answer(
        f"ကြိုဆိုပါတယ် {full_name} ရေ...\n\nအောက်က ခလုတ်လေးတွေကနေ လုပ်ဆောင်နိုင်ပါတယ်။",
        reply_markup=main_menu_keyboard()
    )

@dp.callback_query(F.data == "check_join")
async def check_join_callback(callback: CallbackQuery):
    user_id = callback.from_user.id
    joined, not_joined = await check_channels(user_id)
    
    if joined:
        await callback.message.delete()
        await cmd_start(callback.message)
    else:
        await callback.answer("ကျေးဇူးပြု၍ Channel များကို Join ပါ။", show_alert=True)

# ==================== MY INFO ====================
@dp.callback_query(F.data == "my_info")
async def my_info(callback: CallbackQuery):
    user_id = callback.from_user.id
    
    with db.get_connection() as conn:
        user = conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()
        
        if not user:
            await callback.answer("User not found!")
            return
        
        info_text = f"""
📋 **My Information**
━━━━━━━━━━━━━━━━
👤 နာမည် - {user['full_name']}
🆔 User ID - `{user['user_id']}`
👥 Total Invite - {user['total_invite']} ယောက်
💰 လက်ကျန်ငွေ - {user['balance']} ကျပ်
🎲 နောက်ဆုံးကံစမ်းခဲ့သည့်ငွေ - {user['last_game_amount']} ကျပ်
⏰ နောက်ဆုံးကံစမ်းခဲ့သည့်အချိန် - {user['last_game_time'] or 'မရှိသေးပါ'}
━━━━━━━━━━━━━━━━
        """
        
        await callback.message.edit_text(info_text, reply_markup=main_menu_keyboard())

# ==================== INVITE SYSTEM ====================
@dp.callback_query(F.data == "invite")
async def invite_link(callback: CallbackQuery):
    user_id = callback.from_user.id
    
    with db.get_connection() as conn:
        user = conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()
        
        if not user:
            await callback.answer("User not found!")
            return
        
        # Generate invite link
        bot_info = await bot.get_me()
        invite_link = f"https://t.me/{bot_info.username}?start=ref_{user_id}"
        
        invite_text = f"""
👥 **Invite Friends**

လူတစ်ယောက်ခေါ်ရင် 50 ကျပ်ရမည်။
သင်၏လက်ရှိခေါ်ဆောင်ထားသူ: {user['total_invite']} ယောက်
ခေါ်ဆောင်နိုင်သည့်အများဆုံး: {user['invite_limit']} ယောက်

**သင်၏ Invite Link:**
`{invite_link}`

👉 အထက်ပါ Link ကိုနှိပ်၍ Copy ကူးနိုင်ပါသည်။
        """
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📋 Copy Link", callback_data=f"copy_{invite_link}")],
            [InlineKeyboardButton(text="🔙 Back", reply_to="back_to_main")]
        ])
        
        await callback.message.edit_text(invite_text, reply_markup=keyboard)
        
        # Check if reached limit
        if user['total_invite'] >= user['invite_limit']:
            request_keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📢 Request More", callback_data="request_limit")],
                [InlineKeyboardButton(text="🔙 Back", callback_data="back_to_main")]
            ])
            await callback.message.answer(
                "⚠️ သင်၏ Invite Limit ပြည့်သွားပါပြီ။ Limit တိုးရန် Request လုပ်ပါ။",
                reply_markup=request_keyboard
            )

@dp.callback_query(F.data == "request_limit")
async def request_limit(callback: CallbackQuery):
    user_id = callback.from_user.id
    
    with db.get_connection() as conn:
        user = conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()
        
        if not user:
            await callback.answer("User not found!")
            return
        
        # Send to owner
        request_text = f"""
📢 **Limit တိုးရန် Request**
━━━━━━━━━━━━━━━━
👤 နာမည် - {user['full_name']}
🆔 User ID - `{user['user_id']}`
🔗 Username - @{user['username']}
👥 Total Invite - {user['total_invite']}
📊 Current Limit - {user['invite_limit']}
━━━━━━━━━━━━━━━━
        """
        
        confirm_keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Confirm", callback_data=f"confirm_limit_{user['user_id']}"),
                InlineKeyboardButton(text="❌ Cancel", callback_data=f"cancel_limit_{user['user_id']}")
            ]
        ])
        
        await bot.send_message(OWNER_ID, request_text, reply_markup=confirm_keyboard)
        await callback.answer("Request sent to owner!", show_alert=True)

# ==================== GAME SYSTEM ====================
@dp.callback_query(F.data == "play_game")
async def play_game(callback: CallbackQuery):
    user_id = callback.from_user.id
    
    # Check force channels first
    joined, not_joined = await check_channels(user_id)
    if not joined:
        keyboard = get_force_channels_keyboard(not_joined)
        await callback.message.answer(
            "🔒 ကျေးဇူးပြု၍ အောက်ပါ Channel များကို Join ပေးပါ။",
            reply_markup=keyboard
        )
        return
    
    with db.get_connection() as conn:
        game = conn.execute("SELECT * FROM game_settings WHERE id = 1").fetchone()
        
        if not game['game_active']:
            await callback.answer("ဂိမ်းမစတင်သေးပါ။ Owner စတင်ရန်စောင့်ဆိုင်းပါ။", show_alert=True)
            return
        
        if game['current_amount'] <= 0:
            await callback.answer("ကံစမ်းငွေကုန်သွားပါပြီ။ နောက်ရက်မှကံစမ်းပါ။", show_alert=True)
            return
        
        # Random amount between 100 and 500
        game_amount = random.randint(100, 500)
        
        # Make sure not to exceed current amount
        if game_amount > game['current_amount']:
            game_amount = game['current_amount']
        
        # Update game and user
        new_amount = game['current_amount'] - game_amount
        conn.execute(
            "UPDATE game_settings SET current_amount = ? WHERE id = 1",
            (new_amount,)
        )
        
        conn.execute(
            """UPDATE users SET 
               balance = balance + ?,
               last_game_amount = ?,
               last_game_time = ?
               WHERE user_id = ?""",
            (game_amount, game_amount, datetime.now().isoformat(), user_id)
        )
        
        # Save winner
        user = conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()
        conn.execute(
            """INSERT INTO game_winners 
               (user_id, username, full_name, amount, win_time) 
               VALUES (?, ?, ?, ?, ?)""",
            (user_id, user['username'], user['full_name'], game_amount, datetime.now().isoformat())
        )
        
        await callback.answer(f"ဂုဏ်ယူပါတယ်။ သင်ကံစမ်းရရှိငွေ {game_amount} ကျပ်", show_alert=True)
        
        # Check if game amount finished
        if new_amount <= 0:
            # Update game inactive
            conn.execute("UPDATE game_settings SET game_active = 0 WHERE id = 1")
            
            # Get all winners
            winners = conn.execute(
                "SELECT * FROM game_winners ORDER BY win_time DESC"
            ).fetchall()
            
            # Send winners list to owner
            winners_text = "📊 **ဂိမ်းပြီးဆုံးချိန် ရလဒ်များ**\n\n"
            total_given = 0
            
            for w in winners:
                winners_text += f"👤 {w['full_name']} (@{w['username']})\n"
                winners_text += f"🆔 `{w['user_id']}`\n"
                winners_text += f"💰 ရရှိငွေ - {w['amount']} ကျပ်\n"
                winners_text += f"⏰ {w['win_time']}\n\n"
                total_given += w['amount']
            
            winners_text += f"━━━━━━━━━━━━━━━━\n"
            winners_text += f"စုစုပေါင်းပေးအပ်ငွေ: {total_given} ကျပ်"
            
            await bot.send_message(OWNER_ID, winners_text)
            await bot.send_message(OWNER_ID, "⚠️ ကံစမ်းငွေကုန်သွားပါပြီ။ ဂိမ်းရပ်နားထားပါသည်။")

# ==================== WITHDRAW SYSTEM ====================
@dp.callback_query(F.data == "withdraw")
async def withdraw_start(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    
    with db.get_connection() as conn:
        user = conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()
        
        if not user or user['balance'] <= 0:
            await callback.answer("သင့်တွင်ငွေမရှိပါ။", show_alert=True)
            return
    
    await callback.message.edit_text(
        "💰 **ငွေထုတ်ယူရန်**\n\n"
        "ကျေးဇူးပြု၍ သင့် KPay/Wave နာမည်နှင့် ဖုန်းနံပါတ်ကို ရိုက်ထည့်ပါ။\n"
        "ပုံစံ - နာမည်၊ဖုန်းနံပါတ်\n"
        "ဥပမာ - မောင်မောင်၊၀၉၄၂၈၅၆၃၆၃"
    )
    await state.set_state(UserStates.waiting_for_withdraw_info)

@dp.message(UserStates.waiting_for_withdraw_info)
async def process_withdraw_info(message: Message, state: FSMContext):
    try:
        name, phone = message.text.split(',')
        name = name.strip()
        phone = phone.strip()
        
        user_id = message.from_user.id
        username = message.from_user.username or "No username"
        full_name = message.from_user.full_name
        
        with db.get_connection() as conn:
            user = conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()
            
            # Update user phone and name
            conn.execute(
                "UPDATE users SET phone = ?, kpay_name = ? WHERE user_id = ?",
                (phone, name, user_id)
            )
            
            # Send to owner
            withdraw_text = f"""
📤 **ငွေထုတ်ယူရန် တောင်းဆိုချက်**
━━━━━━━━━━━━━━━━
👤 အမည် - {full_name}
🆔 User ID - `{user_id}`
🔗 Username - @{username}
💰 ထုတ်ယူမည့်ငွေ - {user['balance']} ကျပ်
💳 ငွေလက်ခံမည့် အကောင့် - KPay/Wave
📞 ဖုန်းနံပါတ် - {phone}
💵 လက်ကျန်ငွေ - {user['balance']} ကျပ်
━━━━━━━━━━━━━━━━
            """
            
            confirm_keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(text="✅ Confirm", callback_data=f"confirm_withdraw_{user_id}"),
                    InlineKeyboardButton(text="❌ Cancel", callback_data=f"cancel_withdraw_{user_id}")
                ]
            ])
            
            await bot.send_message(OWNER_ID, withdraw_text, reply_markup=confirm_keyboard)
            
        await message.answer("သင်၏တောင်းဆိုချက်ကို Owner ထံပို့လိုက်ပါပြီ။ ခွင့်ပြုချက်စောင့်ဆိုင်းပါ။")
        await state.clear()
        
        # Show main menu again
        await message.answer("Main Menu", reply_markup=main_menu_keyboard())
            
    except Exception as e:
        await message.answer("ပုံစံမှားနေပါသည်။ နမူနာလိုက်ပါ။ နာမည်၊ဖုန်းနံပါတ်")

# ==================== ADMIN COMMANDS ====================
@dp.message(Command("admin"))
async def admin_panel(message: Message):
    if message.from_user.id != OWNER_ID:
        return
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="💰 ငွေထည့်ရန်", callback_data="admin_add_amount"),
            InlineKeyboardButton(text="📊 Game Status", callback_data="admin_game_status")
        ],
        [
            InlineKeyboardButton(text="🔐 Force Channel", callback_data="admin_force"),
            InlineKeyboardButton(text="📈 Statistics", callback_data="admin_stats")
        ],
        [
            InlineKeyboardButton(text="🎮 ဂိမ်းစတင်ရန်", callback_data="admin_start_game"),
            InlineKeyboardButton(text="⏹ ဂိမ်းရပ်ရန်", callback_data="admin_stop_game")
        ]
    ])
    
    await message.answer(
        "👑 **Admin Panel**\n\nအောက်ပါလုပ်ဆောင်ချက်များကို ရွေးချယ်ပါ။",
        reply_markup=keyboard
    )

@dp.callback_query(F.data == "admin_add_amount")
async def admin_add_amount(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id != OWNER_ID:
        return
    
    await callback.message.edit_text(
        "💰 ကံစမ်းငွေထည့်ရန်\n\n"
        "ငွေပမာဏ ရိုက်ထည့်ပါ။"
    )
    await state.set_state(AdminStates.waiting_for_amount)

@dp.message(AdminStates.waiting_for_amount)
async def process_add_amount(message: Message, state: FSMContext):
    if message.from_user.id != OWNER_ID:
        return
    
    try:
        amount = int(message.text)
        
        with db.get_connection() as conn:
            game = conn.execute("SELECT * FROM game_settings WHERE id = 1").fetchone()
            new_total = game['total_amount'] + amount
            new_current = game['current_amount'] + amount
            
            conn.execute(
                "UPDATE game_settings SET total_amount = ?, current_amount = ? WHERE id = 1",
                (new_total, new_current)
            )
        
        await message.answer(f"✅ ငွေထည့်ပြီးပါပြီ။ လက်ရှိငွေ: {new_current} ကျပ်")
        await state.clear()
        
    except ValueError:
        await message.answer("နံပါတ်သာရိုက်ပါ။")

@dp.callback_query(F.data == "admin_start_game")
async def admin_start_game(callback: CallbackQuery):
    if callback.from_user.id != OWNER_ID:
        return
    
    with db.get_connection() as conn:
        game = conn.execute("SELECT * FROM game_settings WHERE id = 1").fetchone()
        
        if game['current_amount'] <= 0:
            await callback.answer("ငွေအရင်ထည့်ပါ။", show_alert=True)
            return
        
        conn.execute("UPDATE game_settings SET game_active = 1 WHERE id = 1")
    
    await callback.answer("ဂိမ်းစတင်ပါပြီ။")
    await admin_panel(callback.message)

@dp.callback_query(F.data == "admin_stop_game")
async def admin_stop_game(callback: CallbackQuery):
    if callback.from_user.id != OWNER_ID:
        return
    
    with db.get_connection() as conn:
        conn.execute("UPDATE game_settings SET game_active = 0 WHERE id = 1")
    
    await callback.answer("ဂိမ်းရပ်နားထားပါသည်။")
    await admin_panel(callback.message)

@dp.callback_query(F.data == "admin_game_status")
async def admin_game_status(callback: CallbackQuery):
    if callback.from_user.id != OWNER_ID:
        return
    
    with db.get_connection() as conn:
        game = conn.execute("SELECT * FROM game_settings WHERE id = 1").fetchone()
    
    status_text = f"""
📊 **Game Status**
━━━━━━━━━━━━━━━━
💰 စုစုပေါင်းငွေ - {game['total_amount']} ကျပ်
💵 လက်ကျန်ငွေ - {game['current_amount']} ကျပ်
🎮 ဂိမ်းအခြေအနေ - {'ဖွင့်ထားသည်' if game['game_active'] else 'ပိတ်ထားသည်'}
━━━━━━━━━━━━━━━━
    """
    
    await callback.message.edit_text(
        status_text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Back", callback_data="admin_back")]
        ])
    )

@dp.callback_query(F.data == "admin_stats")
async def admin_stats(callback: CallbackQuery):
    if callback.from_user.id != OWNER_ID:
        return
    
    with db.get_connection() as conn:
        total_users = conn.execute("SELECT COUNT(*) as count FROM users").fetchone()['count']
        total_balance = conn.execute("SELECT SUM(balance) as total FROM users").fetchone()['total'] or 0
        game = conn.execute("SELECT * FROM game_settings WHERE id = 1").fetchone()
        channels = conn.execute("SELECT COUNT(*) as count FROM force_channels").fetchone()['count']
        total_winners = conn.execute("SELECT COUNT(*) as count FROM game_winners").fetchone()['count']
        total_given = conn.execute("SELECT SUM(amount) as total FROM game_winners").fetchone()['total'] or 0
    
    stats_text = f"""
📈 **Bot Statistics**
━━━━━━━━━━━━━━━━
👥 စုစုပေါင်းအသုံးပြုသူ - {total_users}
💰 စုစုပေါင်းလက်ကျန်ငွေ - {total_balance} ကျပ်
🎲 ဂိမ်းလက်ကျန်ငွေ - {game['current_amount']} ကျပ်
🔐 Force Channels - {channels} ခု
🏆 စုစုပေါင်းဆုရှင် - {total_winners} ဦး
💸 စုစုပေါင်းပေးအပ်ငွေ - {total_given} ကျပ်
━━━━━━━━━━━━━━━━
    """
    
    await callback.message.edit_text(
        stats_text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Back", callback_data="admin_back")]
        ])
    )

# ==================== FORCE CHANNEL SYSTEM ====================
@dp.callback_query(F.data == "admin_force")
async def admin_force(callback: CallbackQuery):
    if callback.from_user.id != OWNER_ID:
        return
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="➕ Add Channel", callback_data="force_add"),
            InlineKeyboardButton(text="📋 List Channels", callback_data="force_list")
        ],
        [
            InlineKeyboardButton(text="🔙 Back", callback_data="admin_back")
        ]
    ])
    
    await callback.message.edit_text(
        "🔐 **Force Channel Settings**\n\n"
        "Channel တွေထည့်ရန် Add Channel ကိုနှိပ်ပါ။\n"
        "Channel တွေကြည့်ရန် List Channels ကိုနှိပ်ပါ။",
        reply_markup=keyboard
    )

@dp.callback_query(F.data == "force_add")
async def force_add_start(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "➕ **Add Channel**\n\n"
        "Channel Link ကိုရိုက်ထည့်ပါ။\n"
        "ဥပမာ: https://t.me/yourchannel"
    )
    await state.set_state(AdminStates.waiting_for_channel_link)

@dp.message(AdminStates.waiting_for_channel_link)
async def force_add_channel_link(message: Message, state: FSMContext):
    channel_link = message.text.strip()
    await state.update_data(channel_link=channel_link)
    
    await message.answer(
        "Channel Name ကိုရိုက်ထည့်ပါ။"
    )
    await state.set_state(AdminStates.waiting_for_channel_name)

@dp.message(AdminStates.waiting_for_channel_name)
async def force_add_channel_name(message: Message, state: FSMContext):
    channel_name = message.text.strip()
    data = await state.get_data()
    
    # Extract channel ID from link
    channel_username = data['channel_link'].split('/')[-1]
    
    try:
        chat = await bot.get_chat(f"@{channel_username}")
        channel_id = str(chat.id)
        
        with db.get_connection() as conn:
            conn.execute(
                "INSERT INTO force_channels (channel_id, channel_name, channel_link, added_date) VALUES (?, ?, ?, ?)",
                (channel_id, channel_name, data['channel_link'], datetime.now().isoformat())
            )
        
        await message.answer(f"✅ Channel {channel_name} added successfully!\n\nBot ကို Channel မှာ Admin လုပ်ထားရန်မမေ့ပါနှင့်။")
        await state.clear()
        
    except Exception as e:
        await message.answer(f"❌ Error: {str(e)}\n\nChannel ID ရှာမတွေ့ပါ။ Bot ကို Channel မှာ Admin လုပ်ထားကြောင်းစစ်ပါ။")

@dp.callback_query(F.data == "force_list")
async def force_list(callback: CallbackQuery):
    with db.get_connection() as conn:
        channels = conn.execute("SELECT * FROM force_channels").fetchall()
    
    if not channels:
        await callback.message.edit_text(
            "No channels added yet.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Back", callback_data="admin_force")]
            ])
        )
        return
    
    text = "📋 **Force Channels**\n\n"
    keyboard = []
    
    for i, channel in enumerate(channels, 1):
        text += f"{i}. {channel['channel_name']}\n"
        text += f"   Link: {channel['channel_link']}\n\n"
        keyboard.append([InlineKeyboardButton(
            text=f"❌ Delete {channel['channel_name']}",
            callback_data=f"del_chan_{channel['id']}"
        )])
    
    keyboard.append([InlineKeyboardButton(text="🔙 Back", callback_data="admin_force")])
    
    await callback.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
    )

@dp.callback_query(F.data.startswith("del_chan_"))
async def force_delete_channel(callback: CallbackQuery):
    channel_id = int(callback.data.split("_")[2])
    
    with db.get_connection() as conn:
        conn.execute("DELETE FROM force_channels WHERE id = ?", (channel_id,))
    
    await callback.answer("Channel deleted!")
    await force_list(callback)

# ==================== ADMIN CALLBACKS ====================
@dp.callback_query(F.data == "admin_back")
async def admin_back(callback: CallbackQuery):
    if callback.from_user.id != OWNER_ID:
        return
    
    await admin_panel(callback.message)

# ==================== WITHDRAW CONFIRM CALLBACKS ====================
@dp.callback_query(F.data.startswith("confirm_withdraw_"))
async def confirm_withdraw(callback: CallbackQuery):
    if callback.from_user.id != OWNER_ID:
        return
    
    user_id = int(callback.data.split("_")[2])
    
    with db.get_connection() as conn:
        user = conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()
        
        if not user:
            await callback.answer("User not found!")
            return
        
        # Generate transfer ID
        transfer_id = f"TRX{random.randint(100000, 999999)}"
        
        # Update user balance (deduct)
        conn.execute(
            "UPDATE users SET balance = 0 WHERE user_id = ?",
            (user_id,)
        )
        
        # Send receipt to user
        receipt_text = f"""
📤 **ငွေထုတ်ပြေစာ**
━━━━━━━━━━━━━━━━
👤 ငွေထုတ်ယူသူအမည် - {user['full_name']}
🆔 User ID - `{user['user_id']}`
💰 ထုတ်ယူခဲ့သည့်ငွေ - {user['balance']} ကျပ်
💳 ငွေပေးပို့သူအမည် - Owner
📤 လွဲပေးခဲ့သည့်ငွေ - {user['balance']} ကျပ်
⏰ အချိန် - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
🔢 ပြေစာ Transfer ID - `{transfer_id}`
━━━━━━━━━━━━━━━━
✨ ကျေးဇူးတင်ပါသည်။
        """
        
        await bot.send_message(user_id, receipt_text)
        
        # Send to group
        group_text = f"{user['full_name']} နက် {user['balance']} ကျပ် ထုတ်ယူပြီးပါပြီ။ အကောင့်ထဲဝင်စစ်ပေးပါ။"
        await bot.send_message(GROUP_ID, group_text)
    
    await callback.message.edit_text(f"✅ Withdraw confirmed for user {user_id}")
    await callback.answer("Withdraw confirmed!")

@dp.callback_query(F.data.startswith("cancel_withdraw_"))
async def cancel_withdraw(callback: CallbackQuery):
    if callback.from_user.id != OWNER_ID:
        return
    
    user_id = int(callback.data.split("_")[2])
    
    await bot.send_message(
        user_id,
        "❌ သင့်ငွေထုတ်ယူရန် တောင်းဆိုချက်ကို ပယ်ဖျက်လိုက်ပါသည်။"
    )
    
    await callback.message.edit_text(f"✅ Withdraw cancelled for user {user_id}")
    await callback.answer("Withdraw cancelled!")

# ==================== LIMIT CONFIRM CALLBACKS ====================
@dp.callback_query(F.data.startswith("confirm_limit_"))
async def confirm_limit(callback: CallbackQuery):
    if callback.from_user.id != OWNER_ID:
        return
    
    user_id = int(callback.data.split("_")[2])
    
    with db.get_connection() as conn:
        conn.execute(
            "UPDATE users SET invite_limit = 200 WHERE user_id = ?",
            (user_id,)
        )
    
    await bot.send_message(
        user_id,
        "✅ သင်၏ Invite Limit ကို 200 သို့တိုးပေးလိုက်ပါပြီ။"
    )
    
    await callback.message.edit_text(f"✅ Limit increased for user {user_id}")
    await callback.answer("Limit confirmed!")

@dp.callback_query(F.data.startswith("cancel_limit_"))
async def cancel_limit(callback: CallbackQuery):
    if callback.from_user.id != OWNER_ID:
        return
    
    user_id = int(callback.data.split("_")[2])
    
    await bot.send_message(
        user_id,
        "
