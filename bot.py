import asyncio
import logging
from datetime import datetime
import sqlite3
import random
import json
import os
from contextlib import contextmanager

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton, FSInputFile
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

# ==================== CONFIG ====================
BOT_TOKEN = "7654055081:AAFJSMVlJ1nZtZSeYiU9hLsl_4AVgUoAiHs"
OWNER_ID = 6762363593
GROUP_ID = -1002473190844

# Token စစ်ဆေး
if not BOT_TOKEN:
    raise ValueError("❌ Bot Token ထည့်ပေးပါ။")

# ==================== LOGGING ====================
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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
                is_banned BOOLEAN DEFAULT 0
            )''')
            
            # Game settings
            conn.execute('''CREATE TABLE IF NOT EXISTS game_settings (
                id INTEGER PRIMARY KEY CHECK (id=1),
                total_amount INTEGER DEFAULT 0,
                current_amount INTEGER DEFAULT 0,
                game_active INTEGER DEFAULT 0,
                game_date TEXT
            )''')
            
            # Winners
            conn.execute('''CREATE TABLE IF NOT EXISTS game_winners (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                username TEXT,
                full_name TEXT,
                amount INTEGER,
                win_time TEXT,
                game_date TEXT
            )''')
            
            # Force channels
            conn.execute('''CREATE TABLE IF NOT EXISTS force_channels (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                channel_id TEXT UNIQUE,
                channel_name TEXT,
                channel_link TEXT,
                added_date TEXT
            )''')
            
            # Referrals
            conn.execute('''CREATE TABLE IF NOT EXISTS referrals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                referrer_id INTEGER,
                referred_id INTEGER UNIQUE,
                referred_date TEXT,
                bonus_paid BOOLEAN DEFAULT 0,
                username TEXT,
                full_name TEXT
            )''')
            
            # Welcome settings
            conn.execute('''CREATE TABLE IF NOT EXISTS welcome_settings (
                id INTEGER PRIMARY KEY CHECK (id=1),
                welcome_text TEXT DEFAULT 'ကြိုဆိုပါတယ် {name} ရေ...\n\nအောက်က ခလုတ်လေးတွေကနေ လုပ်ဆောင်နိုင်ပါတယ်။',
                buttons TEXT DEFAULT '[]',
                photo_id TEXT DEFAULT NULL
            )''')
            
            # Banned users
            conn.execute('''CREATE TABLE IF NOT EXISTS banned_users (
                user_id INTEGER PRIMARY KEY
            )''')
            
            # Insert defaults
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
    waiting_for_ban_id = State()
    waiting_for_unban_id = State()
    waiting_for_restore_file = State()

class UserStates(StatesGroup):
    waiting_for_account_name = State()
    waiting_for_phone = State()
    waiting_for_withdraw_amount = State()

# ==================== INIT ====================
db = Database()
bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# ==================== KEYBOARDS ====================
def main_menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🎲 ကံစမ်းမည်"), KeyboardButton(text="💰 ထုတ်ယူရန်")],
            [KeyboardButton(text="📊 My Info"), KeyboardButton(text="👥 Invite")]
        ],
        resize_keyboard=True
    )

def back_btn(callback="admin_back"):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Back", callback_data=callback)]
    ])

def parse_buttons(data):
    try:
        return json.loads(data)
    except:
        return []

def make_buttons(buttons, width=2):
    if not buttons:
        return None
    kb = []
    row = []
    for btn in buttons:
        row.append(InlineKeyboardButton(text=btn['text'], url=btn.get('url', '')))
        if len(row) == width:
            kb.append(row)
            row = []
    if row:
        kb.append(row)
    return InlineKeyboardMarkup(inline_keyboard=kb)

# ==================== CHANNEL CHECK ====================
async def check_channels(user_id):
    with db.get_connection() as conn:
        channels = conn.execute("SELECT * FROM force_channels").fetchall()
    
    not_joined = []
    for ch in channels:
        try:
            member = await bot.get_chat_member(chat_id=ch['channel_id'], user_id=user_id)
            if member.status in ['left', 'kicked']:
                not_joined.append(ch)
        except:
            not_joined.append(ch)
    
    return len(not_joined) == 0, not_joined

def force_kb(channels):
    kb = []
    for ch in channels:
        if ch['channel_link']:
            kb.append([InlineKeyboardButton(text=f"📢 Join {ch['channel_name']}", url=ch['channel_link'])])
    kb.append([InlineKeyboardButton(text="🔄 Check Again", callback_data="check_join")])
    return InlineKeyboardMarkup(inline_keyboard=kb)

# ==================== CHECK BAN ====================
async def is_banned(user_id):
    with db.get_connection() as conn:
        banned = conn.execute("SELECT * FROM banned_users WHERE user_id=?", (user_id,)).fetchone()
    return banned is not None

# ==================== START ====================
@dp.message(Command("start"))
async def start(message: Message):
    user_id = message.from_user.id
    username = message.from_user.username or "No username"
    full_name = message.from_user.full_name
    
    # Get referrer from link (direct user_id)
    referrer_id = None
    if message.text and len(message.text.split()) > 1:
        try:
            referrer_id = int(message.text.split()[1])
            if referrer_id == user_id:
                referrer_id = None
            print(f"🔗 Referrer ID from link: {referrer_id}")  # Debug
        except:
            pass
    
    # Check ban
    if await is_banned(user_id):
        await message.answer(f"❌ သင်သည် Bot မှ ပိတ်ပင်ခံထားရပါသည်။")
        return
    
    # Add user to DB
    with db.get_connection() as conn:
        user = conn.execute("SELECT * FROM users WHERE user_id=?", (user_id,)).fetchone()
        
        if not user:
            conn.execute(
                "INSERT INTO users (user_id, username, full_name, join_date, referred_by) VALUES (?,?,?,?,?)",
                (user_id, username, full_name, datetime.now().isoformat(), referrer_id or 0)
            )
            print(f"✅ New user added: {user_id}")  # Debug
            
            # Handle referral notification
            if referrer_id:
                referrer = conn.execute("SELECT * FROM users WHERE user_id=?", (referrer_id,)).fetchone()
                if referrer:
                    conn.execute(
                        "INSERT INTO referrals (referrer_id, referred_id, referred_date, username, full_name) VALUES (?,?,?,?,?)",
                        (referrer_id, user_id, datetime.now().isoformat(), username, full_name)
                    )
                    
                    # Notify referrer
                    try:
                        text = f"""
👋 **လူသစ်ခေါ်ယူမှုအကြောင်းကြားစာ**
━━━━━━━━━━━━━━━━
သင့် Link ကနေ လူသစ်ဝင်ရောက်လာပါပြီ။

👤 နာမည်: {full_name}
🆔 User ID: `{user_id}`
🔗 Username: @{username if username != 'No username' else 'မရှိ'}
⏰ အချိန်: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
━━━━━━━━━━━━━━━━
💰 သူကံစမ်းမှသာ Bonus 50 ကျပ်ရမည်။
                        """
                        await bot.send_message(referrer_id, text)
                        print(f"📤 Referral notification sent to {referrer_id}")  # Debug
                    except Exception as e:
                        print(f"❌ Failed to send referral notification: {e}")
    
    # Check channels
    joined, not_joined = await check_channels(user_id)
    if not joined:
        await message.answer("🔒 ကျေးဇူးပြု၍ အောက်ပါ Channel များကို Join ပေးပါ။", reply_markup=force_kb(not_joined))
        return
    
    # Welcome message
    with db.get_connection() as conn:
        welcome = conn.execute("SELECT * FROM welcome_settings WHERE id=1").fetchone()
    
    text = welcome['welcome_text'].replace("{name}", full_name)
    buttons = parse_buttons(welcome['buttons'])
    photo = welcome['photo_id']
    
    if photo:
        try:
            await message.answer_photo(photo=photo, caption=text, reply_markup=main_menu())
        except:
            await message.answer(text, reply_markup=main_menu())
    else:
        await message.answer(text, reply_markup=main_menu())
    
    if buttons:
        await message.answer("🔗 **အသုံးဝင်သော Link များ**", reply_markup=make_buttons(buttons))
    
    print(f"✅ Start completed for user {user_id}")  # Debug

@dp.callback_query(F.data == "check_join")
async def check_join(callback: CallbackQuery):
    joined, _ = await check_channels(callback.from_user.id)
    if joined:
        await callback.message.delete()
        await start(callback.message)
    else:
        await callback.answer("ကျေးဇူးပြု၍ Channel များကို Join ပါ။", show_alert=True)

# ==================== MY INFO ====================
@dp.message(F.text == "📊 My Info")
async def my_info(message: Message):
    user_id = message.from_user.id
    if await is_banned(user_id):
        return
    
    with db.get_connection() as conn:
        user = conn.execute("SELECT * FROM users WHERE user_id=?", (user_id,)).fetchone()
        if not user:
            return
        
        text = f"""
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
        await message.answer(text, reply_markup=main_menu())

# ==================== INVITE ====================
@dp.message(F.text == "👥 Invite")
async def invite(message: Message):
    user_id = message.from_user.id
    if await is_banned(user_id):
        return
    
    with db.get_connection() as conn:
        user = conn.execute("SELECT * FROM users WHERE user_id=?", (user_id,)).fetchone()
        if not user:
            return
        
        bot_info = await bot.get_me()
        # Generate invite link - direct user_id (without ref_)
        invite_link = f"https://t.me/{bot_info.username}?start={user_id}"
        
        text = f"""
👥 **Invite Friends**

လူတစ်ယောက်ခေါ်ရင် 50 ကျပ်ရမည်။
ခေါ်လာတဲ့လူက ကံစမ်းမှသာ ရမည်။

သင်၏လက်ရှိခေါ်ဆောင်ထားသူ: {user['total_invite']} ယောက်
ခေါ်ဆောင်နိုင်သည့်အများဆုံး: {user['invite_limit']} ယောက်

**သင်၏ Invite Link:**
 {invite_link}

👉 အထက်ပါ Link ကိုနှိပ်၍ Copy ကူးနိုင်ပါသည်။
        """
        await message.answer(text, reply_markup=main_menu())
        
        # Show recent referrals
        refs = conn.execute(
            "SELECT * FROM referrals WHERE referrer_id=? ORDER BY referred_date DESC LIMIT 5",
            (user_id,)
        ).fetchall()
        
        if refs:
            t = "**လတ်တလော ခေါ်ယူထားသူများ**\n\n"
            for r in refs:
                t += f"👤 {r['full_name']}\n"
                t += f"🆔 `{r['referred_id']}`\n"
                t += f"💰 Bonus: {'ရပြီ' if r['bonus_paid'] else 'မရသေး (ကံစမ်းရန်)'}\n\n"
            await message.answer(t)
        
        # Check limit
        if user['total_invite'] >= user['invite_limit']:
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📢 Request More", callback_data="request_limit")],
                [InlineKeyboardButton(text="🔙 Back", callback_data="back_to_main")]
            ])
            await message.answer("⚠️ သင်၏ Invite Limit ပြည့်သွားပါပြီ။ Limit တိုးရန် Request လုပ်ပါ။", reply_markup=kb)

@dp.callback_query(F.data == "request_limit")
async def request_limit(callback: CallbackQuery):
    user_id = callback.from_user.id
    
    with db.get_connection() as conn:
        user = conn.execute("SELECT * FROM users WHERE user_id=?", (user_id,)).fetchone()
        if not user:
            return
        
        text = f"""
📢 **Limit တိုးရန် Request**
━━━━━━━━━━━━━━━━
👤 နာမည် - {user['full_name']}
🆔 User ID - `{user['user_id']}`
🔗 Username - @{user['username']}
👥 Total Invite - {user['total_invite']}
📊 Current Limit - {user['invite_limit']}
━━━━━━━━━━━━━━━━
        """
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Confirm", callback_data=f"confirm_limit_{user_id}")],
            [InlineKeyboardButton(text="❌ Cancel", callback_data=f"cancel_limit_{user_id}")]
        ])
        await bot.send_message(OWNER_ID, text, reply_markup=kb)
        await callback.answer("Request sent to owner!", show_alert=True)

@dp.callback_query(F.data == "back_to_main")
async def back_to_main(callback: CallbackQuery):
    await callback.message.delete()
    await start(callback.message)

# ==================== GAME ====================
@dp.message(F.text == "🎲 ကံစမ်းမည်")
async def play_game(message: Message):
    user_id = message.from_user.id
    today = datetime.now().strftime("%Y-%m-%d")
    
    if await is_banned(user_id):
        return
    
    joined, not_joined = await check_channels(user_id)
    if not joined:
        await message.answer("🔒 ကျေးဇူးပြု၍ အောက်ပါ Channel များကို Join ပေးပါ။", reply_markup=force_kb(not_joined))
        return
    
    with db.get_connection() as conn:
        game = conn.execute("SELECT * FROM game_settings WHERE id=1").fetchone()
        user = conn.execute("SELECT * FROM users WHERE user_id=?", (user_id,)).fetchone()
        
        if not game['game_active']:
            await message.answer("ဂိမ်းမစတင်သေးပါ။ Owner စတင်ရန်စောင့်ဆိုင်းပါ။", reply_markup=main_menu())
            return
        
        if game['current_amount'] <= 0:
            await message.answer("ကံစမ်းငွေကုန်သွားပါပြီ။ နောက်ရက်မှကံစမ်းပါ။", reply_markup=main_menu())
            return
        
        if user['has_played']:
            await message.answer("ယနေ့အတွက် သင်ကံစမ်းပြီးပါပြီ။ နောက်ရက်မှပြန်ကံစမ်းပါ။", reply_markup=main_menu())
            return
        
        # Calculate amount
        total = game['total_amount']
        current = game['current_amount']
        
        if total <= 2000:
            amount = random.randint(120, 200)
        elif total <= 4000:
            amount = random.randint(200, 270)
        elif total <= 20000:
            amount = random.randint(570, 800)
        else:
            amount = random.randint(250, 500) if random.random() < 0.2 else random.randint(100, 250)
        
        if amount > current:
            amount = current
        if amount < 100:
            amount = 100
        
        # Update game
        new_current = current - amount
        conn.execute("UPDATE game_settings SET current_amount=? WHERE id=1", (new_current,))
        
        # Update user
        conn.execute(
            "UPDATE users SET balance=balance+?, last_game_amount=?, last_game_time=?, has_played=1 WHERE user_id=?",
            (amount, amount, datetime.now().isoformat(), user_id)
        )
        
        # Get updated user
        updated_user = conn.execute("SELECT * FROM users WHERE user_id=?", (user_id,)).fetchone()
        
        # CHECK REFERRAL BONUS - Give bonus to referrer
        if user['referred_by'] and user['referred_by'] > 0:
            ref = conn.execute("SELECT * FROM referrals WHERE referred_id=? AND bonus_paid=0", (user_id,)).fetchone()
            if ref:
                # Give bonus to referrer (+50 balance and +1 invite count)
                conn.execute(
                    "UPDATE users SET balance=balance+50, total_invite=total_invite+1 WHERE user_id=?",
                    (user['referred_by'],)
                )
                conn.execute("UPDATE referrals SET bonus_paid=1 WHERE referred_id=?", (user_id,))
                
                # Get referrer for notification
                referrer = conn.execute("SELECT * FROM users WHERE user_id=?", (user['referred_by'],)).fetchone()
                
                # Send notification to referrer
                try:
                    text = f"""
🎉 **Referral Bonus ရရှိပါပြီ!**
━━━━━━━━━━━━━━━━
သင်ခေါ်ယူထားသူ {user['full_name']} ကံစမ်းလိုက်ပါပြီ။

👤 ခေါ်ယူထားသူ: {user['full_name']}
🆔 User ID: `{user_id}`

💰 ရရှိသော Bonus: 50 ကျပ်
👥 ခေါ်ယူထားသူဦးရေ: +1

📊 **သင်၏ ယခုအခြေအနေ**
━━━━━━━━━━━━━━━━
👥 စုစုပေါင်းခေါ်ယူထားသူ: {referrer['total_invite'] + 1} ယောက်
💰 လက်ကျန်ငွေ: {referrer['balance'] + 50} ကျပ်
━━━━━━━━━━━━━━━━
                    """
                    await bot.send_message(user['referred_by'], text)
                except:
                    pass
                
                # Send notification to group
                try:
                    await bot.send_message(
                        GROUP_ID,
                        f"🎉 **Referral Bonus အကြောင်းကြားစာ**\n━━━━━━━━━━━━━━━━\n👤 {referrer['full_name']} နှင့် {user['full_name']} တို့ Referral စနစ်အရ\n💰 {referrer['full_name']} အကောင့်ထဲသို့ 50 ကျပ် ထည့်ပေးလိုက်ပါပြီ။\n👥 ခေါ်ယူထားသူဦးရေ 1 တိုးလာပါပြီ။\n━━━━━━━━━━━━━━━━"
                    )
                except:
                    pass
        
        # Save winner
        conn.execute(
            "INSERT INTO game_winners (user_id, username, full_name, amount, win_time, game_date) VALUES (?,?,?,?,?,?)",
            (user_id, user['username'], user['full_name'], amount, datetime.now().isoformat(), today)
        )
        
        # Send result to user
        result = f"""
🎲 **ကံစမ်းရလဒ်**
━━━━━━━━━━━━━━━━
👤 နာမည် - {user['full_name']}
💰 ရရှိငွေ - {amount} ကျပ်
💵 လက်ကျန်ငွေ - {updated_user['balance']} ကျပ်
⏰ အချိန် - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
━━━━━━━━━━━━━━━━
✨ ဆက်လက်ကံစမ်းရန် ကံစမ်းမည်ကိုနှိပ်ပါ။
        """
        await message.answer(result, reply_markup=main_menu())
        
        # Check if game finished
        if new_current <= 0:
            conn.execute("UPDATE game_settings SET game_active=0 WHERE id=1")
            
            winners = conn.execute(
                "SELECT * FROM game_winners WHERE game_date=? ORDER BY win_time DESC",
                (today,)
            ).fetchall()
            
            text = f"📊 **ယနေ့ဂိမ်းပြီးဆုံးချိန် ရလဒ်များ ({today})**\n\n"
            total = 0
            for w in winners:
                text += f"👤 {w['full_name']} (@{w['username']})\n"
                text += f"🆔 `{w['user_id']}`\n"
                text += f"💰 ရရှိငွေ - {w['amount']} ကျပ်\n"
                text += f"⏰ {w['win_time']}\n\n"
                total += w['amount']
            text += f"━━━━━━━━━━━━━━━━\nစုစုပေါင်းပေးအပ်ငွေ: {total} ကျပ်"
            
            await bot.send_message(OWNER_ID, text)
            await bot.send_message(OWNER_ID, "⚠️ ကံစမ်းငွေကုန်သွားပါပြီ။ ဂိမ်းရပ်နားထားပါသည်။")

# ==================== WITHDRAW ====================
@dp.message(F.text == "💰 ထုတ်ယူရန်")
async def withdraw_start(message: Message, state: FSMContext):
    user_id = message.from_user.id
    if await is_banned(user_id):
        return
    
    with db.get_connection() as conn:
        user = conn.execute("SELECT * FROM users WHERE user_id=?", (user_id,)).fetchone()
        if not user or user['balance'] < 1500:
            await message.answer("❌ အနည်းဆုံး 1500 ကျပ်ရှိမှထုတ်နိုင်ပါသည်။", reply_markup=main_menu())
            return
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 KPay", callback_data="pay_kpay"),
         InlineKeyboardButton(text="🏦 Wave", callback_data="pay_wave")],
        [InlineKeyboardButton(text="🔙 Back", callback_data="back_to_main")]
    ])
    
    await message.answer("💰 **ငွေထုတ်ယူရန်**\n\nကျေးဇူးပြု၍ သင့်ငွေလက်ခံမည့်နည်းလမ်းကို ရွေးချယ်ပါ။", reply_markup=kb)

@dp.callback_query(F.data.startswith("pay_"))
async def withdraw_method(callback: CallbackQuery, state: FSMContext):
    method = callback.data.split("_")[1]
    await state.update_data(method=method.upper())
    
    await callback.message.edit_text(
        f"💳 **{method.upper()} ငွေထုတ်ယူရန်**\n\nကျေးဇူးပြု၍ သင့် အကောင့်နာမည် ကို ရိုက်ထည့်ပါ။\nဥပမာ - {method.upper()} အကောင့်နာမည်",
        reply_markup=back_btn("back_to_main")
    )
    await state.set_state(UserStates.waiting_for_account_name)

@dp.message(UserStates.waiting_for_account_name)
async def withdraw_account(message: Message, state: FSMContext):
    await state.update_data(account=message.text.strip())
    await message.answer("📞 **ဖုန်းနံပါတ် ထည့်ပါ**\n\nကျေးဇူးပြု၍ သင့် ဖုန်းနံပါတ် ကို ရိုက်ထည့်ပါ။\nဥပမာ - 09793251923")
    await state.set_state(UserStates.waiting_for_phone)

@dp.message(UserStates.waiting_for_phone)
async def withdraw_phone(message: Message, state: FSMContext):
    await state.update_data(phone=message.text.strip())
    
    user_id = message.from_user.id
    with db.get_connection() as conn:
        user = conn.execute("SELECT * FROM users WHERE user_id=?", (user_id,)).fetchone()
    
    await message.answer(
        f"💰 **ငွေပမာဏ ထည့်ပါ**\n\n"
        f"သင့်လက်ကျန်ငွေ: {user['balance']} ကျပ်\n"
        f"ထုတ်ယူလိုသောငွေပမာဏကို ရိုက်ထည့်ပါ။\n"
        f"(အနည်းဆုံး 1500 ကျပ်)"
    )
    await state.set_state(UserStates.waiting_for_withdraw_amount)

@dp.message(UserStates.waiting_for_withdraw_amount)
async def withdraw_amount(message: Message, state: FSMContext):
    try:
        amount = int(message.text.strip())
        user_id = message.from_user.id
        username = message.from_user.username or "No username"
        full_name = message.from_user.full_name
        
        data = await state.get_data()
        
        with db.get_connection() as conn:
            user = conn.execute("SELECT * FROM users WHERE user_id=?", (user_id,)).fetchone()
            
            if amount > user['balance']:
                await message.answer(f"သင့်လက်ကျန်ငွေ {user['balance']} ကျပ်သာရှိသည်။ ထပ်မံကြိုးစားပါ။")
                await state.clear()
                return
            
            if amount < 1500:
                await message.answer("❌ အနည်းဆုံး 1500 ကျပ်မှ ထုတ်ယူနိုင်ပါသည်။")
                await state.clear()
                return
            
            conn.execute(
                "UPDATE users SET phone=?, kpay_name=? WHERE user_id=?",
                (data['phone'], data['account'], user_id)
            )
            
            text = f"""
📤 **ငွေထုတ်ယူရန် တောင်းဆိုချက်**
━━━━━━━━━━━━━━━━
👤 အမည် - {full_name}
🆔 User ID - `{user_id}`
🔗 Username - @{username}
💰 ထုတ်ယူမည့်ငွေ - {amount} ကျပ်
💳 ငွေလက်ခံမည့် အကောင့် - {data['method']}
📝 အကောင့်နာမည် - {data['account']}
📞 ဖုန်းနံပါတ် - {data['phone']}
💵 လက်ကျန်ငွေ - {user['balance']} ကျပ်
━━━━━━━━━━━━━━━━
            """
            
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="✅ Confirm", callback_data=f"confirm_withdraw_{user_id}_{amount}"),
                 InlineKeyboardButton(text="❌ Cancel", callback_data=f"cancel_withdraw_{user_id}")]
            ])
            
            await bot.send_message(OWNER_ID, text, reply_markup=kb)
        
        await message.answer("✅ သင်၏တောင်းဆိုချက်ကို Owner ထံပို့လိုက်ပါပြီ။ ခွင့်ပြုချက်စောင့်ဆိုင်းပါ။", reply_markup=main_menu())
        await state.clear()
        
    except ValueError:
        await message.answer("❌ ကျေးဇူးပြု၍ ငွေပမာဏကို ဂဏန်းသာရိုက်ထည့်ပါ။")

# ==================== ADMIN PANEL ====================
@dp.message(Command("admin"))
async def admin_panel(message: Message):
    if message.from_user.id != OWNER_ID:
        await message.answer("❌ သင်သည် Owner မဟုတ်ပါ။")
        return
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💰 ငွေထည့်ရန်", callback_data="admin_add"),
         InlineKeyboardButton(text="📊 Game Status", callback_data="admin_status")],
        [InlineKeyboardButton(text="🔐 Force Channel", callback_data="admin_force"),
         InlineKeyboardButton(text="📈 Statistics", callback_data="admin_stats")],
        [InlineKeyboardButton(text="🎮 ဂိမ်းစတင်ရန်", callback_data="admin_start"),
         InlineKeyboardButton(text="🔄 Reset User Plays", callback_data="admin_reset")],
        [InlineKeyboardButton(text="📢 Broadcast", callback_data="admin_broadcast"),
         InlineKeyboardButton(text="👋 Welcome Settings", callback_data="admin_welcome")],
        [InlineKeyboardButton(text="🚫 Ban User", callback_data="admin_ban"),
         InlineKeyboardButton(text="✅ Unban User", callback_data="admin_unban")],
        [InlineKeyboardButton(text="📋 Banned List", callback_data="admin_banned"),
         InlineKeyboardButton(text="💾 Backup Data", callback_data="admin_backup")],
        [InlineKeyboardButton(text="🔄 Restore Data", callback_data="admin_restore")]
    ])
    
    await message.answer("👑 **Admin Panel**\n\nအောက်ပါလုပ်ဆောင်ချက်များကို ရွေးချယ်ပါ။", reply_markup=kb)

# ==================== ADMIN ADD AMOUNT ====================
@dp.callback_query(F.data == "admin_add")
async def admin_add(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text("💰 ကံစမ်းငွေထည့်ရန်\n\nငွေပမာဏ ရိုက်ထည့်ပါ။", reply_markup=back_btn())
    await state.set_state(AdminStates.waiting_for_amount)

@dp.message(AdminStates.waiting_for_amount)
async def process_add_amount(message: Message, state: FSMContext):
    try:
        amount = int(message.text)
        today = datetime.now().strftime("%Y-%m-%d")
        
        with db.get_connection() as conn:
            game = conn.execute("SELECT * FROM game_settings WHERE id=1").fetchone()
            new_total = game['total_amount'] + amount
            new_current = game['current_amount'] + amount
            conn.execute(
                "UPDATE game_settings SET total_amount=?, current_amount=?, game_date=? WHERE id=1",
                (new_total, new_current, today)
            )
        
        await message.answer(f"✅ ငွေထည့်ပြီးပါပြီ။ လက်ရှိငွေ: {new_current} ကျပ်")
        await state.clear()
    except:
        await message.answer("❌ နံပါတ်သာရိုက်ပါ။")

# ==================== ADMIN START GAME ====================
@dp.callback_query(F.data == "admin_start")
async def admin_start_game(callback: CallbackQuery):
    with db.get_connection() as conn:
        game = conn.execute("SELECT * FROM game_settings WHERE id=1").fetchone()
        if game['current_amount'] <= 0:
            await callback.answer("ငွေအရင်ထည့်ပါ။", show_alert=True)
            return
        conn.execute("UPDATE game_settings SET game_active=1 WHERE id=1")
    await callback.answer("ဂိမ်းစတင်ပါပြီ။")
    await admin_panel(callback.message)

# ==================== ADMIN RESET PLAYS ====================
@dp.callback_query(F.data == "admin_reset")
async def admin_reset_plays(callback: CallbackQuery):
    with db.get_connection() as conn:
        conn.execute("UPDATE users SET has_played=0")
    await callback.answer("ယနေ့အတွက် User အားလုံး ကံစမ်းခွင့်ပြန်ရပါပြီ။")
    await admin_panel(callback.message)

# ==================== ADMIN GAME STATUS ====================
@dp.callback_query(F.data == "admin_status")
async def admin_game_status(callback: CallbackQuery):
    with db.get_connection() as conn:
        game = conn.execute("SELECT * FROM game_settings WHERE id=1").fetchone()
        today_players = conn.execute(
            "SELECT COUNT(*) as count FROM users WHERE has_played=1"
        ).fetchone()['count']
        today_winners = conn.execute(
            "SELECT COUNT(*) as count FROM game_winners WHERE game_date=?",
            (datetime.now().strftime("%Y-%m-%d"),)
        ).fetchone()['count']
    
    text = f"""
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
    await callback.message.edit_text(text, reply_markup=back_btn())

# ==================== ADMIN STATISTICS ====================
@dp.callback_query(F.data == "admin_stats")
async def admin_statistics(callback: CallbackQuery):
    with db.get_connection() as conn:
        total_users = conn.execute("SELECT COUNT(*) as count FROM users").fetchone()['count']
        active_users = conn.execute("SELECT COUNT(*) as count FROM users WHERE is_banned=0").fetchone()['count']
        banned_users = conn.execute("SELECT COUNT(*) as count FROM users WHERE is_banned=1").fetchone()['count']
        total_balance = conn.execute("SELECT SUM(balance) as total FROM users").fetchone()['total'] or 0
        game = conn.execute("SELECT * FROM game_settings WHERE id=1").fetchone()
        channels = conn.execute("SELECT COUNT(*) as count FROM force_channels").fetchone()['count']
        total_winners = conn.execute("SELECT COUNT(*) as count FROM game_winners").fetchone()['count']
        total_given = conn.execute("SELECT SUM(amount) as total FROM game_winners").fetchone()['total'] or 0
        total_referrals = conn.execute("SELECT COUNT(*) as count FROM referrals").fetchone()['count']
        paid_referrals = conn.execute("SELECT COUNT(*) as count FROM referrals WHERE bonus_paid=1").fetchone()['count']
    
    text = f"""
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
    await callback.message.edit_text(text, reply_markup=back_btn())

# ==================== ADMIN BACK ====================
@dp.callback_query(F.data == "admin_back")
async def admin_back(callback: CallbackQuery):
    await admin_panel(callback.message)

# ==================== WITHDRAW CONFIRM ====================
@dp.callback_query(F.data.startswith("confirm_withdraw_"))
async def confirm_withdraw(callback: CallbackQuery):
    parts = callback.data.split("_")
    user_id = int(parts[2])
    amount = int(parts[3])
    
    with db.get_connection() as conn:
        user = conn.execute("SELECT * FROM users WHERE user_id=?", (user_id,)).fetchone()
        if not user:
            return
        
        tid = f"TRX{random.randint(100000, 999999)}"
        new_balance = user['balance'] - amount
        conn.execute("UPDATE users SET balance=? WHERE user_id=?", (new_balance, user_id))
        
        text = f"""
📤 **ငွေထုတ်ပြေစာ**
━━━━━━━━━━━━━━━━
👤 ငွေထုတ်ယူသူအမည် - {user['full_name']}
🆔 User ID - `{user['user_id']}`
💰 ထုတ်ယူခဲ့သည့်ငွေ - {amount} ကျပ်
💳 ငွေပေးပို့သူအမည် - Owner
📤 လွဲပေးခဲ့သည့်ငွေ - {amount} ကျပ်
⏰ အချိန် - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
🔢 ပြေစာ Transfer ID - `{tid}`
━━━━━━━━━━━━━━━━
✨ ကျေးဇူးတင်ပါသည်။
        """
        await bot.send_message(user_id, text)
        await bot.send_message(GROUP_ID, f"{user['full_name']} နက် {amount} ကျပ် ထုတ်ယူပြီးပါပြီ။ အကောင့်ထဲဝင်စစ်ပေးပါ။")
    
    await callback.message.edit_text(f"✅ Withdraw confirmed for user {user_id}\n\nငွေပမာဏ: {amount} ကျပ်")
    await callback.answer("Withdraw confirmed!")

@dp.callback_query(F.data.startswith("cancel_withdraw_"))
async def cancel_withdraw(callback: CallbackQuery):
    user_id = int(callback.data.split("_")[2])
    await bot.send_message(user_id, "❌ သင့်ငွေထုတ်ယူရန် တောင်းဆိုချက်ကို ပယ်ဖျက်လိုက်ပါသည်။")
    await callback.message.edit_text(f"✅ Withdraw cancelled for user {user_id}")

# ==================== LIMIT CONFIRM ====================
@dp.callback_query(F.data.startswith("confirm_limit_"))
async def confirm_limit(callback: CallbackQuery):
    user_id = int(callback.data.split("_")[2])
    
    with db.get_connection() as conn:
        conn.execute("UPDATE users SET invite_limit=200 WHERE user_id=?", (user_id,))
    
    await bot.send_message(user_id, "✅ သင်၏ Invite Limit ကို 200 သို့တိုးပေးလိုက်ပါပြီ။")
    await callback.message.edit_text(f"✅ Limit increased for user {user_id}")
    await callback.answer("Limit confirmed!")

@dp.callback_query(F.data.startswith("cancel_limit_"))
async def cancel_limit(callback: CallbackQuery):
    user_id = int(callback.data.split("_")[2])
    await bot.send_message(user_id, "❌ သင်၏ Limit တိုးရန် တောင်းဆိုချက်ကို ပယ်ဖျက်လိုက်ပါသည်။")
    await callback.message.edit_text(f"✅ Limit request cancelled for user {user_id}")

# ==================== FORCE CHANNEL ====================
@dp.callback_query(F.data == "admin_force")
async def force_menu(callback: CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Add Channel", callback_data="force_add"),
         InlineKeyboardButton(text="📋 List Channels", callback_data="force_list")],
        [InlineKeyboardButton(text="🔙 Back", callback_data="admin_back")]
    ])
    await callback.message.edit_text("🔐 **Force Channel Settings**\n\nChannel တွေထည့်ရန် Add Channel ကိုနှိပ်ပါ။", reply_markup=kb)

@dp.callback_query(F.data == "force_add")
async def force_add_start(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text("➕ **Add Channel**\n\nChannel Link ကိုရိုက်ထည့်ပါ။\nဥပမာ: https://t.me/yourchannel", reply_markup=back_btn("admin_force"))
    await state.set_state(AdminStates.waiting_for_channel_link)

@dp.message(AdminStates.waiting_for_channel_link)
async def force_add_link(message: Message, state: FSMContext):
    await state.update_data(link=message.text.strip())
    await message.answer("Channel Name ကိုရိုက်ထည့်ပါ။")
    await state.set_state(AdminStates.waiting_for_channel_name)

@dp.message(AdminStates.waiting_for_channel_name)
async def force_add_name(message: Message, state: FSMContext):
    name = message.text.strip()
    data = await state.get_data()
    
    try:
        if "t.me/" in data['link']:
            username = data['link'].split('/')[-1]
        else:
            username = data['link'].replace('@', '')
        
        chat = await bot.get_chat(f"@{username}")
        channel_id = str(chat.id)
        
        with db.get_connection() as conn:
            conn.execute(
                "INSERT INTO force_channels (channel_id, channel_name, channel_link, added_date) VALUES (?,?,?,?)",
                (channel_id, name, data['link'], datetime.now().isoformat())
            )
        
        await message.answer(f"✅ Channel {name} added successfully!")
        await state.clear()
    except Exception as e:
        await message.answer(f"❌ Error: {str(e)}\n\nBot ကို Channel မှာ Admin လုပ်ထားကြောင်းစစ်ပါ။")

@dp.callback_query(F.data == "force_list")
async def force_list_channels(callback: CallbackQuery):
    with db.get_connection() as conn:
        channels = conn.execute("SELECT * FROM force_channels").fetchall()
    
    if not channels:
        await callback.message.edit_text("No channels added yet.", reply_markup=back_btn("admin_force"))
        return
    
    text = "📋 **Force Channels**\n\n"
    kb = []
    
    for ch in channels:
        text += f"• {ch['channel_name']}\n"
        text += f"  Link: {ch['channel_link']}\n"
        text += f"  ID: `{ch['channel_id']}`\n\n"
        kb.append([InlineKeyboardButton(text=f"❌ Delete {ch['channel_name']}", callback_data=f"del_chan_{ch['id']}")])
    
    kb.append([InlineKeyboardButton(text="🔙 Back", callback_data="admin_force")])
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

@dp.callback_query(F.data.startswith("del_chan_"))
async def force_delete_channel(callback: CallbackQuery):
    cid = int(callback.data.split("_")[2])
    with db.get_connection() as conn:
        conn.execute("DELETE FROM force_channels WHERE id=?", (cid,))
    await callback.answer("Channel deleted!")
    await force_list_channels(callback)

# ==================== BAN/UNBAN ====================
@dp.callback_query(F.data == "admin_ban")
async def ban_start(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text("🚫 **Ban User**\n\nပိတ်ပင်လိုသော User ID ကိုရိုက်ထည့်ပါ။", reply_markup=back_btn())
    await state.set_state(AdminStates.waiting_for_ban_id)

@dp.message(AdminStates.waiting_for_ban_id)
async def ban_process(message: Message, state: FSMContext):
    try:
        uid = int(message.text.strip())
        
        with db.get_connection() as conn:
            user = conn.execute("SELECT * FROM users WHERE user_id=?", (uid,)).fetchone()
            if not user:
                await message.answer("❌ User ID မတွေ့ပါ။")
                await state.clear()
                return
            
            conn.execute("INSERT OR IGNORE INTO banned_users (user_id) VALUES (?)", (uid,))
            conn.execute("UPDATE users SET is_banned=1 WHERE user_id=?", (uid,))
        
        try:
            await bot.send_message(uid, f"🚫 သင်သည် Bot မှ ပိတ်ပင်ခံထားရပါသည်။")
        except:
            pass
        
        await message.answer(f"✅ User {uid} ({user['full_name']}) ကို ပိတ်ပင်လိုက်ပါပြီ။")
        await state.clear()
    except ValueError:
        await message.answer("❌ User ID သည် နံပါတ်ဖြစ်ရပါမည်။")

@dp.callback_query(F.data == "admin_unban")
async def unban_start(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text("✅ **Unban User**\n\nပြန်ဖွင့်ပေးလိုသော User ID ကိုရိုက်ထည့်ပါ။", reply_markup=back_btn())
    await state.set_state(AdminStates.waiting_for_unban_id)

@dp.message(AdminStates.waiting_for_unban_id)
async def unban_process(message: Message, state: FSMContext):
    try:
        uid = int(message.text.strip())
        
        with db.get_connection() as conn:
            banned = conn.execute("SELECT * FROM banned_users WHERE user_id=?", (uid,)).fetchone()
            if not banned:
                await message.answer("❌ ဤ User သည် ပိတ်ပင်ခံထားရသူမဟုတ်ပါ။")
                await state.clear()
                return
            
            conn.execute("DELETE FROM banned_users WHERE user_id=?", (uid,))
            conn.execute("UPDATE users SET is_banned=0 WHERE user_id=?", (uid,))
            user = conn.execute("SELECT * FROM users WHERE user_id=?", (uid,)).fetchone()
        
        try:
            await bot.send_message(uid, f"✅ ပြန်လည်ခွင့်ပြုလိုက်ပါပြီ။")
        except:
            pass
        
        await message.answer(f"✅ User {uid} ({user['full_name']}) ကို ပြန်ဖွင့်ပေးလိုက်ပါပြီ။")
        await state.clear()
    except ValueError:
        await message.answer("❌ User ID သည် နံပါတ်ဖြစ်ရပါမည်။")

@dp.callback_query(F.data == "admin_banned")
async def banned_list(callback: CallbackQuery):
    with db.get_connection() as conn:
        banned = conn.execute(
            "SELECT b.user_id, u.full_name, u.username FROM banned_users b LEFT JOIN users u ON b.user_id=u.user_id"
        ).fetchall()
    
    if not banned:
        await callback.message.edit_text("📋 **Banned Users List**\n\nပိတ်ပင်ခံထားရသူ မရှိပါ။", reply_markup=back_btn())
        return
    
    text = "📋 **Banned Users List**\n\n"
    kb = []
    
    for b in banned:
        text += f"👤 {b['full_name']}\n"
        text += f"🆔 `{b['user_id']}`\n"
        text += f"🔗 @{b['username'] if b['username'] != 'No username' else 'မရှိ'}\n\n"
        kb.append([InlineKeyboardButton(text=f"✅ Unban {b['full_name'][:15]}", callback_data=f"unban_{b['user_id']}")])
    
    kb.append([InlineKeyboardButton(text="🔙 Back", callback_data="admin_back")])
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

@dp.callback_query(F.data.startswith("unban_"))
async def quick_unban(callback: CallbackQuery):
    uid = int(callback.data.split("_")[1])
    
    with db.get_connection() as conn:
        conn.execute("DELETE FROM banned_users WHERE user_id=?", (uid,))
        conn.execute("UPDATE users SET is_banned=0 WHERE user_id=?", (uid,))
        user = conn.execute("SELECT * FROM users WHERE user_id=?", (uid,)).fetchone()
    
    try:
        await bot.send_message(uid, f"✅ ပြန်လည်ခွင့်ပြုလိုက်ပါပြီ။")
    except:
        pass
    
    await callback.answer(f"User {uid} unbanned!")
    await banned_list(callback)

# ==================== WELCOME SETTINGS ====================
@dp.callback_query(F.data == "admin_welcome")
async def welcome_menu(callback: CallbackQuery):
    with db.get_connection() as conn:
        w = conn.execute("SELECT * FROM welcome_settings WHERE id=1").fetchone()
    
    has_photo = "ရှိသည်" if w['photo_id'] else "မရှိ"
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏️ Edit Text", callback_data="welcome_text")],
        [InlineKeyboardButton(text="🔘 Edit Buttons (2 Columns)", callback_data="welcome_buttons")],
        [InlineKeyboardButton(text="🖼 Add/Change Photo", callback_data="welcome_add_photo")],
        [InlineKeyboardButton(text="🗑 Remove Photo", callback_data="welcome_remove_photo")],
        [InlineKeyboardButton(text="👁 Preview", callback_data="welcome_preview")],
        [InlineKeyboardButton(text="🔙 Back", callback_data="admin_back")]
    ])
    
    await callback.message.edit_text(
        f"👋 **Welcome Message Settings**\n\n"
        f"📸 ဓာတ်ပုံ: {has_photo}\n"
        f"📝 စာသား: {w['welcome_text'][:50]}...",
        reply_markup=kb
    )

@dp.callback_query(F.data == "welcome_text")
async def welcome_edit_text(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "✏️ **Edit Welcome Text**\n\n"
        "ကြိုဆိုစာသားအသစ်ကို ရိုက်ထည့်ပါ။\n"
        "Variable: {{name}} ကိုသုံးပြီး user နာမည်ထည့်နိုင်သည်။\n\n"
        "ဥပမာ: ကြိုဆိုပါတယ် {{name}} ရေ...\n\n"
        "မူလစာသားပြန်သုံးလိုပါက /default ရိုက်ပါ။",
        reply_markup=back_btn("admin_welcome")
    )
    await state.set_state(AdminStates.waiting_for_welcome_text)

@dp.message(AdminStates.waiting_for_welcome_text)
async def process_welcome_text(message: Message, state: FSMContext):
    if message.text == "/default":
        text = "ကြိုဆိုပါတယ် {name} ရေ...\n\nအောက်က ခလုတ်လေးတွေကနေ လုပ်ဆောင်နိုင်ပါတယ်။"
    else:
        text = message.text.strip()
    
    with db.get_connection() as conn:
        conn.execute("UPDATE welcome_settings SET welcome_text=? WHERE id=1", (text,))
    
    await message.answer("✅ Welcome Message အသစ်သိမ်းပြီးပါပြီ။")
    await state.clear()

@dp.callback_query(F.data == "welcome_buttons")
async def welcome_edit_buttons(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "🔘 **Edit Welcome Buttons**\n\n"
        "Button ထည့်ရန်: နာမည်,link\n"
        "ဥပမာ: Channel,https://t.me/yourchannel\n"
        "Website,https://example.com\n\n"
        "Button များကို 2 Column နှုန်းဖြင့် ပြသမည်ဖြစ်သည်။\n\n"
        "ပြီးရင် /done ရိုက်ပါ။\n"
        "ဖျက်ချင်ရင် /clear ရိုက်ပါ။\n"
        "လက်ရှိ Buttons ကြည့်ရန် /list ရိုက်ပါ။",
        reply_markup=back_btn("admin_welcome")
    )
    await state.set_state(AdminStates.waiting_for_welcome_buttons)
    await state.update_data(btns=[])

@dp.message(AdminStates.waiting_for_welcome_buttons)
async def process_welcome_buttons(message: Message, state: FSMContext):
    data = await state.get_data()
    btns = data.get('btns', [])
    
    if message.text == "/done":
        with db.get_connection() as conn:
            conn.execute("UPDATE welcome_settings SET buttons=? WHERE id=1", (json.dumps(btns),))
        await message.answer(f"✅ Welcome buttons updated! Total: {len(btns)} buttons")
        await state.clear()
    
    elif message.text == "/clear":
        await state.update_data(btns=[])
        await message.answer("✅ Buttons cleared! Add new buttons or /done")
    
    elif message.text == "/list":
        if btns:
            t = "**လက်ရှိ Buttons များ**\n\n"
            for i, b in enumerate(btns, 1):
                t += f"{i}. {b['text']} - {b['url']}\n"
            await message.answer(t)
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
            
            if not link.startswith(('http://', 'https://', 't.me/')):
                link = 'https://' + link
            
            btns.append({'text': name, 'url': link})
            await state.update_data(btns=btns)
            await message.answer(f"✅ Button added! Total: {len(btns)}\nAdd more or /done")
        except Exception as e:
            await message.answer(f"❌ အမှားဖြစ်နေပါသည်။ နမူနာ - နာမည်,link")

@dp.callback_query(F.data == "welcome_add_photo")
async def welcome_add_photo(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "🖼 **Add Welcome Photo**\n\n"
        "ဓာတ်ပုံတစ်ပုံပို့ပေးပါ။\n"
        "ဖျက်လိုပါက /skip ရိုက်ပါ။",
        reply_markup=back_btn("admin_welcome")
    )
    await state.set_state(AdminStates.waiting_for_welcome_photo)

@dp.message(AdminStates.waiting_for_welcome_photo)
async def process_welcome_photo(message: Message, state: FSMContext):
    if message.text == "/skip":
        await message.answer("✅ Photo မထည့်ပဲ ရပ်နားလိုက်ပါသည်။")
        await state.clear()
        return
    
    if message.photo:
        pid = message.photo[-1].file_id
        with db.get_connection() as conn:
            conn.execute("UPDATE welcome_settings SET photo_id=? WHERE id=1", (pid,))
        await message.answer("✅ Welcome photo updated successfully!")
        await state.clear()
    else:
        await message.answer("❌ ကျေးဇူးပြု၍ ဓာတ်ပုံပို့ပေးပါ။")

@dp.callback_query(F.data == "welcome_remove_photo")
async def welcome_remove_photo(callback: CallbackQuery):
    with db.get_connection() as conn:
        conn.execute("UPDATE welcome_settings SET photo_id=NULL WHERE id=1")
    await callback.answer("Photo removed!")
    await welcome_menu(callback)

@dp.callback_query(F.data == "welcome_preview")
async def welcome_preview(callback: CallbackQuery):
    with db.get_connection() as conn:
        w = conn.execute("SELECT * FROM welcome_settings WHERE id=1").fetchone()
    
    text = w['welcome_text'].replace("{name}", callback.from_user.full_name)
    btns = parse_buttons(w['buttons'])
    photo = w['photo_id']
    
    if photo:
        await callback.message.delete()
        await callback.message.answer_photo(
            photo=photo,
            caption=f"👁 **Preview**\n\n{text}",
            reply_markup=make_buttons(btns) or back_btn("admin_welcome")
        )
    else:
        await callback.message.edit_text(
            f"👁 **Preview**\n\n{text}",
            reply_markup=make_buttons(btns) or back_btn("admin_welcome")
        )

# ==================== BROADCAST ====================
@dp.callback_query(F.data == "admin_broadcast")
async def broadcast_start(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "📢 **Broadcast ပို့ရန်**\n\n"
        "စာသားရိုက်ထည့်ပါ။\n"
        "Button ထည့်လိုပါက /done ရိုက်ပြီး button ထည့်နိုင်သည်။\n"
        "Photo ပါထည့်လိုပါက photo ကိုအရင်ပို့ပါ။",
        reply_markup=back_btn()
    )
    await state.set_state(AdminStates.waiting_for_broadcast)

@dp.message(AdminStates.waiting_for_broadcast)
async def broadcast_text(message: Message, state: FSMContext):
    pid = None
    txt = message.caption if message.photo else message.text
    
    if message.photo:
        pid = message.photo[-1].file_id
        txt = message.caption or ""
    
    await state.update_data(text=txt, photo=pid, btns=[])
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Add Button", callback_data="broadcast_add")],
        [InlineKeyboardButton(text="🚀 Send Now", callback_data="broadcast_send")],
        [InlineKeyboardButton(text="❌ Cancel", callback_data="admin_back")]
    ])
    
    preview = f"Broadcast Preview:\n\n{txt}"
    
    if pid:
        await message.answer_photo(photo=pid, caption=preview + "\n\nButton ထည့်လိုပါက Add Button နှိပ်ပါ။", reply_markup=kb)
    else:
        await message.answer(preview + "\n\nButton ထည့်လိုပါက Add Button နှိပ်ပါ။", reply_markup=kb)

@dp.callback_query(F.data == "broadcast_add")
async def broadcast_add_button(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "Button ထည့်ရန်\n\n"
        "Button Name နှင့် Link ကိုရိုက်ထည့်ပါ။\n"
        "ပုံစံ - နာမည်,link\n"
        "ဥပမာ - Channel,https://t.me/yourchannel",
        reply_markup=back_btn("admin_broadcast")
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
        btns = data.get('btns', [])
        btns.append({'text': name, 'url': link})
        await state.update_data(btns=btns)
        
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="➕ Add More", callback_data="broadcast_add")],
            [InlineKeyboardButton(text="🚀 Send Now", callback_data="broadcast_send")],
            [InlineKeyboardButton(text="❌ Cancel", callback_data="admin_back")]
        ])
        
        await message.answer(f"Button Added! Total Buttons: {len(btns)}\n\nSend Now နှိပ်ပြီးပို့နိုင်သည်။", reply_markup=kb)
    except Exception as e:
        await message.answer("ပုံစံမှားနေပါသည်။ နမူနာ - နာမည်,link")

@dp.callback_query(F.data == "broadcast_send")
async def broadcast_send_now(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    text = data.get('text', '')
    photo = data.get('photo')
    btns = data.get('btns', [])
    
    # Create keyboard (2 columns)
    kb = None
    if btns:
        rows = []
        row = []
        for btn in btns:
            row.append(InlineKeyboardButton(text=btn['text'], url=btn['url']))
            if len(row) == 2:
                rows.append(row)
                row = []
        if row:
            rows.append(row)
        kb = InlineKeyboardMarkup(inline_keyboard=rows)
    
    # Get all users (non-banned only)
    with db.get_connection() as conn:
        users = conn.execute("SELECT user_id FROM users WHERE is_banned=0").fetchall()
    
    sent = 0
    failed = 0
    
    await callback.message.edit_text("📤 Broadcasting...")
    
    for u in users:
        try:
            if photo:
                await bot.send_photo(chat_id=u['user_id'], photo=photo, caption=text, reply_markup=kb)
            else:
                await bot.send_message(chat_id=u['user_id'], text=text, reply_markup=kb)
            sent += 1
            await asyncio.sleep(0.05)
        except:
            failed += 1
    
    await callback.message.edit_text(f"✅ Broadcast Done!\nSent: {sent}\nFailed: {failed}", reply_markup=back_btn())
    await state.clear()

# ==================== BACKUP ====================
@dp.callback_query(F.data == "admin_backup")
async def backup_data(callback: CallbackQuery):
    try:
        os.makedirs("backups", exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        fn = f"backups/backup_{ts}.json"
        
        # Export data
        data = {}
        with db.get_connection() as conn:
            tables = ['users', 'game_settings', 'game_winners', 'force_channels', 
                     'referrals', 'welcome_settings', 'banned_users']
            for t in tables:
                rows = conn.execute(f"SELECT * FROM {t}").fetchall()
                data[t] = [dict(r) for r in rows]
        
        with open(fn, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        size = os.path.getsize(fn)
        
        await callback.message.answer_document(
            FSInputFile(fn),
            caption=f"✅ **Backup Successful**\n\n📅 Date: {ts}\n📦 Size: {size} bytes"
        )
    except Exception as e:
        await callback.message.answer(f"❌ Backup failed: {str(e)}")

@dp.callback_query(F.data == "admin_restore")
async def restore_start(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "🔄 **Restore Data**\n\n"
        "ယခင် backup လုပ်ထားသော JSON ဖိုင်ကို ပို့ပေးပါ။\n"
        "⚠️ **သတိပေးချက်**: လက်ရှိဒေတာအားလုံး ပျက်သွားမည်ဖြစ်သည်။",
        reply_markup=back_btn()
    )
    await state.set_state(AdminStates.waiting_for_restore_file)

@dp.message(AdminStates.waiting_for_restore_file)
async def restore_file(message: Message, state: FSMContext):
    if not message.document:
        await message.answer("❌ JSON ဖိုင်ပို့ပေးပါ။")
        return
    
    try:
        file = await bot.get_file(message.document.file_id)
        downloaded = await bot.download_file(file.file_path)
        data = json.loads(downloaded.read().decode('utf-8'))
        
        await state.update_data(restore=data)
        
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Confirm Restore", callback_data="restore_confirm"),
             InlineKeyboardButton(text="❌ Cancel", callback_data="admin_back")]
        ])
        
        await message.answer(
            f"✅ **File loaded successfully**\n\nTables: {len(data)}\n\n⚠️ ဒေတာအားလုံး အစားထိုးမည်ဖြစ်သည်။ သေချာပါသလား?",
            reply_markup=kb
        )
    except Exception as e:
        await message.answer(f"❌ Restore failed: {str(e)}")

@dp.callback_query(F.data == "restore_confirm")
async def restore_confirm(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    restore = data.get('restore')
    
    if not restore:
        await callback.message.edit_text("❌ No data to restore")
        return
    
    try:
        with db.get_connection() as conn:
            tables = ['users', 'game_settings', 'game_winners', 'force_channels', 
                     'referrals', 'welcome_settings', 'banned_users']
            for t in tables:
                conn.execute(f"DELETE FROM {t}")
            
            for t, rows in restore.items():
                if t in tables and rows:
                    for r in rows:
                        cols = ', '.join(r.keys())
                        vals = ', '.join(['?' for _ in r])
                        try:
                            conn.execute(f"INSERT INTO {t} ({cols}) VALUES ({vals})", list(r.values()))
                        except:
                            pass
            
            conn.execute("INSERT OR IGNORE INTO game_settings (id) VALUES (1)")
            conn.execute("INSERT OR IGNORE INTO welcome_settings (id) VALUES (1)")
        
        await callback.message.edit_text("✅ **Restore completed successfully!**\n\nဒေတာအားလုံး ပြန်လည်တင်ပြီးပါပြီ။", reply_markup=back_btn())
        await state.clear()
    except Exception as e:
        await callback.message.edit_text(f"❌ Restore failed: {str(e)}")

# ==================== ERROR HANDLER ====================
@dp.errors()
async def errors_handler(update: types.Update, error: Exception):
    logger.error(f"Update {update} caused error {error}")
    return True

# ==================== START BOT ====================
async def main():
    print("🤖 Bot is starting...")
    print(f"👑 Owner ID: {OWNER_ID}")
    print(f"👥 Group ID: {GROUP_ID}")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
