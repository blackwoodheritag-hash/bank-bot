import nest_asyncio
nest_asyncio.apply()

import os
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler

# ===== ТВОИ ДАННЫЕ =====
TOKEN = "8713781397:AAGs7bYWG30XlSqbeP68iQM4ys9WXfcVJ30"
SHEET_NAME = "BankBot"
JSON_FILE = "bank-bot-490007-2a84923ee37c.json"
ADMIN_NAME = "Лия"
PORT = int(os.environ.get("PORT", 8443))  # Важно для Render!
# =======================

# Состояния
REG_NAME, TRANSFER_NAME, TRANSFER_AMOUNT = range(3)

print("🔌 ПОДКЛЮЧЕНИЕ К GOOGLE ТАБЛИЦЕ")

scope = ["https://spreadsheets.google.com/feeds",
         "https://www.googleapis.com/auth/drive"]

try:
    creds = ServiceAccountCredentials.from_json_keyfile_name(JSON_FILE, scope)
    client = gspread.authorize(creds)
    sheet = client.open(SHEET_NAME).sheet1
    print("✅ Таблица открыта успешно!")
except Exception as e:
    print(f"❌ Ошибка: {e}")
    sheet = None

def is_admin(user_id):
    try:
        all_records = sheet.get_all_records()
        for record in all_records:
            if str(record.get('telegram_id')) == str(user_id) and record.get('name') == ADMIN_NAME:
                return True
    except:
        pass
    return False

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    
    if sheet:
        all_records = sheet.get_all_records()
        for record in all_records:
            if str(record.get('telegram_id')) == user_id:
                name = record.get('name')
                balance = record.get('balance', 0)
                
                if is_admin(user_id):
                    await update.message.reply_text(
                        f"💰 С возвращением, Админ {name}!\n"
                        f"Твой баланс: {balance} ₽\n\n"
                        f"⚡ АДМИН КОМАНДЫ:\n"
                        f"/addmoney ИМЯ СУММА\n"
                        f"/takemoney ИМЯ СУММА\n"
                        f"/allusers\n"
                        f"/setbalance ИМЯ СУММА\n\n"
                        f"👤 Обычные команды:\n"
                        f"/balance - баланс\n"
                        f"/send - перевести"
                    )
                else:
                    await update.message.reply_text(
                        f"💰 С возвращением, {name}!\n"
                        f"Баланс: {balance} ₽\n\n"
                        f"Команды:\n"
                        f"/balance - баланс\n"
                        f"/send - перевести"
                    )
                return
    
    await update.message.reply_text(
        "👋 Привет! Ты новый пользователь.\n"
        "Напиши свое имя:"
    )
    return REG_NAME

async def get_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    name = update.message.text.strip()
    
    if len(name) < 2 or len(name) > 20:
        await update.message.reply_text("❌ Имя должно быть от 2 до 20 символов. Попробуй еще раз:")
        return REG_NAME
    
    try:
        sheet.append_row([user_id, name, 100 if name == ADMIN_NAME else 0])
        
        if name == ADMIN_NAME:
            await update.message.reply_text(f"🎉 Админ {name} зарегистрирован!")
        else:
            await update.message.reply_text(f"✅ Ты зарегистрирован как {name}!")
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка регистрации: {e}")
    
    return ConversationHandler.END

async def balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    
    if not sheet:
        await update.message.reply_text("❌ Ошибка таблицы")
        return
    
    try:
        all_records = sheet.get_all_records()
        for record in all_records:
            if str(record.get('telegram_id')) == user_id:
                await update.message.reply_text(
                    f"👤 {record.get('name')}\n"
                    f"💰 Баланс: {record.get('balance', 0)} ₽"
                )
                return
        await update.message.reply_text("❌ Ты не зарегистрирован. Напиши /start")
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {e}")

async def send_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    
    all_records = sheet.get_all_records()
    sender_found = None
    
    for record in all_records:
        if str(record.get('telegram_id')) == user_id:
            sender_found = record
            break
    
    if not sender_found:
        await update.message.reply_text("❌ Сначала зарегистрируйся: /start")
        return ConversationHandler.END
    
    context.user_data['sender'] = sender_found
    await update.message.reply_text(
        f"💰 Твой баланс: {sender_found.get('balance')} ₽\n\n"
        f"Введи ИМЯ получателя:"
    )
    return TRANSFER_NAME

async def send_get_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    receiver_name = update.message.text.strip()
    sender = context.user_data.get('sender')
    
    all_records = sheet.get_all_records()
    receiver_found = None
    
    for record in all_records:
        if record.get('name', '').lower() == receiver_name.lower():
            receiver_found = record
            break
    
    if not receiver_found:
        await update.message.reply_text(f"❌ Пользователь '{receiver_name}' не найден. Проверь имя:")
        return TRANSFER_NAME
    
    context.user_data['receiver'] = receiver_found
    await update.message.reply_text(
        f"✅ Получатель: {receiver_found.get('name')}\n"
        f"Введи сумму:"
    )
    return TRANSFER_AMOUNT

async def send_get_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        amount = float(update.message.text)
        if amount <= 0:
            await update.message.reply_text("❌ Сумма должна быть больше 0:")
            return TRANSFER_AMOUNT
        
        sender = context.user_data.get('sender')
        receiver = context.user_data.get('receiver')
        
        if sender.get('balance') < amount:
            await update.message.reply_text(
                f"❌ Недостаточно средств. Баланс: {sender.get('balance')} ₽\n"
                f"Введи другую сумму:"
            )
            return TRANSFER_AMOUNT
        
        # Находим строки
        all_records = sheet.get_all_records()
        sender_row = None
        receiver_row = None
        
        for i, record in enumerate(all_records, start=2):
            if str(record.get('telegram_id')) == str(sender.get('telegram_id')):
                sender_row = i
            if str(record.get('telegram_id')) == str(receiver.get('telegram_id')):
                receiver_row = i
        
        sheet.update_cell(sender_row, 3, sender.get('balance') - amount)
        sheet.update_cell(receiver_row, 3, receiver.get('balance') + amount)
        
        await update.message.reply_text(
            f"✅ Перевод выполнен!\n"
            f"Сумма: {amount} ₽\n"
            f"Кому: {receiver.get('name')}\n"
            f"Твой новый баланс: {sender.get('balance') - amount} ₽"
        )
        
        try:
            await context.bot.send_message(
                chat_id=int(receiver.get('telegram_id')),
                text=f"💰 {sender.get('name')} перевел тебе {amount} ₽"
            )
        except:
            pass
        
    except ValueError:
        await update.message.reply_text("❌ Введи число:")
        return TRANSFER_AMOUNT
    
    return ConversationHandler.END

# Админ-команды
async def add_money(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(str(update.effective_user.id)):
        await update.message.reply_text("❌ Только для админа!")
        return
    
    try:
        name = context.args[0]
        amount = float(context.args[1])
        
        all_records = sheet.get_all_records()
        for i, record in enumerate(all_records, start=2):
            if record.get('name', '').lower() == name.lower():
                new_balance = record.get('balance', 0) + amount
                sheet.update_cell(i, 3, new_balance)
                await update.message.reply_text(f"✅ Начислено {amount} ₽ пользователю {record.get('name')}")
                return
        await update.message.reply_text(f"❌ Пользователь '{name}' не найден")
    except (IndexError, ValueError):
        await update.message.reply_text("❌ Формат: /addmoney ИМЯ СУММА")

async def all_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(str(update.effective_user.id)):
        await update.message.reply_text("❌ Только для админа!")
        return
    
    all_records = sheet.get_all_records()
    text = "📋 ВСЕ ПОЛЬЗОВАТЕЛИ:\n\n"
    for record in all_records:
        text += f"👤 {record.get('name')}: {record.get('balance')} ₽\n"
    await update.message.reply_text(text)

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Действие отменено")
    return ConversationHandler.END

# Создаем приложение
app = Application.builder().token(TOKEN).build()

# Регистрация
reg_handler = ConversationHandler(
    entry_points=[CommandHandler('start', start)],
    states={REG_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_name)]},
    fallbacks=[CommandHandler('cancel', cancel)],
)

# Перевод
send_handler = ConversationHandler(
    entry_points=[CommandHandler('send', send_start)],
    states={
        TRANSFER_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, send_get_name)],
        TRANSFER_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, send_get_amount)],
    },
    fallbacks=[CommandHandler('cancel', cancel)],
)

app.add_handler(reg_handler)
app.add_handler(send_handler)
app.add_handler(CommandHandler("balance", balance))
app.add_handler(CommandHandler("addmoney", add_money))
app.add_handler(CommandHandler("allusers", all_users))

print("\n" + "="*60)
print("🚀 БОТ ЗАПУЩЕН!")
print("="*60 + "\n")

if __name__ == "__main__":
    app.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        url_path=TOKEN,
        webhook_url=f"https://{os.environ.get('RENDER_EXTERNAL_HOSTNAME', 'localhost')}/{TOKEN}"
    )