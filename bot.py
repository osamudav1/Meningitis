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
                is_banned BOOLEAN DEFAULT 0,
                ban_reason TEXT
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
                bonus_paid BOOLEAN DEFAULT 0,
                username TEXT,
                full_name TEXT
            )''')
            
            # Welcome settings table
            conn.execute('''CREATE TABLE IF NOT EXISTS welcome_settings (
                id INTEGER PRIMARY KEY CHECK (id=1),
                welcome_text TEXT DEFAULT 'ကြိုဆိုပါတယ် {name} ရေ...\n\nအောက်က ခလုတ်လေးတွေကနေ လုပ်ဆောင်နိုင်ပါတယ်။',
                buttons TEXT DEFAULT '[]',
                photo_id TEXT DEFAULT NULL
            )''')
            
            # Banned users table
            conn.execute('''CREATE TABLE IF NOT EXISTS banned_users (
                user_id INTEGER PRIMARY KEY,
                reason TEXT,
                banned_date TEXT,
                banned_by INTEGER
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
    waiting_for_welcome_photo = State()
    waiting_for_ban_reason = State()
    waiting_for_unban_id = State()

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

def create_button_keyboard(buttons_data, row_width=2):
    """Create keyboard from button data"""
    if not buttons_data:
        return None
    
    keyboard = []
    row = []
    for i, btn in enumerate(buttons_data):
        row.append(InlineKeyboardButton(text=btn['text'], url=btn.get('url', '')))
        if len(row) == row_width:
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

# ==================== CHECK BAN ====================
async def check_ban(user_id: int) -> bool:
    """Check if user is banned"""
    with db.get_connection() as conn:
        user = conn.execute("SELECT is_banned FROM users WHERE user_id = ?", (user_id,)).fetchone()
        banned = conn.execute("SELECT * FROM banned_users WHERE user_id = ?", (user_id,)).fetchone()
    
    return (user and user['is_banned']) or (banned is not None)

# ==================== START COMMAND ====================
@dp.message(Command("start"))
async def cmd_start(message: Message):
    user_id = message.from_user.id
    username = message.from_user.username or "No username"
    full_name = message.from_user.full_name
    
    # Check if user is banned
    if await check_ban(user_id):
        with db.get_connection() as conn:
            ban_info = conn.execute("SELECT * FROM banned_users WHERE user_id = ?", (user_id,)).fetchone()
        
        reason = ban_info['reason'] if ban_info else "အကြောင်းပြချက်မရှိပါ"
        await message.answer(f"❌ သင်သည် Bot မှ ပိတ်ပင်ခံထားရပါသည်။\nအကြောင်းပြချက်: {reason}")
        return
    
    # Extract referrer from start command
    referrer_id = None
    if message.text and len(message.text.split()) > 1:
        try:
            referrer_id = int(message.text.split()[1].replace("ref_", ""))
            # Don't allow self-referral
            if referrer_id == user_id:
                referrer_id = None
        except:
            pass
    
    # Add user to database if not exists
    with db.get_connection() as conn:
        user = conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()
        if not user:
            conn.execute(
                """INSERT INTO users 
                   (user_id, username, full_name, join_date, has_played, referred_by) 
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (user_id, username, full_name, datetime.now().isoformat(), 0, referrer_id or 0)
            )
            
            # Handle referral
            if referrer_id:
                # Check if referrer exists
                referrer = conn.execute("SELECT * FROM users WHERE user_id = ?", (referrer_id,)).fetchone()
                if referrer:
                    # Add to referrals table
                    conn.execute(
                        """INSERT INTO referrals 
                           (referrer_id, referred_id, referred_date, bonus_paid, username, full_name) 
                           VALUES (?, ?, ?, ?, ?, ?)""",
                        (referrer_id, user_id, datetime.now().isoformat(), 0, username, full_name)
                    )
                    
                    # Notify referrer
                    try:
                        await bot.send_message(
                            referrer_id,
                            f"👥 **လူသစ်ခေါ်ယူမှုအကြောင်းကြားစာ**\n\n"
                            f"သင့် Link ကနေ လူသစ်ဝင်ရောက်လာပါပြီ။\n"
                            f"အမည်: {full_name}\n"
                            f"Username: @{username if username != 'No username' else 'မရှိ'}\n"
                            f"User ID: `{user_id}`\n\n"
                            f"သူကံစမ်းမှသာ Bonus ရမည်ဖြစ်ပါသည်။"
                        )
                    except:
                        pass
    
    # Check force channels
    joined, not_joined = await check_channels(user_id)
    
    if not joined:
        keyboard = get_force_channels_keyboard(not_joined)
        await message.answer(
            "🔒 ကျေးဇူးပြု၍ အောက်ပါ Channel များကို Join ပေးပါ။",
            reply_markup=keyboard
        )
        return
    
    # Get welcome settings from database
    with db.get_connection() as conn:
        welcome = conn.execute("SELECT * FROM welcome_settings WHERE id = 1").fetchone()
    
    welcome_text = welcome['welcome_text'].replace("{name}", full_name)
    buttons_data = parse_buttons(welcome['buttons'])
    photo_id = welcome['photo_id']
    
    # Create keyboard for welcome buttons
    keyboard = create_button_keyboard(buttons_data, row_width=2)
    
    # Send welcome message with photo if available
    if photo_id:
        try:
            await message.answer_photo(
                photo=photo_id,
                caption=welcome_text,
                reply_markup=main_menu_keyboard()
            )
        except:
            await message.answer(
                welcome_text,
                reply_markup=main_menu_keyboard()
            )
    else:
        await message.answer(
            welcome_text,
            reply_markup=main_menu_keyboard()
        )
    
    # If there are inline buttons, send them as a separate message
    if keyboard:
        await message.answer(
            "🔗 **အသုံးဝင်သော Link များ**",
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
    
    # Check if user is banned
    if await check_ban(user_id):
        return
    
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
👥 ခေါ်ယူထားသူဦးရေ - {user['total_invite']} ယောက်
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
    
    # Check if user is banned
    if await check_ban(user_id):
        return
    
    with db.get_connection() as conn:
        user = conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()
        
        if not user:
            await message.answer("User not found!")
            return
        
        # Generate invite link
        bot_info = await bot.get_me()
        invite_link = f"https://t.me/{bot_info.username}?start=ref_{user_id}"
        
        # Get recent referrals
        referrals = conn.execute(
            """SELECT * FROM referrals 
               WHERE referrer_id = ? 
               ORDER BY referred_date DESC 
               LIMIT 5""",
            (user_id,)
        ).fetchall()
        
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
        
        # Show recent referrals if any
        if referrals:
            ref_text = "**လတ်တလော ခေါ်ယူထားသူများ**\n\n"
            for ref in referrals:
                ref_text += f"👤 {ref['full_name']}\n"
                ref_text += f"🆔 `{ref['referred_id']}`\n"
                ref_text += f"⏰ {ref['referred_date'][:10]}\n"
                ref_text += f"💰 Bonus: {'ရပြီ' if ref['bonus_paid'] else 'မရသေး (ကံစမ်းရန်)'}\n\n"
            
            await message.answer(ref_text)
        
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
    
    # Check if user is banned
    if await check_ban(user_id):
        return
    
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
        
        # Check if this user was referred and hasn't played yet (bonus for referrer)
        if user['referred_by'] and user['referred_by'] > 0:
            # Check if referral bonus already paid
            referral = conn.execute(
                "SELECT * FROM referrals WHERE referred_id = ?",
                (user_id,)
            ).fetchone()
            
            if referral and not referral['bonus_paid']:
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
                
                # Get referrer info
                referrer = conn.execute(
                    "SELECT * FROM users WHERE user_id = ?",
                    (user['referred_by'],)
                ).fetchone()
                
                # Send notification to referrer
                try:
                    await bot.send_message(
                        user['referred_by'],
                        f"🎉 **Referral Bonus ရရှိပါပြီ**\n\n"
                        f"သင်ခေါ်ယူထားသူ {user['full_name']} ကံစမ်းလိုက်ပါပြီ။\n"
                        f"သင့်အကောင့်ထဲသို့ 50 ကျပ် ထည့်ပေးလိုက်ပါပြီ။\n\n"
                        f"လက်ရှိခေါ်ယူထားသူ: {referrer['total_invite'] + 1} ယောက်\n"
                        f"လက်ကျန်ငွေ: {referrer['balance'] + 50} ကျပ်"
                    )
                except:
                    pass
                
                # Send notification to group
                try:
                    await bot.send_message(
                        GROUP_ID,
                        f"🎉 **Referral Bonus**\n\n"
                        f"{referrer['full_name']} နှင့် {user['full_name']} တို့ Referral စနစ်အရ\n"
                        f"{referrer['full_name']} အကောင့်ထဲသို့ 50 ကျပ် ထည့်ပေးလိုက်ပါပြီ။"
                    )
                except:
                    pass
        
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
    
    # Check if user is banned
    if await check_ban(user_id):
        return
    
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
        ],
        [
            InlineKeyboardButton(text="🚫 Ban User", callback_data="admin_ban"),
            InlineKeyboardButton(text="✅ Unban User", callback_data="admin_unban")
        ],
        [
            InlineKeyboardButton(text="📋 Banned List", callback_data="admin_banned_list")
        ]
    ])
    
    await message.answer(
        "👑 **Admin Panel**\n\nအောက်ပါလုပ်ဆောင်ချက်များကို ရွေးချယ်ပါ။",
        reply_markup=keyboard
    )

# ==================== BAN/UNBAN SYSTEM ====================
@dp.callback_query(F.data == "admin_ban")
async def admin_ban(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id != OWNER_ID:
        return
    
    await callback.message.edit_text(
        "🚫 **Ban User**\n\n"
        "ပိတ်ပင်လိုသော User ID ကိုရိုက်ထည့်ပါ။"
    )
    await state.set_state(AdminStates.waiting_for_ban_reason)
    await state.update_data(ban_user_id=None)

@dp.message(AdminStates.waiting_for_ban_reason)
async def process_ban_user_id(message: Message, state: FSMContext):
    try:
        user_id = int(message.text.strip())
        
        # Check if user exists
        with db.get_connection() as conn:
            user = conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()
        
        if not user:
            await message.answer("❌ User ID မတွေ့ပါ။")
            await state.clear()
            await admin_panel(message)
            return
        
        await state.update_data(ban_user_id=user_id)
        await message.answer(
            f"User: {user['full_name']}\n"
            f"User ID: `{user_id}`\n\n"
            "ပိတ်ပင်ရခြင်းအကြောင်းအရင်းကိုရိုက်ထည့်ပါ။"
        )
        # State remains waiting_for_ban_reason but now we know the user_id
        
    except ValueError:
        await message.answer("❌ User ID သည် နံပါတ်ဖြစ်ရပါမည်။")
        await state.clear()
        await admin_panel(message)

@dp.message(AdminStates.waiting_for_ban_reason)
async def process_ban_reason(message: Message, state: FSMContext):
    data = await state.get_data()
    user_id = data.get('ban_user_id')
    reason = message.text.strip()
    
    if not user_id:
        await message.answer("❌ User ID မတွေ့ပါ။ ပြန်လုပ်ပါ။")
        await state.clear()
        await admin_panel(message)
        return
    
    with db.get_connection() as conn:
        # Update users table
        conn.execute(
            "UPDATE users SET is_banned = 1 WHERE user_id = ?",
            (user_id,)
        )
        
        # Add to banned_users table
        conn.execute(
            """INSERT OR REPLACE INTO banned_users 
               (user_id, reason, banned_date, banned_by) 
               VALUES (?, ?, ?, ?)""",
            (user_id, reason, datetime.now().isoformat(), OWNER_ID)
        )
        
        # Get user info
        user = conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()
    
    # Notify user
    try:
        await bot.send_message(
            user_id,
            f"🚫 **သင်သည် Bot မှ ပိတ်ပင်ခံထားရပါသည်**\n\n"
            f"အကြောင်းအရင်း: {reason}\n"
            f"ရက်စွဲ: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )
    except:
        pass
    
    await message.answer(f"✅ User {user_id} ({user['full_name']}) ကို ပိတ်ပင်လိုက်ပါပြီ။\nအကြောင်းအရင်း: {reason}")
    await state.clear()
    await admin_panel(message)

@dp.callback_query(F.data == "admin_unban")
async def admin_unban(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id != OWNER_ID:
        return
    
    await callback.message.edit_text(
        "✅ **Unban User**\n\n"
        "ပြန်ဖွင့်ပေးလိုသော User ID ကိုရိုက်ထည့်ပါ။"
    )
    await state.set_state(AdminStates.waiting_for_unban_id)

@dp.message(AdminStates.waiting_for_unban_id)
async def process_unban(message: Message, state: FSMContext):
    try:
        user_id = int(message.text.strip())
        
        with db.get_connection() as conn:
            # Check if banned
            banned = conn.execute("SELECT * FROM banned_users WHERE user_id = ?", (user_id,)).fetchone()
            
            if not banned:
                await message.answer("❌ ဤ User သည် ပိတ်ပင်ခံထားရသူမဟုတ်ပါ။")
                await state.clear()
                await admin_panel(message)
                return
            
            # Update users table
            conn.execute(
                "UPDATE users SET is_banned = 0 WHERE user_id = ?",
                (user_id,)
            )
            
            # Remove from banned_users
            conn.execute("DELETE FROM banned_users WHERE user_id = ?", (user_id,))
            
            # Get user info
            user = conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()
        
        # Notify user
        try:
            await bot.send_message(
                user_id,
                f"✅ **သင့်အား Bot မှ ပြန်လည်ခွင့်ပြုလိုက်ပါပြီ**\n\n"
                f"ယခုမှစ၍ ပုံမှန်အသုံးပြုနိုင်ပါပြီ။"
            )
        except:
            pass
        
        await message.answer(f"✅ User {user_id} ({user['full_name']}) ကို ပြန်ဖွင့်ပေးလိုက်ပါပြီ။")
        await state.clear()
        await admin_panel(message)
        
    except ValueError:
        await message.answer("❌ User ID သည် နံပါတ်ဖြစ်ရပါမည်။")
        await state.clear()
        await admin_panel(message)

@dp.callback_query(F.data == "admin_banned_list")
async def admin_banned_list(callback: CallbackQuery):
    if callback.from_user.id != OWNER_ID:
        return
    
    with db.get_connection() as conn:
        banned = conn.execute(
            """SELECT b.*, u.full_name, u.username 
               FROM banned_users b
               LEFT JOIN users u ON b.user_id = u.user_id
               ORDER BY b.banned_date DESC"""
        ).fetchall()
    
    if not banned:
        await callback.message.edit_text(
            "📋 **Banned Users List**\n\n"
            "ပိတ်ပင်ခံထားရသူ မရှိပါ။",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Back", callback_data="admin_back")]
            ])
        )
        return
    
    text = "📋 **Banned Users List**\n\n"
    keyboard = []
    
    for b in banned:
        text += f"👤 {b['full_name']}\n"
        text += f"🆔 `{b['user_id']}`\n"
        text += f"🔗 @{b['username'] if b['username'] != 'No username' else 'မရှိ'}\n"
        text += f"❌ အကြောင်းရင်း: {b['reason']}\n"
        text += f"📅 ရက်စွဲ: {b['banned_date'][:10]}\n\n"
        
        keyboard.append([InlineKeyboardButton(
            text=f"✅ Unban {b['full_name'][:15]}",
            callback_data=f"unban_{b['user_id']}"
        )])
    
    keyboard.append([InlineKeyboardButton(text="🔙 Back", callback_data="admin_back")])
    
    await callback.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
    )

@dp.callback_query(F.data.startswith("unban_"))
async def quick_unban(callback: CallbackQuery):
    if callback.from_user.id != OWNER_ID:
        return
    
    user_id = int(callback.data.split("_")[1])
    
    with db.get_connection() as conn:
        # Update users table
        conn.execute(
            "UPDATE users SET is_banned = 0 WHERE user_id = ?",
            (user_id,)
        )
        
        # Remove from banned_users
        conn.execute("DELETE FROM banned_users WHERE user_id = ?", (user_id,))
        
        # Get user info
        user = conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()
    
    # Notify user
    try:
        await bot.send_message(
            user_id,
            f"✅ **သင့်အား Bot မှ ပြန်လည်ခွင့်ပြုလိုက်ပါပြီ**\n\n"
            f"ယခုမှစ၍ ပုံမှန်အသုံးပြုနိုင်ပါပြီ။"
        )
    except:
        pass
    
    await callback.answer(f"User {user_id} unbanned!")
    await admin_banned_list(callback)

# ==================== WELCOME SETTINGS ====================
@dp.callback_query(F.data == "admin_welcome")
async def admin_welcome(callback: CallbackQuery):
    if callback.from_user.id != OWNER_ID:
        return
    
    with db.get_connection() as conn:
        welcome = conn.execute("SELECT * FROM welcome_settings WHERE id = 1").fetchone()
    
    has_photo = "ရှိသည်" if welcome['photo_id'] else "မရှိ"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏️ Edit Text", callback_data="welcome_edit_text")],
        [InlineKeyboardButton(text="🔘 Edit Buttons (2 Columns)", callback_data="welcome_edit_buttons")],
        [InlineKeyboardButton(text="🖼 Add/Change Photo", callback_data="welcome_add_photo")],
        [InlineKeyboardButton(text="🗑 Remove Photo", callback_data="welcome_remove_photo")],
        [InlineKeyboardButton(text="👁 Preview", callback_data="welcome_preview")],
        [InlineKeyboardButton(text="🔙 Back", callback_data="admin_back")]
    ])
    
    await callback.message.edit_text(
        f"👋 **Welcome Message Settings**\n\n"
        f"ကြိုဆိုစာသားနှင့် ခလုတ်များကို ပြင်ဆင်ရန် အောက်ပါရွေးချယ်မှုများကို နှိပ်ပါ။\n\n"
        f"📸 ဓာတ်ပုံ: {has_photo}\n"
        f"📝 စာသား: {welcome['welcome_text'][:50]}...",
        reply_markup=keyboard
    )

@dp.callback_query(F.data == "welcome_edit_text")
async def welcome_edit_text(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "✏️ **Edit Welcome Text**\n\n"
        "ကြိုဆိုစာသားအသစ်ကို ရိုက်ထည့်ပါ။\n"
        "Variable: {{name}} ကိုသုံးပြီး user နာမည်ထည့်နိုင်သည်။\n\n"
        "ဥပမာ: ကြိုဆိုပါတယ် {{name}} ရေ...\n\n"
        "မူလစာသားပြန်သုံးလိုပါက /default ရိုက်ပါ။"
    )
    await state.set_state(AdminStates.waiting_for_welcome_text)

@dp.message(AdminStates.waiting_for_welcome_text)
async def process_welcome_text(message: Message, state: FSMContext):
    if message.from_user.id != OWNER_ID:
        return
    
    if message.text == "/default":
        new_text = "ကြိုဆိုပါတယ် {name} ရေ...\n\nအောက်က ခလုတ်လေးတွေကနေ လုပ်ဆောင်နိုင်ပါတယ်။"
    else:
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
        "ဥပမာ: Channel,https://t.me/yourchannel\n"
        "Website,https://example.com\n\n"
        "Button များကို 2 Column နှုန်းဖြင့် ပြသမည်ဖြစ်သည်။\n\n"
        "ပြီးရင် /done ရိုက်ပါ။\n"
        "ဖျက်ချင်ရင် /clear ရိုက်ပါ။\n"
        "လက်ရှိ Buttons ကြည့်ရန် /list ရိုက်ပါ။"
    )
    await state.set_state(AdminStates.waiting_for_welcome_buttons)
    await state.update_data(buttons=[])

@dp.message(AdminStates.waiting_for_welcome_buttons)
async def process_welcome_buttons(message: Message, state: FSMContext):
    if message.from_user.id != OWNER_ID:
        return
    
    data = await state.get_data()
    buttons = data.get('buttons', [])
    
    if message.text == "/done":
        with db.get_connection() as conn:
            conn.execute(
                "UPDATE welcome_settings SET buttons = ? WHERE id = 1",
                (json.dumps(buttons),)
            )
        
        await message.answer(f"✅ Welcome buttons updated! Total: {len(buttons)} buttons")
        await state.clear()
        await admin_panel(message)
    
    elif message.text == "/clear":
        await state.update_data(buttons=[])
        await message.answer("✅ Buttons cleared! Add new buttons or /done")
    
    elif message.text == "/list":
        if buttons:
            text = "**လက်ရှိ Buttons များ**\n\n"
            for i, btn in enumerate(buttons, 1):
                text += f"{i}. {btn['text']} - {btn['url']}\n"
            await message.answer(text)
        else:
            await message.answer("Buttons မရှိသေးပါ။")
    
    else:
        try:
            parts = message.text.split(',', 1)
            if len(parts) != 2:
                await message.answer("❌ ပုံစံမှားနေပါသည်။ နမူနာ - နာမည်,link")
                return
            
            name = parts[0].strip()
            link = parts[1].strip()
            
            if not name or not link:
                await message.answer("❌ နာမည် နှင့် link ဖြည့်ရန်လိုအပ်ပါသည်။")
                return
            
            if not link.startswith(('http://', 'https://', 't.me/')):
                link = 'https://' + link
            
            buttons.append({'text': name, 'url': link})
            await state.update_data(buttons=buttons)
            
            await message.answer(f"✅ Button added! Total: {len(buttons)}\nAdd more or /done")
        except Exception as e:
            await message.answer(f"❌ အမှားဖြစ်နေပါသည်။ နမူနာ - နာမည်,link")

@dp.callback_query(F.data == "welcome_add_photo")
async def welcome_add_photo(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "🖼 **Add Welcome Photo**\n\n"
        "ဓာတ်ပုံတစ်ပုံပို့ပေးပါ။\n"
        "ဖျက်လိုပါက /skip ရိုက်ပါ။"
    )
    await state.set_state(AdminStates.waiting_for_welcome_photo)

@dp.message(AdminStates.waiting_for_welcome_photo)
async def process_welcome_photo(message: Message, state: FSMContext):
    if message.from_user.id != OWNER_ID:
        return
    
    if message.text == "/skip":
        await message.answer("✅ Photo မထည့်ပဲ ရပ်နားလိုက်ပါသည်။")
        await state.clear()
        await admin_panel(message)
        return
    
    if message.photo:
        photo_id = message.photo[-1].file_id
        
        with db.get_connection() as conn:
            conn.execute(
                "UPDATE welcome_settings SET photo_id = ? WHERE id = 1",
                (photo_id,)
            )
        
        await message.answer("✅ Welcome photo updated successfully!")
        await state.clear()
        await admin_panel(message)
    else:
        await message.answer("❌ ကျေးဇူးပြု၍ ဓာတ်ပုံပို့ပေးပါ။")

@dp.callback_query(F.data == "welcome_remove_photo")
async def welcome_remove_photo(callback: CallbackQuery):
    with db.get_connection() as conn:
        conn.execute(
            "UPDATE welcome_settings SET photo_id = NULL WHERE id = 1"
        )
    
    await callback.answer("Photo removed!")
    await admin_welcome(callback)

@dp.callback_query(F.data == "welcome_preview")
async def welcome_preview(callback: CallbackQuery):
    with db.get_connection() as conn:
        welcome = conn.execute("SELECT * FROM welcome_settings WHERE id = 1").fetchone()
    
    text = welcome['welcome_text'].replace("{name}", callback.from_user.full_name)
    buttons_data = parse_buttons(welcome['buttons'])
    photo_id = welcome['photo_id']
    
    # Create 2-column keyboard
    keyboard = create_button_keyboard(buttons_data, row_width=2)
    
    if photo_id:
        await callback.message.delete()
        await callback.message.answer_photo(
            photo=photo_id,
            caption=f"👁 **Preview**\n\n{text}",
            reply_markup=keyboard or InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Back", callback_data="admin_welcome")]
            ])
        )
    else:
        await callback.message.edit_text(
            f"👁 **Preview**\n\n{text}",
            reply_markup=keyboard or InlineKeyboardMarkup(inline_keyboard=[
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
        "Button ထည့်လိုပါက /done ရိုက်ပြီး button ထည့်နိုင်သည်။\n"
        "Photo ပါထည့်လိုပါက photo ကိုအရင်ပို့ပါ။",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Back", callback_data="admin_back")]
        ])
    )
    await state.set_state(AdminStates.waiting_for_broadcast)

@dp.message(AdminStates.waiting_for_broadcast)
async def process_broadcast_text(message: Message, state: FSMContext):
    if message.from_user.id != OWNER_ID:
        return
    
    # Check if message has photo
    photo_id = None
    text = message.caption if message.photo else message.text
    
    if message.photo:
        photo_id = message.photo[-1].file_id
        text = message.caption or ""
    
    await state.update_data(broadcast_text=text, broadcast_photo=photo_id)
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Add Button", callback_data="broadcast_add_button")],
        [InlineKeyboardButton(text="🚀 Send Now", callback_data="broadcast_send")],
        [InlineKeyboardButton(text="❌ Cancel", callback_data="admin_back")]
    ])
    
    preview = f"Broadcast Preview:\n\n{text}"
    if photo_id:
        await message.answer_photo(
            photo=photo_id,
            caption=preview + "\n\nButton ထည့်လိုပါက Add Button နှိပ်ပါ။",
            reply_markup=keyboard
        )
    else:
        await message.answer(
            preview + "\n\nButton ထည့်လိုပါက Add Button နှိပ်ပါ။",
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
        parts = message.text.split(',', 1)
        if len(parts) != 2:
            await message.answer("ပုံစံမှားနေပါသည်။ နမူနာ - နာမည်,link")
            return
        
        name = parts[0].strip()
        link = parts[1].strip()
        
        if not link.startswith(('http://', 'https://', 't.me/')):
            link = 'https://' + link
        
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
    photo_id = data.get('broadcast_photo')
    buttons = data.get('buttons', [])
    
    # Create keyboard if buttons exist
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
        users = conn.execute("SELECT user_id FROM users WHERE is_banned = 0").fetchall()
    
    sent = 0
    failed = 0
    
    await callback.message.edit_text("📤 Broadcasting...")
    
    for user in users:
        try:
            if photo_id:
                await bot.send_photo(
                    chat_id=user['user_id'],
                    photo=photo_id,
                    caption=text,
                    reply_markup=keyboard
                )
            else:
                await bot.send_message(
                    user['user_id'],
                    text,
                    reply_markup=keyboard
                )
            sent += 1
            await asyncio.sleep(0.05)  # 20 per second
        except Exception as e:
            failed += 1
            logger.error(f"Failed to send to {user['user_id']}: {e}")
    
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
        today_winners = conn.execute(
            "SELECT COUNT(*) as count FROM game_winners WHERE game_date = ?",
            (datetime.now().strftime("%Y-%m-%d"),)
        ).fetchone()['count']
    
    status_text = f"""
📊 **Game Status**
━━━━━━━━━━━━━━━━
💰 စုစုပေါင်းငွေ - {game['total_amount']} ကျပ်
💵 လက်ကျန်ငွေ - {game['current_amount']} ကျပ်
🎮 ဂိမ်းအခြေအနေ - {'ဖွင့်ထားသည်' if game['game_active'] else 'ပိတ်ထားသည်'}
👥 ယနေ့ကစားသူ - {today_players} ယောက်
🏆 ယနေ့ဆုရှင် - {today_winners} ယောက်
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
        active_users = conn.execute("SELECT COUNT(*) as count FROM users WHERE is_banned = 0").fetchone()['count']
        banned_users = conn.execute("SELECT COUNT(*) as count FROM users WHERE is_banned = 1").fetchone()['count']
        total_balance = conn.execute("SELECT SUM(balance) as total FROM users").fetchone()['total'] or 0
        game = conn.execute("SELECT * FROM game_settings WHERE id = 1").fetchone()
        channels = conn.execute("SELECT COUNT(*) as count FROM force_channels").fetchone()['count']
        total_winners = conn.execute("SELECT COUNT(*) as count FROM game_winners").fetchone()['count']
        total_given = conn.execute("SELECT SUM(amount) as total FROM game_winners").fetchone()['total'] or 0
        total_referrals = conn.execute("SELECT COUNT(*) as count FROM referrals").fetchone()['count']
        paid_referrals = conn.execute("SELECT COUNT(*) as count FROM referrals WHERE bonus_paid = 1").fetchone()['count']
    
    stats_text = f"""
📈 **Bot Statistics**
━━━━━━━━━━━━━━━━
👥 စုစုပေါင်းအသုံးပြုသူ - {total_users}
✅ အသုံးပြုခွင့်ရှိသူ - {active_users}
🚫 ပိတ်ပင်ခံထားရသူ - {banned_users}
💰 စုစုပေါင်းလက်ကျန်ငွေ - {total_balance} ကျပ်
🎲 ဂိမ်းလက်ကျန်ငွေ - {game['current_amount']} ကျပ်
🔐 Force Channels - {channels} ခု
🏆 စုစုပေါင်းဆုရှင် - {total_winners} ဦး
💸 စုစုပေါင်းပေးအပ်ငွေ - {total_given} ကျပ်
👥 စုစုပေါင်းခေါ်ယူမှု - {total_referrals} ကြိမ်
💰 ပေးပြီးသော Referral Bonus - {paid_referrals * 50} ကျပ်
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
        "ဥပမာ: https://t.me/yourchannel\n"
        "သို့မဟုတ် @channelusername"
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
    channel_link = data['channel_link']
    
    # Extract channel username from link
    try:
        if "t.me/" in channel_link:
            channel_username = channel_link.split('/')[-1]
            if channel_username.startswith('+'):
                # Private channel
                await message.answer("Private Channel များအတွက် Channel ID ကိုတိုက်ရိုက်ထည့်ရန်လိုအပ်ပါသည်။")
                return
        elif channel_link.startswith('@'):
            channel_username = channel_link[1:]
        else:
            channel_username = channel_link
        
        # Try to get chat info
        chat = await bot.get_chat(f"@{channel_username}")
        channel_id = str(chat.id)
        
        with db.get_connection() as conn:
            conn.execute(
                "INSERT INTO force_channels (channel_id, channel_name, channel_link, added_date) VALUES (?, ?, ?, ?)",
                (channel_id, channel_name, channel_link, datetime.now().isoformat())
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

# ==================== ERROR HANDLER ====================
@dp.errors()
async def errors_handler(update: types.Update, exception: Exception):
    logger.error(f"Update {update} caused error {exception}")
    return True

# ==================== START BOT ====================
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
