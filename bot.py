from telegram import Update, Bot, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
import os
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, time, timedelta
import pytz
import logging
logging.basicConfig(level=logging.INFO)
import asyncio
from flask import Flask, request

TOKEN = os.getenv('TOKEN')
application = Application.builder().token(TOKEN).concurrent_updates(4).build()
bot =application.bot

# Google Sheets setup
GOOGLE_CREDS = {
  "type": "service_account",
  "project_id": os.getenv('PROJECT_ID'),
  "private_key_id": os.getenv('PRIVATE_KEY_ID'),
  "private_key": os.getenv('PRIVATE_KEY').replace('\\n', '\n'),
  "client_email": os.getenv('CLIENT_EMAIL'),
  "client_id": os.getenv('CLIENT_ID'),
  "auth_uri": "https://accounts.google.com/o/oauth2/auth",
  "token_uri": "https://oauth2.googleapis.com/token",
  "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
  "client_x509_cert_url": os.getenv('CLIENT_CERT_URL')
}

# Inizializza Google Sheets
scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
creds = ServiceAccountCredentials.from_json_keyfile_dict(GOOGLE_CREDS, scope)
gc = gspread.authorize(creds)
sh = gc.open_by_key(os.environ.get('SHEET_ID'))

# Inizializza Flask
app = Flask(__name__)

# Lista degli utenti registrati
saved_chat_ids = [637735039]
saved_chat_ids2 = [1832764914, 5201631829, 700212414]

# Mappa degli ID e i fogli corrispondenti
sheet_map = {
    637735039: 2,
    1832764914: 1,  # Foglio 2
    #5201631829: 2,  # Foglio 3
    700212414: 3    # Foglio 4
}

# Domande del quiz
DOMANDE = [
    "Quanti drum/sigarette hai fumato oggi?",
    "Quante terea/heets hai fumato oggi?",
    "Quante canne hai fumato oggi?"
]

# Stato degli utenti
user_states = {}
# Lista degli utenti che non hanno completato il quiz
users_mancanti = {}
# Dizionario per tenere traccia degli utenti che hanno completato il quiz
quiz_completati = {}

async def save_to_sheet(chat_id, risposta, domanda_num):
	worksheet = await asyncio.to_thread(sh.get_worksheet, 0)
	timestamp = (datetime.now() - timedelta(hours=18)).strftime("%Y-%m-%d")
	row = [str(chat_id), domanda_num, risposta, timestamp]
	await asyncio.to_thread(worksheet.append_row, row)

async def send_question(context: ContextTypes.DEFAULT_TYPE, chat_id, question_num):
    """
    Manda una domanda all'utente.
    """
    if question_num < len(DOMANDE):
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"{question_num + 1}️⃣ {DOMANDE[question_num]}"
        )
        user_states[chat_id] = question_num + 1  # Aggiorna la domanda corrente per l'utente
    else:
        await context.bot.send_message(chat_id=chat_id, text="🎉 Quiz completato! Ci rivediamo domani.")
        # Aggiungi l'utente al dizionario dei quiz completati
        quiz_completati[chat_id] = True
        del user_states[chat_id]  # Rimuove lo stato dell'utente una volta completato il quiz

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if not is_authorized(chat_id):
         await update.message.reply_text("⛔ Non sei autorizzato ad usare questo bot!")
         return
    # Se l'utente è autorizzato:
    await update.message.reply_text("Sei già registrato! Usa il comando /quiz per iniziare il quiz.")
    
async def quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Permette di testare manualmente il quiz inviando le domande una alla volta.
    """
    chat_id = update.message.chat_id
    if not is_authorized(chat_id):
         await update.message.reply_text("⛔ Non sei autorizzato ad usare questo bot!")
         return
    user_states[chat_id] = 0
    await send_question(context, chat_id, 0)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Gestisce le risposte alle domande.
    """
    chat_id = update.message.chat_id
    if not is_authorized(chat_id):
         await update.message.reply_text("⛔ Non sei autorizzato ad usare questo bot!")
         return
    text = update.message.text.strip()
    
    if chat_id not in user_states:
        await update.message.reply_text("📝 Il quiz è terminato, se vuoi compilare in anticipo quello di oggi usa il comando /quiz.")
        return

    # Verifica che l'utente stia partecipando al quiz e che la risposta sia valida
    if not text.isdigit():
        await update.message.reply_text("⚠️ Risposta non valida! Invia solo numeri.")
        return
    if text == "0":
        if chat_id == 700212414:
            await update.message.reply_text("Bravo! 🥳")
        else: 
            await update.message.reply_text("Brava! 🥳")

    if chat_id in users_mancanti:
        # Se l'utente ha risposto, lo rimuovi dalla lista
        users_mancanti[chat_id] = False
        del users_mancanti[chat_id]
        
    current_question = user_states[chat_id] - 1
    await save_to_sheet(chat_id, text, current_question + 1)
    
    # Manda la prossima domanda o completa il quiz
    if current_question < len(DOMANDE) - 1:
        await send_question(context, chat_id, current_question + 1)
    else:
        await update.message.reply_text("🎉 Quiz completato! Risposte salvate.")
        
        obiettivi = get_obiettivi(chat_id, tipo="settimanale")
        calcolo_weekgoal(chat_id)
        oggi = datetime.now() - timedelta(hours=18)
        if oggi.weekday() == 6:
            if obiettivi is None:
                await update.message.reply_text("⚠️ Errore nel recuperare gli obiettivi.")
                obj = f"⚠️ C'è stato un errore con gli obiettivi settimanali! Contattare il grande capo"
            else:
                if obiettivi[3]==1:
                    obj = f"😄 Grande!!!\nHai raggiunto gli obiettivi settimanali! 🎯✅"
                    await context.bot.send_message(chat_id=chat_id, text=obj, parse_mode="Markdown")
                else: 
                    obj = f"😔 Nooo peccato!\nNon hai raggiunto gli obiettivi settimanali 🎯❌\nDa adesso concentrati su quelli della prossima settimana, so che puoi farcela! 💪"
                    await context.bot.send_message(chat_id=chat_id, text=obj, parse_mode="Markdown")

        # Aggiungi l'utente al dizionario dei quiz completati
        quiz_completati[chat_id] = True

        if chat_id in users_mancanti:
            users_mancanti[chat_id] = False

        obiettivi = get_obiettivi(chat_id, tipo="giornaliero")
        if obiettivi is None:
            await update.message.reply_text("⚠️ Errore nel recuperare gli obiettivi.")
            obj = f"⚠️ C'è stato un errore con gli obiettivi giornalieri! Contattare il grande capo"
            return
        
        if obiettivi[3]==1:
            obj = f"😊 Hai raggiunto gli obiettivi di oggi! 🎯✅"
        else: obj = f"😔 Non hai raggiunto gli obiettivi di oggi 🎯❌"

        oggi_zero = today_zero(chat_id)
        if oggi_zero is not None:
            if oggi_zero == 0:
                if chat_id == 700212414:
                    msg = f"Ammazza oh! Oggi sei andato da dio!🔥"
                else: 
                    msg = f"Ammazza oh! Oggi sei andata da dio!🔥"
            
            else:
                improvement_status = get_improvement_status(chat_id)
                if improvement_status == 404:
                    await update.message.reply_text("⚠️ Impossibile verificare il tuo progresso perchè ieri non hai inserito i dati")
                else:
                    if improvement_status < -4:
                        if chat_id == 700212414:
                            msg = f"Grandissimo! Oggi ne hai fumate {abs(improvement_status)} in meno di ieri, dai eh nun mullà! 💪"
                        else: 
                            msg = f"Grandissima! Oggi ne hai fumate {abs(improvement_status)} in meno di ieri, dai eh nun mullà! 💪"
                    elif improvement_status < 0:
                        if chat_id == 700212414:
                            msg = f"Bravo oggi ne hai fumate {abs(improvement_status)} in meno di ieri, continua così! 💪"
                        else: 
                            msg = f"Brava oggi ne hai fumate {abs(improvement_status)} in meno di ieri, continua così! 💪"
                    elif improvement_status > 9:
                        msg = f"Ella madò! Oggi ci hai dato dentro eh?! Ne hai fumate {abs(improvement_status)} in più di ieri, ricorda l'obiettivo! 💪"
                    elif improvement_status > 4:
                        msg = f"Ma porca di quella... oggi ne hai fumate {abs(improvement_status)} in più di ieri, so che puoi fare di meglio! 💪"    
                    elif improvement_status > 0:
                        msg = f"Vabbè dai, oggi {abs(improvement_status)} in più di ieri, daje eh domani 💪"
                    else:
                        msg = "Oggi ne hai fumate quante ieri. ⚖️"
            await update.message.reply_text(msg)
            await update.message.reply_text(obj)
            
        else:
            await update.message.reply_text("⚠️ Impossibile verificare i dati di oggi")    

        buttons = [
            ("📈 Mostra il grafico", "/grafico"),
            ("💸 Soldi spesi in totale", "/soldi_spesi"),
            ("📊 Medie", "/medie"),
            ("🎯 Obiettivi", "/obiettivi"),
            ("🗓️ Questa settimana", "/settimana_corrente")]
        
        reply_markup = create_keyboard(buttons)
        
        # Invia il bottone per visualizzare il grafico, i soldi spesi, le medie o gli obiettivi
        await update.message.reply_text(
            text="Usa questi pulsanti per le funzioni aggiuntive",
            reply_markup=reply_markup
        )
        
async def handle_button_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()  # Rispondi al clic del pulsante
    chat_id = query.message.chat.id

    if not is_authorized(chat_id):
         await context.bot.send_message(chat_id=chat_id, text="⛔ Non sei autorizzato ad usare questo bot!")
         return
        
    if query.data == '/quiz':  # Se è il pulsante per iniziare il quiz
        user_states[chat_id] = 0
        await send_question(context, chat_id, 0)
    elif query.data == '/soldi_spesi':  # Se è il pulsante per vedere i soldi spesi
        soldi_spesi = get_soldi_spesi(chat_id)
        if soldi_spesi:
            await context.bot.send_message(chat_id=chat_id, text=f"💸 In tutto hai speso: {soldi_spesi}€")
        else:
            await context.bot.send_message(chat_id=chat_id, text="⚠️ Non ho trovato il tuo totale speso.")
    elif query.data == '/medie':  # Aggiunto nuovo tasto per le medie
        daymean = get_medie(chat_id, tipo="giornaliero")
        weekmean = get_medie(chat_id, tipo="settimanale")

        if daymean and weekmean:
            msg = (f"📊 *Medie giornaliere:*\n"
                   f"🚬 Drum/Sigarette: {daymean[0]}\n"
                   f"💨 Terea/Heets: {daymean[1]}\n"
                   f"🍁 Canne: {daymean[2]}\n\n"
                   f"📊 *Medie settimanali:*\n"
                   f"🚬 Drum/Sigarette: {weekmean[0]}\n"
                   f"💨 Terea/Heets: {weekmean[1]}\n"
                   f"🍁 Canne: {weekmean[2]}")
            
            await context.bot.send_message(chat_id=chat_id, text=msg, parse_mode="Markdown")
        else:
            await context.bot.send_message(chat_id=chat_id, text="⚠️ Non ho trovato le tue medie.")
    elif query.data == '/obiettivi':  # Aggiunto nuovo tasto per gli obiettivi
        buttons = [
            ("🎯 Giornaliero", "/obiettivi_gior"),
            ("🎯 Settimanale", "/obiettivi_sett")]
        reply_markup = create_keyboard(buttons)
        
        await context.bot.send_message(chat_id=chat_id, text="Quali obiettivi vuoi vedere?", reply_markup=reply_markup)

    elif query.data == '/obiettivi_gior':
        daygoal = get_obiettivi(chat_id, tipo="giornaliero")
        if daygoal:
            msg = ( f"🎯 *Obiettivi per domani:*\n"
                    f"🚬 Drum/Sigarette: {daygoal[0]}\n"
                    f"💨 Terea/Heets: {daygoal[1]}\n"
                    f"🍁 Canne: {daygoal[2]}")
            await context.bot.send_message(chat_id=chat_id, text=msg, parse_mode="Markdown")
        else:
            await context.bot.send_message(chat_id=chat_id, text="⚠️ Non ho trovato i tuoi obiettivi giornalieri.")

    elif query.data == '/obiettivi_sett':
        weekgoal = get_obiettivi(chat_id, tipo="settimanale")
        if weekgoal:
            msg = ( f"🎯 *Obiettivi per questa settimana:*\n"
                    f"🚬 Drum/Sigarette: {weekgoal[0]}\n"
                    f"💨 Terea/Heets: {weekgoal[1]}\n"
                    f"🍁 Canne: {weekgoal[2]}")
            await context.bot.send_message(chat_id=chat_id, text=msg, parse_mode="Markdown")
        else:
            await context.bot.send_message(chat_id=chat_id, text="⚠️ Non ho trovato i tuoi obiettivi settimanali.")

    elif query.data == '/grafico':  # Se l'utente preme "Grafico"
        daychart_url = get_grafico_url(chat_id, tipo="giornaliero")
        weekchart_url = get_grafico_url(chat_id, tipo="settimanale") 
        keyboard = [
            [InlineKeyboardButton("📈 Giornaliero", url=daychart_url)],
            [InlineKeyboardButton("📈 Settimanale", url=weekchart_url)]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await context.bot.send_message(chat_id=chat_id, text="Quale grafico vuoi vedere?", reply_markup=reply_markup)
    
    elif query.data == '/settimana_corrente':  # Aggiunto nuovo tasto per le medie
        settimana = get_settimana_corrente(chat_id)
        weekgoal = get_obiettivi(chat_id, tipo="settimanale")
        if settimana and weekgoal:
            categorie = ["🚬 Drum/Sigarette", "💨 Terea/Heets", "🍁 Canne"]
            colori = ["🟢", "🟡", "🔴"]
            msg = "🗓️ *Fumato questa settimana:*\n"
            for i in range(3):
                stato = colori[0] if (settimana[i] == 0 or settimana[i] < weekgoal[i]) else colori[1] if settimana[i] == weekgoal[i] else colori[2]
                msg += f"{categorie[i]}: {settimana[i]}*/{weekgoal[i]}*  {stato}\n"
            await context.bot.send_message(chat_id=chat_id, text=msg, parse_mode="Markdown")
        else:
            await context.bot.send_message(chat_id=chat_id, text="⚠️ Non ho trovato i tuoi dati di questa settimana.")

async def inizia_quiz_automatico(context: ContextTypes.DEFAULT_TYPE):
    """
    Funzione che viene chiamata automaticamente ogni giorno a mezzanotte
    """
    for chat_id in saved_chat_ids:
        if chat_id in quiz_completati and quiz_completati[chat_id]:
            continue  # Salta l'utente se ha già completato il quiz
        try:
            # Crea un bottone inline per il comando /quiz
            button = [("📝 Inizia il quiz", "/quiz")]
            reply_markup = create_keyboard(button)
            # Invia il messaggio con il pulsante inline
            await context.bot.send_message(
                chat_id=chat_id,
                text="⏰ È il momento del quiz giornaliero!",
                reply_markup=reply_markup
            )
            users_mancanti[chat_id] = True  # True significa "non ha ancora risposto"
        except Exception as e:
            print(f"Errore nell'inviare il messaggio al chat_id {chat_id}: {e}")

async def invia_promemoria_mattina(context: ContextTypes.DEFAULT_TYPE):
    #Funzione per inviare il promemoria la mattina agli utenti che non hanno completato il quiz.
    
    for chat_id in list(users_mancanti.keys()):
        if users_mancanti[chat_id] and (chat_id not in quiz_completati or not quiz_completati[chat_id]):
            try:
                # Crea un bottone inline per il comando /quiz
                button = [("📝 Inizia il quiz", "/quiz")]
                reply_markup = create_keyboard(button)
                # Invia il messaggio con il pulsante inline
                await context.bot.send_message(
                    chat_id=chat_id,
                    text="🌞 Hey Buongiorno!\nNon hai completato il quiz, vuoi farlo ora?",
                    reply_markup=reply_markup
                )
            except Exception as e:
                print(f"Errore nell'inviare il messaggio al chat_id {chat_id}: {e}")

async def reset_quiz_completati(context: ContextTypes.DEFAULT_TYPE):
    """
    Resetta il dizionario dei quiz completati ogni giorno a mezzanotte.
    """
    global quiz_completati
    quiz_completati = {}

def create_keyboard(buttons):
    #Crea una tastiera inline con i pulsanti specificati.
    keyboard = [[InlineKeyboardButton(text, callback_data=data)] for text, data in buttons]
    return InlineKeyboardMarkup(keyboard)

def get_grafico_url(chat_id, tipo):
    grafici = {
        1832764914: {
            "giornaliero": "https://docs.google.com/spreadsheets/d/e/2PACX-1vTZnK4kFwfA4EONo5mKHz32uk2QS0OHzgW6suVPz2EwgHnaWilA9z07NRJ_gmjZD83ri89NpaZtDIIv/pubchart?oid=1293144718&format=image",
            "settimanale": "https://docs.google.com/spreadsheets/d/e/2PACX-1vTZnK4kFwfA4EONo5mKHz32uk2QS0OHzgW6suVPz2EwgHnaWilA9z07NRJ_gmjZD83ri89NpaZtDIIv/pubchart?oid=1154554874&format=image"
        },
        5201631829: {
            "giornaliero": "https://docs.google.com/spreadsheets/d/e/2PACX-1vTZnK4kFwfA4EONo5mKHz32uk2QS0OHzgW6suVPz2EwgHnaWilA9z07NRJ_gmjZD83ri89NpaZtDIIv/pubchart?oid=36108840&format=image",
            "settimanale": "https://docs.google.com/spreadsheets/d/e/2PACX-1vTZnK4kFwfA4EONo5mKHz32uk2QS0OHzgW6suVPz2EwgHnaWilA9z07NRJ_gmjZD83ri89NpaZtDIIv/pubchart?oid=1306110414&format=image"
        },
        700212414: {
            "giornaliero": "https://docs.google.com/spreadsheets/d/e/2PACX-1vTZnK4kFwfA4EONo5mKHz32uk2QS0OHzgW6suVPz2EwgHnaWilA9z07NRJ_gmjZD83ri89NpaZtDIIv/pubchart?oid=937722899&format=image",
            "settimanale": "https://docs.google.com/spreadsheets/d/e/2PACX-1vTZnK4kFwfA4EONo5mKHz32uk2QS0OHzgW6suVPz2EwgHnaWilA9z07NRJ_gmjZD83ri89NpaZtDIIv/pubchart?oid=1136748667&format=image"
        }
    }
    
    return grafici.get(chat_id, {}).get(tipo, "⚠️ Non ho trovato il grafico richiesto.")
           
def get_soldi_spesi(chat_id):
    
    # Verifica se l'ID dell'utente è nella mappa
    if chat_id not in sheet_map:
        return None  # Se l'ID non è trovato, ritorna None

    # Ottieni il numero del foglio in base all'ID
    sheet_number = sheet_map[chat_id]
    worksheet = sh.get_worksheet(sheet_number)  # Ottieni il foglio corrispondente

    # Recupera il valore dalla cella W5
    soldi_spesi = worksheet.cell(3, 24).value  # La cella X3 è nella riga 3, colonna 24
    soldi_spesi = soldi_spesi.replace("€", "").strip()
    return soldi_spesi

def get_improvement_status(chat_id):

    if chat_id not in sheet_map:
        return None

    # Ottieni il foglio corrispondente
    worksheet = sh.get_worksheet(sheet_map[chat_id])
    
    # Leggi la cella W5 (modifica questo riferimento se cambia posizione nello sheet)
    status_cell = int(worksheet.cell(6, 24).value) # X6 = riga 6, colonna 24
    return status_cell

def today_zero(chat_id):

    if chat_id not in sheet_map:
        return None

    # Ottieni il foglio corrispondente
    worksheet = sh.get_worksheet(sheet_map[chat_id])
    
    # Leggi la cella W5 (modifica questo riferimento se cambia posizione nello sheet)
    status_cell = int(worksheet.cell(9, 24).value)  # X9 = riga 9, colonna 24
    return status_cell

def get_medie(chat_id, tipo):
    
    if chat_id not in sheet_map:
        return None

    # Ottieni il foglio corrispondente
    worksheet = sh.get_worksheet(sheet_map[chat_id])
    if tipo == "giornaliero":
        try:
            # Recupera i valori delle tre medie dalle celle Z2, Z3, Z4 (colonna 26)
            daymean_1 = worksheet.cell(3, 26).value  # Z3
            daymean_2 = worksheet.cell(6, 26).value  # Z6
            daymean_3 = worksheet.cell(9, 26).value  # Z9

            return daymean_1, daymean_2, daymean_3
        except Exception as e:
            print(f"Errore nel recuperare le medie per {chat_id}: {e}")
            return None
    
    elif tipo == "settimanale":
        try:
            # Recupera i valori delle tre medie settimanali dalle celle Z5, Z6, Z7 (colonna 26)
            weekmean_1 = worksheet.cell(23, 26).value  # Z12
            weekmean_2 = worksheet.cell(26, 26).value  # Z15
            weekmean_3 = worksheet.cell(29, 26).value  # Z18

            return weekmean_1, weekmean_2, weekmean_3
        except Exception as e:
            print(f"Errore nel recuperare le medie settimanali per {chat_id}: {e}")
            return None
        
def get_obiettivi(chat_id,tipo):
    
    if chat_id not in sheet_map:
        return None
    
    if tipo not in ["giornaliero", "settimanale"]:
        return None

    # Ottieni il foglio corrispondente
    worksheet = sh.get_worksheet(sheet_map[chat_id])
    if tipo == "giornaliero":
        try:
            # Recupera i valori dei tre obiettivi dalle celle Z13, Z16, Z19 (colonna 26)
            obiettivo_1 = int(worksheet.cell(13, 26).value)  # Z13
            obiettivo_2 = int(worksheet.cell(16, 26).value)  # Z16
            obiettivo_3 = int(worksheet.cell(19, 26).value)  # Z19

            # Vede se l'obiettivo è stato raggiunto
            goal_reached = int(worksheet.cell(12, 24).value) #X12

            return obiettivo_1, obiettivo_2, obiettivo_3, goal_reached
        except Exception as e:
            print(f"Errore nel recuperare gli obiettivi per {chat_id}: {e}")
            return None
    else:
        try:
            # Recupera i valori dei tre obiettivi dalle celle X16, X19, X22 (colonna 24)
            obiettivo_1 = int(worksheet.cell(16, 24).value)  # X16
            obiettivo_2 = int(worksheet.cell(19, 24).value)  # X19
            obiettivo_3 = int(worksheet.cell(22, 24).value)  # X22

            # Vede se l'obiettivo è stato raggiunto
            goal_reached = int(worksheet.cell(25, 24).value) #X25

            return obiettivo_1, obiettivo_2, obiettivo_3, goal_reached
        except Exception as e:
            print(f"Errore nel recuperare gli obiettivi per {chat_id}: {e}")
            return None

def calcolo_weekgoal(chat_id):
    if chat_id not in sheet_map:
        return None

    # Ottieni il foglio corrispondente
    worksheet = sh.get_worksheet(sheet_map[chat_id])

    try:
        # Recupera i valori dei tre obiettivi dalle celle Z33, Z36, Z39 (colonna 26)
        obiettivo_1 = int(worksheet.cell(33, 26).value)  # Z33
        obiettivo_2 = int(worksheet.cell(36, 26).value)  # Z36
        obiettivo_3 = int(worksheet.cell(39, 26).value)  # Z39

        worksheet.update_acell("X16", obiettivo_1)
        worksheet.update_acell("X19", obiettivo_2)
        worksheet.update_acell("X22", obiettivo_3)
        
        return

    except Exception as e:
        print(f"Errore nel recuperare gli obiettivi per {chat_id}: {e}")
        return None

def get_settimana_corrente(chat_id):
    if chat_id not in sheet_map:
        return None

    # Ottieni il foglio corrispondente
    worksheet = sh.get_worksheet(sheet_map[chat_id])

    try:
        # Recupera i valori dei tre obiettivi dalle celle X29, X32, X35 (colonna 24)
        obiettivo_1 = int(worksheet.cell(29, 24).value)  # X29
        obiettivo_2 = int(worksheet.cell(32, 24).value)  # X32
        obiettivo_3 = int(worksheet.cell(35, 24).value)  # X35
        
        return obiettivo_1, obiettivo_2, obiettivo_3

    except Exception as e:
        print(f"Errore nel recuperare i dati di questa settimana per {chat_id}: {e}")
        return None

def setup_job_queue(application: Application):
    """
    Configura il job schedulato per mezzanotte
    """
    job_queue = application.job_queue
    
    # Imposta il fuso orario (es. Europe/Rome per l'Italia)
    timezone = pytz.timezone("Europe/Rome")
    
    # Impostazione per il promemoria della mattina (10:00 AM)
    target_time_mattina = timezone.localize(datetime.combine(datetime.now(), time(10, 0)))
    utc_time_mattina = target_time_mattina.astimezone(pytz.utc).timetz()
    
    # Impostiamo il job per inviare il promemoria ogni giorno alle 10:00
    job_queue.run_daily(invia_promemoria_mattina, utc_time_mattina)
    
    target_time = timezone.localize(datetime.combine(datetime.now(), time(0, 0)))
    # Converti in UTC
    utc_time = target_time.astimezone(pytz.utc).timetz()
    # Programma il job per le 00:00 ogni giorno
    job_queue.run_daily(inizia_quiz_automatico, utc_time)
    job_queue.run_daily(reset_quiz_completati, utc_time)

def is_authorized(chat_id):
    return chat_id in saved_chat_ids  # oppure usa una lista dedicata, ad es. allowed_chat_ids


    # Handlers
application.add_handler(CommandHandler("start", start))
application.add_handler(CommandHandler("quiz", quiz))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
application.add_handler(CallbackQueryHandler(handle_button_click))

setup_job_queue(application)

@app.route('/')
def home():
    return "Il bot è attivo!"

@app.route('/webhook', methods=['POST'])
def webhook():
    """
    Gestisce le richieste in arrivo da Telegram.
    """
    if request.method == 'POST':
        update = Update.de_json(request.get_json(force=True), bot)
        application.process_update(update)
        return 'ok', 200
    return 'Method Not Allowed', 405

# Funzione asincrona per impostare il webhook
async def set_webhook_async():
    WEBHOOK_URL = "https://bot-telegram-no-fumo.up.railway.app/webhook"
    await application.bot.set_webhook(url=WEBHOOK_URL)
    logger.info(f"Webhook impostato su {WEBHOOK_URL}")
	
if __name__ == '__main__':
    import asyncio

    # Imposta il webhook e avvia l'app Flask
    async def main():
        await set_webhook_async()

    asyncio.run(main())
