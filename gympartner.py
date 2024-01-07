import telebot
from telebot import types
import sqlite3
import settings
db = sqlite3.connect('exercise_list.db', check_same_thread=False)
cursor = db.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS exercises (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sets TEXT, 
    exercise_name TEXT,
    telegram_user TEXT
)
""")
cursor.close() 

API_TOKEN = settings.telegrambot_api
bot = telebot.TeleBot(API_TOKEN)

states = {}

user_data = {}

def get_user_exercises(user_id):
    with sqlite3.connect('exercise_list.db', check_same_thread=False) as con:
        cur = con.cursor()
        cur.execute("SELECT exercise_name FROM exercises WHERE telegram_user = ? ORDER BY exercise_name ASC", (user_id,))
        exercises = cur.fetchall()
    return [ex[0] for ex in exercises]

def create_choice_buttons(exercise_names):
    markup = types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)  
    for name in exercise_names:
        button = types.KeyboardButton(name)
        markup.add(button)
    return markup

@bot.message_handler(commands=['add'])
def command_add(message):
    msg = bot.send_message(message.chat.id, "Введите название упражнения:")
    bot.register_next_step_handler(msg, process_exercise_step)

def process_exercise_step(message):
    try:
        chat_id = message.chat.id
        exercise_name = message.text
        user = message.from_user.id
        user_data[chat_id] = {'exercise_name': exercise_name, 'telegram_user': user}
        add_exercise_to_db(exercise_name, user)
        bot.send_message(chat_id, "Упражнение добавлено!")
    except Exception as e:
        bot.reply_to(message, 'Упс! Произошла ошибка.')

def add_exercise_to_db(exercise_name, user):
    with sqlite3.connect('exercise_list.db', check_same_thread=False) as con:
        cur = con.cursor()
        cur.execute("INSERT INTO exercises (exercise_name, telegram_user) VALUES (?, ?)", (exercise_name, user))
        con.commit()  

@bot.message_handler(commands=['read'])
def command_read(message):
    states[message.chat.id] = 'read'
    user_id = message.from_user.id
    exercises = get_user_exercises(user_id)
    if exercises:
        markup = create_choice_buttons(exercises)
        bot.send_message(message.chat.id, "Выберите упражнение для чтения:", reply_markup=markup)
    else:
        bot.send_message(message.chat.id, "У вас нет добавленных упражнений.")

def process_read_exercise(message,exercise_name, user_id):
    cursor = db.cursor()
    cursor.execute("SELECT sets FROM exercises WHERE exercise_name=? AND telegram_user = ?", (exercise_name,user_id))
    result = cursor.fetchone()
    cursor.close()
    response = f" {exercise_name}: {result[0]}"
    states[message.chat.id] = None
    bot.send_message(message.chat.id, response)

@bot.message_handler(commands=['write'])
def command_write(message):
    states[message.chat.id] = 'write'
    user_id = message.from_user.id
    exercises = get_user_exercises(user_id)
    if exercises:
        markup = create_choice_buttons(exercises)
        bot.send_message(message.chat.id, "Выберите упражнение для записи:", reply_markup=markup)
    else:
        bot.send_message(message.chat.id, "У вас нет добавленных упражнений.")

def process_exercise_name(message):
    exercise_name = message.text
    user_id = message.from_user.id
    cursor = db.cursor()
    cursor.execute("SELECT count(*) FROM exercises WHERE exercise_name = ? AND telegram_user = ?", (exercise_name, user_id)) 
    result = cursor.fetchone()
    db.commit()
    cursor.close()
    if result[0] > 0:
        msg = bot.send_message(message.chat.id, "Введите значения сета:")
        bot.register_next_step_handler(msg, lambda msg: process_set_values(msg, exercise_name, user_id))
    else: 
        states[message.chat.id] = None
        bot.send_message(message.chat.id, "Введенное упражнение не существует в вашем списке.")

def process_set_values(message, exercise_name, user_id):
    set_values = message.text
    cursor = db.cursor()
    cursor.execute("UPDATE exercises SET sets = ? WHERE exercise_name = ? AND telegram_user = ?", (set_values, exercise_name, user_id))
    db.commit()
    cursor.close()
    states[message.chat.id] = None
    bot.send_message(message.chat.id, "Значения сета успешно записаны.")

@bot.message_handler(commands=['delete'])
def command_delete(message):
    states[message.chat.id] = 'delete'
    user_id = message.from_user.id
    exercises = get_user_exercises(user_id)
    if exercises:
        markup = create_choice_buttons(exercises)
        bot.send_message(message.chat.id, "Выберите упражнение, которое вы хотите удалить:", reply_markup=markup)
    else:
        states[message.chat.id] = None
        bot.send_message(message.chat.id, "У вас нет добавленных упражнений.")

def process_delete_exercise(message,exercise_name,user_id):
    cursor = db.cursor()
    cursor.execute("SELECT count(*) FROM exercises WHERE exercise_name = ? AND telegram_user = ?", (exercise_name, user_id)) 
    result = cursor.fetchone()
    db.commit()
    cursor.close()
    if result[0] > 0:
        cursor = db.cursor()
        cursor.execute("DELETE from exercises WHERE exercise_name = ? AND telegram_user = ? ", ( exercise_name, user_id))
        db.commit()
        cursor.close()
        states[message.chat.id] = None
        bot.send_message(message.chat.id, "Упражнение успешно удалено.")
    else: 
        states[message.chat.id] = None
        bot.send_message(message.chat.id, "Введенное упражнение не существует в вашем списке.")

@bot.message_handler(func=lambda message: states.get(message.chat.id, '') in ['read', 'write', 'delete'])
def handle_keyboard_button(message):
    state = states.get(message.chat.id)
    if state == 'read':
        process_read_exercise(message, message.text, message.from_user.id)
    elif state == 'write':
        process_exercise_name(message)
    elif state == 'delete':
        process_delete_exercise(message, message.text, message.from_user.id)
    
bot.polling()
