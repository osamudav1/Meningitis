import asyncio
import logging
from datetime import datetime, timedelta
from typing import Union
import sqlite3
import random
import json
from contextlib import contextmanager

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ==================== CONFIGURATION ====================
import os

BOT_TOKEN = os.environ.get('BOT_TOKEN')
OWNER_ID = int(os.environ.get('OWNER_ID', 0))
GROUP_ID = int(os.environ.get('GROUP_ID', 0))

print(f"BOT_TOKEN from env: {BOT_TOKEN}")
print(f"OWNER_ID from env: {OWNER_ID}")
print(f"GROUP_ID from env: {GROUP_ID}")

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN environment variable not set!")

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
                join_date TEXT,
                has_played BOOLEAN DEFAULT 0,
                referred_by INTEGER DEFAULT 0,
                has_played_for_referral BOOLEAN DEFAULT 0
            )''')
            
            # Game settings table
            conn.execute('''CREATE TABLE IF NOT EXISTS game_settings (
                id INTEGER PRIMARY KEY CHECK (id=1),
                total_amount INTEGER DEFAULT 0,
                current_amount INTEGER DEFAULT 0,
                game_active INTEGER DEFAULT 0,
                game_date TEXT
            )''')
            
            # Game winners table
            conn.execute('''CREATE TABLE IF NOT EXISTS game_winners (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                username TEXT,
                full_name TEXT,
                amount INTEGER,
                win_time TEXT,
                game_date TEXT
            )''')
            
            # Force channels table
            conn.execute('''CREATE TABLE IF NOT EXISTS force_channels (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                channel_id TEXT UNIQUE,
                channel_name TEXT,
                channel_link TEXT,
                added_date TEXT
            )''')
            
            # Referral table
            conn.execute('''CREATE TABLE IF NOT EXISTS referrals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                referrer_id INTEGER,
                referred_id INTEGER UNIQUE,
                referred_date TEXT,
                bonus_paid BOOLEAN DEFAULT 0
            )''')
            
            # Welcome settings table
            conn.execute('''CREATE TABLE IF NOT EXISTS welcome_settings (
                id INTEGER PRIMARY KEY CHECK (id=1),
                welcome_text TEXT DEFAULT 'ကြိုဆိုပါတယ် {name} ရေ...\n\nအောက်က ခလုတ်လေးတွေကနေ လုပ်ဆောင်နိုင်ပါတယ်။',
                buttons TEXT DEFAULT '[]'
            )''')
            
            # Insert default game settings
            conn.execute("INSERT OR IGNORE INTO game_settings (id) VALUES (1)")
            conn.execute("INSERT OR IGNORE INTO welcome_settings (id) VALUES (1)")

# ==================== FSM STATES ====================
class AdminStates(StatesGroup):
    waiting_for_amount = State()
    waiting_for_channel_link = State()
    waiting_for_channel_name = State()
    waiting_for_broadcast = State()
    waiting_for_broadcast_button = State()
    waiting_for_welcome_text = State()
    waiting_for_welcome_buttons = State()

class UserStates(StatesGroup):
    waiting_for_payment_method = State()
    waiting_for_account_name = State()
    waiting_for_phone = State()
    waiting_for_withdraw_amount = State()

# ==================== INITIALIZE ====================
db = Database()
bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# ==================== MAIN MENU KEYBOARD (Reply Keyboard) ====================
def main_menu_keyboard():
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="🎲 ကံစမ်းမည်"),
                KeyboardButton(text="💰 ထုတ်ယူရန်")
            ],
            [
                KeyboardButton(text="📊 My Info"),
                KeyboardButton(text="👥 Invite")
            ]
        ],
        resize_keyboard=True,
        input_field_placeholder="မီနူးတစ်ခုခုကိုရွေးချယ်ပါ..."
    )
    return keyboard

def back_button_keyboard():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Back", callback_data="back_to_main")]
    ])
    return keyboard

def parse_buttons(buttons_json: str):
    """Parse buttons from JSON string"""
    try:
        return json.loads(buttons_json)
    except:
        return []

def create_button_keyboard(buttons_data):
    """Create keyboard from button data"""
    if not buttons_data:
        return None
    
    keyboard = []
    row = []
    for i, btn in enumerate(buttons_data):
        row.append(InlineKeyboardButton(text=btn['text'], url=btn.get('url', '')))
        if len(row) == 2:  # 2 columns
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

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
    
    # Extract referrer from start command
    referrer_id = None
    if message.text and len(message.text.split()) > 1:
        try:
            referrer_id = int(message.text.split()[1].replace("ref_", ""))
        except:
            pass
    
    # Add user to database if not exists
    with db.get_connection() as conn:
        user = conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()
        if not user:
            conn.execute(
                """INSERT INTO users 
                   (user_id, username, full_name, join_date, has_played, referred_by, has_played_for_referral) 
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (user_id, username, full_name, datetime.now().isoformat(), 0, referrer_id or 0, 0)
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
    
    # Get welcome text and buttons from database
    with db.get_connection() as conn:
        welcome = conn.execute("SELECT * FROM welcome_settings WHERE id = 1").fetchone()
    
    welcome_text = welcome['welcome_text'].replace("{name}", full_name)
    buttons_data = parse_buttons(welcome['buttons'])
    keyboard = create_button_keyboard(buttons_data)
    
    # Show main menu with reply keyboard and welcome message with inline buttons
    await message.answer(
        welcome_text,
        reply_markup=main_menu_keyboard()
    )
    
    # If there are inline buttons, send them as a separate message
    if keyboard:
        await message.answer(
            "🔗 အသုံးဝင်သော Link များ",
            reply_markup=keyboard
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

@dp.callback_query(F.data == "back_to_main")
async def back_to_main(callback: CallbackQuery):
    await callback.message.delete()
    await cmd_start(callback.message)

# ==================== MESSAGE HANDLERS FOR MAIN MENU ====================
@dp.message(F.text == "📊 My Info")
async def my_info(message: Message):
    user_id = message.from_user.id
    
    with db.get_connection() as conn:
        user = conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()
        
        if not user:
            await message.answer("User not found!")
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
📅 ယနေ့ကံစမ်းပြီးပြီလား - {'ပြီးပါပြီ' if user['has_played'] else 'မရှိသေးပါ'}
━━━━━━━━━━━━━━━━
        """
        
        await message.answer(info_text, reply_markup=main_menu_keyboard())

@dp.message(F.text == "👥 Invite")
async def invite_link(message: Message):
    user_id = message.from_user.id
    
    with db.get_connection() as conn:
        user = conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()
        
        if not user:
            await message.answer("User not found!")
            return
        
        # Generate invite link
        bot_info = await bot.get_me()
        invite_link = f"https://t.me/{bot_info.username}?start=ref_{user_id}"
        
        invite_text = f"""
👥 **Invite Friends**

လူတစ်ယောက်ခေါ်ရင် 50 ကျပ်ရမည်။
ခေါ်လာတဲ့လူက ကံစမ်းမှသာ ရမည်။

သင်၏လက်ရှိခေါ်ဆောင်ထားသူ: {user['total_invite']} ယောက်
ခေါ်ဆောင်နိုင်သည့်အများဆုံး: {user['invite_limit']} ယောက်

**သင်၏ Invite Link:**
`{invite_link}`

👉 အထက်ပါ Link ကိုနှိပ်၍ Copy ကူးနိုင်ပါသည်။
        """
        
        await message.answer(invite_text, reply_markup=main_menu_keyboard())
        
        # Check if reached limit
        if user['total_invite'] >= user['invite_limit']:
            request_keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📢 Request More", callback_data="request_limit")],
                [InlineKeyboardButton(text="🔙 Back", callback_data="back_to_main")]
            ])
            await message.answer(
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
@dp.message(F.text == "🎲 ကံစမ်းမည်")
async def play_game(message: Message):
    user_id = message.from_user.id
    today = datetime.now().strftime("%Y-%m-%d")
    
    # Check force channels first
    joined, not_joined = await check_channels(user_id)
    if not joined:
        keyboard = get_force_channels_keyboard(not_joined)
        await message.answer(
            "🔒 ကျေးဇူးပြု၍ အောက်ပါ Channel များကို Join ပေးပါ။",
            reply_markup=keyboard
        )
        return
    
    with db.get_connection() as conn:
        game = conn.execute("SELECT * FROM game_settings WHERE id = 1").fetchone()
        user = conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()
        
        # Check if game is active
        if not game['game_active']:
            await message.answer("ဂိမ်းမစတင်သေးပါ။ Owner စတင်ရန်စောင့်ဆိုင်းပါ။", reply_markup=main_menu_keyboard())
            return
        
        # Check if game amount is available
        if game['current_amount'] <= 0:
            await message.answer("ကံစမ်းငွေကုန်သွားပါပြီ။ နောက်ရက်မှကံစမ်းပါ။", reply_markup=main_menu_keyboard())
            return
        
        # Check if user already played today
        if user['has_played']:
            await message.answer("ယနေ့အတွက် သင်ကံစမ်းပြီးပါပြီ။ နောက်ရက်မှပြန်ကံစမ်းပါ။", reply_markup=main_menu_keyboard())
            return
        
        # Calculate random amount based on total amount
        total = game['total_amount']
        current = game['current_amount']
        
        # Smart distribution based on total amount
        if total <= 2000:
            # 10-16 people for 2000
            game_amount = random.randint(120, 200)
        elif total <= 4000:
            # 15-20 people for 4000
            game_amount = random.randint(200, 270)
        elif total <= 20000:
            # 25-35 people for 20000
            game_amount = random.randint(570, 800)
        else:
            # Normal distribution with occasional big wins
            if random.random() < 0.2:  # 20% chance for bigger win
                game_amount = random.randint(250, 500)
            else:
                game_amount = random.randint(100, 250)
        
        # Make sure not to exceed current amount
        if game_amount > current:
            game_amount = current
        
        # Make sure at least 100
        if game_amount < 100:
            game_amount = 100
        
        # Update game and user
        new_amount = current - game_amount
        conn.execute(
            "UPDATE game_settings SET current_amount = ? WHERE id = 1",
            (new_amount,)
        )
        
        # Update user: add balance, mark as played today
        conn.execute(
            """UPDATE users SET 
               balance = balance + ?,
               last_game_amount = ?,
               last_game_time = ?,
               has_played = 1
               WHERE user_id = ?""",
            (game_amount, game_amount, datetime.now().isoformat(), user_id)
        )
        
        # Check if this user was referred and hasn't played yet
        if user['referred_by'] and user['referred_by'] > 0 and not user['has_played_for_referral']:
            # Mark as played for referral
            conn.execute(
                "UPDATE users SET has_played_for_referral = 1 WHERE user_id = ?",
                (user_id,)
            )
            
            # Give bonus to referrer
            conn.execute(
                """UPDATE users SET 
                   balance = balance + 50,
                   total_invite = total_invite + 1
                   WHERE user_id = ?""",
                (user['referred_by'],)
            )
            
            # Update referrals table
            conn.execute(
                "UPDATE referrals SET bonus_paid = 1 WHERE referred_id = ?",
                (user_id,)
            )
        
        # Save winner
        conn.execute(
            """INSERT INTO game_winners 
               (user_id, username, full_name, amount, win_time, game_date) 
               VALUES (?, ?, ?, ?, ?, ?)""",
            (user_id, user['username'], user['full_name'], game_amount, datetime.now().isoformat(), today)
        )
        
        # Send game result to user
        game_result_text = f"""
🎲 **ကံစမ်းရလဒ်**
━━━━━━━━━━━━━━━━
👤 နာမည် - {user['full_name']}
💰 ရရှိငွေ - {game_amount} ကျပ်
💵 လက်ကျန်ငွေ - {user['balance'] + game_amount} ကျပ်
⏰ အချိန် - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
━━━━━━━━━━━━━━━━
✨ ဆက်လက်ကံစမ်းရန် ကံစမ်းမည်ကိုနှိပ်ပါ။
        """
        
        await message.answer(game_result_text, reply_markup=main_menu_keyboard())
        
        # Check if game amount finished
        if new_amount <= 0:
            # Update game inactive
            conn.execute("UPDATE game_settings SET game_active = 0 WHERE id = 1")
            
            # Get all winners for today
            winners = conn.execute(
                "SELECT * FROM game_winners WHERE game_date = ? ORDER BY win_time DESC",
                (today,)
            ).fetchall()
            
            # Send winners list to owner
            winners_text = f"📊 **ယနေ့ဂိမ်းပြီးဆုံးချိန် ရလဒ်များ ({today})**\n\n"
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
@dp.message(F.text == "💰 ထုတ်ယူရန်")
async def withdraw_start(message: Message, state: FSMContext):
    user_id = message.from_user.id
    
    with db.get_connection() as conn:
        user = conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()
        
        if not user or user['balance'] < 1500:  # Minimum withdraw 1500
            await message.answer("❌ အနည်းဆုံး 1500 ကျပ်ရှိမှထုတ်နိုင်ပါသည်။", reply_markup=main_menu_keyboard())
            return
    
    # Payment method selection
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="💳 KPay", callback_data="pay_kpay"),
            InlineKeyboardButton(text="🏦 Wave", callback_data="pay_wave")
        ],
        [InlineKeyboardButton(text="🔙 Back", callback_data="back_to_main")]
    ])
    
    await message.answer(
        "💰 **ငွေထုတ်ယူရန်**\n\n"
        "ကျေးဇူးပြု၍ သင့်ငွေလက်ခံမည့်နည်းလမ်းကို ရွေးချယ်ပါ။",
        reply_markup=keyboard
    )

@dp.callback_query(F.data.startswith("pay_"))
async def withdraw_payment_method(callback: CallbackQuery, state: FSMContext):
    method = callback.data.split("_")[1]  # kpay or wave
    
    # Save payment method to state
    await state.update_data(payment_method=method.upper())
    
    await callback.message.edit_text(
        f"💳 **{method.upper()} ငွေထုတ်ယူရန်**\n\n"
        "ကျေးဇူးပြု၍ သင့် အကောင့်နာမည် ကို ရိုက်ထည့်ပါ။\n"
        f"ဥပမာ - {method.upper()} အကောင့်နာမည်"
    )
    await state.set_state(UserStates.waiting_for_account_name)

@dp.message(UserStates.waiting_for_account_name)
async def process_account_name(message: Message, state: FSMContext):
    account_name = message.text.strip()
    
    # Save account name to state
    await state.update_data(account_name=account_name)
    
    await message.answer(
        "📞 **ဖုန်းနံပါတ် ထည့်ပါ**\n\n"
        "ကျေးဇူးပြု၍ သင့် ဖုန်းနံပါတ် ကို ရိုက်ထည့်ပါ။\n"
        "ဥပမာ - 09793251923"
    )
    await state.set_state(UserStates.waiting_for_phone)

@dp.message(UserStates.waiting_for_phone)
async def process_phone(message: Message, state: FSMContext):
    phone = message.text.strip()
    
    # Save phone to state
    await state.update_data(phone=phone)
    
    user_id = message.from_user.id
    
    with db.get_connection() as conn:
        user = conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()
    
    await message.answer(
        f"💰 **ငွေပမာဏ ထည့်ပါ**\n\n"
        f"သင့်လက်ကျန်ငွေ: {user['balance']} ကျပ်\n"
        f"ထုတ်ယူလိုသောငွေပမာဏကို ရိုက်ထည့်ပါ။\n"
        f"(အနည်းဆုံး 1500 ကျပ်)"
    )
    await state.set_state(UserStates.waiting_for_withdraw_amount)

@dp.message(UserStates.waiting_for_withdraw_amount)
async def process_withdraw_amount(message: Message, state: FSMContext):
    try:
        withdraw_amount = int(message.text.strip())
        
        user_id = message.from_user.id
        username = message.from_user.username or "No username"
        full_name = message.from_user.full_name
        
        # Get data from state
        data = await state.get_data()
        payment_method = data.get('payment_method', 'KPay')
        account_name = data.get('account_name', '')
        phone = data.get('phone', '')
        
        with db.get_connection() as conn:
            user = conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()
            
            if withdraw_amount > user['balance']:
                await message.answer(f"သင့်လက်ကျန်ငွေ {user['balance']} ကျပ်သာရှိသည်။ ထပ်မံကြိုးစားပါ။")
                await state.clear()
                return
            
            if withdraw_amount < 1500:
                await message.answer("❌ အနည်းဆုံး 1500 ကျပ်မှ ထုတ်ယူနိုင်ပါသည်။")
                await state.clear()
                return
            
            # Update user phone and name
            conn.execute(
                "UPDATE users SET phone = ?, kpay_name = ? WHERE user_id = ?",
                (phone, account_name, user_id)
            )
            
            # Send to owner
            withdraw_text = f"""
📤 **ငွေထုတ်ယူရန် တောင်းဆိုချက်**
━━━━━━━━━━━━━━━━
👤 အမည် - {full_name}
🆔 User ID - `{user_id}`
🔗 Username - @{username}
💰 ထုတ်ယူမည့်ငွေ - {withdraw_amount} ကျပ်
💳 ငွေလက်ခံမည့် အကောင့် - {payment_method}
📝 အကောင့်နာမည် - {account_name}
📞 ဖုန်းနံပါတ် - {phone}
💵 လက်ကျန်ငွေ - {user['balance']} ကျပ်
━━━━━━━━━━━━━━━━
            """
            
            confirm_keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(text="✅ Confirm", callback_data=f"confirm_withdraw_{user_id}_{withdraw_amount}"),
                    InlineKeyboardButton(text="❌ Cancel", callback_data=f"cancel_withdraw_{user_id}")
                ]
            ])
            
            await bot.send_message(OWNER_ID, withdraw_text, reply_markup=confirm_keyboard)
            
        await message.answer("✅ သင်၏တောင်းဆိုချက်ကို Owner ထံပို့လိုက်ပါပြီ။ ခွင့်ပြုချက်စောင့်ဆိုင်းပါ။", reply_markup=main_menu_keyboard())
        await state.clear()
            
    except ValueError:
        await message.answer("❌ ကျေးဇူးပြု၍ ငွေပမာဏကို ဂဏန်းသာရိုက်ထည့်ပါ။")

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
            InlineKeyboardButton(text="🔄 Reset User Plays", callback_data="admin_reset_plays")
        ],
        [
            InlineKeyboardButton(text="📢 Broadcast", callback_data="admin_broadcast"),
            InlineKeyboardButton(text="👋 Welcome Settings", callback_data="admin_welcome")
        ]
    ])
    
    await message.answer(
        "👑 **Admin Panel**\n\nအောက်ပါလုပ်ဆောင်ချက်များကို ရွေးချယ်ပါ။",
        reply_markup=keyboard
    )

# ==================== WELCOME SETTINGS ====================
@dp.callback_query(F.data == "admin_welcome")
async def admin_welcome(callback: CallbackQuery):
    if callback.from_user.id != OWNER_ID:
        return
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏️ Edit Text", callback_data="welcome_edit_text")],
        [InlineKeyboardButton(text="🔘 Edit Buttons", callback_data="welcome_edit_buttons")],
        [InlineKeyboardButton(text="👁 Preview", callback_data="welcome_preview")],
        [InlineKeyboardButton(text="🔙 Back", callback_data="admin_back")]
    ])
    
    await callback.message.edit_text(
        "👋 **Welcome Message Settings**\n\n"
        "ကြိုဆိုစာသားနှင့် ခလုတ်များကို ပြင်ဆင်ရန် အောက်ပါရွေးချယ်မှုများကို နှိပ်ပါ။",
        reply_markup=keyboard
    )

@dp.callback_query(F.data == "welcome_edit_text")
async def welcome_edit_text(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "✏️ **Edit Welcome Text**\n\n"
        "ကြိုဆိုစာသားအသစ်ကို ရိုက်ထည့်ပါ။\n"
        "Variable: {name} ကိုသုံးပြီး user နာမည်ထည့်နိုင်သည်။\n\n"
        "ဥပမာ: ကြိုဆိုပါတယ် {name} ရေ..."
    )
    await state.set_state(AdminStates.waiting_for_welcome_text)

@dp.message(AdminStates.waiting_for_welcome_text)
async def process_welcome_text(message: Message, state: FSMContext):
    if message.from_user.id != OWNER_ID:
        return
    
    new_text = message.text.strip()
    
    with db.get_connection() as conn:
        conn.execute(
            "UPDATE welcome_settings SET welcome_text = ? WHERE id = 1",
            (new_text,)
        )
    
    await message.answer(f"✅ Welcome Message အသစ်သိမ်းပြီးပါပြီ။")
    await state.clear()
    await admin_panel(message)

@dp.callback_query(F.data == "welcome_edit_buttons")
async def welcome_edit_buttons(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "🔘 **Edit Welcome Buttons**\n\n"
        "Button ထည့်ရန်: နာမည်,link\n"
        "ဥပမာ: Channel,https://t.me/yourchannel\n\n"
        "ပြီးရင် /done ရိုက်ပါ။\n"
        "ဖျက်ချင်ရင် /clear ရိုက်ပါ။"
    )
    await state.set_state(AdminStates.waiting_for_welcome_buttons)
    await state.update_data(buttons=[])

@dp.message(AdminStates.waiting_for_welcome_buttons)
async def process_welcome_buttons(message: Message, state: FSMContext):
    if message.from_user.id != OWNER_ID:
        return
    
    if message.text == "/done":
        data = await state.get_data()
        buttons = data.get('buttons', [])
        
        with db.get_connection() as conn:
            conn.execute(
                "UPDATE welcome_settings SET buttons = ? WHERE id = 1",
                (json.dumps(buttons),)
            )
        
        await message.answer("✅ Welcome buttons updated!")
        await state.clear()
        await admin_panel(message)
    
    elif message.text == "/clear":
        await state.update_data(buttons=[])
        await message.answer("✅ Buttons cleared! Add new buttons or /done")
    
    else:
        try:
            name, link = message.text.split(',')
            name = name.strip()
            link = link.strip()
            
            data = await state.get_data()
            buttons = data.get('buttons', [])
            buttons.append({'text': name, 'url': link})
            await state.update_data(buttons=buttons)
            
            await message.answer(f"✅ Button added! Total: {len(buttons)}\nAdd more or /done")
        except:
            await message.answer("❌ ပုံစံမှားနေပါသည်။ နမူနာ - နာမည်,link")

@dp.callback_query(F.data == "welcome_preview")
async def welcome_preview(callback: CallbackQuery):
    with db.get_connection() as conn:
        welcome = conn.execute("SELECT * FROM welcome_settings WHERE id = 1").fetchone()
    
    text = welcome['welcome_text'].replace("{name}", callback.from_user.full_name)
    buttons_data = parse_buttons(welcome['buttons'])
    keyboard = create_button_keyboard(buttons_data)
    
    await callback.message.edit_text(
        f"👁 **Preview**\n\n{text}",
        reply_markup=keyboard or back_button_keyboard()
    )
    
    # Add back button
    if keyboard:
        await callback.message.answer(
            "🔙 Back to settings",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Back", callback_data="admin_welcome")]
            ])
        )

# ==================== BROADCAST SYSTEM ====================
@dp.callback_query(F.data == "admin_broadcast")
async def admin_broadcast(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id != OWNER_ID:
        return
    
    await callback.message.edit_text(
        "📢 **Broadcast ပို့ရန်**\n\n"
        "စာသားရိုက်ထည့်ပါ။\n"
        "Button ထည့်လိုပါက /done ရိုက်ပြီး button ထည့်နိုင်သည်။",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Back", callback_data="admin_back")]
        ])
    )
    await state.set_state(AdminStates.waiting_for_broadcast)

@dp.message(AdminStates.waiting_for_broadcast)
async def process_broadcast_text(message: Message, state: FSMContext):
    if message.from_user.id != OWNER_ID:
        return
    
    await state.update_data(broadcast_text=message.text)
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Add Button", callback_data="broadcast_add_button")],
        [InlineKeyboardButton(text="🚀 Send Now", callback_data="broadcast_send")],
        [InlineKeyboardButton(text="❌ Cancel", callback_data="admin_back")]
    ])
    
    await message.answer(
        f"Broadcast Text:\n{message.text}\n\nButton ထည့်လိုပါက Add Button နှိပ်ပါ။",
        reply_markup=keyboard
    )

@dp.callback_query(F.data == "broadcast_add_button")
async def broadcast_add_button(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "Button ထည့်ရန်\n\n"
        "Button Name နှင့် Link ကိုရိုက်ထည့်ပါ။\n"
        "ပုံစံ - နာမည်,link\n"
        "ဥပမာ - Channel,https://t.me/yourchannel"
    )
    await state.set_state(AdminStates.waiting_for_broadcast_button)

@dp.message(AdminStates.waiting_for_broadcast_button)
async def process_broadcast_button(message: Message, state: FSMContext):
    try:
        name, link = message.text.split(',')
        name = name.strip()
        link = link.strip()
        
        data = await state.get_data()
        buttons = data.get('buttons', [])
        buttons.append({'text': name, 'url': link})
        
        await state.update_data(buttons=buttons)
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="➕ Add More", callback_data="broadcast_add_button")],
            [InlineKeyboardButton(text="🚀 Send Now", callback_data="broadcast_send")],
            [InlineKeyboardButton(text="❌ Cancel", callback_data="admin_back")]
        ])
        
        await message.answer(
            f"Button Added! Total Buttons: {len(buttons)}\n\nSend Now နှိပ်ပြီးပို့နိုင်သည်။",
            reply_markup=keyboard
        )
        
    except Exception as e:
        await message.answer("ပုံစံမှားနေပါသည်။ နမူနာ - နာမည်,link")

@dp.callback_query(F.data == "broadcast_send")
async def broadcast_send(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    text = data.get('broadcast_text', '')
    buttons = data.get('buttons', [])
    
    keyboard = None
    if buttons:
        kb_rows = []
        row = []
        for i, btn in enumerate(buttons):
            row.append(InlineKeyboardButton(text=btn['text'], url=btn['url']))
            if len(row) == 2:
                kb_rows.append(row)
                row = []
        if row:
            kb_rows.append(row)
        keyboard = InlineKeyboardMarkup(inline_keyboard=kb_rows)
    
    # Get all users
    with db.get_connection() as conn:
        users = conn.execute("SELECT user_id FROM users").fetchall()
    
    sent = 0
    failed = 0
    
    await callback.message.edit_text("📤 Broadcasting...")
    
    for user in users:
        try:
            await bot.send_message(user['user_id'], text, reply_markup=keyboard)
            sent += 1
            await asyncio.sleep(0.05)  # 20 per second
        except:
            failed += 1
    
    await callback.message.edit_text(
        f"✅ Broadcast Done!\n"
        f"Sent: {sent}\n"
        f"Failed: {failed}",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Back", callback_data="admin_back")]
        ])
    )
    await state.clear()

# ==================== ADMIN CALLBACKS ====================
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
        today = datetime.now().strftime("%Y-%m-%d")
        
        with db.get_connection() as conn:
            game = conn.execute("SELECT * FROM game_settings WHERE id = 1").fetchone()
            new_total = game['total_amount'] + amount
            new_current = game['current_amount'] + amount
            
            conn.execute(
                "UPDATE game_settings SET total_amount = ?, current_amount = ?, game_date = ? WHERE id = 1",
                (new_total, new_current, today)
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

@dp.callback_query(F.data == "admin_reset_plays")
async def admin_reset_plays(callback: CallbackQuery):
    if callback.from_user.id != OWNER_ID:
        return
    
    with db.get_connection() as conn:
        # Reset all users' has_played status for new day
        conn.execute("UPDATE users SET has_played = 0")
    
    await callback.answer("ယနေ့အတွက် User အားလုံး ကံစမ်းခွင့်ပြန်ရပါပြီ။")
    await admin_panel(callback.message)

@dp.callback_query(F.data == "admin_game_status")
async def admin_game_status(callback: CallbackQuery):
    if callback.from_user.id != OWNER_ID:
        return
    
    with db.get_connection() as conn:
        game = conn.execute("SELECT * FROM game_settings WHERE id = 1").fetchone()
        today_players = conn.execute(
            "SELECT COUNT(*) as count FROM users WHERE has_played = 1"
        ).fetchone()['count']
    
    status_text = f"""
📊 **Game Status**
━━━━━━━━━━━━━━━━
💰 စုစုပေါင်းငွေ - {game['total_amount']} ကျပ်
💵 လက်ကျန်ငွေ - {game['current_amount']} ကျပ်
🎮 ဂိမ်းအခြေအနေ - {'ဖွင့်ထားသည်' if game['game_active'] else 'ပိတ်ထားသည်'}
👥 ယနေ့ကစားသူ - {today_players} ယောက်
📅 ဂိမ်းရက်စွဲ - {game['game_date'] or 'မသတ်မှတ်ရသေး'}
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
        today_winners = conn.execute(
            "SELECT COUNT(*) as count FROM game_winners WHERE game_date = ?",
            (datetime.now().strftime("%Y-%m-%d"),)
        ).fetchone()['count']
    
    stats_text = f"""
📈 **Bot Statistics**
━━━━━━━━━━━━━━━━
👥 စုစုပေါင်းအသုံးပြုသူ - {total_users}
💰 စုစုပေါင်းလက်ကျန်ငွေ - {total_balance} ကျပ်
🎲 ဂိမ်းလက်ကျန်ငွေ - {game['current_amount']} ကျပ်
🔐 Force Channels - {channels} ခု
🏆 စုစုပေါင်းဆုရှင် - {total_winners} ဦး
💸 စုစုပေါင်းပေးအပ်ငွေ - {total_given} ကျပ်
📅 ယနေ့ဆုရှင် - {today_winners} ဦး
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
        "Channel တွေကြည့်ရန် List Channels ကိုနှိပ်ပါ။\n\n"
        "Bot ကို Channel မှာ Admin လုပ်ထားရန်မမေ့ပါနှင့်။",
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
    
    # Extract channel username from link
    try:
        if "t.me/" in data['channel_link']:
            channel_username = data['channel_link'].split('/')[-1]
            if channel_username.startswith('+'):
                # Private channel
                await message.answer("Private Channel များအတွက် Channel ID ကိုတိုက်ရိုက်ထည့်ရန်လိုအပ်ပါသည်။")
                return
        else:
            # Maybe it's already an ID
            channel_username = data['channel_link']
        
        # Try to get chat info
        chat = await bot.get_chat(f"@{channel_username}")
        channel_id = str(chat.id)
        
        with db.get_connection() as conn:
            conn.execute(
                "INSERT INTO force_channels (channel_id, channel_name, channel_link, added_date) VALUES (?, ?, ?, ?)",
                (channel_id, channel_name, data['channel_link'], datetime.now().isoformat())
            )
        
        await message.answer(f"✅ Channel {channel_name} added successfully!")
        await state.clear()
        
    except Exception as e:
        await message.answer(f"❌ Error: {str(e)}\n\nBot ကို Channel မှာ Admin လုပ်ထားကြောင်းစစ်ပါ။")

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
        text += f"   Link: {channel['channel_link']}\n"
        text += f"   ID: `{channel['channel_id']}`\n\n"
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

# ==================== ADMIN BACK ====================
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
    
    parts = callback.data.split("_")
    user_id = int(parts[2])
    withdraw_amount = int(parts[3])
    
    with db.get_connection() as conn:
        user = conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()
        
        if not user:
            await callback.answer("User not found!")
            return
        
        # Generate transfer ID
        transfer_id = f"TRX{random.randint(100000, 999999)}"
        
        # Update user balance (deduct)
        new_balance = user['balance'] - withdraw_amount
        conn.execute(
            "UPDATE users SET balance = ? WHERE user_id = ?",
            (new_balance, user_id)
        )
        
        # Send receipt to user
        receipt_text = f"""
📤 **ငွေထုတ်ပြေစာ**
━━━━━━━━━━━━━━━━
👤 ငွေထုတ်ယူသူအမည် - {user['full_name']}
🆔 User ID - `{user['user_id']}`
💰 ထုတ်ယူခဲ့သည့်ငွေ - {withdraw_amount} ကျပ်
💳 ငွေပေးပို့သူအမည် - Owner
📤 လွဲပေးခဲ့သည့်ငွေ - {withdraw_amount} ကျပ်
⏰ အချိန် - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
🔢 ပြေစာ Transfer ID - `{transfer_id}`
━━━━━━━━━━━━━━━━
✨ ကျေးဇူးတင်ပါသည်။
        """
        
        await bot.send_message(user_id, receipt_text)
        
        # Send to group
        group_text = f"{user['full_name']} နက် {withdraw_amount} ကျပ် ထုတ်ယူပြီးပါပြီ။ အကောင့်ထဲဝင်စစ်ပေးပါ။"
        await bot.send_message(GROUP_ID, group_text)
    
    await callback.message.edit_text(f"✅ Withdraw confirmed for user {user_id}\n\nငွေပမာဏ: {withdraw_amount} ကျပ်")
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
        "❌ သင်၏ Limit တိုးရန် တောင်းဆိုချက်ကို ပယ်ဖျက်လိုက်ပါသည်။"
    )
    
    await callback.message.edit_text(f"✅ Limit request cancelled for user {user_id}")
    await callback.answer("Limit cancelled!")

# ==================== START BOT ====================
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
