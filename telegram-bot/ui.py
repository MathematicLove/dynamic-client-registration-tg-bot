from telegram import InlineKeyboardButton, InlineKeyboardMarkup

def main_menu_keyboard():
    buttons = [
        [InlineKeyboardButton("Записаться", callback_data="sign_up")],
        [InlineKeyboardButton("Отменить запись", callback_data="cancel")],
        [InlineKeyboardButton("Изменить запись", callback_data="change")],
        [InlineKeyboardButton("Посмотреть мою запись", callback_data="view")],
    ]
    return InlineKeyboardMarkup(buttons)

def build_time_keyboard(available_times, busy_slots, date_str, prefix="time_"):
    keyboard = []
    row = []
    for t in available_times:
        if (date_str, t) in busy_slots:
            continue
        row.append(InlineKeyboardButton(t, callback_data=f"{prefix}{t}"))
        if len(row) == 4:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    return InlineKeyboardMarkup(keyboard)
