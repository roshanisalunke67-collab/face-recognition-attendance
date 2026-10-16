from flask import (
    Flask, request, redirect, url_for, render_template_string, Response, jsonify
)
import sqlite3
import csv
import io
import base64
import cv2
import numpy as np
from pathlib import Path
from datetime import datetime, date

app = Flask(__name__)
DATABASE = Path(__file__).parent / "attendance.db"


def get_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    """Create the application's tables without deleting existing data."""
    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS students (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                roll_number TEXT UNIQUE NOT NULL,
                department TEXT NOT NULL
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS attendance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id INTEGER NOT NULL,
                attendance_date TEXT NOT NULL,
                attendance_time TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'Present',
                UNIQUE(student_id, attendance_date),
                FOREIGN KEY(student_id) REFERENCES students(id)
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS attendance_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_date TEXT NOT NULL UNIQUE,
                session_name TEXT NOT NULL DEFAULT 'Regular Class',
                department TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)


BASE_STYLE = """
* { box-sizing: border-box; }
body {
    margin: 0;
    font-family: Arial, Helvetica, sans-serif;
    background: #f4f7fb;
    color: #172033;
}
.layout { display: flex; min-height: 100vh; }
.sidebar {
    width: 235px; flex-shrink: 0; background: #172554;
    color: white; padding: 28px 17px;
}
.brand { font-size: 21px; font-weight: 700; margin-bottom: 8px; }
.brand-sub { font-size: 12px; color: #c7d2fe; margin-bottom: 35px; }
.nav-link {
    display: block; padding: 13px 14px; margin: 6px 0;
    border-radius: 8px; color: #e0e7ff; text-decoration: none;
    font-size: 14px;
}
.nav-link:hover, .nav-link.active { background: #334786; color: white; }
.content { flex: 1; min-width: 0; padding: 30px; }
.topbar {
    display: flex; justify-content: space-between; align-items: center;
    gap: 15px; flex-wrap: wrap; margin-bottom: 25px;
}
h1 { font-size: 27px; margin: 0 0 7px; }
h2 { font-size: 18px; margin: 0 0 18px; }
.subtitle { color: #64748b; font-size: 14px; }
.cards {
    display: grid; grid-template-columns: repeat(4, minmax(0, 1fr));
    gap: 16px; margin-bottom: 25px;
}
.card, .panel {
    background: white; border: 1px solid #e5eaf2; border-radius: 13px;
    padding: 21px; box-shadow: 0 3px 12px #0f172a08;
    margin-bottom: 20px;
}
.card-label { color: #64748b; font-size: 13px; }
.card-value { font-size: 29px; font-weight: 700; margin-top: 12px; }
.card-note { color: #64748b; font-size: 12px; margin-top: 7px; }
.table-wrap { overflow-x: auto; }
table { width: 100%; border-collapse: collapse; min-width: 600px; }
th, td {
    padding: 14px 12px; border-bottom: 1px solid #edf0f5;
    text-align: left; font-size: 13px;
}
th { background: #f8fafc; color: #64748b; font-weight: 600; white-space: nowrap; }
tbody tr:hover { background: #f8fafc; }
a.date-link { color: #294caa; font-weight: 700; text-decoration: none; }
a.date-link:hover { text-decoration: underline; }
.badge {
    display: inline-block; padding: 5px 9px; border-radius: 20px;
    font-size: 12px; font-weight: 700;
}
.present { background: #dcfce7; color: #166534; }
.absent { background: #fee2e2; color: #991b1b; }
.neutral { background: #e2e8f0; color: #334155; }
.button {
    display: inline-block; border: 0; border-radius: 8px;
    padding: 11px 15px; background: #294caa; color: white;
    text-decoration: none; cursor: pointer; font-size: 13px;
}
.button:hover { background: #1e3a8a; }
.button.secondary { background: #e8eefb; color: #24438e; }
.toolbar {
    display: flex; gap: 10px; align-items: center;
    flex-wrap: wrap; margin-bottom: 18px;
}
input, select {
    padding: 11px 12px; border: 1px solid #cbd5e1;
    border-radius: 8px; font-size: 13px; background: white;
}
input { max-width: 100%; }
.notice {
    padding: 12px 14px; border-radius: 8px; background: #eff6ff;
    color: #1e40af; font-size: 13px; margin-bottom: 18px;
}
.success { background: #dcfce7; color: #166534; }
.error { background: #fee2e2; color: #991b1b; }
.form-grid {
    display: grid; grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 12px;
}
.form-grid input, .form-grid select { width: 100%; }
.empty { color: #64748b; padding: 25px 5px; font-size: 14px; }
@media (max-width: 1050px) {
    .cards { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
@media (max-width: 700px) {
    .layout { display: block; }
    .sidebar { width: 100%; padding: 18px; }
    .brand-sub { margin-bottom: 15px; }
    .nav-link { display: inline-block; margin: 3px; }
    .content { padding: 18px 12px; }
    .cards { grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; }
    .card, .panel { padding: 15px; }
    .card-value { font-size: 24px; }
    h1 { font-size: 23px; }
    .form-grid { grid-template-columns: 1fr; }
}
"""

SHELL_START = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{{ title }} | FaceAttend</title>
<style>""" + BASE_STYLE + """</style>
</head>
<body>
<div class="layout">
<aside class="sidebar">
    <div class="brand">FaceAttend</div>
    <div class="brand-sub">Face Recognition Attendance</div>
    <a class="nav-link {{ 'active' if nav == 'dashboard' else '' }}"
       href="{{ url_for('dashboard') }}">▦ &nbsp; Dashboard</a>
    <a class="nav-link {{ 'active' if nav == 'students' else '' }}"
       href="{{ url_for('home') }}">♙ &nbsp; Students</a>
    <a class="nav-link {{ 'active' if nav == 'sessions' else '' }}"
       href="{{ url_for('sessions_page') }}">◷ &nbsp; Class Sessions</a>
    <a class="nav-link {{ 'active' if nav == 'live' else '' }}"
       href="{{ url_for('live_attendance_page') }}">◎ &nbsp; Live Attendance</a>
    <a class="nav-link {{ 'active' if nav == 'attendance' else '' }}"
       href="{{ url_for('attendance_report') }}">▤ &nbsp; Attendance Records</a>
</aside>
<main class="content">
"""

SHELL_END = """
</main>
</div>
</body>
</html>
"""


def format_date(date_text):
    try:
        return datetime.strptime(date_text, "%Y-%m-%d").strftime("%d %b %Y (%A)")
    except (ValueError, TypeError):
        return date_text or ""


def get_daily_summary(conn):
    total_students = conn.execute(
        "SELECT COUNT(*) FROM students"
    ).fetchone()[0]

    # Show only confirmed sessions in the daily summary. Old attendance dates
    # without a session remain available in Attendance Records as legacy data.
    daily_rows = conn.execute("""
        SELECT
            s.session_date AS attendance_date,
            s.session_name,
            s.department AS session_department,
            COUNT(DISTINCT CASE
                WHEN LOWER(a.status) = 'present' THEN a.student_id
            END) AS present_count
        FROM attendance_sessions s
        LEFT JOIN attendance a ON a.attendance_date = s.session_date
        GROUP BY s.id, s.session_date, s.session_name, s.department
        ORDER BY s.session_date DESC
    """).fetchall()

    summaries = []
    for row in daily_rows:
        present = row["present_count"]
        # If a session is department-specific, calculate its expected roster
        # using that department; otherwise use all registered students.
        if row["session_department"]:
            expected = conn.execute(
                "SELECT COUNT(*) FROM students WHERE department = ?",
                (row["session_department"],)
            ).fetchone()[0]
            present = conn.execute("""
                SELECT COUNT(DISTINCT a.student_id)
                FROM attendance a
                JOIN students st ON st.id = a.student_id
                WHERE a.attendance_date = ?
                  AND LOWER(a.status) = 'present'
                  AND st.department = ?
            """, (row["attendance_date"], row["session_department"])).fetchone()[0]
        else:
            expected = total_students

        summaries.append({
            "date": row["attendance_date"],
            "formatted_date": format_date(row["attendance_date"]),
            "session_name": row["session_name"],
            "department": row["session_department"] or "All departments",
            "present": present,
            "total": expected,
            "absent": max(expected - present, 0),
            "rate": round(present / expected * 100, 1) if expected else 0
        })

    return total_students, summaries


@app.route("/")
def dashboard():
    with get_connection() as conn:
        total_students, summaries = get_daily_summary(conn)
        today = date.today().isoformat()
        today_summary = next((item for item in summaries if item["date"] == today), None)
        present_today = today_summary["present"] if today_summary else 0
        absent_today = today_summary["absent"] if today_summary else 0
        rate_today = today_summary["rate"] if today_summary else 0

    html = SHELL_START + """
    <div class="topbar">
        <div>
            <h1>Attendance Dashboard</h1>
            <div class="subtitle">Overview of student attendance and confirmed class sessions</div>
        </div>
        <a class="button" href="{{ url_for('sessions_page') }}">+ Create Class Session</a>
    </div>

    <div class="cards">
        <div class="card"><div class="card-label">Registered Students</div>
            <div class="card-value">{{ total_students }}</div>
            <div class="card-note">Students in the database</div></div>
        <div class="card"><div class="card-label">Present Today</div>
            <div class="card-value">{{ present_today }}</div>
            <div class="card-note">{{ today_label }}</div></div>
        <div class="card"><div class="card-label">Absent Today</div>
            <div class="card-value">{{ absent_today }}</div>
            <div class="card-note">{% if has_today %}Confirmed session{% else %}No confirmed session today{% endif %}</div></div>
        <div class="card"><div class="card-label">Today's Attendance Rate</div>
            <div class="card-value">{{ rate_today }}%</div>
            <div class="card-note">Based on a confirmed session</div></div>
    </div>

    <section class="panel">
        <div class="topbar">
            <div><h2>Confirmed Session Summary</h2>
                <div class="subtitle">Absences are estimated only after a class session is created.</div></div>
            <a class="button secondary" href="{{ url_for('export_attendance') }}">Export CSV</a>
        </div>
        <div class="table-wrap"><table>
            <thead><tr><th>Date</th><th>Session</th><th>Department</th><th>Expected</th><th>Present</th><th>Absent</th><th>Rate</th><th>Details</th></tr></thead>
            <tbody>
            {% for day in summaries %}
                <tr>
                    <td><a class="date-link" href="{{ url_for('attendance_report', date=day.date) }}">{{ day.formatted_date }}</a></td>
                    <td>{{ day.session_name }}</td><td>{{ day.department }}</td>
                    <td>{{ day.total }}</td><td><span class="badge present">{{ day.present }}</span></td>
                    <td><span class="badge absent">{{ day.absent }}</span></td><td>{{ day.rate }}%</td>
                    <td><a class="button secondary" href="{{ url_for('attendance_report', date=day.date) }}">View</a></td>
                </tr>
            {% else %}
                <tr><td colspan="8" class="empty">No confirmed sessions yet. Create a class session before treating missing attendance as absence.</td></tr>
            {% endfor %}
            </tbody>
        </table></div>
        <p class="subtitle">Older attendance dates without a confirmed session are preserved in Attendance Records and are not counted as official absences here.</p>
    </section>
    """ + SHELL_END

    return render_template_string(
        html, title="Dashboard", nav="dashboard",
        total_students=total_students, present_today=present_today,
        absent_today=absent_today, rate_today=rate_today,
        today_label=format_date(today), has_today=today_summary is not None,
        summaries=summaries
    )


@app.route("/students")
def home():
    with get_connection() as conn:
        students = conn.execute("""
            SELECT id, name, roll_number, department
            FROM students ORDER BY name COLLATE NOCASE
        """).fetchall()

    html = SHELL_START + """
    <div class="topbar">
        <div><h1>Student Management</h1><div class="subtitle">Register and view students</div></div>
        <a class="button secondary" href="{{ url_for('dashboard') }}">Back to Dashboard</a>
    </div>
    <section class="panel">
        <h2>Register Student</h2>
        {% if message %}<div class="notice {{ 'error' if message_type == 'error' else 'success' }}">{{ message }}</div>{% endif %}
        <form method="POST" action="{{ url_for('register') }}">
            <div class="form-grid">
                <input name="name" placeholder="Student full name" required maxlength="100">
                <input name="roll_number" placeholder="Roll number" required maxlength="50">
                <input name="department" placeholder="Department" required maxlength="100">
            </div>
            <p><button class="button" type="submit">Register Student</button></p>
        </form>
    </section>
    <section class="panel">
        <div class="topbar"><h2>Registered Students ({{ students|length }})</h2><input id="studentSearch" placeholder="Search students..."></div>
        <div class="table-wrap"><table id="studentTable">
            <thead><tr><th>Name</th><th>Roll Number</th><th>Department</th><th>Face Images</th></tr></thead>
            <tbody>
            {% for student in students %}<tr><td>{{ student["name"] }}</td><td>{{ student["roll_number"] }}</td><td>{{ student["department"] }}</td><td><a class="button secondary" href="{{ url_for('capture_face_page', student_id=student['id']) }}">Capture Face</a></td></tr>
            {% else %}<tr><td colspan="4" class="empty">No students registered.</td></tr>{% endfor %}
            </tbody>
        </table></div>
    </section>
    <script>
    document.getElementById("studentSearch").addEventListener("input", function() {
        const query = this.value.toLowerCase();
        document.querySelectorAll("#studentTable tbody tr").forEach(row => {
            row.style.display = row.innerText.toLowerCase().includes(query) ? "" : "none";
        });
    });
    </script>
    """ + SHELL_END

    message = request.args.get("message", "")
    message_type = request.args.get("type", "success")
    return render_template_string(
        html, title="Students", nav="students", students=students,
        message=message, message_type=message_type
    )


@app.route("/register", methods=["POST"])
def register():
    name = request.form.get("name", "").strip()
    roll = request.form.get("roll_number", "").strip()
    department = request.form.get("department", "").strip()

    if not name or not roll or not department:
        return redirect(url_for("home", message="All fields are required.", type="error"))

    try:
        with get_connection() as conn:
            conn.execute("""
                INSERT INTO students (name, roll_number, department)
                VALUES (?, ?, ?)
            """, (name, roll, department))
    except sqlite3.IntegrityError:
        return redirect(url_for("home", message="That roll number is already registered.", type="error"))

    return redirect(url_for("home", message="Student registered successfully.", type="success"))


@app.route("/sessions", methods=["GET", "POST"])
def sessions_page():
    message = ""
    message_type = "success"

    if request.method == "POST":
        session_date = request.form.get("session_date", "").strip()
        session_name = request.form.get("session_name", "").strip() or "Regular Class"
        department = request.form.get("department", "").strip() or None

        try:
            datetime.strptime(session_date, "%Y-%m-%d")
        except ValueError:
            message = "Please select a valid session date."
            message_type = "error"
        else:
            with get_connection() as conn:
                try:
                    conn.execute("""
                        INSERT INTO attendance_sessions (session_date, session_name, department)
                        VALUES (?, ?, ?)
                    """, (session_date, session_name, department))
                    message = "Class session created successfully."
                except sqlite3.IntegrityError:
                    message = "A session already exists for that date. Edit the existing session in the database or choose another date."
                    message_type = "error"

    with get_connection() as conn:
        departments = conn.execute("""
            SELECT DISTINCT department FROM students ORDER BY department COLLATE NOCASE
        """).fetchall()
        sessions = conn.execute("""
            SELECT session_date, session_name, department, created_at
            FROM attendance_sessions ORDER BY session_date DESC
        """).fetchall()

    html = SHELL_START + """
    <div class="topbar">
        <div><h1>Class Sessions</h1><div class="subtitle">Create a confirmed class session before calculating absences.</div></div>
        <a class="button secondary" href="{{ url_for('dashboard') }}">Back to Dashboard</a>
    </div>
    <section class="panel">
        <h2>Create a Class Session</h2>
        {% if message %}<div class="notice {{ 'error' if message_type == 'error' else 'success' }}">{{ message }}</div>{% endif %}
        <div class="notice">This version supports one session per date, matching the current attendance database rule of one attendance record per student per day.</div>
        <form method="POST" action="{{ url_for('sessions_page') }}">
            <div class="form-grid">
                <input type="date" name="session_date" value="{{ today }}" required>
                <input name="session_name" placeholder="Session name (e.g. AI Lab)" maxlength="100" value="Regular Class" required>
                <select name="department">
                    <option value="">All departments</option>
                    {% for item in departments %}<option value="{{ item['department'] }}">{{ item['department'] }}</option>{% endfor %}
                </select>
            </div>
            <p><button class="button" type="submit">Create Session</button></p>
        </form>
    </section>
    <section class="panel">
        <h2>Session History ({{ sessions|length }})</h2>
        <div class="table-wrap"><table>
            <thead><tr><th>Date</th><th>Session Name</th><th>Department</th><th>Created At</th><th>Attendance</th></tr></thead>
            <tbody>
            {% for item in sessions %}
                <tr><td>{{ item["session_date"] }}</td><td>{{ item["session_name"] }}</td>
                    <td>{{ item["department"] or "All departments" }}</td><td>{{ item["created_at"] }}</td>
                    <td><a class="button secondary" href="{{ url_for('attendance_report', date=item['session_date']) }}">View Records</a></td></tr>
            {% else %}<tr><td colspan="5" class="empty">No class sessions created yet.</td></tr>{% endfor %}
            </tbody>
        </table></div>
    </section>
    """ + SHELL_END

    return render_template_string(
        html, title="Class Sessions", nav="sessions", message=message,
        message_type=message_type, departments=departments, sessions=sessions,
        today=date.today().isoformat()
    )


@app.route("/attendance")
def attendance_report():
    selected_date = request.args.get("date", "").strip()
    search = request.args.get("search", "").strip()

    with get_connection() as conn:
        total_students = conn.execute("SELECT COUNT(*) FROM students").fetchone()[0]
        available_dates = conn.execute("""
            SELECT attendance_date FROM (
                SELECT DISTINCT attendance_date FROM attendance
                UNION
                SELECT DISTINCT session_date AS attendance_date FROM attendance_sessions
            ) ORDER BY attendance_date DESC
        """).fetchall()

        if not selected_date and available_dates:
            selected_date = available_dates[0]["attendance_date"]

        session = None
        present_students = []
        absent_students = []
        present_ids = set()
        expected_total = total_students
        session_department = None

        if selected_date:
            session = conn.execute("""
                SELECT session_name, department FROM attendance_sessions WHERE session_date = ?
            """, (selected_date,)).fetchone()
            if session and session["department"]:
                session_department = session["department"]
                expected_total = conn.execute(
                    "SELECT COUNT(*) FROM students WHERE department = ?",
                    (session_department,)
                ).fetchone()[0]

            department_condition = " AND s.department = ?" if session_department else ""
            base_params = [selected_date]
            if session_department:
                base_params.append(session_department)

            present_students = conn.execute(f"""
                SELECT s.name, s.roll_number, s.department, a.attendance_time, a.status
                FROM attendance a
                JOIN students s ON s.id = a.student_id
                WHERE a.attendance_date = ? AND LOWER(a.status) = 'present'
                {department_condition}
                AND (s.name LIKE ? OR s.roll_number LIKE ?)
                ORDER BY s.name COLLATE NOCASE
            """, base_params + [f"%{search}%", f"%{search}%"]).fetchall()

            present_ids = {
                row["roll_number"] for row in conn.execute(f"""
                    SELECT s.roll_number
                    FROM attendance a JOIN students s ON s.id = a.student_id
                    WHERE a.attendance_date = ? AND LOWER(a.status) = 'present'
                    {department_condition}
                """, base_params).fetchall()
            }

            absent_students = conn.execute(f"""
                SELECT name, roll_number, department
                FROM students
                WHERE (? IS NULL OR department = ?)
                  AND roll_number NOT IN (
                    SELECT s.roll_number FROM attendance a
                    JOIN students s ON s.id = a.student_id
                    WHERE a.attendance_date = ? AND LOWER(a.status) = 'present'
                    {department_condition}
                  )
                  AND (name LIKE ? OR roll_number LIKE ?)
                ORDER BY name COLLATE NOCASE
            """, (
                session_department, session_department, selected_date,
                *([session_department] if session_department else []),
                f"%{search}%", f"%{search}%"
            )).fetchall() if session else []

        present_count = len(present_ids)
        absent_count = max(expected_total - present_count, 0) if session else 0

    html = SHELL_START + """
    <div class="topbar">
        <div><h1>Attendance Records</h1><div class="subtitle">Search attendance by date, student name, or roll number.</div></div>
        <a class="button secondary" href="{{ url_for('export_attendance', date=selected_date) }}">Export Selected Date</a>
    </div>
    <section class="panel">
        <form method="GET" action="{{ url_for('attendance_report') }}" class="toolbar">
            <label for="date"><strong>Date</strong></label>
            <select id="date" name="date" onchange="this.form.submit()">
                {% for item in available_dates %}
                    <option value="{{ item['attendance_date'] }}" {% if item['attendance_date'] == selected_date %}selected{% endif %}>{{ item['attendance_date'] }}</option>
                {% endfor %}
            </select>
            <input type="text" name="search" value="{{ search }}" placeholder="Search name or roll number">
            <button class="button" type="submit">Search</button>
            <a class="button secondary" href="{{ url_for('attendance_report', date=selected_date) }}">Clear Search</a>
        </form>

        {% if selected_date %}
            {% if session %}
                <div class="notice">Confirmed session: <strong>{{ session['session_name'] }}</strong> — {{ formatted_date }}. Expected group: {{ session['department'] or 'All departments' }}.</div>
            {% else %}
                <div class="notice">Legacy attendance records for {{ formatted_date }}. No class session is registered for this date, so absences are not classified as official.</div>
            {% endif %}
            <div class="cards">
                <div class="card"><div class="card-label">Expected Students</div><div class="card-value">{{ expected_total if session else '—' }}</div></div>
                <div class="card"><div class="card-label">Present</div><div class="card-value">{{ present_count }}</div></div>
                <div class="card"><div class="card-label">Absent</div><div class="card-value">{{ absent_count if session else '—' }}</div></div>
                <div class="card"><div class="card-label">Attendance Rate</div><div class="card-value">{{ rate if session else '—' }}{% if session %}%{% endif %}</div></div>
            </div>
            <h2>Present Students ({{ present_students|length }} matching)</h2>
            <div class="table-wrap panel"><table>
                <thead><tr><th>Name</th><th>Roll Number</th><th>Department</th><th>Time</th><th>Status</th></tr></thead>
                <tbody>
                {% for student in present_students %}
                    <tr><td>{{ student["name"] }}</td><td>{{ student["roll_number"] }}</td><td>{{ student["department"] }}</td><td>{{ student["attendance_time"] }}</td><td><span class="badge present">Present</span></td></tr>
                {% else %}<tr><td colspan="5" class="empty">No matching present students.</td></tr>{% endfor %}
                </tbody>
            </table></div>
            {% if session %}
                <h2 style="margin-top:25px;">Absent Students ({{ absent_students|length }} matching)</h2>
                <div class="table-wrap panel"><table>
                    <thead><tr><th>Name</th><th>Roll Number</th><th>Department</th><th>Status</th></tr></thead>
                    <tbody>
                    {% for student in absent_students %}
                        <tr><td>{{ student["name"] }}</td><td>{{ student["roll_number"] }}</td><td>{{ student["department"] }}</td><td><span class="badge absent">Absent (no present record)</span></td></tr>
                    {% else %}<tr><td colspan="4" class="empty">No matching students in this list.</td></tr>{% endfor %}
                    </tbody>
                </table></div>
            {% endif %}
        {% else %}
            <p class="empty">No attendance records or sessions exist yet.</p>
        {% endif %}
    </section>
    """ + SHELL_END

    return render_template_string(
        html, title="Attendance Records", nav="attendance",
        selected_date=selected_date, formatted_date=format_date(selected_date),
        available_dates=available_dates, total_students=total_students,
        present_students=present_students, absent_students=absent_students,
        present_count=present_count, absent_count=absent_count,
        expected_total=expected_total, session=session,
        rate=round(present_count / expected_total * 100, 1) if expected_total and session else 0,
        search=search
    )


@app.route("/export")
def export_attendance():
    selected_date = request.args.get("date", "").strip()

    with get_connection() as conn:
        query = """
            SELECT s.name, s.roll_number, s.department,
                   a.attendance_date, a.attendance_time, a.status
            FROM attendance a
            JOIN students s ON s.id = a.student_id
        """
        params = []
        if selected_date:
            query += " WHERE a.attendance_date = ?"
            params.append(selected_date)
        query += " ORDER BY a.attendance_date DESC, s.name COLLATE NOCASE"
        rows = conn.execute(query, params).fetchall()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Name", "Roll Number", "Department",
        "Attendance Date", "Attendance Time", "Status"
    ])
    for row in rows:
        writer.writerow(list(row))

    filename = f"attendance_{selected_date}.csv" if selected_date else "attendance_all_dates.csv"
    return Response(
        "\ufeff" + output.getvalue(),
        mimetype="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )


# ---------- Face recognition integration ----------
# The InsightFace model is loaded lazily on first use, not when Flask starts.
_face_model_module = None
_face_database = None


def get_face_model_module():
    global _face_model_module
    if _face_model_module is None:
        import face_recognition_model as module
        _face_model_module = module
    return _face_model_module


def refresh_face_database():
    """Reload enrolled embeddings after new face images are captured."""
    global _face_database
    module = get_face_model_module()
    _face_database = module.load_face_database()
    return _face_database


def get_face_database():
    global _face_database
    if _face_database is None:
        return refresh_face_database()
    return _face_database


def save_attendance_for_student(student_id):
    """Save one present record per student per date using the existing schema."""
    today = date.today().isoformat()
    current_time = datetime.now().strftime("%H:%M:%S")

    with get_connection() as conn:
        student = conn.execute(
            "SELECT id, name, roll_number, department FROM students WHERE id = ?",
            (student_id,)
        ).fetchone()

        if student is None:
            return False, "Recognized student ID is not registered."

        session = conn.execute(
            "SELECT department FROM attendance_sessions WHERE session_date = ?",
            (today,)
        ).fetchone()

        if session is None:
            return False, "Create today's class session first, then start attendance."

        if session["department"] and session["department"] != student["department"]:
            return False, "This student is not part of today's session department."

        cursor = conn.execute("""
            INSERT OR IGNORE INTO attendance
                (student_id, attendance_date, attendance_time, status)
            VALUES (?, ?, ?, 'Present')
        """, (student_id, today, current_time))

        inserted = cursor.rowcount == 1
        if inserted:
            return True, f"Attendance recorded for {student['name']} ({student['roll_number']})."
        return True, f"Already marked present today: {student['name']} ({student['roll_number']})."


def decode_camera_image(data_url):
    """Decode a browser canvas data URL into an OpenCV BGR frame."""
    if not isinstance(data_url, str) or "," not in data_url:
        return None
    try:
        encoded = data_url.split(",", 1)[1]
        raw = base64.b64decode(encoded, validate=True)
        array = np.frombuffer(raw, dtype=np.uint8)
        frame = cv2.imdecode(array, cv2.IMREAD_COLOR)
        return frame
    except (ValueError, base64.binascii.Error):
        return None


@app.route("/students/<int:student_id>/capture-face")
def capture_face_page(student_id):
    with get_connection() as conn:
        student = conn.execute(
            "SELECT id, name, roll_number, department FROM students WHERE id = ?",
            (student_id,)
        ).fetchone()

    if student is None:
        return redirect(url_for("home", message="Student not found.", type="error"))

    html = SHELL_START + """
    <div class="topbar">
      <div><h1>Capture Student Face</h1>
      <div class="subtitle">Student: {{ student['name'] }} · Roll {{ student['roll_number'] }}</div></div>
      <a class="button secondary" href="{{ url_for('home') }}">Back to Students</a>
    </div>
    <section class="panel">
      <div class="notice">Ask for the student's informed consent. Capture one face at a time in good lighting. Five clear images from slightly different angles are recommended.</div>
      <video id="video" autoplay playsinline style="width:100%;max-width:640px;background:#111;border-radius:12px"></video>
      <canvas id="canvas" hidden></canvas>
      <p><button class="button" id="start">Start Camera</button>
      <button class="button" id="capture" disabled>Capture Image</button>
      <button class="button secondary" id="stop" disabled>Stop Camera</button></p>
      <p id="status" class="notice">Start the camera, then capture five clear images.</p>
      <p id="count">Captured this session: 0 / 5</p>
    </section>
    <script>
    const studentId = {{ student['id'] }};
    const video = document.getElementById('video');
    const canvas = document.getElementById('canvas');
    const statusBox = document.getElementById('status');
    const countBox = document.getElementById('count');
    const startBtn = document.getElementById('start');
    const captureBtn = document.getElementById('capture');
    const stopBtn = document.getElementById('stop');
    let stream = null, count = 0, busy = false;

    startBtn.onclick = async () => {
      try {
        stream = await navigator.mediaDevices.getUserMedia({video: true, audio: false});
        video.srcObject = stream;
        captureBtn.disabled = false;
        stopBtn.disabled = false;
        startBtn.disabled = true;
        statusBox.textContent = 'Camera ready. Center the student’s face and capture an image.';
      } catch (e) {
        statusBox.textContent = 'Camera unavailable. Allow camera permission and use localhost.';
      }
    };

    captureBtn.onclick = async () => {
      if (!stream || busy || count >= 5) return;
      busy = true;
      canvas.width = video.videoWidth;
      canvas.height = video.videoHeight;
      canvas.getContext('2d').drawImage(video, 0, 0);
      try {
        const response = await fetch(`/api/students/${studentId}/face-images`, {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({image: canvas.toDataURL('image/jpeg', 0.92), captured: count})
        });
        const result = await response.json();
        if (!response.ok) throw new Error(result.message || 'Could not save image.');
        count = result.captured;
        countBox.textContent = `Captured this session: ${count} / 5`;
        statusBox.textContent = result.message;
        if (count >= 5) {
          captureBtn.disabled = true;
          statusBox.textContent += ' You can return to Students now.';
        }
      } catch (e) {
        statusBox.textContent = e.message;
      } finally { busy = false; }
    };

    stopBtn.onclick = () => {
      if (stream) stream.getTracks().forEach(track => track.stop());
      stream = null;
      video.srcObject = null;
      captureBtn.disabled = true;
      stopBtn.disabled = true;
      startBtn.disabled = false;
    };
    window.addEventListener('beforeunload', () => {
      if (stream) stream.getTracks().forEach(track => track.stop());
    });
    </script>
    """ + SHELL_END
    return render_template_string(html, title="Capture Face", nav="students", student=student)


@app.route("/api/students/<int:student_id>/face-images", methods=["POST"])
def save_face_image(student_id):
    payload = request.get_json(silent=True) or {}
    frame = decode_camera_image(payload.get("image"))
    if frame is None:
        return jsonify(message="Could not decode camera image."), 400

    with get_connection() as conn:
        student = conn.execute(
            "SELECT id FROM students WHERE id = ?", (student_id,)
        ).fetchone()
    if student is None:
        return jsonify(message="Student not found."), 404

    module = get_face_model_module()
    detected_face = module.get_largest_face(frame)
    if detected_face is None:
        return jsonify(message="No face detected. Improve lighting and try again."), 400

    face_folder = Path(__file__).resolve().parent / "data" / "faces" / str(student_id)
    face_folder.mkdir(parents=True, exist_ok=True)

    existing_numbers = []
    for path in face_folder.glob("face_*.jpg"):
        try:
            existing_numbers.append(int(path.stem.removeprefix("face_")))
        except ValueError:
            continue
    next_number = max(existing_numbers, default=0) + 1
    image_path = face_folder / f"face_{next_number}.jpg"

    if not cv2.imwrite(str(image_path), frame):
        return jsonify(message="Could not save image."), 500

    # Refresh embeddings so the next recognition request includes this image.
    refresh_face_database()
    saved_this_session = min(5, int(payload.get("captured", 0)) + 1)
    # Client sends its count to keep the five-image counter session-local.
    return jsonify(
        message=f"Face image saved and face detected ({saved_this_session}/5).",
        captured=saved_this_session
    )


@app.route("/live-attendance")
def live_attendance_page():
    today = date.today().isoformat()
    with get_connection() as conn:
        session = conn.execute(
            "SELECT session_name, department FROM attendance_sessions WHERE session_date = ?",
            (today,)
        ).fetchone()

    html = SHELL_START + """
    <div class="topbar">
      <div><h1>Live Face Attendance</h1><div class="subtitle">Start the class, scan each student, then finish to see the attendance summary.</div></div>
      <a class="button secondary" href="{{ url_for('attendance_report', date=today) }}">View Today's Records</a>
    </div>
    <section class="panel">
      {% if not session %}
        <div class="notice error">No class session exists for today. Create today's session before recording attendance.</div>
        <a class="button" href="{{ url_for('sessions_page') }}">Create Class Session</a>
      {% else %}
        <div class="notice">Session: <strong>{{ session['session_name'] }}</strong> · Department: {{ session['department'] or 'All departments' }}</div>
        <p>Ask students for consent before using the camera. Recognition can make mistakes; verify the displayed student before relying on the record.</p>
        <div style="display:flex;gap:10px;flex-wrap:wrap;margin:16px 0">
          <button class="button" id="start">Start Attendance</button>
          <button class="button" id="next" disabled>Next Student →</button>
          <button class="button secondary" id="done" disabled>Done / Finish Attendance</button>
        </div>
        <video id="video" autoplay playsinline style="width:100%;max-width:720px;min-height:240px;background:#111;border-radius:12px;object-fit:cover"></video>
        <canvas id="canvas" hidden></canvas>
        <div id="status" class="notice" style="margin-top:14px">Press “Start Attendance” to open the camera.</div>
        <div id="studentResult" style="font-size:1.25rem;font-weight:700;margin:12px 0" aria-live="polite"></div>
        <section id="summary" class="panel" style="display:none;margin-top:18px">
          <h2>Attendance Summary</h2>
          <p id="summaryCount"></p>
          <div style="overflow-x:auto"><table style="width:100%"><thead><tr><th>Name</th><th>Roll Number</th><th>Department</th><th>Status</th></tr></thead><tbody id="summaryRows"></tbody></table></div>
          <p><a class="button" href="{{ url_for('attendance_report', date=today) }}">Open Final Attendance Records</a></p>
        </section>
      {% endif %}
    </section>
    {% if session %}
    <script>
    const video = document.getElementById('video');
    const canvas = document.getElementById('canvas');
    const statusBox = document.getElementById('status');
    const studentResult = document.getElementById('studentResult');
    const startBtn = document.getElementById('start');
    const nextBtn = document.getElementById('next');
    const doneBtn = document.getElementById('done');
    const summaryBox = document.getElementById('summary');
    const attended = new Map();
    let stream = null, running = false, requestBusy = false, lastSent = 0, waitingForNext = false, finished = false;

    function beepSuccess() {
      try {
        const AudioCtx = window.AudioContext || window.webkitAudioContext;
        if (!AudioCtx) return;
        const ctx = new AudioCtx();
        const oscillator = ctx.createOscillator();
        const gain = ctx.createGain();
        oscillator.connect(gain); gain.connect(ctx.destination);
        oscillator.frequency.value = 880; gain.gain.value = 0.12;
        oscillator.start(); oscillator.stop(ctx.currentTime + 0.18);
        oscillator.onended = () => ctx.close();
      } catch (e) { /* Sound may be blocked by browser settings. */ }
    }

    async function processFrame() {
      if (!running || requestBusy || waitingForNext || finished) {
        if (running && !finished) requestAnimationFrame(processFrame);
        return;
      }
      if (video.readyState >= 2 && Date.now() - lastSent > 1000) {
        requestBusy = true; lastSent = Date.now();
        canvas.width = video.videoWidth; canvas.height = video.videoHeight;
        canvas.getContext('2d').drawImage(video, 0, 0, canvas.width, canvas.height);
        try {
          const response = await fetch('/api/live-recognize', {
            method: 'POST', headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({image: canvas.toDataURL('image/jpeg', 0.8)})
          });
          const data = await response.json();
          if (!response.ok) statusBox.textContent = data.message || 'Recognition request failed.';
          else if (data.student) {
            const s = data.student;
            const key = String(s.id);
            if (data.attendance_ok || attended.has(key)) {
              attended.set(key, {name:s.name, roll_number:s.roll_number, department:s.department, status:'Present'});
              studentResult.textContent = '✓  ' + s.name + ' · Roll No. ' + s.roll_number;
              studentResult.style.color = '#15803d';
              statusBox.textContent = data.attendance_message || 'Attendance recorded.';
              beepSuccess();
              waitingForNext = true;
              nextBtn.disabled = false;
              doneBtn.disabled = false;
            } else {
              statusBox.textContent = data.attendance_message || data.message || 'Student recognized, but attendance was not saved.';
            }
          } else {
            statusBox.textContent = data.message || 'No registered student recognized yet. Keep looking at the camera.';
          }
        } catch (e) { statusBox.textContent = 'Could not contact the attendance server.'; }
        finally { requestBusy = false; }
      }
      if (running && !finished) requestAnimationFrame(processFrame);
    }

    startBtn.onclick = async () => {
      try {
        stream = await navigator.mediaDevices.getUserMedia({video: {facingMode:'user'}, audio:false});
        video.srcObject = stream; await video.play();
        running = true; startBtn.disabled = true; doneBtn.disabled = false;
        statusBox.textContent = 'Camera is ready. Ask the first student to look at the camera.';
        requestAnimationFrame(processFrame);
      } catch (e) { statusBox.textContent = 'Camera unavailable. Allow camera permission and use localhost.'; }
    };

    nextBtn.onclick = () => {
      waitingForNext = false; nextBtn.disabled = true;
      studentResult.textContent = '';
      statusBox.textContent = 'Ready for the next student. Ask them to look at the camera.';
      if (running) requestAnimationFrame(processFrame);
    };

    doneBtn.onclick = () => {
      finished = true; running = false; waitingForNext = false;
      if (stream) stream.getTracks().forEach(track => track.stop());
      stream = null; video.srcObject = null;
      startBtn.disabled = true; nextBtn.disabled = true; doneBtn.disabled = true;
      statusBox.textContent = 'Attendance session finished.';
      studentResult.textContent = '';
      const rows = document.getElementById('summaryRows');
      rows.innerHTML = '';
      for (const s of attended.values()) {
        const tr = document.createElement('tr');
        [s.name, s.roll_number, s.department, s.status].forEach(value => {
          const td = document.createElement('td'); td.textContent = value; tr.appendChild(td);
        });
        rows.appendChild(tr);
      }
      document.getElementById('summaryCount').textContent = 'Students marked present in this run: ' + attended.size;
      summaryBox.style.display = 'block';
      summaryBox.scrollIntoView({behavior:'smooth', block:'start'});
    };

    window.addEventListener('beforeunload', () => {
      running = false;
      if (stream) stream.getTracks().forEach(track => track.stop());
    });
    </script>
    {% endif %}
    """ + SHELL_END
    return render_template_string(
        html, title="Live Attendance", nav="live", session=session, today=today
    )


@app.route("/api/live-recognize", methods=["POST"])
def api_live_recognize():
    payload = request.get_json(silent=True) or {}
    frame = decode_camera_image(payload.get("image"))
    if frame is None:
        return jsonify(message="Could not decode camera image."), 400

    database = get_face_database()
    if not database:
        return jsonify(message="No enrolled face images found. Capture faces first.")

    module = get_face_model_module()
    match = module.recognize_face(frame, face_database=database)

    if match["student_id"] is None:
        return jsonify(message=match["message"], similarity=match["similarity"])

    with get_connection() as conn:
        student = conn.execute(
            "SELECT id, name, roll_number, department FROM students WHERE id = ?",
            (match["student_id"],)
        ).fetchone()

    if student is None:
        return jsonify(message="Matched face folder does not map to a registered student.")

    # Department-specific session check and unique constraint are enforced here.
    success, attendance_message = save_attendance_for_student(student["id"])
    return jsonify(
        message=match["message"],
        similarity=match["similarity"],
        student={
            "id": student["id"],
            "name": student["name"],
            "roll_number": student["roll_number"],
            "department": student["department"]
        },
        attendance_message=attendance_message,
        attendance_ok=success
    )


if __name__ == "__main__":
    init_db()
    app.run(debug=True)
