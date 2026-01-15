import tkinter as tk
from tkinter import messagebox, filedialog, ttk
from tkcalendar import DateEntry
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import (SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer)
from reportlab.lib.styles import getSampleStyleSheet
from datetime import datetime, timedelta
from pathlib import Path
import pandas as pd, json, sys, os, sqlite3
from PIL import Image, ImageTk

# ── PATH HELPERS ───────────────────────────────────────────────────────

def app_path(rel: str) -> Path:
    """Return a path to a *read‑only* bundled resource (works both frozen & source)."""
    if getattr(sys, "frozen", False):
        base = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    else:
        base = Path(__file__).parent
    return base / rel


def user_path(rel: str) -> Path:
    """Return a *writable* path that survives upgrades – exe dir when frozen,
    project root when running from source."""
    base = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).parent
    p = base / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    return p

# ── DATABASE SETUP ─────────────────────────────────────────────────────

def get_db():
    db_path = user_path("data/tips_data.db")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row 
    return conn

def init_db():
    conn = get_db()
    cursor = conn.cursor()
    # No "Role" column, just Name and Points
    cursor.execute('''CREATE TABLE IF NOT EXISTS staff (
        StaffID INTEGER PRIMARY KEY AUTOINCREMENT,
        StaffName TEXT UNIQUE,
        Points REAL
    )''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS tip_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT,
        staff_name TEXT,
        points REAL,
        share REAL,
        kitchen REAL,
        damage REAL
    )''')
    conn.commit()
    conn.close()

init_db() 

# Default password is '1234' for testing.
# In production, set the MANAGER_PASSWORD environment variable.
manager_password = os.getenv("MANAGER_PASSWORD", "1234")

# ── HELPER FOR REPORTS ────────────────────────────────────────────────
def get_logs_df():
    """Reads the entire SQL log table into a Pandas DataFrame for reporting."""
    conn = get_db()
    try:
        df = pd.read_sql_query("SELECT * FROM tip_logs", conn)
        # Rename columns to match what your report functions expect
        # SQL: staff_name -> DF: Staff
        # SQL: share -> DF: Share (€) ... etc
        df = df.rename(columns={
            "date": "Date",
            "staff_name": "Staff",
            "points": "Points",
            "share": "Share (€)",
            "kitchen": "Kitchen (€)",
            "damage": "Damage (€)"
        })
        if not df.empty:
            df["Date"] = pd.to_datetime(df["Date"])
        return df
    finally:
        conn.close()

# ── GUI – ROOT WINDOW ─────────────────────────────────────────────────
root = tk.Tk()
root.title("Restaurant Tip App")
root.geometry("1400x1000")
root.configure(bg="#FAF8F4")

# Watermark
try:
    logo_photo = ImageTk.PhotoImage(Image.open(app_path("assets/logo.png")).resize((400, 400)))
    tk.Label(root, image=logo_photo, bd=0).place(relx=.5, rely=.75, anchor="center")
except: pass # safe fail if logo missing

# Variables
tip_var   = tk.StringVar()
date_var  = tk.StringVar(value=datetime.today().strftime("%Y-%m-%d"))
cal_var   = tk.StringVar()
worked    = [] 
manager_authenticated = False

# ── MENU BAR ──────────────────────────────────────────────────────────
MENU_FONT = ("Segoe UI", 12)
menubar   = tk.Menu(root, tearoff=0, font=MENU_FONT)
tools = tk.Menu(menubar, tearoff=0, font=MENU_FONT)
menubar.add_cascade(label="Tools", menu=tools, font=MENU_FONT)
root.config(menu=menubar)

tools.add_command(label="Edit Staff Points",   command=lambda: pw_gate(open_point_editor))
tools.add_command(label="Add New Staff",       command=lambda: pw_gate(open_add_staff_window))
tools.add_command(label="Remove Staff",        command=lambda: pw_gate(open_remove_staff_window))
tools.add_separator()
tools.add_command(label="Export Tips Report (PDF)", command=lambda: pw_gate(export_report))

# ── MAIN LAYOUT ───────────────────────────────────────────────────────
tk.Label(root, text="Restaurant Tip App", font=("Segoe UI Semibold", 18),
         fg="#BF653E", bg="#FAF8F4").pack(pady=15)

holder = tk.Frame(root, bg="#FAF8F4")
holder.pack(pady=10)

# Left Column
left = tk.Frame(holder, bg="#FAF8F4")
left.pack(side="left", padx=40)

tk.Label(left, text="Work Date:", bg="#FAF8F4").pack(anchor="w")
DateEntry(left, textvariable=date_var, date_pattern="yyyy-mm-dd",
          width=22, font=("Segoe UI", 12)).pack(pady=5, ipady=6)

tk.Label(left, text="Total Tips (€):", bg="#FAF8F4").pack(anchor="w")
tk.Entry(left, textvariable=tip_var, width=30, font=("Segoe UI", 12),
         bg="#FFF2E0", relief="solid", bd=2).pack(pady=5, ipady=6)

def big_btn(master, txt, cmd, col="#D55923"):
    tk.Button(master, text=txt, command=cmd, width=25, height=2,
              bg=col, fg="#FAF8F4", font=("Segoe UI", 11, "bold"),
              relief="flat", cursor="hand2").pack(pady=15)

big_btn(left, "📅 Save & Calculate", lambda: save_tips())

tk.Button(left, text="✅ Check All Staff", width=25,
          command=lambda: [v.set(1) for _, v in worked]).pack(pady=5)

# Right Column
right = tk.Frame(holder, bg="#FAF8F4")
right.pack(side="right", padx=40)

tk.Label(right, text="🗓 Select Date to View Logs", bg="#FAF8F4").pack()
DateEntry(right, textvariable=cal_var, date_pattern="yyyy-mm-dd", width=20).pack(pady=5)

btn = lambda txt, cmd: tk.Button(right, text=txt, width=25, command=cmd).pack(pady=5)
btn("📋 View Logs for Selected Date", lambda: open_logs_by_date(cal_var.get()))
btn("📆 View Tips for This Week",    lambda: weekly_for(cal_var.get()))
btn("📊 View Tips for This Month",   lambda: monthly_for(cal_var.get()))
btn("✏️ Edit Entry for Selected Date", lambda: edit_entry_for_date(cal_var.get()))
btn("🗑 Delete Entry for Selected Date", lambda: delete_entry(cal_var.get()))
right.winfo_children()[-1].configure(fg="red") 

# ── STAFF CHECKLIST PANEL ─────────────────────────────────────────────
PANEL_BG       = "#FAF8F4"
BAR_BG, BAR_FG = "#D4C8B8", "#E6855B"

staff_container = tk.Frame(root, bg="#E6855B")
staff_container.pack(side="left", fill="y", padx=20, pady=(0, 10))

tk.Label(staff_container, text="Who worked?", fg="white", bg="#F96323",
         font=("Segoe UI Semibold", 12)).pack(fill="x", ipady=4)

body = tk.Frame(staff_container, bg=PANEL_BG)
body.pack(fill="both", expand=True)

canvas = tk.Canvas(body, bg=PANEL_BG, highlightthickness=0)
vbar   = ttk.Scrollbar(body, orient="vertical", command=canvas.yview,
                       style="Brown.Vertical.TScrollbar")
canvas.configure(yscrollcommand=vbar.set)
vbar.pack(side="right", fill="y")
canvas.pack(side="left", fill="both", expand=True)

style = ttk.Style()
style.theme_use(style.theme_use())
style.configure("Brown.Vertical.TScrollbar", gripcount=0, background=BAR_FG, 
                troughcolor=BAR_BG, bordercolor=BAR_BG, arrowcolor=BAR_FG, relief="flat")

staff_frame = tk.Frame(canvas, bg=PANEL_BG)
canvas.create_window((0, 0), window=staff_frame, anchor="nw")
staff_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))

def _wheel(event):
    delta = int(-1 * (event.delta / 120)) if event.delta else 1 if event.num == 5 else -1
    canvas.yview_scroll(delta, "units")
    return "break"
canvas.bind("<Enter>",  lambda e: canvas.bind_all("<MouseWheel>", _wheel))
canvas.bind("<Leave>",  lambda e: canvas.unbind_all("<MouseWheel>"))
canvas.bind_all("<Button-4>", _wheel) 
canvas.bind_all("<Button-5>", _wheel)

def refresh_staff_checklist():
    global worked
    worked.clear()
    for w in staff_frame.winfo_children(): w.destroy()

    conn = get_db()
    query = "SELECT StaffID, StaffName, Points FROM staff ORDER BY Points DESC, StaffName ASC"
    staff_rows = conn.execute(query).fetchall()
    conn.close()

    for row in staff_rows:
        var = tk.IntVar()
        display_text = f"{row['StaffName']} ({row['Points']} pts)"
        tk.Checkbutton(staff_frame, text=display_text, variable=var, 
                       bg=PANEL_BG, anchor="w", font=("Segoe UI", 10)).pack(fill="x")
        worked.append((row, var))

refresh_staff_checklist()

# ── LOGIC FUNCTIONS ───────────────────────────────────────────────────

def save_tips():
    try:
        tips = float(tip_var.get())
        work_date = date_var.get()
        
        chosen = [(row['StaffName'], row['Points']) for row, var in worked if var.get()]
        if not chosen:
            messagebox.showerror("Error", "No staff selected."); return

        total_points = sum(p for _, p in chosen)
        k_share = round(tips * 0.20, 2)
        d_share = round(tips * 0.05, 2)
        net = round(tips - k_share - d_share, 2)
        point_val = round(net / total_points, 2) if total_points > 0 else 0

        conn = get_db()
        # Overwrite previous entry for this date
        conn.execute("DELETE FROM tip_logs WHERE date = ?", (work_date,))
        
        for name, pts in chosen:
            share = round((pts / total_points) * net, 2)
            conn.execute("INSERT INTO tip_logs (date, staff_name, points, share, kitchen, damage) VALUES (?, ?, ?, ?, ?, ?)",
                         (work_date, name, pts, share, 0, 0))
        
        # Total Row
        conn.execute("INSERT INTO tip_logs (date, staff_name, points, share, kitchen, damage) VALUES (?, ?, ?, ?, ?, ?)",
                     (work_date, "TOTAL", 0, net, k_share, d_share))
        conn.commit()
        conn.close()
        
        messagebox.showinfo("Saved", f"Success!\n1 point = €{point_val}")
        tip_var.set(""); [v.set(0) for _, v in worked]
    except Exception as e:
        messagebox.showerror("Error", str(e))

def open_remove_staff_window():
    win = tk.Toplevel(root); win.geometry("300x420")
    lb = tk.Listbox(win, selectmode="extended", width=28, height=15)
    
    conn = get_db()
    names = conn.execute("SELECT StaffName FROM staff ORDER BY StaffName").fetchall()
    conn.close()
    for row in names: lb.insert(tk.END, row["StaffName"])
    lb.pack(pady=5)

    def remove_selected():
        idxs = lb.curselection()
        if not idxs: return
        names = [lb.get(i) for i in idxs]
        if not messagebox.askyesno("Confirm", f"Remove {len(names)} staff?"): return
        
        conn = get_db()
        for name in names:
            conn.execute("DELETE FROM staff WHERE StaffName = ?", (name,))
        conn.commit(); conn.close()
        refresh_staff_checklist(); win.destroy()
        messagebox.showinfo("Removed", "Staff deleted.")

    tk.Button(win, text="🗑 Remove Selected", fg="red", command=remove_selected).pack(pady=12)

def pw_gate(on_success):
    global manager_authenticated
    if manager_authenticated: on_success(); return
    
    win = tk.Toplevel(root); win.geometry("300x110")
    tk.Label(win, text="Manager Password:").pack(pady=8)
    pw_var = tk.StringVar()
    tk.Entry(win, textvariable=pw_var, show="*").pack()
    
    def check():
        global manager_authenticated
        if pw_var.get().strip() == manager_password:
            manager_authenticated = True; win.destroy(); on_success()
        else: messagebox.showerror("Error", "Wrong password")
    
    tk.Button(win, text="Submit", command=check).pack(pady=5)
    win.bind("<Return>", lambda e: check())

def open_point_editor():
    win = tk.Toplevel(root); win.geometry("600x750")
    frm = tk.Frame(win); frm.pack()
    
    conn = get_db()
    staff_data = conn.execute("SELECT StaffID, StaffName, Points FROM staff").fetchall()
    conn.close()

    ents = []
    for i, row in enumerate(staff_data):
        tk.Label(frm, text=row["StaffName"]).grid(row=i, column=0, sticky="w", padx=8)
        v = tk.StringVar(value=str(row["Points"]))
        tk.Entry(frm, textvariable=v, width=6).grid(row=i, column=1)
        ents.append((row["StaffID"], v))

    def save():
        conn = get_db()
        try:
            for sid, v in ents:
                conn.execute("UPDATE staff SET Points = ? WHERE StaffID = ?", 
                             (float(v.get().replace(",",".")), sid))
            conn.commit(); refresh_staff_checklist(); win.destroy()
            messagebox.showinfo("Saved", "Points updated")
        except Exception as e: messagebox.showerror("Error", str(e))
        finally: conn.close()

    tk.Button(win, text="Save Changes", command=save).pack(pady=10)

def open_add_staff_window():
    win = tk.Toplevel(root); win.geometry("350x200")
    tk.Label(win, text="Add Staff", font=("Segoe UI", 12, "bold")).pack(pady=10)
    
    n_var, p_var = tk.StringVar(), tk.StringVar()
    
    tk.Label(win, text="Name:").pack()
    name_entry = tk.Entry(win, textvariable=n_var)
    name_entry.pack()
    name_entry.focus_set()  # Automatically allows you to type without clicking
    
    tk.Label(win, text="Points:").pack()
    tk.Entry(win, textvariable=p_var).pack()

    def save():
        name = n_var.get().strip(); pts = p_var.get().strip().replace(",", ".")
        if not name or not pts: return
        conn = get_db()
        try:
            conn.execute("INSERT INTO staff (StaffName, Points) VALUES (?, ?)", (name, float(pts)))
            conn.commit(); refresh_staff_checklist(); win.destroy()
        except Exception as e: messagebox.showerror("Error", str(e))
        finally: conn.close()
        
    tk.Button(win, text="Save", command=save).pack(pady=15)
    
    # This triggers the save function when you press ENTER
    win.bind('<Return>', lambda event: save())

def weekly_for(date_str):
    d = pd.to_datetime(date_str)
    monday = d - timedelta(days=d.weekday())
    open_weekly_summary(monday, monday + timedelta(days=6))

def open_weekly_summary(fr, to):
    win = tk.Toplevel(root); win.geometry("500x640")
    show_summary_data(fr, to, win)
    tk.Button(win, text="Export Per-Day", command=lambda: export_range_report(fr, to)).pack(pady=5)
    tk.Button(win, text="Export Per-Staff", command=lambda: export_staff_range(fr, to)).pack(pady=5)

def monthly_for(date_str):
    d = pd.to_datetime(date_str)
    first = d.replace(day=1)
    last = (first + pd.offsets.MonthBegin(1)) - timedelta(days=1)
    open_monthly_summary(first, last)

def open_monthly_summary(fr, to):
    win = tk.Toplevel(root); win.geometry("500x640")
    show_summary_data(fr, to, win)
    tk.Button(win, text="Export Per-Day", command=lambda: export_range_report(fr, to)).pack(pady=5)
    tk.Button(win, text="Export Per-Staff", command=lambda: export_staff_range(fr, to)).pack(pady=5)

def show_summary_data(fr, to, con):
    # READ FROM SQL, NOT EXCEL
    df = get_logs_df()
    if df.empty: return

    df["Date"] = pd.to_datetime(df["Date"]).dt.normalize()
    fr, to = fr.normalize(), to.normalize()
    
    staff_df = df[(df["Date"] >= fr) & (df["Date"] <= to) & (df["Staff"] != "TOTAL")]
    total_df = df[(df["Date"] >= fr) & (df["Date"] <= to) & (df["Staff"] == "TOTAL")]

    summ = staff_df.groupby("Staff")["Share (€)"].sum().reset_index()

    tk.Label(con, text=f"{fr.date()} – {to.date()}", font=("Segoe UI Semibold", 12)).pack(pady=5)
    tbl = tk.Frame(con); tbl.pack()
    tk.Label(tbl, text="Staff").grid(row=0, column=0)
    tk.Label(tbl, text="Tips (€)").grid(row=0, column=1)

    for i, r in summ.iterrows():
        tk.Label(tbl, text=r["Staff"]).grid(row=i+1, column=0)
        tk.Label(tbl, text=f"{r['Share (€)']:.2f}").grid(row=i+1, column=1)

    k_total = pd.to_numeric(total_df["Kitchen (€)"], errors="coerce").sum()
    d_total = pd.to_numeric(total_df["Damage (€)"], errors="coerce").sum()
    tk.Label(con, text=f"Kitchen: €{k_total:.2f}").pack(pady=4)
    tk.Label(con, text=f"Damage: €{d_total:.2f}").pack()

def open_logs_by_date(date_str):
    win = tk.Toplevel(root); win.geometry("850x520")
    df = get_logs_df()
    if df.empty: tk.Label(win, text="No Logs").pack(); return
    
    df["Date"] = pd.to_datetime(df["Date"]).dt.normalize()
    target = pd.to_datetime(date_str).normalize()
    df_day = df[df["Date"] == target]

    if df_day.empty: tk.Label(win, text="No logs").pack(); return

    staff_rows = df_day[df_day["Staff"] != "TOTAL"].sort_values("Staff")
    if not df_day[df_day["Staff"] == "TOTAL"].empty:
        tot_row = df_day[df_day["Staff"] == "TOTAL"].iloc[0]
        summary_txt = f"Tips: {tot_row['Share (€)'] + tot_row['Kitchen (€)'] + tot_row['Damage (€)']:.2f}"
    else:
        summary_txt = "TOTAL row missing"

    frame = tk.Frame(win); frame.pack(fill="both", expand=True)
    tk.Label(frame, text=f"Log for {date_str}", font=("Bold", 12)).pack()
    
    for _, row in staff_rows.iterrows():
        tk.Label(frame, text=f"{row['Staff']}: {row['Share (€)']:.2f}").pack()
    
    tk.Label(frame, text=summary_txt, bg="#f0e6d6").pack(pady=10)

def edit_entry_for_date(sel_date):
    # Fully converted to SQL
    try:
        conn = get_db()
        # Check if logs exist
        logs = conn.execute("SELECT * FROM tip_logs WHERE date = ?", (sel_date,)).fetchall()
        if not logs:
            messagebox.showinfo("Info", "No logs for this date"); conn.close(); return
            
        # Get total row
        tot_row = next((r for r in logs if r["staff_name"] == "TOTAL"), None)
        if not tot_row: 
            messagebox.showerror("Error", "Corrupt log (Missing TOTAL)"); conn.close(); return
            
        tips_today = tot_row["share"] + tot_row["kitchen"] + tot_row["damage"]
        
        # Get staff list for checklist
        all_staff = conn.execute("SELECT StaffName, Points FROM staff").fetchall()
        pts_lookup = {r["StaffName"]: r["Points"] for r in all_staff}
        
        # Who worked? (Names currently in log)
        worked_names = [r["staff_name"] for r in logs if r["staff_name"] != "TOTAL"]
        conn.close()

        dlg = tk.Toplevel(root); dlg.geometry("600x800")
        tips_var = tk.StringVar(value=str(tips_today))
        tk.Label(dlg, text="Total Tips:").pack()
        tk.Entry(dlg, textvariable=tips_var).pack()
        
        tick_vars = []
        for row in all_staff:
            v = tk.IntVar(value=row["StaffName"] in worked_names)
            tk.Checkbutton(dlg, text=f"{row['StaffName']}", variable=v).pack(anchor="w")
            tick_vars.append((row["StaffName"], v))

        def save_edit():
            try:
                tips = float(tips_var.get())
                kitchen = round(tips * 0.20, 2)
                damage = round(tips * 0.05, 2)
                net = round(tips - kitchen - damage, 2)
                
                chosen = [n for n, v in tick_vars if v.get()]
                if not chosen: return
                
                total_pts = sum(pts_lookup[n] for n in chosen)
                
                conn = get_db()
                conn.execute("DELETE FROM tip_logs WHERE date = ?", (sel_date,))
                
                for name in chosen:
                    share = round((pts_lookup[name] / total_pts) * net, 2)
                    conn.execute("INSERT INTO tip_logs (date, staff_name, points, share, kitchen, damage) VALUES (?, ?, ?, ?, ?, ?)",
                                 (sel_date, name, pts_lookup[name], share, 0, 0))
                
                conn.execute("INSERT INTO tip_logs (date, staff_name, points, share, kitchen, damage) VALUES (?, ?, ?, ?, ?, ?)",
                             (sel_date, "TOTAL", 0, net, kitchen, damage))
                conn.commit(); conn.close()
                messagebox.showinfo("Saved", "Updated"); dlg.destroy()
            except Exception as e: messagebox.showerror("Error", str(e))

        tk.Button(dlg, text="Save", command=save_edit).pack(pady=10)

    except Exception as e: messagebox.showerror("Error", str(e))

def delete_entry(date_str):
    if messagebox.askyesno("Confirm", f"Delete {date_str}?"):
        conn = get_db()
        conn.execute("DELETE FROM tip_logs WHERE date = ?", (date_str,))
        conn.commit(); conn.close()
        messagebox.showinfo("Deleted", "Entry removed.")

# ── EXPORT FUNCTIONS (RESTORED STYLES) ─────────────────────────────────

def get_styled_table(data, col_widths=None):
    """Helper to apply your original brown/beige theme to the table."""
    tbl = Table(data, repeatRows=1, hAlign="LEFT", colWidths=col_widths)
    tbl.setStyle(TableStyle([
        # Header Styling
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E55410")),    
        ("TEXTCOLOR",  (0, 0), (-1, 0), colors.white),
        ("FONTNAME",   (0, 0), (-1, 0), "Helvetica-Bold"),
        
        # Grand Total Row Styling (Last Row)
        ("BACKGROUND", (0, -1), (-1, -1), colors.beige),
        ("FONTNAME",   (0, -1), (-1, -1), "Helvetica-Bold"),
        
        # Alignment (Right align numbers, starting from col 1)
        ("ALIGN",      (1, 0), (-1, -1), "RIGHT"),
        ("FONTSIZE",   (0, 0), (-1, -1), 9),
        
        # Make the "Tips" column bold in the body
        ("FONTNAME",   (1, 1), (1, -1), "Helvetica-Bold"),

        # Alternating Row Colors
        ("ROWBACKGROUNDS", (0, 1), (-1, -2), [colors.whitesmoke, colors.beige]),
        
        # Grid
        ("GRID",       (0, 0), (-1, -1), 0.25, colors.grey),
    ]))
    return tbl

def export_report():
    """Export All-Time Daily Logs"""
    try:
        df = get_logs_df()
        if df.empty: 
            messagebox.showinfo("No Data", "The tip log is empty."); return
            
        out_path = filedialog.asksaveasfilename(
            defaultextension=".pdf", filetypes=[("PDF files", "*.pdf")],
            title="Save Tips Report As…")
        if not out_path: return

        # Filter for TOTAL rows only
        totals = df[df["Staff"] == "TOTAL"].sort_values("Date")
        
        rows = [["Date", "Total Tips (€)", "Staff Share (€)", "Kitchen (€)", "Damage (€)"]]
        g_total = g_staff = g_k = g_d = 0.0

        for _, r in totals.iterrows():
            tot = r["Share (€)"] + r["Kitchen (€)"] + r["Damage (€)"]
            rows.append([
                r["Date"].strftime("%Y-%m-%d"), 
                f"{tot:.2f}", 
                f"{r['Share (€)']:.2f}", 
                f"{r['Kitchen (€)']:.2f}", 
                f"{r['Damage (€)']:.2f}"
            ])
            g_total += tot; g_staff += r['Share (€)']
            g_k += r['Kitchen (€)']; g_d += r['Damage (€)']

        rows.append(["TOTAL", f"{g_total:.2f}", f"{g_staff:.2f}", f"{g_k:.2f}", f"{g_d:.2f}"])

        doc = SimpleDocTemplate(out_path, pagesize=A4, leftMargin=36, rightMargin=36, topMargin=36, bottomMargin=36)
        elems = [Paragraph("Mnemes – Tips Summary Report", getSampleStyleSheet()["Title"]), Spacer(1, 12)]
        elems.append(get_styled_table(rows))
        doc.build(elems)
        
        messagebox.showinfo("Exported", f"Report saved to\n{out_path}")
    except Exception as e:
        messagebox.showerror("Error", str(e))

def export_range_report(d_from, d_to):
    """Export Daily Logs for a specific Date Range"""
    try:
        path = filedialog.asksaveasfilename(
            defaultextension=".pdf", filetypes=[("PDF files", "*.pdf")],
            title="Save Report As…")
        if not path: return

        df = get_logs_df()
        if df.empty: return
        
        # Filter by Date and TOTAL
        mask = (df["Staff"] == "TOTAL") & (df["Date"] >= d_from) & (df["Date"] <= d_to)
        wk = df[mask].sort_values("Date")

        if wk.empty:
            messagebox.showinfo("No Data", "Nothing logged in that range."); return

        rows = [["Date", "Total Tips (€)", "Staff Share (€)", "Kitchen (€)", "Damage (€)"]]
        g_total = g_staff = g_k = g_d = 0.0

        for _, r in wk.iterrows():
            tot = r["Share (€)"] + r["Kitchen (€)"] + r["Damage (€)"]
            rows.append([
                r["Date"].strftime("%Y-%m-%d"), 
                f"{tot:.2f}", 
                f"{r['Share (€)']:.2f}", 
                f"{r['Kitchen (€)']:.2f}", 
                f"{r['Damage (€)']:.2f}"
            ])
            g_total += tot; g_staff += r['Share (€)']
            g_k += r['Kitchen (€)']; g_d += r['Damage (€)']

        rows.append(["TOTAL", f"{g_total:.2f}", f"{g_staff:.2f}", f"{g_k:.2f}", f"{g_d:.2f}"])

        doc = SimpleDocTemplate(path, pagesize=A4, leftMargin=36, rightMargin=36, topMargin=36, bottomMargin=36)
        elems = [Paragraph("Mnemes – Weekly Tips Report", getSampleStyleSheet()["Title"]), Spacer(1, 12)]
        elems.append(get_styled_table(rows))
        doc.build(elems)

        messagebox.showinfo("Exported", f"Saved to\n{path}")
    except Exception as e:
        messagebox.showerror("Error", str(e))

def export_staff_range(d_from, d_to):
    """Export Per-Staff Totals for a specific Date Range"""
    try:
        path = filedialog.asksaveasfilename(
            defaultextension=".pdf", filetypes=[("PDF files", "*.pdf")],
            title="Save Staff Report As…")
        if not path: return

        df = get_logs_df()
        if df.empty: return

        mask = (df["Date"] >= d_from) & (df["Date"] <= d_to) & (df["Staff"] != "TOTAL")
        staff = df[mask]

        if staff.empty:
            messagebox.showinfo("No Data", "No entries in that range."); return

        summ = staff.groupby("Staff")["Share (€)"].sum().reset_index().sort_values("Staff")
        grand = summ["Share (€)"].sum()

        rows = [["Staff", "Total Tips (€)"]]
        for _, r in summ.iterrows():
            rows.append([r["Staff"], f"{r['Share (€)']:.2f}"])
        
        rows.append(["TOTAL", f"{grand:.2f}"])

        doc = SimpleDocTemplate(path, pagesize=A4, leftMargin=36, rightMargin=36, topMargin=36, bottomMargin=36)
        elems = [Paragraph("Mnemes – Staff Breakdown", getSampleStyleSheet()["Title"]), Spacer(1, 12)]
        
        # Use the same style helper, but we can pass specific column widths if we want
        elems.append(get_styled_table(rows, col_widths=[230, 80]))
        doc.build(elems)

        messagebox.showinfo("Exported", f"Report saved to\n{path}")
    except Exception as e:
        messagebox.showerror("Error", str(e))

root.mainloop()