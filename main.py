import os
from dotenv import load_dotenv, find_dotenv
from PIL import Image
import pytesseract
from deep_translator import GoogleTranslator
import re
from typing import Final
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update, CallbackQuery
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, MessageHandler, filters, ContextTypes
from jisho_api.kanji import Kanji
import json 
from pymongo import MongoClient
import random

pytesseract.pytesseract.tesseract_cmd = r'C:\\Program Files\\tesseract\\tesseract.exe'

print('Starting up bot...')

load_dotenv(find_dotenv())

password = os.environ.get('MONGODB_PWD')

connection_string = f"mongodb+srv://Oleksa:{password}@cluster0.bjdsloy.mongodb.net/?retryWrites=true&w=majority"
client = MongoClient(connection_string)

dbs = client.list_database_names()
accounts_db = client.Translations
collections = accounts_db.list_collection_names()
acc_collection = accounts_db.Translations

TOKEN: Final = os.environ.get('BOT_TOKEN')

def insert_into_doc(user_data_doc, update:Update):
    collection = accounts_db.Translations
    inserted_id = collection.insert_one(user_data_doc).inserted_id

async def start_command(update: Update, context:ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Вітаю!\nУсю інформацію щодо користування ви зможете знайти за командою /help\nБажаємо приємного користування!")

def value(variable):
    if variable is None:
        return " "
    else:
        return variable
    
def is_a_valid_symbol(a:str):
    a = a.strip()
    if not a.isnumeric():
        if not (a == ""):
            return True
        else:
            return False
    else:
            return False
    
async def kanji_meaning(symbol: str, query: CallbackQuery, update:Update):
    await query.message.reply_text("Запит виконується, зачекайте")
    response = Kanji.request(symbol).json()
    response_json = json.loads(response)
    kanji = value(response_json["data"]["kanji"])
    main_meanings = value(response_json["data"]["main_meanings"])
    main_readings_kun = value(response_json["data"]["main_readings"]["kun"])
    main_readings_on = value(response_json["data"]["main_readings"]["on"])
    
    ex_readings_kun = value(response_json["data"]["reading_examples"]["kun"])
    ex_readings_kun_m = ""
    for i in range(len(ex_readings_kun)):
        ex_readings_kun_m = ex_readings_kun_m + "\n\nДля " + ex_readings_kun[i]["kanji"] + " 「" + ex_readings_kun[i]["reading"] + "」(кун) є такі значення:"
        for m in ex_readings_kun[i]["meanings"]:
            if is_a_valid_symbol(m):
                m = GoogleTranslator(source='en', target='uk').translate(m)
            #t = GoogleTranslator(source='en', target='uk').translate(m)
            ex_readings_kun_m = ex_readings_kun_m + "\n" + m
    ex_readings_on = value(response_json["data"]["reading_examples"]["on"])
    ex_readings_on_m = ""
    for i in range(len(ex_readings_on)):
        ex_readings_on_m = ex_readings_on_m + "\n\nДля " + ex_readings_on[i]["kanji"] + " 「" + ex_readings_on[i]["reading"] + "」(он) є такі значення:"
        for m in ex_readings_on[i]["meanings"]:
            if is_a_valid_symbol(m):
                m = GoogleTranslator(source='en', target='uk').translate(m)
            #t = GoogleTranslator(source='en', target='uk').translate(m)
            ex_readings_on_m = ex_readings_on_m + "\n" + m

    main_meanings_reply = ""
    main_readings_kun_reply = ""
    main_readings_on_reply = ""
    tr_meanings = []
    for i in main_meanings:
        if is_a_valid_symbol(m):
            i = GoogleTranslator(source='en', target='uk').translate(i)
        tr_meanings.append(i)
        main_meanings_reply = main_meanings_reply + "\n" + i
    for i in main_readings_kun:
        main_readings_kun_reply = main_readings_kun_reply + "\n" + i
    for i in main_readings_on:
        main_readings_on_reply = main_readings_on_reply + "\n" + i
    kanji_data = {
        "kanji" : kanji,
        "main meanings" : tr_meanings,
        "user": query.from_user.id
    }
    insert_into_doc(kanji_data, update)
    await query.message.reply_text("Канджі:\n" + kanji + "\n\nОсновні значення:" + main_meanings_reply + "\n\nОсновні кун читання:" + main_readings_kun_reply + "\n\nОсновні он читання:" + main_readings_on_reply + ex_readings_kun_m +  ex_readings_on_m)

async def translate_command(update: Update, context:ContextTypes.DEFAULT_TYPE):
    results = list(find_words(update))
    if not results:
        await update.message.reply_text("Не знайдено жодних вивчених слів, за допомогою зверніться до команди /help")
        return
    n = len(results)
    if n<4:
        await update.message.reply_text("Виявлена недостатня кількість слів, будь ласка, додайте хоча б 4 слова до вашого спику\nЯкщо виникають проблеми зверніться до /help")
        return
    right = random.randint(0, n-1)
    question = "Оберіть значення " + results[right]["kanji"]
    correct_options = results[right]["main meanings"]
    n2 = len(correct_options)
    cor_op_id = random.randint(0, n2-1)
    correct_option = correct_options[cor_op_id]
    all_options = []
    for a in results:
        for b in a["main meanings"]:
            all_options.append(b)
    n1 = len(all_options)
    options = []
    for i in range(3):
        option_id = random.randint(0, n1-1)
        option = all_options[option_id]
        options.append(option)
    correct_id = random.randint(0, 3)
    options.insert(correct_id, correct_option)
    print(f"Correct option: {correct_option}")
    await update.message.reply_poll(type="quiz", question=question, options=options, correct_option_id=correct_id)

def find_words(update: Update):
    id = update.message.from_user.id
    results = acc_collection.find({"user":id})
    return results

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    if query.data.startswith('Vertical') or query.data.startswith('Horizontal'):
        await recognise(update, context, query.data)
    else:
        await kanji_meaning(query.data, query, update)

async def error(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print(f'Update {update} caused error {context.error}')

async def downloader(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Download file
    new_file = await update.message.effective_attachment[-1].get_file()
    file = await new_file.download_to_drive()
    return file

def is_kanji(character):
    kanji_range = (0x4E00, 0x9FBF)  # Unicode range for kanji characters
    character_code = ord(character)
    return kanji_range[0] <= character_code <= kanji_range[1]

def chunks(lst, n):
    for i in range(0, len(lst), n):
        yield lst[i:i + n]

async def recognise(update: Update, context: ContextTypes.DEFAULT_TYPE, mode:str):
    s=mode.split(",,")
    type=s[0]
    file=s[1]
    image = Image.open(file)
    #_vert --oem 1
    
    if type=="Vertical":
        text = pytesseract.image_to_string(image, config='-l jpn_vert --oem 1 --psm 1')
    else:
        text = pytesseract.image_to_string(image, config='-l jpn --oem 1 --psm 1')
    if not text:
        await update.callback_query.message.reply_text("Щось пішло не так, спробуйте ще раз")
        return
    new_text = re.sub(r"[\n\r]+", " ", text).strip()
    translated_text = GoogleTranslator(source='ja', target='uk').translate(new_text)
    kanji_list = []
    for i in new_text:
        if is_kanji(i):
            kanji_list.append(i)
    no_dupes_kanji = []
    for i in kanji_list:
        if i not in no_dupes_kanji:
            no_dupes_kanji.append(i)
    new_kanji_list = list(chunks(no_dupes_kanji, 8))
    keyboard = []
    for a in new_kanji_list:
        temp_list = []
        for b in a:
            temp_list.append(InlineKeyboardButton(b, callback_data=b))
        keyboard.append(temp_list)
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.callback_query.message.reply_text(new_text, reply_markup=reply_markup)
    await update.callback_query.message.reply_text(translated_text)


async def translate_msg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if (
            not update.message
            or not update.effective_chat
            or (
                not update.message.photo
                and not update.message.video
                and not update.message.document
                and not update.message.sticker
                and not update.message.animation
            )
        ):
            return
    file = await downloader(update, context)
    if not file:
        await update.message.reply_text("щось пішло не так, спробуйте ще раз")
        return
    
    vert_b=[]
    vert_b.append(InlineKeyboardButton("Вертикальний", callback_data="Vertical"+ ",,"+ str(file)))
    vert_b.append(InlineKeyboardButton("Горизонтальний", callback_data="Horizontal"+ ",,"+ str(file)))
    vert_k=[]
    vert_k.append(vert_b)
    vert_r=InlineKeyboardMarkup(vert_k)
    await update.message.reply_text("Текст на зображенні вертикальний чи горизонтальний?",reply_markup=vert_r) 

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Вітаю!\nЩоб перекласти текст з зображення надішліть зображення з текстом японською і отримаєте переклад тексту, а також усі канджі наявні у ньому у вигляді кнопок.\nПри використанні команди /quiz можна протестувати ваші знання канджі, значення яких ви дізнавались за кнопками.\nЯкщо при виклику команди /quiz не було виявлено слів, ви можете їх додати шляхом надсилання зображення та натискання кнопок, що будуть відображені")

if __name__ == '__main__':
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler('start', start_command))
    app.add_handler(CommandHandler('quiz', translate_command))
    app.add_handler(CommandHandler('help', help_command))

    app.add_handler(MessageHandler(filters.PHOTO, translate_msg))

    app.add_handler(CallbackQueryHandler(button))

    app.add_error_handler(error)

    print("polling")
    app.run_polling(poll_interval=3)
