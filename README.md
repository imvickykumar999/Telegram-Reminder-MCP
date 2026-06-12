># Telegram Reminder MCP
>
>![Uploading image.png…](https://github.com/user-attachments/assets/ed942b05-2c2b-4df0-8e79-76a991bc564e)
>
>A context-aware, secure, and intuitive Telegram Reminder Bot powered by **FastMCP** and **SQLite3**. Set, view, modify, and delete reminders using simple conversational phrases or standard commands. 

## 🤖 Live Bot & Web Preview
*   **Telegram Bot**: [Reminder_MCP_Bot](https://t.me/Reminder_MCP_Bot)
*   **Web Dashboard**: [reminder.minecraftbedrock.dpdns.org](http://reminder.minecraftbedrock.dpdns.org)

---

## ✨ Features
1.  **Natural Language Parsing**: Recognizes relative phrases to set reminders (e.g., `in 5 minutes`, `after 2 hours`, `in 3 days`).
2.  **Full CRUD Capabilities**: View, update, or cancel your reminders directly from Telegram chat messages.
3.  **Strict Privacy & Multi-User Isolation**: Reminders are strictly isolated using Telegram `chat_id`. A user can **never** view, edit, or delete reminders belonging to another Telegram user.
4.  **Local Timezone Alignment**: Configured specifically to calculate and store times in the **Asia/Kolkata** (IST) timezone.
5.  **Robust Cron Engine**: A background worker polls the database every 5 seconds to ensure alerts are dispatched down to the second.
6.  **Voice Message Support & Normalization**: Send voice notes directly in Telegram to set, list, edit, or delete reminders. Spoken number words (like "five" or "twenty-three") are automatically normalized to digits (like "5" or "23") to integrate seamlessly with the command parser.

---

## 💬 Sentence Tips & Parser Syntax

The bot supports natural conversational inputs. The syntax parser uses flexible regular expressions under the hood.

### Setting a Reminder
You can set reminders using two main sentence structures:
*   `remind me after [number] [unit] to [action]`
    *   *Example*: `remind me after 15 minutes to drink water`
    *   *Example*: `remind me after 1 hr to stretch`
*   `remind me to [action] in [number] [unit]`
    *   *Example*: `remind me to call dad in 2 days`
    *   *Example*: `remind me to stretch in 30 seconds`

*Supported Units: `sec`, `second`, `seconds`, `min`, `minute`, `minutes`, `hr`, `hour`, `hours`, `day`, `days`.*

### Voice Message Commands
You can tap the microphone icon in Telegram to speak any command. Spoken numbers are converted to digits automatically:
*   *Voice Input*: *"remind me in ten minutes to do yoga"* -> bot normalizes to `"remind me in 10 minutes to do yoga"` and schedules it.
*   *Voice Input*: *"list reminders"* -> bot transcribes and returns active reminders.
*   *Voice Input*: *"delete reminder four"* -> bot normalizes to `"delete reminder 4"` and deletes it.
*   *Voice Input*: *"edit reminder five to walk dog in twenty minutes"* -> bot normalizes to `"edit reminder 5 to walk dog in 20 minutes"` and updates it.

### Updating a Reminder via Chat
*   `edit reminder [id] to [new text]` or `edit [id] to [new text]`
    *   *Example*: `edit reminder 11 to go to gym in 5 minutes`
    *   *Example*: `edit 11 to buy juice`

### Deleting a Reminder via Chat
*   `delete reminder [id]`, `delete [id]`, or `remove [id]`
    *   *Example*: `delete reminder 11`

### Listing Reminders via Chat
*   `list reminders`, `list`, `list all`, or `show reminders`

---

## 🛠️ Command Reference

For users who prefer classic bot commands:

| Command | Usage | Description |
|---|---|---|
| `/start` | `/start` | Welcomes the user and lists available options. |
| `/help` | `/help` | Displays the usage guidelines and tips. |
| `/list` | `/list` | Displays a detailed list of all your active reminders and their remaining time. |
| `/delete` | `/delete <id>` | Instantly cancels and removes the specified reminder from the database. |
| `/edit` | `/edit <id> <new text and/or time>` | Modifies the task text or time offset for an active reminder. |

---

## 🔒 Security & Multi-User Privacy Check

All reminder actions (reading, updating, deleting) are secured on the FastMCP Server by verifying that the requesting user's Telegram `chat_id` matches the owner of the target reminder ID in the database.

*   **Isolation Test**: If `User A` attempts to run `delete reminder 5` or `/delete 5`, but the reminder belongs to `User B`, the server returns an `Unauthorized` error and blocks the transaction.
*   **Result**: Reminders are strictly confidential, and no cross-user visibility is possible.

---

## 🚀 Technical Setup (Local Deployment)

### 1. Requirements
*   Python 3.9+
*   FastMCP
*   SQLite3

### 2. Configuration
Copy the `.env.template` to `.env` and fill in your details:
```env
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
MCP_SERVER_URL=http://127.0.0.1:9876/mcp
```

### 3. Run Server
Start the database server:
```bash
python3 server.py
```

### 4. Run Client
Start the Telegram Bot polling and background cron checker:
```bash
python3 client.py
```
