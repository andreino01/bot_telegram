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

# Domande del quiz
DOMANDE = [
    "Quanti drum/sigarette hai fumato oggi?",
    "Quante terea/heets hai fumato oggi?",
    "Quante canne hai fumato oggi?"
]

# Stato degli utenti
user_states = {}

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
        await update.message.reply_text("Bravo/a! 🥳")
    
    current_question = user_states[chat_id] - 1
    save_to_sheet(chat_id, text, current_question + 1)
    
    # Manda la prossima domanda o completa il quiz
    if current_question < len(DOMANDE) - 1:
        await send_question(context, chat_id, current_question + 1)
    else:
        await update.message.reply_text("🎉 Quiz completato! Risposte salvate.")
	   
        improvement_status = get_improvement_status(chat_id)
        if improvement_status is not None:
            if improvement_status < 0:
                msg = f"Bravo/a oggi ne hai fumate {abs(improvement_status)} in meno di ieri, continua così! 💪"
            elif improvement_status > 0:
                msg = f"Oggi ne hai fumate {abs(improvement_status)} in più rispetto a ieri, ma domani è un altro giorno e so che puoi fare di meglio! 🔥"
            else:
                msg = "Oggi ne hai fumate quante ieri. ⚖️"
            await update.message.reply_text(msg)
        else:
            await update.message.reply_text("⚠️ Impossibile verificare il tuo progresso oggi")

	 # Determina l'URL del grafico per l'utente
        if chat_id == 637735039: #1832764914
            chart_url = "https://docs.google.com/spreadsheets/d/e/2PACX-1vTZnK4kFwfA4EONo5mKHz32uk2QS0OHzgW6suVPz2EwgHnaWilA9z07NRJ_gmjZD83ri89NpaZtDIIv/pubchart?oid=1293144718&format=image"
        elif chat_id == 5201631829:
            chart_url = "https://docs.google.com/spreadsheets/d/e/2PACX-1vTZnK4kFwfA4EONo5mKHz32uk2QS0OHzgW6suVPz2EwgHnaWilA9z07NRJ_gmjZD83ri89NpaZtDIIv/pubchart?oid=36108840&format=image"
        elif chat_id == 700212414:
            chart_url = "https://docs.google.com/spreadsheets/d/e/2PACX-1vTZnK4kFwfA4EONo5mKHz32uk2QS0OHzgW6suVPz2EwgHnaWilA9z07NRJ_gmjZD83ri89NpaZtDIIv/pubchart?oid=937722899&format=image"

         # Crea il bottone per visualizzare il grafico
        keyboard = [
            [InlineKeyboardButton("📊 Mostra il grafico", url=chart_url)],
			[InlineKeyboardButton("💸 Soldi spesi", callback_data='/soldi_spesi')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        # Invia il bottone per visualizzare il grafico o i soldi spesi
        await update.message.reply_text(
            text="Clicca i bottoni qui sotto per vedere il tuo grafico oppure quanto hai speso in fumo",
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
                text="⏰ È il momento del quiz giornaliero!\n Clicca sul pulsante qui sotto per iniziare",
                reply_markup=reply_markup
            )
        except Exception as e:
            print(f"Errore nell'inviare il messaggio al chat_id {chat_id}: {e}")


def get_soldi_spesi(chat_id):
    # Mappa degli ID e i fogli corrispondenti
    sheet_map = {
	637735039: 1,
        #1832764914: 1,  # Foglio 2
        5201631829: 2,  # Foglio 3
        700212414: 3    # Foglio 4
    }

    # Verifica se l'ID dell'utente è nella mappa
    if chat_id not in sheet_map:
        return None  # Se l'ID non è trovato, ritorna None

    # Ottieni il numero del foglio in base all'ID
    sheet_number = sheet_map[chat_id]
    worksheet = sh.get_worksheet(sheet_number)  # Ottieni il foglio corrispondente

    # Recupera il valore dalla cella W5
    soldi_spesi = worksheet.cell(5, 23).value  # La cella W5 è nella riga 5, colonna 23
    soldi_spesi = soldi_spesi.replace("€", "").strip()
    return soldi_spesi

def get_improvement_status(chat_id):
    # Mappa degli ID e i fogli corrispondenti
    sheet_map = {
	637735039: 1,
        #1832764914: 1,  # Foglio 2
        5201631829: 2,  # Foglio 3
        700212414: 3    # Foglio 4
    }

    if chat_id not in sheet_map:
        return None

    # Ottieni il foglio corrispondente
    worksheet = sh.get_worksheet(sheet_map[chat_id])
    
    # Leggi la cella W5 (modifica questo riferimento se cambia posizione nello sheet)
    status_cell = int(worksheet.cell(5, 24).value)  # X5 = riga 5, colonna 24
    return status_cell

def setup_job_queue(application: Application):
    """
    Configura il job schedulato per mezzanotte
    """
    job_queue = application.job_queue
    
    # Imposta il fuso orario (es. Europe/Rome per l'Italia)
    timezone = pytz.timezone("Europe/Rome")
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
