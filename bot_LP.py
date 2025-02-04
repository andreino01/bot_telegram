from telegram import Update, Bot, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
import os
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, time, timedelta
import pytz

TOKEN = os.environ.get('TOKEN')
bot = Bot(token=TOKEN)

# Google Sheets setup
GOOGLE_CREDS = {
  "type": "service_account",
  "project_id": os.environ.get('PROJECT_ID'),
  "private_key_id": os.environ.get('PRIVATE_KEY_ID'),
  "private_key": os.environ.get('PRIVATE_KEY').replace('\\n', '\n'),
  "client_email": os.environ.get('CLIENT_EMAIL'),
  "client_id": os.environ.get('CLIENT_ID'),
  "auth_uri": "https://accounts.google.com/o/oauth2/auth",
  "token_uri": "https://oauth2.googleapis.com/token",
  "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
  "client_x509_cert_url": os.environ.get('CLIENT_CERT_URL')
}

# Inizializza Google Sheets
scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
creds = ServiceAccountCredentials.from_json_keyfile_dict(GOOGLE_CREDS, scope)
gc = gspread.authorize(creds)
sh = gc.open_by_key(os.environ.get('SHEET_ID'))

# Lista degli utenti registrati
saved_chat_ids2 = [637735039]
saved_chat_ids = [1832764914, 5201631829, 637735039, 700212414]

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


def save_to_sheet(chat_id, risposta, domanda_num):
    worksheet = sh.get_worksheet(0)
    timestamp = (datetime.now() - timedelta(hours=18)).strftime("%Y-%m-%d")
    worksheet.append_row([str(chat_id), domanda_num, risposta, timestamp])

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
        del user_states[chat_id]  # Rimuove lo stato dell'utente una volta completato il quiz

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if chat_id in saved_chat_ids:
        await update.message.reply_text("Sei già registrato! Usa il comando /quiz per iniziare il quiz.")
    else:
        saved_chat_ids.append(chat_id)
        await update.message.reply_text(
            f"Benvenuto! Il tuo Chat ID è: {chat_id}. Ora sei registrato. Usa il comando /quiz per iniziare il quiz."
        )

async def quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Permette di testare manualmente il quiz inviando le domande una alla volta.
    """
    chat_id = update.message.chat_id
    user_states[chat_id] = 0
    await send_question(context, chat_id, 0)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Gestisce le risposte alle domande.
    """
    chat_id = update.message.chat_id
    text = update.message.text.strip()
    
    if chat_id not in user_states:
        await update.message.reply_text("Il quiz è terminato, aspetta mezzanotte per compilare il prossimo!")
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
    save_to_sheet(chat_id, text, current_question + 1)
    
    # Manda la prossima domanda o completa il quiz
    if current_question < len(DOMANDE) - 1:
        await send_question(context, chat_id, current_question + 1)
    else:
        await update.message.reply_text("🎉 Quiz completato! Risposte salvate.")
        
        obiettivi = get_obiettivi(chat_id)
        if obiettivi is None:
            await update.message.reply_text("⚠️ Errore nel recuperare gli obiettivi.")
            obj = f"⚠️ C'è stato un errore con gli obiettivi giornalieri! Contattare il grande capo"
        else:
            if obiettivi[3]==1:
                obj = f"😁 Hai anche raggiunto gli obiettivi di oggi! 🎯✅"
            else: obj = f"😔 Non hai raggiunto gli obiettivi di oggi 🎯❌"

        oggi_zero = today_zero(chat_id)
        if oggi_zero is not None:
            if oggi_zero == 0:
                if chat_id == 700212414:
                    msg = f"Ammazza oh! Oggi sei andato da dio!🔥"
                else: 
                    msg = f"Ammazza oh! Oggi sei andata da dio!🔥"
                
                await update.message.reply_text(msg)
                await update.message.reply_text(obj)
                # Rimuovi l'utente da users_mancanti dopo aver completato il quiz
                if chat_id in users_mancanti:
                    users_mancanti[chat_id] = False
            
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
                        msg = f"Vabbè oh, ogni tanto ci sta fumarne qualcuna in più, oggi {abs(improvement_status)} in più di ieri, dai domani ti voglio focused! 💪"
                    else:
                        msg = "Oggi ne hai fumate quante ieri. ⚖️"
                    await update.message.reply_text(msg)
                    await update.message.reply_text(obj)
                    # Rimuovi l'utente da users_mancanti dopo aver completato il quiz
                    if chat_id in users_mancanti:
                        users_mancanti[chat_id] = False
        else:
            await update.message.reply_text("⚠️ Impossibile verificare i dati di oggi")    

        # Determina l'URL del grafico per l'utente
        if chat_id == 1832764914:
            chart_url = "https://docs.google.com/spreadsheets/d/e/2PACX-1vTZnK4kFwfA4EONo5mKHz32uk2QS0OHzgW6suVPz2EwgHnaWilA9z07NRJ_gmjZD83ri89NpaZtDIIv/pubchart?oid=1293144718&format=image"
        elif chat_id == 5201631829 or chat_id == 637735039:
            chart_url = "https://docs.google.com/spreadsheets/d/e/2PACX-1vTZnK4kFwfA4EONo5mKHz32uk2QS0OHzgW6suVPz2EwgHnaWilA9z07NRJ_gmjZD83ri89NpaZtDIIv/pubchart?oid=36108840&format=image"
        elif chat_id == 700212414:
            chart_url = "https://docs.google.com/spreadsheets/d/e/2PACX-1vTZnK4kFwfA4EONo5mKHz32uk2QS0OHzgW6suVPz2EwgHnaWilA9z07NRJ_gmjZD83ri89NpaZtDIIv/pubchart?oid=937722899&format=image"
        else:
            await update.message.reply_text("⚠️ Impossibile trovare il grafico dei tuoi progressi")
            del user_states[chat_id]
            return
        
        # Crea il bottone per visualizzare il grafico
        keyboard = [
            [InlineKeyboardButton("📈 Mostra il grafico", url=chart_url)],
            [InlineKeyboardButton("💸 Soldi spesi in totale", callback_data='/soldi_spesi')],
            [InlineKeyboardButton("📊 Medie", callback_data='/medie')],
            [InlineKeyboardButton("🎯 Obiettivi", callback_data='/obiettivi')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Invia il bottone per visualizzare il grafico, i soldi spesi, le medie o gli obiettivi
        await update.message.reply_text(
            text="Usa questi pulsanti per le funzioni aggiuntive",
            reply_markup=reply_markup
        )
        del user_states[chat_id]
        
async def handle_button_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()  # Rispondi al clic del pulsante
    chat_id = query.message.chat.id

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
        medie = get_medie(chat_id)
        if medie:
            msg = (f"📊 **Medie giornaliere:**\n"
                   f"🚬 Drum/Sigarette: {medie[0]}\n"
                   f"💨 Terea/Heets: {medie[1]}\n"
                   f"🍁 Canne: {medie[2]}")
            await context.bot.send_message(chat_id=chat_id, text=msg, parse_mode="Markdown")
        else:
            await context.bot.send_message(chat_id=chat_id, text="⚠️ Non ho trovato le tue medie.")
    elif query.data == '/obiettivi':  # Aggiunto nuovo tasto per gli obiettivi
        obiettivi = get_obiettivi(chat_id)
        if obiettivi:
            msg = (f"🎯 **Obiettivi per domani:**\n"
                    f"🚬 Drum/Sigarette: {obiettivi[0]}\n"
                    f"💨 Terea/Heets: {obiettivi[1]}\n"
                    f"🍁 Canne: {obiettivi[2]}")
            await context.bot.send_message(chat_id=chat_id, text=msg, parse_mode="Markdown")
        else:
            await context.bot.send_message(chat_id=chat_id, text="⚠️ Non ho trovato i tuoi obiettivi.")

async def inizia_quiz_automatico(context: ContextTypes.DEFAULT_TYPE):
    """
    Funzione che viene chiamata automaticamente ogni giorno a mezzanotte
    """
    for chat_id in saved_chat_ids:
        try:
            # Crea un bottone inline per il comando /quiz
            keyboard = [
                [InlineKeyboardButton("Inizia il quiz", callback_data='/quiz')]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            # Invia il messaggio con il pulsante inline
            await context.bot.send_message(
                chat_id=chat_id,
                text="⏰ È il momento del quiz giornaliero!\n Clicca qui sotto per iniziare",
                reply_markup=reply_markup
            )
            users_mancanti[chat_id] = True  # True significa "non ha ancora risposto"
        except Exception as e:
            print(f"Errore nell'inviare il messaggio al chat_id {chat_id}: {e}")

async def invia_promemoria_mattina(context: ContextTypes.DEFAULT_TYPE):
    #Funzione per inviare il promemoria la mattina agli utenti che non hanno completato il quiz.
    
    for chat_id in list(users_mancanti.keys()):
        if users_mancanti[chat_id]:
            try:
                # Crea un bottone inline per il comando /quiz
                keyboard = [
                    [InlineKeyboardButton("Inizia il quiz", callback_data='/quiz')]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                # Invia il messaggio con il pulsante inline
                await context.bot.send_message(
                    chat_id=chat_id,
                    text="🌞 Hey Buongiorno! Ieri non hai completato il quiz, vuoi farlo ora?\n Clicca qui sotto per iniziare",
                    reply_markup=reply_markup
                )
            except Exception as e:
                print(f"Errore nell'inviare il messaggio al chat_id {chat_id}: {e}")

            
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

def get_medie(chat_id):
    
    if chat_id not in sheet_map:
        return None

    # Ottieni il foglio corrispondente
    worksheet = sh.get_worksheet(sheet_map[chat_id])

    try:
        # Recupera i valori delle tre medie dalle celle Z2, Z3, Z4 (colonna 26)
        media_1 = worksheet.cell(3, 26).value  # Z3
        media_2 = worksheet.cell(6, 26).value  # Z6
        media_3 = worksheet.cell(9, 26).value  # Z9

        return media_1, media_2, media_3
    except Exception as e:
        print(f"Errore nel recuperare le medie per {chat_id}: {e}")
        return None

def get_obiettivi(chat_id):
    
    if chat_id not in sheet_map:
        return None

    # Ottieni il foglio corrispondente
    worksheet = sh.get_worksheet(sheet_map[chat_id])

    try:
        # Recupera i valori dei tre obiettivi dalle celle Z13, Z16, Z19 (colonna 26)
        obiettivo_1 = worksheet.cell(13, 26).value  # Z13
        obiettivo_2 = worksheet.cell(16, 26).value  # Z16
        obiettivo_3 = worksheet.cell(19, 26).value  # Z19

        # Vede se l'obiettivo è stato raggiunto
        goal_reached = worksheet.cell(12, 24).value #X12

        return obiettivo_1, obiettivo_2, obiettivo_3, goal_reached
    except Exception as e:
        print(f"Errore nel recuperare gli obiettivi per {chat_id}: {e}")
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

if __name__ == '__main__':
    app = Application.builder().token(TOKEN).concurrent_updates(4).build()
    # Handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("quiz", quiz))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CallbackQueryHandler(handle_button_click))
		
  
    # Configura il job schedulato
    setup_job_queue(app)
    # Avvia il bot in long polling
    app.run_polling()
