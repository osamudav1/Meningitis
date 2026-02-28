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
BOT_TOKEN = "7637155076:AAH88nASfWHsN70SeQxE5_8T9Un0xACnR1U"
OWNER_ID = 6231318714
GROUP_ID = -1002473190844

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
                is_banned BOOLEAN DEFAULT 0,
                ban_reason TEXT
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
                user_id INTEGER PRIMARY KEY,
                reason TEXT,
                banned_date TEXT,
                banned_by INTEGER
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
    waiting_for_ban_reason = State()
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
        user = conn.execute("SELECT is_banned FROM users WHERE user_id=?", (user_id,)).fetchone()
        banned = conn.execute("SELECT * FROM banned_users WHERE user_id=?", (user_id,)).fetchone()
    return (user and user['is_banned']) or (banned is not None)

# ==================== START ====================
@dp.message(Command("start"))
async def start(message: Message):
    user_id = message.from_user.id
    username = message.from_user.username or "No username"
    full_name = message.from_user.full_name
    
    # Get referrer from link
    referrer_id = None
    if message.text and len(message.text.split()) > 1:
        try:
            ref = message.text.split()[1]
            if ref.startswith("ref_"):
                referrer_id = int(ref.replace("ref_", ""))
                if referrer_id == user_id:
                    referrer_id = None
        except:
            pass
    
    # Check ban
    if await is_banned(user_id):
        with db.get_connection() as conn:
            ban = conn.execute("SELECT * FROM banned_users WHERE user_id=?", (user_id,)).fetchone()
        reason = ban['reason'] if ban else "N/A"
        await message.answer(f"❌ ပိတ်ပင်ခံထားရပါသည်။\nအကြောင်း: {reason}")
        return
    
    # Add user to DB
    with db.get_connection() as conn:
        user = conn.execute("SELECT * FROM users WHERE user_id=?", (user_id,)).fetchone()
        
        if not user:
            conn.execute(
                "INSERT INTO users (user_id, username, full_name, join_date, referred_by) VALUES (?,?,?,?,?)",
                (user_id, username, full_name, datetime.now().isoformat(), referrer_id or 0)
            )
            
            # Handle referral
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
👋 **လူသစ်ခေါ်ယူမှု**

သင့် Link ကနေ လူသစ်ဝင်လာပါပြီ။

👤 {full_name}
🆔 {user_id}
⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

💰 သူကံစမ်းမှသာ Bonus 50 ကျပ်ရမည်။
                        """
                        await bot.send_message(referrer_id, text)
                    except:
                        pass
    
    # Check channels
    joined, not_joined = await check_channels(user_id)
    if not joined:
        await message.answer("🔒 Channel များ Join ပေးပါ။", reply_markup=force_kb(not_joined))
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
        await message.answer("🔗 Link များ", reply_markup=make_buttons(buttons))

@dp.callback_query(F.data == "check_join")
async def check_join(callback: CallbackQuery):
    joined, _ = await check_channels(callback.from_user.id)
    if joined:
        await callback.message.delete()
        await start(callback.message)
    else:
        await callback.answer("Channel များ Join ပါ။", show_alert=True)

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
📋 **My Info**
━━━━━━━━━━━━━━
👤 {user['full_name']}
🆔 `{user['user_id']}`
👥 ခေါ်ယူထားသူ: {user['total_invite']} ယောက်
💰 လက်ကျန်: {user['balance']} ကျပ်
🎲 နောက်ဆုံးကံစမ်း: {user['last_game_amount']} ကျပ်
⏰ အချိန်: {user['last_game_time'] or 'မရှိ'}
📅 ယနေ့ကံစမ်း: {'ပြီး' if user['has_played'] else 'မရှိ'}
━━━━━━━━━━━━━━
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
        link = f"https://t.me/{bot_info.username}?start=ref_{user_id}"
        
        text = f"""
👥 **Invite Friends**

လူတစ်ယောက်ခေါ်ရင် 50 ကျပ်
ခေါ်လာတဲ့လူ ကံစမ်းမှ ရမည်။

သင့်ခေါ်ယူထားသူ: {user['total_invite']} ယောက်
ခေါ်နိုင်တဲ့အများဆုံး: {user['invite_limit']} ယောက်

**Link:** `{link}`
        """
        await message.answer(text, reply_markup=main_menu())
        
        # Show recent referrals
        refs = conn.execute(
            "SELECT * FROM referrals WHERE referrer_id=? ORDER BY referred_date DESC LIMIT 5",
            (user_id,)
        ).fetchall()
        
        if refs:
            t = "**လတ်တလော ခေါ်ယူထားသူမျာ**\n\n"
            for r in refs:
                t += f"👤 {r['full_name']}\n"
                t += f"💰 Bonus: {'ရပြီ' if r['bonus_paid'] else 'မရသေး'}\n\n"
            await message.answer(t)
        
        # Check limit
        if user['total_invite'] >= user['invite_limit']:
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📢 Request More", callback_data="request_limit")],
                [InlineKeyboardButton(text="🔙 Back", callback_data="back_to_main")]
            ])
            await message.answer("⚠️ Limit ပြည့်သွားပါပြီ။", reply_markup=kb)

@dp.callback_query(F.data == "request_limit")
async def request_limit(callback: CallbackQuery):
    user_id = callback.from_user.id
    
    with db.get_connection() as conn:
        user = conn.execute("SELECT * FROM users WHERE user_id=?", (user_id,)).fetchone()
        if not user:
            return
        
        text = f"""
📢 **Limit Request**
━━━━━━━━━━━━━━
👤 {user['full_name']}
🆔 `{user['user_id']}`
👥 Total: {user['total_invite']}
📊 Limit: {user['invite_limit']}
━━━━━━━━━━━━━━
        """
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Confirm", callback_data=f"confirm_limit_{user_id}")],
            [InlineKeyboardButton(text="❌ Cancel", callback_data=f"cancel_limit_{user_id}")]
        ])
        await bot.send_message(OWNER_ID, text, reply_markup=kb)
        await callback.answer("Request sent!", show_alert=True)

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
        await message.answer("🔒 Channel များ Join ပါ။", reply_markup=force_kb(not_joined))
        return
    
    with db.get_connection() as conn:
        game = conn.execute("SELECT * FROM game_settings WHERE id=1").fetchone()
        user = conn.execute("SELECT * FROM users WHERE user_id=?", (user_id,)).fetchone()
        
        if not game['game_active']:
            await message.answer("ဂိမ်းမစတင်သေးပါ။")
            return
        
        if game['current_amount'] <= 0:
            await message.answer("ငွေကုန်သွားပါပြီ။")
            return
        
        if user['has_played']:
            await message.answer("ယနေ့ ကံစမ်းပြီးပါပြီ။")
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
        
        # Check referral bonus
        if user['referred_by'] and user['referred_by'] > 0:
            ref = conn.execute("SELECT * FROM referrals WHERE referred_id=?", (user_id,)).fetchone()
            if ref and not ref['bonus_paid']:
                # Give bonus to referrer
                conn.execute(
                    "UPDATE users SET balance=balance+50, total_invite=total_invite+1 WHERE user_id=?",
                    (user['referred_by'],)
                )
                conn.execute("UPDATE referrals SET bonus_paid=1 WHERE referred_id=?", (user_id,))
                
                # Get referrer
                referrer = conn.execute("SELECT * FROM users WHERE user_id=?", (user['referred_by'],)).fetchone()
                
                # Notify referrer
                try:
                    text = f"""
🎉 **Referral Bonus**

သင်ခေါ်ယူထားသူ {user['full_name']} ကံစမ်းလိုက်ပါပြီ။

💰 Bonus: 50 ကျပ်
👥 Invite: +1

📊 ယခုအခြေအနေ
👥 ခေါ်ယူထားသူ: {referrer['total_invite']+1} ယောက်
💰 လက်ကျန်: {referrer['balance']+50} ကျပ်
                    """
                    await bot.send_message(user['referred_by'], text)
                except:
                    pass
                
                # Group notification
                try:
                    await bot.send_message(
                        GROUP_ID,
                        f"🎉 Referral Bonus: {referrer['full_name']} က {user['full_name']} ကံစမ်းလို့ 50 ကျပ် ရပါတယ်။"
                    )
                except:
                    pass
        
        # Save winner
        conn.execute(
            "INSERT INTO game_winners (user_id, username, full_name, amount, win_time, game_date) VALUES (?,?,?,?,?,?)",
            (user_id, user['username'], user['full_name'], amount, datetime.now().isoformat(), today)
        )
        
        # Send result
        result = f"""
🎲 **ကံစမ်းရလဒ်**
━━━━━━━━━━━━━━
👤 {user['full_name']}
💰 ရငွေ: {amount} ကျပ်
💵 လက်ကျန်: {updated_user['balance']} ကျပ်
⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
━━━━━━━━━━━━━━
        """
        await message.answer(result, reply_markup=main_menu())
        
        # Check if game finished
        if new_current <= 0:
            conn.execute("UPDATE game_settings SET game_active=0 WHERE id=1")
            
            winners = conn.execute(
                "SELECT * FROM game_winners WHERE game_date=? ORDER BY win_time DESC",
                (today,)
            ).fetchall()
            
            text = f"📊 **ယနေ့ရလဒ်များ ({today})**\n\n"
            total = 0
            for w in winners:
                text += f"👤 {w['full_name']}\n"
                text += f"💰 {w['amount']} ကျပ်\n"
                text += f"⏰ {w['win_time']}\n\n"
                total += w['amount']
            text += f"စုစုပေါင်း: {total} ကျပ်"
            
            await bot.send_message(OWNER_ID, text)
            await bot.send_message(OWNER_ID, "⚠️ ငွေကုန်သွားပါပြီ။ ဂိမ်းရပ်နားထားပါသည်။")

# ==================== WITHDRAW ====================
@dp.message(F.text == "💰 ထုတ်ယူရန်")
async def withdraw_start(message: Message, state: FSMContext):
    user_id = message.from_user.id
    if await is_banned(user_id):
        return
    
    with db.get_connection() as conn:
        user = conn.execute("SELECT * FROM users WHERE user_id=?", (user_id,)).fetchone()
        if not user or user['balance'] < 1500:
            await message.answer("❌ အနည်းဆုံး 1500 ကျပ်ရှိမှ ထုတ်နိုင်ပါသည်။")
            return
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 KPay", callback_data="pay_kpay"),
         InlineKeyboardButton(text="🏦 Wave", callback_data="pay_wave")],
        [InlineKeyboardButton(text="🔙 Back", callback_data="back_to_main")]
    ])
    
    await message.answer("💰 ငွေထုတ်ယူရန်\nငွေလက်ခံမည့်နည်းလမ်းရွေးပါ။", reply_markup=kb)

@dp.callback_query(F.data.startswith("pay_"))
async def withdraw_method(callback: CallbackQuery, state: FSMContext):
    method = callback.data.split("_")[1]
    await state.update_data(method=method.upper())
    
    await callback.message.edit_text(
        f"💳 {method.upper()} အကောင့်နာမည် ရိုက်ထည့်ပါ။",
        reply_markup=back_btn("back_to_main")
    )
    await state.set_state(UserStates.waiting_for_account_name)

@dp.message(UserStates.waiting_for_account_name)
async def withdraw_account(message: Message, state: FSMContext):
    await state.update_data(account=message.text.strip())
    await message.answer("📞 ဖုန်းနံပါတ် ရိုက်ထည့်ပါ။")
    await state.set_state(UserStates.waiting_for_phone)

@dp.message(UserStates.waiting_for_phone)
async def withdraw_phone(message: Message, state: FSMContext):
    await state.update_data(phone=message.text.strip())
    
    user_id = message.from_user.id
    with db.get_connection() as conn:
        user = conn.execute("SELECT * FROM users WHERE user_id=?", (user_id,)).fetchone()
    
    await message.answer(
        f"💰 ထုတ်ယူမည့်ငွေပမာဏ ရိုက်ထည့်ပါ။\n"
        f"လက်ကျန်: {user['balance']} ကျပ်\n"
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
                await message.answer(f"လက်ကျန် {user['balance']} ကျပ်သာရှိသည်။")
                await state.clear()
                return
            
            if amount < 1500:
                await message.answer("❌ အနည်းဆုံး 1500 ကျပ်")
                await state.clear()
                return
            
            conn.execute(
                "UPDATE users SET phone=?, kpay_name=? WHERE user_id=?",
                (data['phone'], data['account'], user_id)
            )
            
            text = f"""
📤 **ငွေထုတ်ယူရန် တောင်းဆိုချက်**
━━━━━━━━━━━━━━━━
👤 {full_name}
🆔 `{user_id}`
💰 ထုတ်မည့်ငွေ: {amount} ကျပ်
💳 နည်းလမ်း: {data['method']}
📝 အကောင့်: {data['account']}
📞 ဖုန်း: {data['phone']}
💵 လက်ကျန်: {user['balance']} ကျပ်
━━━━━━━━━━━━━━━━
            """
            
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="✅ Confirm", callback_data=f"confirm_withdraw_{user_id}_{amount}"),
                 InlineKeyboardButton(text="❌ Cancel", callback_data=f"cancel_withdraw_{user_id}")]
            ])
            
            await bot.send_message(OWNER_ID, text, reply_markup=kb)
        
        await message.answer("✅ တောင်းဆိုချက် ပို့ပြီးပါပြီ။ ခွင့်ပြုချက်စောင့်ပါ။", reply_markup=main_menu())
        await state.clear()
        
    except ValueError:
        await message.answer("❌ ဂဏန်းသာရိုက်ပါ။")

# ==================== ADMIN ====================
@dp.message(Command("admin"))
async def admin(message: Message):
    if message.from_user.id != OWNER_ID:
        return
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💰 ငွေထည့်", callback_data="admin_add"),
         InlineKeyboardButton(text="📊 Game Status", callback_data="admin_status")],
        [InlineKeyboardButton(text="🔐 Force Channel", callback_data="admin_force"),
         InlineKeyboardButton(text="📈 Statistics", callback_data="admin_stats")],
        [InlineKeyboardButton(text="🎮 ဂိမ်းစတင်", callback_data="admin_start"),
         InlineKeyboardButton(text="🔄 Reset Plays", callback_data="admin_reset")],
        [InlineKeyboardButton(text="📢 Broadcast", callback_data="admin_broadcast"),
         InlineKeyboardButton(text="👋 Welcome", callback_data="admin_welcome")],
        [InlineKeyboardButton(text="🚫 Ban User", callback_data="admin_ban"),
         InlineKeyboardButton(text="✅ Unban User", callback_data="admin_unban")],
        [InlineKeyboardButton(text="📋 Banned List", callback_data="admin_banned")],
        [InlineKeyboardButton(text="💾 Backup", callback_data="admin_backup"),
         InlineKeyboardButton(text="🔄 Restore", callback_data="admin_restore")]
    ])
    
    await message.answer("👑 **Admin Panel**", reply_markup=kb)

@dp.callback_query(F.data == "admin_add")
async def admin_add(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text("💰 ငွေပမာဏ ရိုက်ထည့်ပါ။", reply_markup=back_btn())
    await state.set_state(AdminStates.waiting_for_amount)

@dp.message(AdminStates.waiting_for_amount)
async def process_add(message: Message, state: FSMContext):
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
        
        await message.answer(f"✅ ငွေထည့်ပြီးပါပြီ။ လက်ရှိ: {new_current} ကျပ်")
        await state.clear()
    except:
        await message.answer("❌ နံပါတ်သာရိုက်ပါ။")

@dp.callback_query(F.data == "admin_start")
async def admin_start(callback: CallbackQuery):
    with db.get_connection() as conn:
        game = conn.execute("SELECT * FROM game_settings WHERE id=1").fetchone()
        if game['current_amount'] <= 0:
            await callback.answer("ငွေအရင်ထည့်ပါ။", show_alert=True)
            return
        conn.execute("UPDATE game_settings SET game_active=1 WHERE id=1")
    await callback.answer("ဂိမ်းစတင်ပါပြီ။")
    await admin(callback.message)

@dp.callback_query(F.data == "admin_reset")
async def admin_reset(callback: CallbackQuery):
    with db.get_connection() as conn:
        conn.execute("UPDATE users SET has_played=0")
    await callback.answer("Reset လုပ်ပြီးပါပြီ။")
    await admin(callback.message)

@dp.callback_query(F.data == "admin_status")
async def admin_status(callback: CallbackQuery):
    with db.get_connection() as conn:
        game = conn.execute("SELECT * FROM game_settings WHERE id=1").fetchone()
        players = conn.execute("SELECT COUNT(*) as c FROM users WHERE has_played=1").fetchone()['c']
        winners = conn.execute(
            "SELECT COUNT(*) as c FROM game_winners WHERE game_date=?",
            (datetime.now().strftime("%Y-%m-%d"),)
        ).fetchone()['c']
    
    text = f"""
📊 **Game Status**
━━━━━━━━━━━━━━
💰 စုစုပေါင်း: {game['total_amount']} ကျပ်
💵 လက်ကျန်: {game['current_amount']} ကျပ်
🎮 အခြေအနေ: {'ဖွင့်' if game['game_active'] else 'ပိတ်'}
👥 ယနေ့ကစားသူ: {players} ယောက်
🏆 ယနေ့ဆုရှင်: {winners} ယောက်
📅 ရက်စွဲ: {game['game_date'] or 'မရှိ'}
━━━━━━━━━━━━━━
    """
    await callback.message.edit_text(text, reply_markup=back_btn())

@dp.callback_query(F.data == "admin_stats")
async def admin_stats(callback: CallbackQuery):
    with db.get_connection() as conn:
        total_users = conn.execute("SELECT COUNT(*) as c FROM users").fetchone()['c']
        active = conn.execute("SELECT COUNT(*) as c FROM users WHERE is_banned=0").fetchone()['c']
        banned = conn.execute("SELECT COUNT(*) as c FROM users WHERE is_banned=1").fetchone()['c']
        balance = conn.execute("SELECT SUM(balance) as s FROM users").fetchone()['s'] or 0
        game = conn.execute("SELECT * FROM game_settings WHERE id=1").fetchone()
        channels = conn.execute("SELECT COUNT(*) as c FROM force_channels").fetchone()['c']
        winners = conn.execute("SELECT COUNT(*) as c FROM game_winners").fetchone()['c']
        given = conn.execute("SELECT SUM(amount) as s FROM game_winners").fetchone()['s'] or 0
        refs = conn.execute("SELECT COUNT(*) as c FROM referrals").fetchone()['c']
        paid = conn.execute("SELECT COUNT(*) as c FROM referrals WHERE bonus_paid=1").fetchone()['c']
    
    text = f"""
📈 **Statistics**
━━━━━━━━━━━━━━
👥 စုစုပေါင်း: {total_users}
✅ အသုံးပြုခွင့်ရှိ: {active}
🚫 ပိတ်ပင်ခံရ: {banned}
💰 လက်ကျန်စုစုပေါင်း: {balance} ကျပ်
🎲 ဂိမ်းလက်ကျန်: {game['current_amount']} ကျပ်
🔐 Force Channels: {channels}
🏆 ဆုရှင်စုစုပေါင်း: {winners}
💸 ပေးအပ်ငွေစုစုပေါင်း: {given} ကျပ်
👥 စုစုပေါင်းခေါ်ယူမှု: {refs}
💰 Referral Bonus: {paid * 50} ကျပ်
━━━━━━━━━━━━━━
    """
    await callback.message.edit_text(text, reply_markup=back_btn())

@dp.callback_query(F.data == "admin_back")
async def admin_back(callback: CallbackQuery):
    await admin(callback.message)

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
━━━━━━━━━━━━━━
👤 {user['full_name']}
🆔 `{user['user_id']}`
💰 ထုတ်ငွေ: {amount} ကျပ်
⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
🔢 ID: {tid}
━━━━━━━━━━━━━━
        """
        await bot.send_message(user_id, text)
        await bot.send_message(GROUP_ID, f"{user['full_name']} နက် {amount} ကျပ် ထုတ်ယူပါသည်။")
    
    await callback.message.edit_text(f"✅ Withdraw confirmed: {amount} ကျပ်")

@dp.callback_query(F.data.startswith("cancel_withdraw_"))
async def cancel_withdraw(callback: CallbackQuery):
    user_id = int(callback.data.split("_")[2])
    await bot.send_message(user_id, "❌ ငွေထုတ်တောင်းဆိုချက် ပယ်ဖျက်ခံရပါသည်။")
    await callback.message.edit_text(f"✅ Withdraw cancelled")

# ==================== LIMIT CONFIRM ====================
@dp.callback_query(F.data.startswith("confirm_limit_"))
async def confirm_limit(callback: CallbackQuery):
    user_id = int(callback.data.split("_")[2])
    
    with db.get_connection() as conn:
        conn.execute("UPDATE users SET invite_limit=200 WHERE user_id=?", (user_id,))
    
    await bot.send_message(user_id, "✅ Limit 200 သို့တိုးပေးပါပြီ။")
    await callback.message.edit_text(f"✅ Limit increased for {user_id}")

@dp.callback_query(F.data.startswith("cancel_limit_"))
async def cancel_limit(callback: CallbackQuery):
    user_id = int(callback.data.split("_")[2])
    await bot.send_message(user_id, "❌ Limit request cancelled")
    await callback.message.edit_text(f"✅ Limit cancelled for {user_id}")

# ==================== FORCE CHANNEL ====================
@dp.callback_query(F.data == "admin_force")
async def force_menu(callback: CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Add", callback_data="force_add"),
         InlineKeyboardButton(text="📋 List", callback_data="force_list")],
        [InlineKeyboardButton(text="🔙 Back", callback_data="admin_back")]
    ])
    await callback.message.edit_text("🔐 Force Channel Settings", reply_markup=kb)

@dp.callback_query(F.data == "force_add")
async def force_add(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text("➕ Channel Link ထည့်ပါ။", reply_markup=back_btn("admin_force"))
    await state.set_state(AdminStates.waiting_for_channel_link)

@dp.message(AdminStates.waiting_for_channel_link)
async def force_link(message: Message, state: FSMContext):
    await state.update_data(link=message.text.strip())
    await message.answer("Channel Name ထည့်ပါ။")
    await state.set_state(AdminStates.waiting_for_channel_name)

@dp.message(AdminStates.waiting_for_channel_name)
async def force_name(message: Message, state: FSMContext):
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
        
        await message.answer(f"✅ {name} added!")
        await state.clear()
    except Exception as e:
        await message.answer(f"❌ Error: {e}")

@dp.callback_query(F.data == "force_list")
async def force_list(callback: CallbackQuery):
    with db.get_connection() as conn:
        channels = conn.execute("SELECT * FROM force_channels").fetchall()
    
    if not channels:
        await callback.message.edit_text("No channels", reply_markup=back_btn("admin_force"))
        return
    
    text = "📋 **Force Channels**\n\n"
    kb = []
    
    for ch in channels:
        text += f"• {ch['channel_name']}\n"
        text += f"  ID: `{ch['channel_id']}`\n\n"
        kb.append([InlineKeyboardButton(text=f"❌ Delete {ch['channel_name']}", callback_data=f"del_chan_{ch['id']}")])
    
    kb.append([InlineKeyboardButton(text="🔙 Back", callback_data="admin_force")])
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

@dp.callback_query(F.data.startswith("del_chan_"))
async def del_chan(callback: CallbackQuery):
    cid = int(callback.data.split("_")[2])
    with db.get_connection() as conn:
        conn.execute("DELETE FROM force_channels WHERE id=?", (cid,))
    await callback.answer("Deleted!")
    await force_list(callback)

# ==================== BAN/UNBAN ====================
@dp.callback_query(F.data == "admin_ban")
async def ban_start(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text("🚫 User ID ထည့်ပါ။", reply_markup=back_btn())
    await state.set_state(AdminStates.waiting_for_ban_reason)
    await state.update_data(ban_id=None)

@dp.message(AdminStates.waiting_for_ban_reason)
async def ban_id(message: Message, state: FSMContext):
    try:
        uid = int(message.text)
        await state.update_data(ban_id=uid)
        await message.answer("အကြောင်းရင်းရိုက်ထည့်ပါ။")
    except:
        await message.answer("❌ User ID မှားနေပါသည်။")

@dp.message(AdminStates.waiting_for_ban_reason)
async def ban_reason(message: Message, state: FSMContext):
    reason = message.text.strip()
    data = await state.get_data()
    uid = data.get('ban_id')
    
    if not uid:
        await message.answer("❌ User ID မတွေ့ပါ။")
        return
    
    with db.get_connection() as conn:
        conn.execute("UPDATE users SET is_banned=1 WHERE user_id=?", (uid,))
        conn.execute(
            "INSERT OR REPLACE INTO banned_users (user_id, reason, banned_date, banned_by) VALUES (?,?,?,?)",
            (uid, reason, datetime.now().isoformat(), OWNER_ID)
        )
        user = conn.execute("SELECT * FROM users WHERE user_id=?", (uid,)).fetchone()
    
    try:
        await bot.send_message(uid, f"🚫 ပိတ်ပင်ခံရပါသည်။\nအကြောင်း: {reason}")
    except:
        pass
    
    await message.answer(f"✅ {uid} ({user['full_name']}) ကို ပိတ်ပင်လိုက်ပါပြီ။")
    await state.clear()

@dp.callback_query(F.data == "admin_unban")
async def unban_start(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text("✅ User ID ထည့်ပါ။", reply_markup=back_btn())
    await state.set_state(AdminStates.waiting_for_unban_id)

@dp.message(AdminStates.waiting_for_unban_id)
async def unban_process(message: Message, state: FSMContext):
    try:
        uid = int(message.text)
        
        with db.get_connection() as conn:
            banned = conn.execute("SELECT * FROM banned_users WHERE user_id=?", (uid,)).fetchone()
            if not banned:
                await message.answer("❌ ဤ User ပိတ်ပင်ခံထားရသူမဟုတ်ပါ။")
                return
            
            conn.execute("UPDATE users SET is_banned=0 WHERE user_id=?", (uid,))
            conn.execute("DELETE FROM banned_users WHERE user_id=?", (uid,))
            user = conn.execute("SELECT * FROM users WHERE user_id=?", (uid,)).fetchone()
        
        try:
            await bot.send_message(uid, "✅ ပြန်လည်ခွင့်ပြုလိုက်ပါပြီ။")
        except:
            pass
        
        await message.answer(f"✅ {uid} ({user['full_name']}) ကို ပြန်ဖွင့်ပေးလိုက်ပါပြီ။")
        await state.clear()
    except:
        await message.answer("❌ User ID မှားနေပါသည်။")

@dp.callback_query(F.data == "admin_banned")
async def banned_list(callback: CallbackQuery):
    with db.get_connection() as conn:
        banned = conn.execute(
            "SELECT b.*, u.full_name FROM banned_users b LEFT JOIN users u ON b.user_id=u.user_id ORDER BY b.banned_date DESC"
        ).fetchall()
    
    if not banned:
        await callback.message.edit_text("📋 Banned List ဘာမှမရှိပါ။", reply_markup=back_btn())
        return
    
    text = "📋 **Banned List**\n\n"
    kb = []
    
    for b in banned:
        text += f"👤 {b['full_name']}\n"
        text += f"🆔 `{b['user_id']}`\n"
        text += f"❌ {b['reason']}\n"
        text += f"📅 {b['banned_date'][:10]}\n\n"
        kb.append([InlineKeyboardButton(text=f"✅ Unban {b['full_name'][:15]}", callback_data=f"unban_{b['user_id']}")])
    
    kb.append([InlineKeyboardButton(text="🔙 Back", callback_data="admin_back")])
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

@dp.callback_query(F.data.startswith("unban_"))
async def quick_unban(callback: CallbackQuery):
    uid = int(callback.data.split("_")[1])
    
    with db.get_connection() as conn:
        conn.execute("UPDATE users SET is_banned=0 WHERE user_id=?", (uid,))
        conn.execute("DELETE FROM banned_users WHERE user_id=?", (uid,))
        user = conn.execute("SELECT * FROM users WHERE user_id=?", (uid,)).fetchone()
    
    try:
        await bot.send_message(uid, "✅ ပြန်လည်ခွင့်ပြုလိုက်ပါပြီ။")
    except:
        pass
    
    await callback.answer(f"Unbanned {uid}")
    await banned_list(callback)

# ==================== WELCOME ====================
@dp.callback_query(F.data == "admin_welcome")
async def welcome_menu(callback: CallbackQuery):
    with db.get_connection() as conn:
        w = conn.execute("SELECT * FROM welcome_settings WHERE id=1").fetchone()
    
    has_photo = "ရှိ" if w['photo_id'] else "မရှိ"
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏️ Edit Text", callback_data="welcome_text")],
        [InlineKeyboardButton(text="🔘 Edit Buttons", callback_data="welcome_buttons")],
        [InlineKeyboardButton(text="🖼 Add Photo", callback_data="welcome_add_photo")],
        [InlineKeyboardButton(text="🗑 Remove Photo", callback_data="welcome_remove_photo")],
        [InlineKeyboardButton(text="👁 Preview", callback_data="welcome_preview")],
        [InlineKeyboardButton(text="🔙 Back", callback_data="admin_back")]
    ])
    
    await callback.message.edit_text(
        f"👋 Welcome Settings\n\n📸 Photo: {has_photo}\n📝 {w['welcome_text'][:50]}...",
        reply_markup=kb
    )

@dp.callback_query(F.data == "welcome_text")
async def welcome_text(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "✏️ စာသားအသစ်ရိုက်ပါ။\n{name} သုံးနိုင်သည်။\n/default မူလစာသားပြန်",
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
    
    await message.answer("✅ သိမ်းပြီးပါပြီ။")
    await state.clear()

@dp.callback_query(F.data == "welcome_buttons")
async def welcome_buttons(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "🔘 Button ထည့်ရန်: နာမည်,link\n"
        "ဥပမာ: Channel,https://t.me/abc\n"
        "ပြီးရင် /done\n/clear ရှင်းမယ်\n/list ကြည့်မယ်",
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
        await message.answer(f"✅ {len(btns)} buttons သိမ်းပြီးပါပြီ။")
        await state.clear()
    
    elif message.text == "/clear":
        await state.update_data(btns=[])
        await message.answer("✅ Cleared")
    
    elif message.text == "/list":
        if btns:
            t = "**Buttons**\n"
            for i, b in enumerate(btns, 1):
                t += f"{i}. {b['text']} - {b['url']}\n"
            await message.answer(t)
        else:
            await message.answer("Buttons မရှိသေးပါ။")
    
    else:
        try:
            name, link = message.text.split(',', 1)
            name = name.strip()
            link = link.strip()
            if not link.startswith(('http://', 'https://', 't.me/')):
                link = 'https://' + link
            btns.append({'text': name, 'url': link})
            await state.update_data(btns=btns)
            await message.answer(f"✅ Added! Total: {len(btns)}")
        except:
            await message.answer("❌ ပုံစံမှား။ နမူနာ: နာမည်,link")

@dp.callback_query(F.data == "welcome_add_photo")
async def welcome_add_photo(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text("🖼 ဓာတ်ပုံပို့ပါ။ /skip ရိုက်ပါက မထည့်ပဲထား", reply_markup=back_btn("admin_welcome"))
    await state.set_state(AdminStates.waiting_for_welcome_photo)

@dp.message(AdminStates.waiting_for_welcome_photo)
async def process_welcome_photo(message: Message, state: FSMContext):
    if message.text == "/skip":
        await message.answer("✅ မထည့်ပဲထားလိုက်ပါသည်။")
        await state.clear()
        return
    
    if message.photo:
        pid = message.photo[-1].file_id
        with db.get_connection() as conn:
            conn.execute("UPDATE welcome_settings SET photo_id=? WHERE id=1", (pid,))
        await message.answer("✅ Photo added!")
        await state.clear()
    else:
        await message.answer("❌ ဓာတ်ပုံပို့ပါ။")

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
            caption=f"👁 Preview\n\n{text}",
            reply_markup=make_buttons(btns) or back_btn("admin_welcome")
        )
    else:
        await callback.message.edit_text(
            f"👁 Preview\n\n{text}",
            reply_markup=make_buttons(btns) or back_btn("admin_welcome")
        )

# ==================== BROADCAST ====================
@dp.callback_query(F.data == "admin_broadcast")
async def broadcast_start(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "📢 Broadcast ပို့ရန် စာသားရိုက်ပါ။\nPhoto ပါထည့်လိုပါက photo အရင်ပို့ပါ။",
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
    
    if pid:
        await message.answer_photo(photo=pid, caption=txt + "\n\nButton ထည့်လိုပါက Add နှိပ်ပါ။", reply_markup=kb)
    else:
        await message.answer(txt + "\n\nButton ထည့်လိုပါက Add နှိပ်ပါ။", reply_markup=kb)

@dp.callback_query(F.data == "broadcast_add")
async def broadcast_add(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "Button ထည့်ရန်: နာမည်,link\nဥပမာ: Channel,https://t.me/abc",
        reply_markup=back_btn("admin_broadcast")
    )
    await state.set_state(AdminStates.waiting_for_broadcast_button)

@dp.message(AdminStates.waiting_for_broadcast_button)
async def process_broadcast_btn(message: Message, state: FSMContext):
    try:
        name, link = message.text.split(',', 1)
        name = name.strip()
        link = link.strip()
        
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
        
        await message.answer(f"✅ Added! Total: {len(btns)}", reply_markup=kb)
    except:
        await message.answer("❌ ပုံစံမှား။ နမူနာ: နာမည်,link")

@dp.callback_query(F.data == "broadcast_send")
async def broadcast_send(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    text = data.get('text', '')
    photo = data.get('photo')
    btns = data.get('btns', [])
    
    # Create keyboard
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
    
    # Get users
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
    
    await callback.message.edit_text(f"✅ Done!\nSent: {sent}\nFailed: {failed}", reply_markup=back_btn())
    await state.clear()

# ==================== BACKUP/RESTORE ====================
@dp.callback_query(F.data == "admin_backup")
async def backup(callback: CallbackQuery):
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
        
        # Log
        size = os.path.getsize(fn)
        with db.get_connection() as conn:
            conn.execute(
                "INSERT INTO backup_log (backup_date, filename, file_size) VALUES (?,?,?)",
                (datetime.now().isoformat(), fn, size)
            )
        
        await callback.message.answer_document(
            FSInputFile(fn),
            caption=f"✅ Backup Done!\n📅 {ts}\n📦 {size} bytes"
        )
    except Exception as e:
        await callback.message.answer(f"❌ Backup failed: {e}")

@dp.callback_query(F.data == "admin_restore")
async def restore_start(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "🔄 JSON ဖိုင်ကို ပို့ပါ။\n⚠️ လက်ရှိဒေတာ အားလုံး ပျက်သွားမည်။",
        reply_markup=back_btn()
    )
    await state.set_state(AdminStates.waiting_for_restore_file)

@dp.message(AdminStates.waiting_for_restore_file)
async def restore_file(message: Message, state: FSMContext):
    if not message.document:
        await message.answer("❌ JSON ဖိုင်ပို့ပါ။")
        return
    
    try:
        file = await bot.get_file(message.document.file_id)
        downloaded = await bot.download_file(file.file_path)
        data = json.loads(downloaded.read().decode('utf-8'))
        
        await state.update_data(restore=data)
        
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Confirm", callback_data="restore_confirm"),
             InlineKeyboardButton(text="❌ Cancel", callback_data="admin_back")]
        ])
        
        await message.answer(
            f"✅ File loaded!\nTables: {len(data)}\n\n⚠️ သေချာပါသလား?",
            reply_markup=kb
        )
    except Exception as e:
        await message.answer(f"❌ Error: {e}")

@dp.callback_query(F.data == "restore_confirm")
async def restore_confirm(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    restore = data.get('restore')
    
    if not restore:
        await callback.message.edit_text("❌ No data")
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
        
        await callback.message.edit_text("✅ Restore completed!", reply_markup=back_btn())
        await state.clear()
    except Exception as e:
        await callback.message.edit_text(f"❌ Restore failed: {e}")

# ==================== ERROR HANDLER ====================
@dp.errors()
async def errors(update: types.Update, error: Exception):
    logger.error(f"Update {update} caused error {error}")
    return True

# ==================== START BOT ====================
async def main():
    print("🤖 Bot started!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
