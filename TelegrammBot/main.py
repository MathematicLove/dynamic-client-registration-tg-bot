import logging
import re
import os
import threading
import base64
from telegram.ext import ContextTypes
from datetime import datetime, time, timedelta
from pytz import timezone
from dotenv import load_dotenv
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad
import subprocess

from DB import insert_client, insert_appointment, insert_status, update_appointment, update_status, insert_log
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ConversationHandler,
    ContextTypes,
    filters
)
from UI import main_menu_keyboard, build_time_keyboard

load_dotenv()   
TOKEN = os.getenv("TELEGRAMM_API_TOKKEN")
if not TOKEN:
    raise ValueError("Не найден TELEGRAMM_API_TOKKEN в .env файле")

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

AES_KEY = b'mysecretkey12345'

def aes_encrypt(plaintext: str) -> str:
    """
    Зашифровывает строку с помощью AES (CBC) и возвращает Base64-кодированное значение.
    """
    data = plaintext.encode('utf-8')
    cipher = AES.new(AES_KEY, AES.MODE_CBC)
    ct_bytes = cipher.encrypt(pad(data, AES.block_size))
    encrypted = cipher.iv + ct_bytes
    return base64.b64encode(encrypted).decode('utf-8')

def aes_decrypt(ciphertext_b64: str) -> str:
    """
    Дешифрует Base64-кодированное значение, зашифрованное AES (CBC), и возвращает исходный текст.
    """
    ciphertext = base64.b64decode(ciphertext_b64)
    iv = ciphertext[:AES.block_size]
    ct = ciphertext[AES.block_size:]
    cipher = AES.new(AES_KEY, AES.MODE_CBC, iv)
    data = unpad(cipher.decrypt(ct), AES.block_size)
    return data.decode('utf-8')

appointments = {}

busy_slots = {}  # busy_slots[(date, time)] = user_id

AVAILABLE_TIMES = []
hour = 8
minute = 0
while True:
    h_str = str(hour).zfill(2)
    m_str = str(minute).zfill(2)
    tm = f"{h_str}:{m_str}"
    AVAILABLE_TIMES.append(tm)
    minute += 20
    if minute >= 60:
        hour += 1
        minute -= 60
    if hour > 20:
        break

(
    STATE_MENU,
    STATE_SIGNUP_FIO,
    STATE_SIGNUP_PHONE,
    STATE_SIGNUP_DATE,
    STATE_SIGNUP_TIME,
    STATE_CANCEL_CONFIRM,
    STATE_CHANGE_FIO,
    STATE_CHANGE_DATE,
    STATE_CHANGE_TIME,
    STATE_NO_SHOW_REASON,
) = range(10)

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Привет, я бот для записи!\n\nВведи /start, чтобы открыть меню и записаться."
    )

async def info_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Добро пожаловать! Выберите действие:",
        reply_markup=main_menu_keyboard()
    )
    return STATE_MENU

async def menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer()
    if query.data == "sign_up":
        if user_id in appointments:
            decrypted_fio = aes_decrypt(appointments[user_id]['fio'])
            await query.message.reply_text(
                f"У вас уже есть запись ({decrypted_fio}). Сначала отмените или измените её."
            )
            await query.message.reply_text("Возвращаю вас в меню.", reply_markup=main_menu_keyboard())
            return STATE_MENU
        else:
            await query.message.reply_text("Введите ваше ФИО (минимум 2 слова):")
            return STATE_SIGNUP_FIO
    elif query.data == "cancel":
        if user_id not in appointments:
            await query.message.reply_text("У вас нет записи для отмены.")
            await query.message.reply_text("Возвращаю вас в меню.", reply_markup=main_menu_keyboard())
            return STATE_MENU
        else:
            info = appointments[user_id]
            decrypted_fio = aes_decrypt(info['fio'])
            decrypted_phone = aes_decrypt(info['phone'])
            await query.message.reply_text(
                f"Вы действительно хотите отменить запись:\n{decrypted_fio} ({decrypted_phone}) на {info['date']} {info['time']}?\nНапишите 'Да' или 'Нет'."
            )
            return STATE_CANCEL_CONFIRM
    elif query.data == "change":
        if user_id not in appointments:
            await query.message.reply_text("У вас нет записи для изменения.")
            await query.message.reply_text("Возвращаю вас в меню.", reply_markup=main_menu_keyboard())
            return STATE_MENU
        else:
            decrypted_fio = aes_decrypt(appointments[user_id]['fio'])
            await query.message.reply_text(
                f"Текущие ФИО: {decrypted_fio}\n\nВведите новые ФИО или '-' для пропуска:"
            )
            return STATE_CHANGE_FIO
    elif query.data == "view":
        if user_id not in appointments:
            await query.message.reply_text("У вас нет записи.")
        else:
            info = appointments[user_id]
            decrypted_fio = aes_decrypt(info['fio'])
            decrypted_phone = aes_decrypt(info['phone'])
            text = f"Ваша запись:\nФИО: {decrypted_fio}\nТелефон: {decrypted_phone}\nДата: {info['date']}\nВремя: {info['time']}"
            await query.message.reply_text(text)
        await query.message.reply_text("Возвращаю вас в меню.", reply_markup=main_menu_keyboard())
        return STATE_MENU
    else:
        await query.message.reply_text("Неизвестная команда. Возвращаю вас в меню.", reply_markup=main_menu_keyboard())
        return STATE_MENU

async def sign_up_fio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    fio = update.message.text.strip()
    parts = fio.split()
    if len(parts) < 2:
        await update.message.reply_text("Упс! ФИО должно содержать минимум 2 слова. Запись отменена.")
        await update.message.reply_text("Возвращаю вас в меню.", reply_markup=main_menu_keyboard())
        return STATE_MENU
    context.user_data['fio'] = fio
    await update.message.reply_text("Введите номер телефона в формате:\n+7 XXX XXX XX XX или 8 XXX XXX XX XX")
    return STATE_SIGNUP_PHONE

async def sign_up_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    phone = update.message.text.strip()
    pattern = r"^(?:\+7|8)\s?\d{3}\s?\d{3}\s?\d{2}\s?\d{2}$"
    if not re.match(pattern, phone):
        await update.message.reply_text("Неверный формат телефона! Запись отменена.")
        await update.message.reply_text("Возвращаю вас в меню.", reply_markup=main_menu_keyboard())
        return STATE_MENU
    context.user_data['phone'] = phone
    await update.message.reply_text("Введите дату (например, YYYY-MM-DD или DD.MM.YYYY):")
    return STATE_SIGNUP_DATE

async def sign_up_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    date_str = update.message.text.strip()
    parsed_date = None
    for fmt in ["%Y-%m-%d", "%d.%m.%Y"]:
        try:
            parsed_date = datetime.strptime(date_str, fmt)
            break
        except ValueError:
            pass
    if not parsed_date:
        await update.message.reply_text("Непонятный формат даты. Повторите ввод (YYYY-MM-DD или DD.MM.YYYY).")
        return STATE_SIGNUP_DATE
    today = datetime.now().date()
    if parsed_date.date() < today:
        await update.message.reply_text("Упс! Эта дата уже прошла. Запись отменена.")
        await update.message.reply_text("Возвращаю вас в меню.", reply_markup=main_menu_keyboard())
        return STATE_MENU
    normalized_date_str = parsed_date.strftime("%Y-%m-%d")
    context.user_data['date'] = normalized_date_str
    now = datetime.now()
    if parsed_date.date() == today:
        current_time = now.time()
        filtered_times = [t for t in AVAILABLE_TIMES if time(*map(int, t.split(":"))) > current_time]
    else:
        filtered_times = AVAILABLE_TIMES
    if not filtered_times:
        await update.message.reply_text("На сегодня время уже прошло, слотов нет. Запись отменена.")
        await update.message.reply_text("Возвращаю вас в меню.", reply_markup=main_menu_keyboard())
        return STATE_MENU
    keyboard = build_time_keyboard(filtered_times, busy_slots, normalized_date_str, prefix="time_")
    if not keyboard.inline_keyboard:
        await update.message.reply_text("На эту дату всё занято. Запись отменена.")
        await update.message.reply_text("Возвращаю вас в меню.", reply_markup=main_menu_keyboard())
        return STATE_MENU
    await update.message.reply_text("Выберите удобное время:", reply_markup=keyboard)
    return STATE_SIGNUP_TIME

async def sign_up_time_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """После выбора времени шифруем данные, сохраняем их в БД и планируем напоминание."""
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    time_str = query.data.split("_", 1)[1]
    fio = context.user_data['fio']
    phone = context.user_data['phone']
    date_str = context.user_data['date']

    encrypted_fio = aes_encrypt(fio)
    encrypted_phone = aes_encrypt(phone)

    appointments[user_id] = {
        "fio": encrypted_fio,
        "phone": encrypted_phone,
        "date": date_str,
        "time": time_str,
        "job_id_10min": None,
        "job_id_5min": None,
        "has_answered_reminder": False
    }
    busy_slots[(date_str, time_str)] = user_id
    fio_parts = fio.split()
    last_name = fio_parts[0]
    first_name = fio_parts[1]
    patronymic = " ".join(fio_parts[2:]) if len(fio_parts) > 2 else ""
    
    try:
        client_id = insert_client(last_name, first_name, patronymic, encrypted_phone)
        db_appointment_id = insert_appointment(client_id, date_str, time_str, encrypted_fio)
        appointments[user_id]["db_appointment_id"] = db_appointment_id
        insert_status(db_appointment_id, "pending", encrypted_phone, encrypted_fio)
    except Exception as e:
        insert_log(f"Error in sign_up_time_callback: {e}")

    moscow_tz = timezone("Europe/Moscow")
    try:
        appt_dt_naive = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
        appt_datetime = moscow_tz.localize(appt_dt_naive)
        now = datetime.now(moscow_tz)
        delta = (appt_datetime - now).total_seconds()
        logger.info(f"Time until appointment: {delta} seconds")
        if delta >= 10 * 60:
            reminder_time = appt_datetime - timedelta(minutes=10)
            logger.info(f"Scheduling reminder for user {user_id} at {reminder_time}")
            job_10min = context.job_queue.run_once(
                send_10min_reminder,
                when=reminder_time,
                chat_id=user_id,
                name=f"reminder_{user_id}"
            )
            appointments[user_id]["job_id_10min"] = job_10min.job.id
        else:
            logger.info("Not scheduling reminder: less than 10 minutes remain")
        logger.info(f"Appointment set for: {appt_datetime}")
    except ValueError as ve:
        logger.error(f"Error parsing appointment time: {ve}")
    await query.message.reply_text(
        f"Вы записаны!\nФИО: {fio}\nТелефон: {phone}\nДата: {date_str}\nВремя: {time_str}"
    )
    context.user_data.clear()
    await query.message.reply_text("Возвращаю вас в меню.", reply_markup=main_menu_keyboard())
    return STATE_MENU

REMINDER_OPTIONS_KEYBOARD = InlineKeyboardMarkup([
    [InlineKeyboardButton("Да, приду", callback_data="reminder_yes"),
     InlineKeyboardButton("Да, но опоздаю", callback_data="reminder_late")],
    [InlineKeyboardButton("Нет, не приду", callback_data="reminder_no"),
     InlineKeyboardButton("Уже здесь!", callback_data="reminder_here")],
    [InlineKeyboardButton("Выйти", callback_data="reminder_exit")]
])

async def send_10min_reminder(context: ContextTypes.DEFAULT_TYPE):
    job = context.job
    user_id = job.chat_id
    logger.info(f"send_10min_reminder triggered for user {user_id} at {datetime.now()}")
    if user_id not in appointments:
        logger.warning(f"send_10min_reminder: user {user_id} not found")
        return
    if appointments[user_id].get("has_answered_reminder"):
        logger.info(f"User {user_id} already answered reminder; skipping")
        return
    msg = await context.bot.send_message(
        chat_id=user_id,
        text=(
            "Запись скоро начнётся, вы придёте в указанное время?\n"
            "Выберите вариант:"
        ),
        reply_markup=REMINDER_OPTIONS_KEYBOARD
    )
    logger.info(f"Reminder message sent to user {user_id}")
    job_5min = context.job_queue.run_once(
        resend_reminder,
        when=timedelta(minutes=5),
        chat_id=user_id,
        name=f"reask_{user_id}",
        data={"reminder_message_id": msg.message_id},
    )
    appointments[user_id]["job_id_5min"] = job_5min.job.id

async def resend_reminder(context: ContextTypes.DEFAULT_TYPE):
    job = context.job
    user_id = job.chat_id
    logger.info(f"resend_reminder triggered for user {user_id} at {datetime.now()}")
    if user_id not in appointments:
        logger.warning(f"resend_reminder: user {user_id} not found")
        return
    if appointments[user_id].get("has_answered_reminder"):
        logger.info(f"User {user_id} answered; not resending")
        return
    await context.bot.send_message(
        chat_id=user_id,
        text=(
            "Вы не ответили на вопрос!\n"
            "Пожалуйста, ответьте, иначе менеджеру придётся позвонить для уточнения.\n"
            "Пожалейте нашего менеджера!\n\nВы придёте в указанное время?"
        ),
        reply_markup=REMINDER_OPTIONS_KEYBOARD
    )
    logger.info(f"Resend reminder message sent to user {user_id}")

async def reminder_answer_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    data = query.data
    if user_id not in appointments:
        await query.answer("У вас нет записи.")
        return
    appointments[user_id]["has_answered_reminder"] = True
    await query.answer()
    status = None
    if data == "reminder_yes":
        await query.message.reply_text("Супер! Ждём вас.")
        status = "pending"
    elif data == "reminder_late":
        await query.message.reply_text("Опаздывать плохо... Но ладно. Успейте в течение 15 минут, иначе запись будет отменена!")
        status = "pending"
    elif data == "reminder_no":
        keyboard = [
            [InlineKeyboardButton("Написать причину", callback_data="no_show_reason")],
            [InlineKeyboardButton("Выйти", callback_data="no_show_exit")]
        ]
        markup = InlineKeyboardMarkup(keyboard)
        await query.message.reply_text("Очень жаль! Укажите причину неявки:", reply_markup=markup)
        status = "cancelled"
    elif data == "reminder_here":
        await query.message.reply_text("Вау! Скорость как у гепарда!")
        status = "finished"
    elif data == "reminder_exit":
        await query.message.reply_text("Возвращаю вас в меню.", reply_markup=main_menu_keyboard())
        return STATE_MENU
    if status and "db_appointment_id" in appointments[user_id]:
        try:
            update_status(appointments[user_id]["db_appointment_id"], status, appointments[user_id]["phone"], appointments[user_id]["fio"])
            logger.info(f"Status updated for user {user_id} to {status}")
        except Exception as e:
            insert_log(f"Error updating status in reminder_answer_callback: {e}")
    return STATE_MENU

async def no_show_reason_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.message.reply_text("Напишите причину неявки (текстовым сообщением):")
    return STATE_NO_SHOW_REASON

async def no_show_exit_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.message.reply_text("Возвращаю вас в меню.", reply_markup=main_menu_keyboard())
    return STATE_MENU

async def no_show_reason_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    reason = update.message.text.strip()
    user_id = update.effective_user.id
    logger.info(f"Причина неявки от {user_id}: {reason}")
    await update.message.reply_text("Причина принята, спасибо за обратную связь.")
    await update.message.reply_text("Возвращаю вас в меню.", reply_markup=main_menu_keyboard())
    return STATE_MENU

async def cancel_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    answer = update.message.text.strip().lower()
    if answer == "да":
        if user_id in appointments:
            date_str = appointments[user_id]['date']
            time_str = appointments[user_id]['time']
            job_id_10min = appointments[user_id].get("job_id_10min")
            job_id_5min = appointments[user_id].get("job_id_5min")
            if job_id_10min:
                for j in context.job_queue.get_jobs_by_name(f"reminder_{user_id}"):
                    j.schedule_removal()
            if job_id_5min:
                for j in context.job_queue.get_jobs_by_name(f"reask_{user_id}"):
                    j.schedule_removal()
            if (date_str, time_str) in busy_slots:
                del busy_slots[(date_str, time_str)]
            del appointments[user_id]
            await update.message.reply_text("Запись отменена.")
        else:
            await update.message.reply_text("У вас нет записи.")
    else:
        await update.message.reply_text("Отмена записи не подтверждена.")
    await update.message.reply_text("Возвращаю вас в меню.", reply_markup=main_menu_keyboard())
    return STATE_MENU

async def change_fio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    new_fio = update.message.text.strip()
    if new_fio != "-":
        parts = new_fio.split()
        if len(parts) < 2:
            await update.message.reply_text("ФИО должно содержать минимум 2 слова. Изменение отменено.")
            await update.message.reply_text("Возвращаю вас в меню.", reply_markup=main_menu_keyboard())
            return STATE_MENU
        appointments[user_id]['fio'] = aes_encrypt(new_fio)
    await update.message.reply_text("Введите новую дату (или '-' для пропуска):")
    return STATE_CHANGE_DATE

async def change_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    new_date = update.message.text.strip()
    old_date = appointments[user_id]['date']
    old_time = appointments[user_id]['time']
    if new_date != "-":
        parsed_date = None
        for fmt in ["%Y-%m-%d", "%d.%m.%Y"]:
            try:
                parsed_date = datetime.strptime(new_date, fmt)
                break
            except ValueError:
                pass
        if not parsed_date:
            await update.message.reply_text("Непонятный формат даты. Изменение отменено.")
            await update.message.reply_text("Возвращаю вас в меню.", reply_markup=main_menu_keyboard())
            return STATE_MENU
        today = datetime.now().date()
        if parsed_date.date() < today:
            await update.message.reply_text("Упс! Эта дата уже прошла. Изменение отменено.")
            await update.message.reply_text("Возвращаю вас в меню.", reply_markup=main_menu_keyboard())
            return STATE_MENU
        if (old_date, old_time) in busy_slots and busy_slots[(old_date, old_time)] == user_id:
            del busy_slots[(old_date, old_time)]
        new_date_str = parsed_date.strftime("%Y-%m-%d")
        appointments[user_id]['date'] = new_date_str
    else:
        new_date_str = old_date
    job_id_10min = appointments[user_id].get("job_id_10min")
    job_id_5min = appointments[user_id].get("job_id_5min")
    if job_id_10min:
        for j in context.job_queue.get_jobs_by_name(f"reminder_{user_id}"):
            j.schedule_removal()
        appointments[user_id]["job_id_10min"] = None
    if job_id_5min:
        for j in context.job_queue.get_jobs_by_name(f"reask_{user_id}"):
            j.schedule_removal()
        appointments[user_id]["job_id_5min"] = None
    appointments[user_id]["has_answered_reminder"] = False
    parsed_new_date = datetime.strptime(new_date_str, "%Y-%m-%d")
    today_dt = datetime.now().date()
    now = datetime.now()
    if parsed_new_date.date() == today_dt:
        current_time = now.time()
        filtered_times = [t for t in AVAILABLE_TIMES if time(*map(int, t.split(":"))) > current_time]
    else:
        filtered_times = AVAILABLE_TIMES
    keyboard = build_time_keyboard(filtered_times, busy_slots, new_date_str, prefix="change_time_")
    if not keyboard.inline_keyboard:
        await update.message.reply_text("Все слоты заняты или время уже прошло. Изменение отменено.")
        await update.message.reply_text("Возвращаю вас в меню.", reply_markup=main_menu_keyboard())
        return STATE_MENU
    await update.message.reply_text("Выберите новое время:", reply_markup=keyboard)
    return STATE_CHANGE_TIME

async def change_time_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    new_time = query.data.split("_", 2)[2]
    new_date = appointments[user_id]['date']
    appointments[user_id]['time'] = new_time
    busy_slots[(new_date, new_time)] = user_id
    try:
        from pytz import timezone
        moscow_tz = timezone("Europe/Moscow")
        appt_dt_naive = datetime.strptime(f"{new_date} {new_time}", "%Y-%m-%d %H:%M")
        appt_datetime = moscow_tz.localize(appt_dt_naive)
        now = datetime.now(moscow_tz)
        delta = (appt_datetime - now).total_seconds()
        if delta >= 10 * 60:
            job_10min = context.job_queue.run_once(
                send_10min_reminder,
                when=appt_datetime - timedelta(minutes=10),
                chat_id=user_id,
                name=f"reminder_{user_id}"
            )
            appointments[user_id]["job_id_10min"] = job_10min.job.id
        else:
            appointments[user_id]["job_id_10min"] = None
    except ValueError:
        pass
    if "db_appointment_id" in appointments[user_id]:
        try:
            update_appointment(
                appointments[user_id]["db_appointment_id"],
                new_date,
                new_time,
                appointments[user_id]["fio"]
            )
            logger.info(f"Appointment updated in DB for user {user_id}")
        except Exception as e:
            insert_log(f"Error updating appointment in change_time_callback: {e}")
    await query.message.reply_text(
        f"Запись изменена:\nФИО: {aes_decrypt(appointments[user_id]['fio'])}\nТелефон: {aes_decrypt(appointments[user_id]['phone'])}\nДата: {appointments[user_id]['date']}\nВремя: {appointments[user_id]['time']}"
    )
    await query.message.reply_text("Возвращаю вас в меню.", reply_markup=main_menu_keyboard())
    return STATE_MENU
    
async def cancel_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Действие отменено. Возвращаю вас в меню.", reply_markup=main_menu_keyboard())
    return STATE_MENU

def run_java_app():
    compile_process = subprocess.run(
        [
            "javac",
            "Java/db_parser/src/main/java/ru/spbstu/telematics/java/App.java"
        ],
        capture_output=True,
        text=True
    )

    if compile_process.returncode != 0:
        print("Ошибка компиляции:")
        print(compile_process.stderr)
        return
    else:
        print("Компиляция прошла успешно.")

    run_process = subprocess.Popen(
        [
            "java",
            "-cp",
            "Java/db_parser/src/main/java",  
            "ru.spbstu.telematics.java.App"   
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    
    stdout, stderr = run_process.communicate()
    if run_process.returncode != 0:
        print("Ошибка выполнения Java-приложения:")
        print(stderr)
    else:
        print("Вывод Java-приложения:")
        print(stdout)

async def run_java_parser(context: ContextTypes.DEFAULT_TYPE):
    logger.info("Запуск Java-парсера для обновления JSON через Maven")
    compile_process = subprocess.run(
        ["mvn", "compile"],
        capture_output=True,
        text=True,
        cwd="Java/db_parser"  
    )
    if compile_process.returncode != 0:
        logger.error("Ошибка компиляции Maven:")
        logger.error(compile_process.stderr)
        return
    
    run_process = subprocess.run(
        ["mvn", "exec:java", "-Dexec.mainClass=ru.spbstu.telematics.java.App"],
        capture_output=True,
        text=True,
        cwd="Java/db_parser"
    )
    if run_process.returncode != 0:
        logger.error("Ошибка выполнения Java-парсера через Maven:")
        logger.error(run_process.stderr)
    else:
        logger.info("Парсер обновил JSON:")
        logger.info(run_process.stdout)

def main():
    from dotenv import load_dotenv
    load_dotenv("/Users/ayzek/Desktop/Ayzek/Любимка/ОПД - 2 курс/TelegrammBot/.env")
    logger.info(f"Current time: {datetime.now()}")
    TOKEN = os.getenv("TELEGRAMM_API_TOKKEN")
    if not TOKEN:
        raise ValueError("Не найден TELEGRAMM_API_TOKKEN в .env файле")
    application = Application.builder().token(TOKEN).build()
    async def test_job(ctx: ContextTypes.DEFAULT_TYPE):
        logger.info("Test job triggered")
    
    application.job_queue.run_once(test_job, when=timedelta(seconds=10))
    application.job_queue.run_repeating(run_java_parser, interval=120, first=5)
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", info_command)],
        states={
            STATE_MENU: [CallbackQueryHandler(menu_callback)],
            STATE_SIGNUP_FIO: [MessageHandler(filters.TEXT & ~filters.COMMAND, sign_up_fio)],
            STATE_SIGNUP_PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, sign_up_phone)],
            STATE_SIGNUP_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, sign_up_date)],
            STATE_SIGNUP_TIME: [CallbackQueryHandler(sign_up_time_callback, pattern=r"^time_")],
            STATE_CANCEL_CONFIRM: [MessageHandler(filters.TEXT & ~filters.COMMAND, cancel_confirm)],
            STATE_CHANGE_FIO: [MessageHandler(filters.TEXT & ~filters.COMMAND, change_fio)],
            STATE_CHANGE_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, change_date)],
            STATE_CHANGE_TIME: [CallbackQueryHandler(change_time_callback, pattern=r"^change_time_")],
            STATE_NO_SHOW_REASON: [MessageHandler(filters.TEXT & ~filters.COMMAND, no_show_reason_text)],
        },
        fallbacks=[CommandHandler("cancel", cancel_conversation)],
    )
    application.add_handler(CommandHandler("info", start_command))
    application.add_handler(CallbackQueryHandler(reminder_answer_callback, pattern=r"^reminder_"))
    application.add_handler(CallbackQueryHandler(no_show_reason_callback, pattern=r"^no_show_reason"))
    application.add_handler(CallbackQueryHandler(no_show_exit_callback, pattern=r"^no_show_exit"))
    application.add_handler(conv_handler)
    application.run_polling()

if __name__ == "__main__":
    main()
