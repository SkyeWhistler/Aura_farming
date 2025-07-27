# Aura farming 
import sqlite3
from flask import Flask, render_template, request, redirect, g, url_for 
from dotenv import load_dotenv
from datetime import datetime, date, timedelta
import os
import calendar
import openai
import json

# Load environment variables from .env file
load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")

app = Flask(__name__)
DATABASE = 'gratitude.db'

# DB helper functions
def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row 
    return db

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

def init_db():
    with app.app_context():
        db = get_db()
        cursor = db.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                text TEXT NOT NULL,
                description TEXT,
                colour TEXT,
                soft_colour TEXT
            )
        ''')
        db.commit()

# Call init_db on startup
init_db()


# Get aura colour and emotional description from GPT
def get_ai_emotion_analysis(entry_text):
    prompt = (
        "You are a poetic emotion-detecting aura assistant. "
        "Analyze this journal entry and respond ONLY with a JSON object containing:\n"
        "- description: a poetic 1-3 sentence description of the emotional essence\n"
        "- colour: Choose a vibrant and varied hex colour code representing a range of emotional auras, avoiding repetition of similar hues\n\n"
        f"Journal Entry: \"{entry_text}\"\n\n"
        "Format your response EXACTLY like this:\n"
        "{\"description\": \"...\", \"colour\": \"#xxxxxx\"}"
    )
    try:
        response = openai.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are a poetic emotion-detecting aura assistant."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.9,
            max_tokens=150
        )
        text = response.choices[0].message.content.strip()
        data = json.loads(text)
        return data.get("description", "An indescribable feeling"), data.get("colour", "#cccccc")
    except Exception as e:
        print("AI emotion analysis failed:", e)
        return "An indescribable feeling", "#cccccc"
    
def generate_soft_colour(hex_colour):
    import colorsys
    hex_colour = hex_colour.lstrip('#')
    r, g, b = tuple(int(hex_colour[i:i+2], 16) for i in (0, 2, 4))

    h, l, s = colorsys.rgb_to_hls(r / 255, g / 255, b / 255)

    # Slightly shift hue (+/- 0.05)
    h = (h + 0.05) % 1.0
    # Adjust lightness and saturation
    l = min(1, l + 0.2)
    s = max(0, s - 0.2)

    # Convert back to RGB
    r, g, b = colorsys.hls_to_rgb(h, l, s)

    # Convert to hex and return
    return '#{:02x}{:02x}{:02x}'.format(int(r * 255), int(g * 255), int(b * 255))



@app.route("/", methods=["GET", "POST"])
def index():
    db = get_db()
    cursor = db.cursor()

    today = datetime.today()

    # Get month/year from URL parameters or default to July 2025
    year = request.args.get("year", default=2025, type=int)
    month = request.args.get("month", default=7, type=int)

    if request.method == "POST":
        entry_text = request.form.get("entry")
        entry_date = request.form.get("date") or today.strftime('%Y-%m-%d')
        
        if entry_text:
            # Analyse journal entry with AI
            description, aura_colour = get_ai_emotion_analysis(entry_text)
            soft_colour = generate_soft_colour(aura_colour)

            cursor.execute('''
                INSERT INTO entries (date, text, description, colour, soft_colour)
                VALUES (?, ?, ?, ?, ?)
            ''', (entry_date, entry_text, description, aura_colour, soft_colour))
            db.commit()

        return redirect(f"/?month={month}&year={year}")

    
       # Fetch entries from DB
    cursor.execute("SELECT * FROM entries ORDER BY date DESC")
    rows = cursor.fetchall()

    # Convert rows to list of dicts
    gratitude_entries = [dict(row) for row in rows]

    # Build calendar grid
    month_days = calendar.monthcalendar(year, month)
    calendar_grid = []

    for week in month_days:
        week_list = []
        for day in week:
            if day == 0:
                week_list.append({"day": "", "entry": None, "date_str": ""})
            else:
                day_str = f"{year}-{month:02d}-{day:02d}"
                entry = next((e for e in gratitude_entries if e["date"] == day_str), None)
                week_list.append({
                    "day": day,
                    "entry": entry,
                    "date_str": day_str
                })
        calendar_grid.append(week_list)

    # Get all colours for the month to blend into final aura
    month_str = f"{year}-{month:02d}"
    monthly_colours = [e["colour"] for e in gratitude_entries if e["date"].startswith(month_str)]

    return render_template(
        "index.html", 
        calendar_grid=calendar_grid,
        month=month,
        year=year,
        monthly_colours=json.dumps(monthly_colours)
    )


@app.route("/delete", methods=["POST"])
def delete_entry():
    db = get_db()
    cursor = db.cursor()
    entry_id = request.form.get("entry_id")

    if entry_id:
        cursor.execute("DELETE FROM entries WHERE id = ?", (entry_id,))
        db.commit()

    # Redirect to the current month/year
    month = request.args.get("month", default=datetime.today().month, type=int)
    year = request.args.get("year", default=datetime.today().year, type=int)
    return redirect(f"/?month={month}&year={year}")


if __name__ == "__main__":
    app.run(debug=True)
