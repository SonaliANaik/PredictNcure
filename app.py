import streamlit as st
import sqlite3
import re
import pandas as pd
import numpy as np
import joblib
import socket

try:
    import dns.resolver
except ImportError:
    import pip
    pip.main(['install','dnspython'])
    import dns.resolver

# ==================== PAGE CONFIG ====================
st.set_page_config(page_title="PredictNCure", layout="wide")

# ==================== DATABASE SETUP ====================
def init_db():
    with sqlite3.connect("database.db") as conn:
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS users (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        username TEXT UNIQUE,
                        password TEXT,
                        email TEXT,
                        role TEXT)''')
        c.execute('''CREATE TABLE IF NOT EXISTS ratings (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER,
                        rating INTEGER,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
        c.execute('''CREATE TABLE IF NOT EXISTS complaints (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER,
                        complaint TEXT,
                        status TEXT DEFAULT 'Pending',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
        try:
            c.execute("ALTER TABLE complaints ADD COLUMN status TEXT DEFAULT 'Pending'")
        except sqlite3.OperationalError:
            pass
        conn.commit()

init_db()

# ==================== SESSION SETUP ====================
for key in ["page","logged_in","role","user_id","section","temp_rating","temp_complaint","admin_option"]:
    if key not in st.session_state:
        st.session_state[key] = 0 if key=="temp_rating" else "login" if key=="page" else "home" if key=="section" else None if key=="role" else ""

# ==================== VALIDATION ====================
def validate_username(username):
    return len(username) >= 6 and username.isalnum()

def validate_password(password):
    return len(password) >= 6

def validate_email_real(email):
    if not re.match(r"^[^@]+@[^@]+\.[^@]+$", email):
        return False
    domain = email.split('@')[1]
    try:
        dns.resolver.resolve(domain, 'MX')
        return True
    except Exception:
        try:
            socket.gethostbyname(domain)
            return True
        except Exception:
            return False

# ==================== CARD FUNCTION ====================
def card(content, bg="#f5f7fa", padding=20):
    st.markdown(f"""
        <div style='background-color:{bg}; padding:{padding}px; border-radius:15px;
        box-shadow:0 4px 12px rgba(0,0,0,0.08); margin-bottom:15px;'>
        {content}
        </div>
    """, unsafe_allow_html=True)

# ==================== LOGIN / REGISTER / FORGOT ====================
def show_login():
    st.title("🔐 Login")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")
    
    if st.button("Login"):
        if not username or not password:
            st.warning("Please fill all fields.")
        else:
            # Admin login via secrets
            if username == st.secrets["ADMIN_USER"] and password == st.secrets["ADMIN_PASS"]:
                st.success(f"Welcome, {username}!")
                st.session_state.logged_in = True
                st.session_state.role = "admin"
                st.session_state.user_id = None
                st.session_state.page = "dashboard"
            else:
                # Regular user login
                with sqlite3.connect("database.db") as conn:
                    c = conn.cursor()
                    c.execute("SELECT * FROM users WHERE username=? AND password=?", (username, password))
                    user = c.fetchone()
                if user:
                    st.success(f"Welcome, {username}!")
                    st.session_state.logged_in = True
                    st.session_state.role = user[4]
                    st.session_state.user_id = user[0]
                    st.session_state.page = "dashboard"
                else:
                    st.error("Invalid username or password.")
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("New User? Register"):
            st.session_state.page = "register"
    with col2:
        if st.button("Forgot Password?"):
            st.session_state.page = "forgot"

def show_register():
    st.title("📝 Register")
    username = st.text_input("Username (min 6 chars)")
    email = st.text_input("Email")
    password = st.text_input("Password", type="password")
    confirm = st.text_input("Confirm Password", type="password")
    if st.button("Register"):
        if not all([username,email,password,confirm]):
            st.warning("Please fill all fields.")
        elif not validate_username(username):
            st.warning("Username must be at least 6 characters & alphanumeric.")
        elif not validate_email_real(email):
            st.warning("⚠ This email does not exist or is invalid. Please enter a real email.")
        elif not validate_password(password):
            st.warning("Password must be at least 6 characters.")
        elif password != confirm:
            st.warning("Passwords do not match.")
        else:
            try:
                with sqlite3.connect("database.db") as conn:
                    c = conn.cursor()
                    c.execute("INSERT INTO users (username,password,email,role) VALUES (?,?,?,?)",
                              (username,password,email,"user"))
                    conn.commit()
                st.success("Registration successful! Please login.")
                st.session_state.page="login"
            except sqlite3.IntegrityError:
                st.error("Username already exists.")
    if st.button("🔙 Back to Login"):
        st.session_state.page="login"

def show_forgot():
    st.title("🔑 Forgot Password")
    username = st.text_input("Enter your username")
    new_pass = st.text_input("New Password", type="password")
    if st.button("Reset Password"):
        if not username or not new_pass:
            st.warning("Please fill all fields.")
        else:
            with sqlite3.connect("database.db") as conn:
                c = conn.cursor()
                c.execute("SELECT * FROM users WHERE username=?", (username,))
                user = c.fetchone()
                if user:
                    c.execute("UPDATE users SET password=? WHERE username=?", (new_pass,username))
                    conn.commit()
                    st.success("Password updated! Please login.")
                    st.session_state.page="login"
                else:
                    st.error("User not found.")
    if st.button("🔙 Back to Login"):
        st.session_state.page="login"

# ==================== ADMIN DASHBOARD ====================
def show_admin_dashboard():
    st.sidebar.title("📊 Admin Dashboard")
    admin_options = ["Home", "Users", "Ratings", "Complaints", "Logout"]
    if st.session_state.admin_option not in admin_options:
        st.session_state.admin_option = "Home"
    option = st.sidebar.radio("Navigate", admin_options, index=admin_options.index(st.session_state.admin_option))
    st.session_state.admin_option = option

    # Home metrics
    if option == "Home":
        st.markdown("<h1 style='text-align:center; "
                    "background: linear-gradient(90deg, #667eea, #764ba2, #f6d365);"
                    "-webkit-background-clip:text; -webkit-text-fill-color:transparent;"
                    "text-shadow:1px 1px 2px rgba(0,0,0,0.1);'>🏠 Admin Home</h1>",
                    unsafe_allow_html=True)
        with sqlite3.connect("database.db") as conn:
            c = conn.cursor()
            c.execute("SELECT COUNT(*) FROM users WHERE role='user'")
            user_count = c.fetchone()[0]
            c.execute("SELECT COUNT(*) FROM ratings")
            rating_count = c.fetchone()[0]
            c.execute("SELECT COUNT(*) FROM complaints WHERE status='Pending'")
            complaint_count = c.fetchone()[0]
        col1, col2, col3 = st.columns(3)
        col1.metric("👤 Users", user_count)
        col2.metric("⭐ Ratings", rating_count)
        col3.metric("📬 Pending Complaints", complaint_count)

    # Users table
    elif option == "Users":
        st.markdown("<h2 style='color:#4facfe;'>👥 Registered Users</h2>", unsafe_allow_html=True)
        with sqlite3.connect("database.db") as conn:
            c = conn.cursor()
            c.execute("SELECT username, email, role FROM users")
            df = pd.DataFrame(c.fetchall(), columns=["Username", "Email", "Role"])
        st.dataframe(df)

    # Ratings table
    elif option == "Ratings":
        st.markdown("<h2 style='color:#f59e0b;'>⭐ Ratings</h2>", unsafe_allow_html=True)
        with sqlite3.connect("database.db") as conn:
            c = conn.cursor()
            c.execute("SELECT user_id, rating, created_at FROM ratings ORDER BY created_at DESC")
            df = pd.DataFrame(c.fetchall(), columns=["User ID", "Rating", "Date"])
        st.dataframe(df)

    # Complaints table
    elif option == "Complaints":
        st.markdown("<h2 style='color:#ef4444;'>📬 Complaints</h2>", unsafe_allow_html=True)
        with sqlite3.connect("database.db") as conn:
            c = conn.cursor()
            c.execute("SELECT id, user_id, complaint, status, created_at FROM complaints ORDER BY created_at DESC")
            complaints = c.fetchall()
        for comp_id, user_id, text, status, date in complaints:
            bg_color = "#d1fae5" if status=="Resolved" else "#fef3c7"
            icon = "✅" if status=="Resolved" else "⚠"
            col1, col2 = st.columns([4,1])
            with col1:
                card(f"{icon} {text} <br> <small>{date}</small>", bg=bg_color, padding=12)
            with col2:
                if status=="Pending":
                    if st.button("Mark Resolved", key=f"resolve_{comp_id}"):
                        with sqlite3.connect("database.db") as conn:
                            c = conn.cursor()
                            c.execute("UPDATE complaints SET status='Resolved' WHERE id=?", (comp_id,))
                            conn.commit()
                        st.experimental_rerun()

    # Logout
    elif option == "Logout":
        if st.button("Confirm Logout"):
            st.session_state.logged_in = False
            st.session_state.page="login"
            st.session_state.role=None
            st.session_state.user_id=None

# ==================== USER WEBSITE ====================
def show_user_website():
    sections = ["home","about","rate","help","logout"]
    cols = st.columns(len(sections))
    for i, sec in enumerate(sections):
        color = "#667eea" if st.session_state.section==sec else "#d1d5db"
        if sec == "logout":
            if cols[i].button("Logout", key=f"nav_{sec}"):
                st.session_state.logged_in = False
                st.session_state.page = "login"
                st.session_state.role = None
                st.session_state.user_id = None
                return
        else:
            if cols[i].button(sec.capitalize(), key=f"nav_{sec}"):
                st.session_state.section = sec

    st.markdown("<hr style='border-top:1px solid #e0e0e0;'>", unsafe_allow_html=True)

    # ------------------ HOME ------------------
    if st.session_state.section == "home":
        st.markdown(
            "<div style='text-align:center;font-size:3rem;font-weight:bold;"
            "background: linear-gradient(90deg, #667eea, #764ba2, #f6d365);"
            "-webkit-background-clip:text;-webkit-text-fill-color:transparent;"
            "text-shadow: 1px 1px 2px rgba(0,0,0,0.1); margin-bottom:25px;'>"
            "🩺 Welcome to PredictNCure</div>",
            unsafe_allow_html=True
        )

        card("<h3>🔍 Predict Your Disease</h3>", bg="#e8f0fe")

        # Load model bundle
        bundle = joblib.load("disease_prediction_bundle.pkl")
        model = bundle["model"]
        mlb = bundle["mlb"]
        label_encoder = bundle["label_encoder"]
        disease_precautions = bundle["disease_precautions"]
        df = pd.read_csv("DiseaseAndSymptoms.csv")
        symptom_cols = [col for col in df.columns if col.lower().startswith("symptom")]
        all_symptoms = sorted(set(symptom for col in symptom_cols for symptom in df[col].dropna().unique() if symptom != ""))
        selected_symptoms = st.multiselect("Select your symptoms(Minimum 4):", all_symptoms)
        if st.button("Predict Disease"):
            if not selected_symptoms:
                st.warning("⚠ Please select at least one symptom.")
            else:
                input_vector = mlb.transform([selected_symptoms])
                prediction = model.predict(input_vector)
                predicted_disease = label_encoder.inverse_transform(prediction)[0]
                st.success(f"✅ Predicted Disease: {predicted_disease}")
                if predicted_disease in disease_precautions:
                    st.subheader("🛡 Recommended Precautions:")
                    for i,p in enumerate(disease_precautions[predicted_disease],1):
                        st.write(f"{i}. {p}")

    # ------------------ ABOUT ------------------
    elif st.session_state.section == "about":
        card(
            "<h2 style='color:#4facfe; font-weight:bold;'>ℹ About PredictNCure</h2>"
            "<p style='font-size:1rem; color:#374151;'>PredictNCure is a professional tool to help users predict diseases based on their symptoms and provides clear, actionable precautions for healthier living.</p>",
            bg="#fef9f9"
        )

    # ------------------ RATE ------------------
    elif st.session_state.section == "rate":
        st.subheader("⭐ Rate Our Service")
        cols_rate = st.columns(5)
        for i in range(5):
            if cols_rate[i].button("★" if i < st.session_state.temp_rating else "☆", key=f"star_{i}"):
                st.session_state.temp_rating = i + 1
        stars_html = "".join([f'<span style="color:{"#ffb400" if i<st.session_state.temp_rating else "#ddd"}; font-size:3rem;">★</span>' for i in range(5)])
        card(stars_html, bg="#fff8e1", padding=12)
        if st.button("Submit Rating"):
            if st.session_state.temp_rating>0:
                with sqlite3.connect("database.db") as conn:
                    c = conn.cursor()
                    c.execute("INSERT INTO ratings(user_id,rating) VALUES (?,?)", (st.session_state.user_id, st.session_state.temp_rating))
                    conn.commit()
                st.success(f"Thank you for rating {st.session_state.temp_rating}★!")
                st.session_state.temp_rating=0
            else:
                st.warning("Please select a rating first.")

    # ------------------ HELP / COMPLAINTS ------------------
    elif st.session_state.section == "help":
        st.subheader("❓ Help / Complaints")
        st.session_state.temp_complaint = st.text_area("Submit a complaint", value=st.session_state.temp_complaint, height=150)
        if st.button("Submit Complaint"):
            if st.session_state.temp_complaint.strip():
                with sqlite3.connect("database.db") as conn:
                    c = conn.cursor()
                    c.execute("INSERT INTO complaints(user_id, complaint) VALUES (?,?)", (st.session_state.user_id, st.session_state.temp_complaint))
                    conn.commit()
                st.success("Complaint submitted successfully!")
                st.session_state.temp_complaint=""
            else:
                st.warning("Please enter a complaint first.")

# ==================== MAIN ROUTER ====================
def main():
    if not st.session_state.logged_in:
        if st.session_state.page=="login":
            show_login()
        elif st.session_state.page=="register":
            show_register()
        elif st.session_state.page=="forgot":
            show_forgot()
    else:
        if st.session_state.role=="admin":
            show_admin_dashboard()
        else:
            show_user_website()

if __name__=="__main__":
    main()
