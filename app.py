from flask import (
    Flask, request, redirect, url_for, render_template_string, Response
)
import sqlite3
import csv
import io
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
            SELECT name, roll_number, department
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
            <thead><tr><th>Name</th><th>Roll Number</th><th>Department</th></tr></thead>
            <tbody>
            {% for student in students %}<tr><td>{{ student["name"] }}</td><td>{{ student["roll_number"] }}</td><td>{{ student["department"] }}</td></tr>
            {% else %}<tr><td colspan="3" class="empty">No students registered.</td></tr>{% endfor %}
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


if __name__ == "__main__":
    init_db()
    app.run(debug=True)
