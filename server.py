"""
FastMCP Telegram Reminder CRUD Server
"""

import sqlite3
import json
from datetime import datetime
from fastmcp import FastMCP

# Create server
mcp = FastMCP("Telegram Reminder Server")
DB_PATH = "reminders.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS reminders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER NOT NULL,
            text TEXT NOT NULL,
            due_time TEXT NOT NULL,
            is_sent INTEGER DEFAULT 0
        )
    """)
    conn.commit()
    conn.close()

# Initialize database on import/startup
init_db()

@mcp.tool
def create_reminder(chat_id: int, text: str, due_time: str) -> str:
    """Create a new reminder.
    
    Args:
        chat_id: The Telegram chat ID of the user.
        text: The content of the reminder.
        due_time: The due date/time in YYYY-MM-DD HH:MM:SS format.
    """
    try:
        # Validate datetime format
        datetime.strptime(due_time, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return "Error: due_time must be in YYYY-MM-DD HH:MM:SS format."

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO reminders (chat_id, text, due_time) VALUES (?, ?, ?)",
        (chat_id, text, due_time)
    )
    conn.commit()
    reminder_id = cursor.lastrowid
    conn.close()
    
    return json.dumps({
        "status": "success",
        "message": f"Reminder created successfully with ID {reminder_id}.",
        "reminder": {
            "id": reminder_id,
            "chat_id": chat_id,
            "text": text,
            "due_time": due_time
        }
    })

@mcp.tool
def list_reminders(chat_id: int) -> str:
    """List all active (unsent) reminders for a specific user.
    
    Args:
        chat_id: The Telegram chat ID of the user.
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, text, due_time FROM reminders WHERE chat_id = ? AND is_sent = 0 ORDER BY due_time ASC",
        (chat_id,)
    )
    rows = cursor.fetchall()
    conn.close()

    reminders = [dict(row) for row in rows]
    return json.dumps(reminders)

@mcp.tool
def edit_reminder(reminder_id: int, chat_id: int, text: str = None, due_time: str = None) -> str:
    """Edit an existing reminder.
    
    Args:
        reminder_id: The ID of the reminder to edit.
        chat_id: The Telegram chat ID of the user (for verification).
        text: The new content of the reminder (optional).
        due_time: The new due date/time in YYYY-MM-DD HH:MM:SS format (optional).
    """
    if not text and not due_time:
        return json.dumps({"status": "error", "message": "Nothing to update."})

    if due_time:
        try:
            datetime.strptime(due_time, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            return json.dumps({"status": "error", "message": "Error: due_time must be in YYYY-MM-DD HH:MM:SS format."})

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Verify ownership
    cursor.execute("SELECT chat_id FROM reminders WHERE id = ?", (reminder_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return json.dumps({"status": "error", "message": f"Reminder with ID {reminder_id} not found."})
    if row[0] != chat_id:
        conn.close()
        return json.dumps({"status": "error", "message": "Unauthorized: This reminder does not belong to you."})

    updates = []
    params = []
    if text:
        updates.append("text = ?")
        params.append(text)
    if due_time:
        updates.append("due_time = ?")
        params.append(due_time)
        updates.append("is_sent = 0") # Reset sent status if time changes

    params.append(reminder_id)
    cursor.execute(f"UPDATE reminders SET {', '.join(updates)} WHERE id = ?", params)
    conn.commit()
    conn.close()

    return json.dumps({"status": "success", "message": f"Reminder {reminder_id} updated successfully."})

@mcp.tool
def delete_reminder(reminder_id: int, chat_id: int) -> str:
    """Delete a reminder.
    
    Args:
        reminder_id: The ID of the reminder to delete.
        chat_id: The Telegram chat ID of the user (for verification).
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Verify ownership
    cursor.execute("SELECT chat_id FROM reminders WHERE id = ?", (reminder_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return json.dumps({"status": "error", "message": f"Reminder with ID {reminder_id} not found."})
    if row[0] != chat_id:
        conn.close()
        return json.dumps({"status": "error", "message": "Unauthorized: This reminder does not belong to you."})

    cursor.execute("DELETE FROM reminders WHERE id = ?", (reminder_id,))
    conn.commit()
    conn.close()

    return json.dumps({"status": "success", "message": f"Reminder {reminder_id} deleted successfully."})

@mcp.tool
def get_due_reminders() -> str:
    """Get all reminders that are due and haven't been sent yet."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute(
        "SELECT id, chat_id, text, due_time FROM reminders WHERE is_sent = 0 AND due_time <= ?",
        (now_str,)
    )
    rows = cursor.fetchall()
    conn.close()

    reminders = [dict(row) for row in rows]
    return json.dumps(reminders)

@mcp.tool
def mark_as_sent(reminder_id: int) -> str:
    """Mark a reminder as sent.
    
    Args:
        reminder_id: The ID of the reminder to mark as sent.
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("UPDATE reminders SET is_sent = 1 WHERE id = ?", (reminder_id,))
    conn.commit()
    conn.close()
    return json.dumps({"status": "success", "message": f"Reminder {reminder_id} marked as sent."})

if __name__ == "__main__":
    # Start the FastMCP server in HTTP mode
    mcp.run(transport="http", host="127.0.0.1", port=9876)
