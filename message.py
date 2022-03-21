

import os
from telegram.ext import CommandHandler, Updater, CallbackContext
from telegram import Update
import logging


TOKEN = os.environ["TELEGRAM_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]
updater = Updater(TOKEN)


def send_message(message: str):
    updater.bot.send_message(CHAT_ID, message)


def chat_id(update: Update, context: CallbackContext):

    chat_id = update.effective_chat.id
    context.bot.send_message(chat_id, f"The chat id is {chat_id}")


if __name__ == "__main__":

    logging.basicConfig(level=logging.DEBUG)
    logging.info("Starting telegram bot")
    dispatch = updater.dispatcher
    chat_id_command = CommandHandler("chat_id", chat_id)
    dispatch.add_handler(chat_id_command)
    updater.start_polling()
    updater.idle()
