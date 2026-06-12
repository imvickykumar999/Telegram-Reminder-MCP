import os
import re
import json
import asyncio
import logging
import tempfile
import subprocess
import speech_recognition as sr
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from fastmcp import Client

KOLKATA_TZ = ZoneInfo("Asia/Kolkata")

def get_now() -> datetime:
    """Get naive datetime representing current time in Kolkata timezone."""
    return datetime.now(KOLKATA_TZ).replace(tzinfo=None)

# Configure logging
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
MCP_SERVER_URL = os.getenv("MCP_SERVER_URL", "http://127.0.0.1:9876/mcp")

# Regular expressions for command parsing
REMIND_ME_PATTERN_1 = re.compile(
    r"(?i)remind\s+me\s+(?:after|in)\s+(\d+)\s*(sec|second|seconds|min|minute|minutes|hr|hour|hours|day|days)\s+to\s+(.+)"
)
REMIND_ME_PATTERN_2 = re.compile(
    r"(?i)remind\s+me\s+to\s+(.+?)\s+(?:after|in)\s+(\d+)\s*(sec|second|seconds|min|minute|minutes|hr|hour|hours|day|days)"
)
EDIT_REMINDER_PATTERN = re.compile(
    r"(?i)(?:edit\s+reminder|edit)\s+(\d+)\s+to\s+(.+)"
)
DELETE_REMINDER_PATTERN = re.compile(
    r"(?i)(?:delete\s+reminder|delete|remove\s+reminder|remove)\s+(\d+)"
)

LIST_REMINDERS_PATTERN = re.compile(
    r"(?i)(?:list\s+reminders|show\s+reminders|list\s+all|list)"
)

def convert_words_to_digits(text: str) -> str:
    # We want to replace "a" or "an" when followed by time units case-insensitively
    text = re.sub(r"\b(a|an)\b\s+(sec|second|min|minute|hour|hr|day)", r"1 \2", text, flags=re.IGNORECASE)
    
    ones = {
        "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
        "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
        "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14,
        "fifteen": 15, "sixteen": 16, "seventeen": 17, "eighteen": 18, "nineteen": 19
    }
    tens = {
        "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50,
        "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90
    }
    
    for ten_word, ten_val in tens.items():
        for one_word, one_val in ones.items():
            if one_val > 0:
                pattern = r"\b" + ten_word + r"[- ]" + one_word + r"\b"
                text = re.sub(pattern, str(ten_val + one_val), text, flags=re.IGNORECASE)
                
    for ten_word, ten_val in tens.items():
        pattern = r"\b" + ten_word + r"\b"
        text = re.sub(pattern, str(ten_val), text, flags=re.IGNORECASE)
        
    for one_word, one_val in ones.items():
        pattern = r"\b" + one_word + r"\b"
        text = re.sub(pattern, str(one_val), text, flags=re.IGNORECASE)
        
    return text



def calculate_due_time(duration: int, unit: str) -> datetime:
    """Calculate the target datetime based on duration and unit."""
    now = get_now()
    unit = unit.lower()
    if unit.startswith("sec"):
        return now + timedelta(seconds=duration)
    elif unit.startswith("min"):
        return now + timedelta(minutes=duration)
    elif unit.startswith("hr") or unit.startswith("hour"):
        return now + timedelta(hours=duration)
    elif unit.startswith("day"):
        return now + timedelta(days=duration)
    return now

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a friendly welcome message and commands overview."""
    welcome_text = (
        "👋 Welcome to the Telegram Reminder Bot!\n\n"
        "Here are some examples of what you can ask me:\n"
        "• *Create a reminder*:\n"
        "  - `remind me after 2 min to go to gym`\n"
        "  - `remind me to drink water in 30 minutes`\n"
        "• *List reminders*:\n"
        "  - `list reminders` or `/list`\n"
        "• *Edit a reminder*:\n"
        "  - `edit reminder 3 to go to gym in 5 minutes`\n"
        "  - `edit 3 to buy milk`\n"
        "• *Delete a reminder*:\n"
        "  - `delete reminder 3` or `/delete 3`\n\n"
        "I will send you a message when it's time!"
    )
    await update.message.reply_text(welcome_text, parse_mode="Markdown")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show the help guidelines."""
    await start(update, context)

async def handle_list(update: Update, chat_id: int) -> None:
    """Fetch and list active reminders from the MCP server."""
    try:
        async with Client(MCP_SERVER_URL) as client:
            result = await client.call_tool("list_reminders", {"chat_id": chat_id})
            res_str = result.content[0].text
            reminders = json.loads(res_str)
            if not reminders:
                await update.message.reply_text("📭 You have no active reminders.")
                return
                
            msg = "📋 *Your Active Reminders:*\n\n"
            for rem in reminders:
                due_display = rem["due_time"]
                try:
                    due_dt = datetime.strptime(rem["due_time"], "%Y-%m-%d %H:%M:%S")
                    due_display = due_dt.strftime("%Y-%m-%d %I:%M:%S %p")
                    remaining = due_dt - get_now()
                    if remaining.total_seconds() > 0:
                        mins, secs = divmod(int(remaining.total_seconds()), 60)
                        hours, mins = divmod(mins, 60)
                        if hours > 0:
                            rem_str = f"{hours}h {mins}m remaining"
                        elif mins > 0:
                            rem_str = f"{mins}m {secs}s remaining"
                        else:
                            rem_str = f"{secs}s remaining"
                    else:
                        rem_str = "due now/overdue"
                except Exception:
                    rem_str = rem["due_time"]
                    
                msg += f"• *#{rem['id']}*: {rem['text']}\n  _Due: {due_display}_ ({rem_str})\n\n"
                
            await update.message.reply_text(msg, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Error calling list_reminders: {e}")
        await update.message.reply_text("❌ Error communicating with the Reminder MCP server. Is it running?")

async def list_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler for the /list command."""
    await handle_list(update, update.message.chat_id)

async def delete_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler for the /delete command."""
    chat_id = update.message.chat_id
    if not context.args:
        await update.message.reply_text("Usage: `/delete <id>`", parse_mode="Markdown")
        return
    try:
        reminder_id = int(context.args[0])
        async with Client(MCP_SERVER_URL) as client:
            result = await client.call_tool("delete_reminder", {
                "reminder_id": reminder_id,
                "chat_id": chat_id
            })
            res_str = result.content[0].text
            res = json.loads(res_str)
            if res.get("status") == "success":
                await update.message.reply_text(f"🗑️ Reminder #{reminder_id} deleted successfully.")
            else:
                await update.message.reply_text(f"❌ Failed to delete reminder: {res.get('message')}")
    except ValueError:
        await update.message.reply_text("Please provide a valid numeric reminder ID.")
    except Exception as e:
        logger.error(f"Error calling delete_reminder: {e}")
        await update.message.reply_text("❌ Error communicating with the Reminder MCP server. Is it running?")

async def edit_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler for the /edit command."""
    chat_id = update.message.chat_id
    if len(context.args) < 2:
        await update.message.reply_text("Usage: `/edit <id> <new text and/or time>`", parse_mode="Markdown")
        return
    try:
        reminder_id = int(context.args[0])
        arg_text = " ".join(context.args[1:])
        await process_edit(update, chat_id, reminder_id, arg_text)
    except ValueError:
        await update.message.reply_text("Please provide a valid numeric reminder ID.")

async def process_edit(update: Update, chat_id: int, reminder_id: int, arg_text: str) -> None:
    """Process an edit action by checking for text and time modifications."""
    arg_text = convert_words_to_digits(arg_text)
    # Check if the edit content includes new time duration details
    time_match_1 = REMIND_ME_PATTERN_1.match(f"remind me {arg_text}")
    time_match_2 = REMIND_ME_PATTERN_2.match(f"remind me to {arg_text}")
    
    new_text = arg_text
    new_due_str = None
    duration_info = ""
    
    if time_match_1:
        duration = int(time_match_1.group(1))
        unit = time_match_1.group(2)
        new_text = time_match_1.group(3).strip()
        due = calculate_due_time(duration, unit)
        new_due_str = due.strftime("%Y-%m-%d %H:%M:%S")
        duration_info = f" at {due.strftime('%I:%M:%S %p')} (in {duration} {unit})"
    elif time_match_2:
        new_text = time_match_2.group(1).strip()
        duration = int(time_match_2.group(2))
        unit = time_match_2.group(3)
        due = calculate_due_time(duration, unit)
        new_due_str = due.strftime("%Y-%m-%d %H:%M:%S")
        duration_info = f" at {due.strftime('%I:%M:%S %p')} (in {duration} {unit})"
        
    params = {
        "reminder_id": reminder_id,
        "chat_id": chat_id,
        "text": new_text
    }
    if new_due_str:
        params["due_time"] = new_due_str
        
    try:
        async with Client(MCP_SERVER_URL) as client:
            result = await client.call_tool("edit_reminder", params)
            res_str = result.content[0].text
            res = json.loads(res_str)
            if res.get("status") == "success":
                await update.message.reply_text(
                    f"📝 Reminder #{reminder_id} updated to: *{new_text}*{duration_info}.",
                    parse_mode="Markdown"
                )
            else:
                await update.message.reply_text(f"❌ Failed to edit reminder: {res.get('message')}")
    except Exception as e:
        logger.error(f"Error calling edit_reminder: {e}")
        await update.message.reply_text("❌ Error communicating with the Reminder MCP server. Is it running?")

async def process_text_input(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str) -> None:
    """Process a string command (which could be typed or spoken)."""
    # Normalize word numbers to digit strings
    normalized_text = convert_words_to_digits(text)
    chat_id = update.message.chat_id
    
    # 1. Create Reminder Match
    match1 = REMIND_ME_PATTERN_1.match(normalized_text)
    match2 = REMIND_ME_PATTERN_2.match(normalized_text)
    
    if match1 or match2:
        if match1:
            duration = int(match1.group(1))
            unit = match1.group(2)
            action = match1.group(3).strip()
        else:
            action = match2.group(1).strip()
            duration = int(match2.group(2))
            unit = match2.group(3)
            
        due = calculate_due_time(duration, unit)
        due_str = due.strftime("%Y-%m-%d %H:%M:%S")
        
        try:
            async with Client(MCP_SERVER_URL) as client:
                result = await client.call_tool("create_reminder", {
                    "chat_id": chat_id,
                    "text": action,
                    "due_time": due_str
                })
                res_str = result.content[0].text
                res = json.loads(res_str)
                if res.get("status") == "success":
                    rem_id = res["reminder"]["id"]
                    formatted_due = due.strftime("%I:%M:%S %p on %Y-%m-%d")
                    await update.message.reply_text(
                        f"✅ Reminder #{rem_id} set for *{action}* at {formatted_due} (in {duration} {unit}).",
                        parse_mode="Markdown"
                    )
                else:
                    await update.message.reply_text(f"❌ Failed to create reminder: {res.get('message')}")
        except Exception as e:
            logger.error(f"Error calling create_reminder: {e}")
            await update.message.reply_text("❌ Error communicating with the Reminder MCP server. Is it running?")
        return

    # 2. Edit Reminder Match
    edit_match = EDIT_REMINDER_PATTERN.match(normalized_text)
    if edit_match:
        reminder_id = int(edit_match.group(1))
        arg_text = edit_match.group(2).strip()
        await process_edit(update, chat_id, reminder_id, arg_text)
        return

    # 3. Delete Reminder Match
    delete_match = DELETE_REMINDER_PATTERN.match(normalized_text)
    if delete_match:
        reminder_id = int(delete_match.group(1))
        try:
            async with Client(MCP_SERVER_URL) as client:
                result = await client.call_tool("delete_reminder", {
                    "reminder_id": reminder_id,
                    "chat_id": chat_id
                })
                res_str = result.content[0].text
                res = json.loads(res_str)
                if res.get("status") == "success":
                    await update.message.reply_text(f"🗑️ Reminder #{reminder_id} deleted successfully.")
                else:
                    await update.message.reply_text(f"❌ Failed to delete reminder: {res.get('message')}")
        except Exception as e:
            logger.error(f"Error calling delete_reminder: {e}")
            await update.message.reply_text("❌ Error communicating with the Reminder MCP server. Is it running?")
        return

    # 4. List Reminders Match
    if LIST_REMINDERS_PATTERN.match(normalized_text):
        await handle_list(update, chat_id)
        return

    # If no pattern matches
    await update.message.reply_text(
        "❓ I didn't quite understand that. Try using one of these options:\n"
        "• `remind me after 5 min to take a break`\n"
        "• `remind me to drink water in 10 minutes`\n"
        "• `list reminders` or `/list`\n"
        "• `edit reminder <id> to <new text>`\n"
        "• `delete reminder <id>` or `/delete <id>`"
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle text chat messages by checking regex rules."""
    text = update.message.text.strip()
    await process_text_input(update, context, text)

async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle voice messages, transcribe them, and process the text."""
    voice = update.message.voice
    if not voice:
        await update.message.reply_text("❌ No voice data found.")
        return

    # Indicate that the bot is recording/processing
    await update.message.reply_chat_action("record_voice")

    try:
        tg_file = await context.bot.get_file(voice.file_id)
        
        # Create unique temp files for safety
        with tempfile.NamedTemporaryFile(suffix=".oga", delete=False) as temp_ogg:
            ogg_path = temp_ogg.name
            
        await tg_file.download_to_drive(ogg_path)
        wav_path = ogg_path.replace(".oga", ".wav")
        
        # Convert OGA to WAV using ffmpeg
        cmd = ["ffmpeg", "-y", "-i", ogg_path, wav_path]
        process = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        if process.returncode != 0:
            logger.error(f"ffmpeg conversion failed: {process.stderr.decode()}")
            await update.message.reply_text("❌ Failed to process the audio file. Please try again.")
            if os.path.exists(ogg_path):
                os.remove(ogg_path)
            return

        recognizer = sr.Recognizer()
        with sr.AudioFile(wav_path) as source:
            audio_data = recognizer.record(source)
            
        try:
            transcription = recognizer.recognize_google(audio_data)
            logger.info(f"Transcription result: {transcription}")
        except sr.UnknownValueError:
            await update.message.reply_text("❌ Sorry, I couldn't understand the voice message. Please try speaking clearly or typing.")
            return
        except sr.RequestError as e:
            logger.error(f"Speech recognition service error: {e}")
            await update.message.reply_text("❌ Error communicating with transcription service. Please try typing.")
            return
        finally:
            # Clean up files
            if os.path.exists(ogg_path):
                os.remove(ogg_path)
            if os.path.exists(wav_path):
                os.remove(wav_path)

        # Notify user of transcription
        await update.message.reply_text(f"🎤 *I heard:* \"{transcription}\"", parse_mode="Markdown")
        
        # Process the transcription text
        await process_text_input(update, context, transcription)

    except Exception as e:
        logger.error(f"Error handling voice message: {e}")
        await update.message.reply_text("❌ An error occurred while processing your voice message.")

async def cron_checker(app: Application):
    """Cron-like background check polling for due reminders every 5 seconds."""
    logger.info("Cron checker background task started.")
    while True:
        try:
            async with Client(MCP_SERVER_URL) as client:
                result = await client.call_tool("get_due_reminders")
                res_str = result.content[0].text
                due_reminders = json.loads(res_str)
                for rem in due_reminders:
                    rem_id = rem["id"]
                    chat_id = rem["chat_id"]
                    text = rem["text"]
                    try:
                        await app.bot.send_message(
                            chat_id=chat_id,
                            text=f"🔔 *REMINDER:* {text}",
                            parse_mode="Markdown"
                        )
                        # Mark as sent
                        await client.call_tool("mark_as_sent", {"reminder_id": rem_id})
                        logger.info(f"Notification sent and marked as sent for reminder {rem_id}")
                    except Exception as tg_err:
                        logger.error(f"Failed to send telegram notification for reminder {rem_id}: {tg_err}")
                        from telegram.error import BadRequest, Forbidden
                        if isinstance(tg_err, (BadRequest, Forbidden)):
                            logger.info(f"Marking reminder {rem_id} as sent/failed due to fatal telegram error: {tg_err}")
                            await client.call_tool("mark_as_sent", {"reminder_id": rem_id})
        except Exception as e:
            # MCP server is probably offline, we log this debug/info but keep running
            logger.debug(f"Cron check failed (MCP server might be offline): {e}")
            
        await asyncio.sleep(5)

async def main():
    if not TOKEN or TOKEN == "your_telegram_bot_token_here":
        print("❌ Error: TELEGRAM_BOT_TOKEN environment variable not set.")
        print("Please copy .env.template to .env and insert your bot token.")
        return
        
    application = Application.builder().token(TOKEN).build()

    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("list", list_cmd))
    application.add_handler(CommandHandler("delete", delete_cmd))
    application.add_handler(CommandHandler("edit", edit_cmd))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(MessageHandler(filters.VOICE, handle_voice))

    # Initialize and start application
    await application.initialize()
    await application.start()
    
    # Start cron checker background task
    checker_task = asyncio.create_task(cron_checker(application))
    
    # Start polling
    await application.updater.start_polling()
    logger.info("Telegram Bot started. Press Ctrl+C to stop.")
    
    # Wait for cancel
    try:
        while True:
            await asyncio.sleep(1)
    except (KeyboardInterrupt, asyncio.CancelledError):
        pass
    finally:
        checker_task.cancel()
        await application.updater.stop()
        await application.stop()
        await application.shutdown()

if __name__ == "__main__":
    import sys
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nBot stopped.")
        sys.exit(0)
