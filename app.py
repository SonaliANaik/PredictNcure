import streamlit as st
import sqlite3
import re
import pandas as pd
import numpy as np
import joblib
import socket
import os
import ast
from fuzzywuzzy import process
from streamlit_tags import st_tags
import gdown
import os

def download_if_missing_drive(file_id, filename):
    """Download file from Google Drive if it doesn't exist locally"""
    if not os.path.exists(filename):
        with st.spinner(f"Downloading {filename} from Google Drive..."):
            url = f"https://drive.google.com/uc?id={file_id}"
            gdown.download(url, filename, quiet=False)

try:
    import dns.resolver
except Exception:
    dns = None

# ---------------- PAGE CONFIG ----------------
st.set_page_config(page_title="PredictNCure", layout="wide")

# ---------------- DB INIT ----------------
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
        conn.commit()

init_db()

# ---------------- SESSION DEFAULTS ----------------
for key in ["page","logged_in","role","user_id","section","temp_rating","admin_option","symptom_input_reset"]:
    if key not in st.session_state:
        st.session_state[key] = (
            "login" if key == "page" else
            "home" if key == "section" else
            0 if key == "temp_rating" else
            None if key == "role" else
            False if key == "logged_in" else 0
        )

# ---------------- HELPERS ----------------
def normalize_key(text: str) -> str:
    if not text:
        return ""
    return re.sub(r'[\s_\-]+', '', text.lower().strip())

def get_info(info_dict, disease_name):
    norm = normalize_key(disease_name)
    for k, v in info_dict.items():
        if normalize_key(k) == norm:
            return v
    return "No data"

def card(content, bg="#f5f7fa", padding=20):
    st.markdown(f"""
        <div style='background-color:{bg}; padding:{padding}px; border-radius:12px;
        box-shadow:0 4px 12px rgba(0,0,0,0.06); margin-bottom:12px;'>
        {content}
        </div>
    """, unsafe_allow_html=True)

def clean_description_paragraph(text):
    if not text:
        return "No data available."
    try:
        parsed = ast.literal_eval(text)
        if isinstance(parsed, list):
            return " ".join(parsed)
        return str(parsed)
    except:
        return str(text)

def clean_and_bullet(text):
    if not text:
        return "- No data"
    try:
        parsed = ast.literal_eval(text)
        items = parsed if isinstance(parsed, list) else [parsed]
    except:
        items = re.split(r',|;|\.', str(text))
    cleaned = []
    for item in items:
        item = item.strip().replace("[", "").replace("]", "").replace("'", "").replace('"', "")
        if item:
            cleaned.append(item)
    return "- No data" if not cleaned else "- " + "\n- ".join(cleaned)

def validate_username(username: str) -> bool:
    if not username or len(username.strip()) < 5:
        return False
    if not username.strip()[0].isalpha():
        return False
    if re.search(r'\d', username):
        return False
    return True

def validate_password(password: str) -> bool:
    if not password or len(password) < 6:
        return False
    if " " in password:
        return False
    return True

def validate_email_real(email: str):
    if not re.match(r"^[^@]+@[^@]+\.[^@]+$", email):
        return False, "Invalid email format."
    domain = email.split('@')[1]
    if dns:
        try:
            dns.resolver.resolve(domain, 'MX')
            return True, ""
        except Exception:
            try:
                socket.gethostbyname(domain)
                return True, ""
            except Exception:
                return False, "Email domain does not resolve."
    else:
        try:
            socket.gethostbyname(domain)
            return True, ""
        except Exception:
            return False, "Email domain does not resolve."

# ---------------- LOAD RESOURCES ----------------
@st.cache_resource
def load_resources():
    # Download both models from Google Drive if missing
    download_if_missing_drive("1i2G2cUL-OLr-H1x3hqRJB-qrO6K_Um_9", "lgb_fast.pkl")
    download_if_missing_drive("1Y4TOBbA862rYfN_2aZbtu1RvzfZ3rLs2", "xgb_fast.pkl")

    model_files = ["lgb_fast.pkl", "xgb_fast.pkl"]
    enc_files = ["disease_encoder.pkl"]

    # Your existing code for loading encoder and dataset
    model_path = next((x for x in model_files if os.path.exists(x)), None)
    enc_path = next((x for x in enc_files if os.path.exists(x)), None)

    if not model_path or not enc_path:
        st.error("Model or encoder missing in root folder.")
        st.stop()

    model = joblib.load(model_path)
    le = joblib.load(enc_path)

    dataset_path = "Diseases_and_Symptoms_dataset.csv"
    if os.path.exists(dataset_path):
        df = pd.read_csv(dataset_path)
        symptom_cols = [c for c in df.columns if c.lower() not in ("diseases","disease")]
    else:
        st.error("Dataset missing: Diseases_and_Symptoms_dataset.csv not found.")
        st.stop()

    # Load info CSVs
    def load_map(path):
        if not os.path.exists(path):
            return {}
        table = pd.read_csv(path)
        if table.shape[1] < 2:
            return {}
        keys = table.iloc[:, 0].astype(str).apply(normalize_key)
        values = table.iloc[:, 1].astype(str).str.strip()
        return dict(zip(keys, values))

    info = {
        "description": load_map("description.csv"),
        "precautions": load_map("precautions.csv"),
        "medications": load_map("medications.csv"),
        "diets": load_map("diets.csv"),
        "workout": load_map("workout.csv")
    }

    return model, le, symptom_cols, info

# ---------------- AUTH PAGES ----------------
def show_login():
    st.title("🔐 Login")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")
    if st.button("Login"):
        if not username or not password:
            st.warning("Please fill all fields.")
        else:
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
    if col1.button("New User? Register"): st.session_state.page = "register"
    if col2.button("Forgot Password?"): st.session_state.page = "forgot"

def show_register():
    st.title("📝 Register")
    username = st.text_input("Username (min 5 chars, start with letter, no numbers)")
    email = st.text_input("Email")
    password = st.text_input("Password (min 6 chars, no spaces)", type="password")
    confirm = st.text_input("Confirm Password", type="password")
    if st.button("Register"):
        if not all([username, email, password, confirm]):
            st.warning("Please fill all fields.")
        elif not validate_username(username):
            st.warning("Invalid username: must be >=5 chars, start with letter, and not contain numbers.")
        else:
            ok, msg = validate_email_real(email)
            if not ok:
                st.warning(f"Invalid email: {msg}")
            elif not validate_password(password):
                st.warning("Invalid password: min 6 chars and no spaces.")
            elif password != confirm:
                st.warning("Passwords do not match.")
            else:
                try:
                    with sqlite3.connect("database.db") as conn:
                        c = conn.cursor()
                        c.execute("INSERT INTO users (username,password,email,role) VALUES (?,?,?,?)",
                                  (username, password, email, "user"))
                        conn.commit()
                    st.success("Registration successful! Please login.")
                    st.session_state.page = "login"
                except sqlite3.IntegrityError:
                    st.error("Username already exists.")
    if st.button("🔙 Back to Login"): st.session_state.page = "login"

def show_forgot():
    st.title("🔑 Forgot Password")
    email = st.text_input("Enter your registered Email")
    new_pass = st.text_input("New Password", type="password")
    confirm_pass = st.text_input("Confirm New Password", type="password")
    if st.button("Reset Password"):
        if not email or not new_pass or not confirm_pass:
            st.warning("Please fill all fields.")
        elif new_pass != confirm_pass:
            st.warning("Passwords do not match.")
        else:
            with sqlite3.connect("database.db") as conn:
                c = conn.cursor()
                c.execute("SELECT * FROM users WHERE email=?", (email,))
                user = c.fetchone()
                if user:
                    c.execute("UPDATE users SET password=? WHERE email=?", (new_pass, email))
                    conn.commit()
                    st.success("Password updated! Please login.")
                    st.session_state.page = "login"
                else:
                    st.error("Email not found.")
    if st.button("🔙 Back to Login"): st.session_state.page = "login"

# ---------------- ADMIN DASHBOARD ----------------
def show_admin_dashboard():
    st.sidebar.title("📊 Admin Dashboard")
    options = ["Home", "Users", "Ratings", "Logout"]
    st.session_state.admin_option = st.sidebar.radio("Navigate", options)
    if st.session_state.admin_option == "Home":
        st.markdown("<h1 style='text-align:center;'>🏠 Admin Home</h1>", unsafe_allow_html=True)
        with sqlite3.connect("database.db") as conn:
            c = conn.cursor()
            c.execute("SELECT COUNT(*) FROM users WHERE role='user'")
            user_count = c.fetchone()[0]
            c.execute("SELECT COUNT(*) FROM ratings")
            rating_count = c.fetchone()[0]
        col1, col2 = st.columns(2)
        col1.metric("👥 Users", user_count)
        col2.metric("⭐ Ratings", rating_count)
    elif st.session_state.admin_option == "Users":
        st.title("👥 Registered Users")
        with sqlite3.connect("database.db") as conn:
            df = pd.read_sql_query("SELECT username,email,role FROM users", conn)
        st.dataframe(df)
    elif st.session_state.admin_option == "Ratings":
        st.title("⭐ Ratings")
        with sqlite3.connect("database.db") as conn:
            df = pd.read_sql_query("SELECT user_id,rating,created_at FROM ratings", conn)
        st.dataframe(df)
    elif st.session_state.admin_option == "Logout":
        if st.button("Confirm Logout"):
            st.session_state.logged_in = False
            st.session_state.role = None
            st.session_state.page = "login"

# ---------------- USER WEBSITE ----------------
def show_user_website():
    model, le, symptom_cols, info = load_resources()
    st.session_state.setdefault("section", "home")

    sections = ["home", "about", "rate", "logout"]
    cols = st.columns(len(sections))
    for i, sec in enumerate(sections):
        if sec == "logout":
            if cols[i].button("Logout"):
                st.session_state.logged_in = False
                st.session_state.page = "login"
                st.session_state.role = None
                return
        else:
            if cols[i].button(sec.capitalize()):
                st.session_state.section = sec
    st.markdown("<hr>", unsafe_allow_html=True)

    # ---------------- HOME ----------------
    if st.session_state.section == "home":
        st.markdown("<h1 style='text-align:center;'>🩺 Welcome to PredictNCure</h1>", unsafe_allow_html=True)
        st.subheader("Enter your symptoms")

        input_symptoms = st_tags(
            label="",
            text='Type each symptom and press enter',
            value=[],
            suggestions=symptom_cols,
            maxtags=10,
            key=f"symptom_input_{st.session_state.symptom_input_reset}"
        )

        col_pred, col_clear = st.columns(2)
        with col_pred:
            if st.button("Predict"):
                if len(input_symptoms) < 3:
                    st.warning("⚠ Please enter at least 3 symptoms for a more reliable prediction.")
                else:
                    matched_symptoms = []
                    for s in input_symptoms:
                        match, score = process.extractOne(s, symptom_cols)
                        if score >= 70:
                            matched_symptoms.append(match)
                        else:
                            st.error(f"Sorry, we couldn't find '{s}' in our database.")
                            matched_symptoms = []
                            break

                    if matched_symptoms:
                        X = np.array([1 if sym in matched_symptoms else 0 for sym in symptom_cols])
                        probs = model.predict_proba([X])[0]
                        top_idx = np.argsort(probs)[::-1][:5]
                        primary_idx = top_idx[0]
                        primary = le.inverse_transform([primary_idx])[0]
                        conf = probs[primary_idx] * 100

                        min_conf = 75.0
                        if conf < min_conf:
                            st.warning(f"⚠ Prediction confidence is low ({conf:.2f}%). Please add more or different symptoms.")
                        else:
                            st.success(f"Primary Disease: {primary} ({conf:.2f}%)")

                            st.subheader("Other Possible Diseases")
                            allowed_gap = 15
                            others = []
                            for idx in top_idx[1:]:
                                conf_other = probs[idx] * 100
                                if (conf - conf_other) <= allowed_gap:
                                    others.append((le.inverse_transform([idx])[0], conf_other))

                            if others:
                                for nm, cval in others:
                                    st.info(f"{nm} — {cval:.2f}%")
                            else:
                                st.warning("No other close-probability diseases.")

                            st.subheader("Recommendations")
                            with st.expander("📋 Description"):
                                st.markdown(clean_description_paragraph(get_info(info["description"], primary)))
                            with st.expander("💊 Medications"):
                                st.markdown(clean_and_bullet(get_info(info["medications"], primary)))
                            with st.expander("🍎 Diet"):
                                st.markdown(clean_and_bullet(get_info(info["diets"], primary)))
                            with st.expander("🛡 Precautions"):
                                st.markdown(clean_and_bullet(get_info(info["precautions"], primary)))
                            with st.expander("💪 Workout"):
                                st.markdown(clean_and_bullet(get_info(info["workout"], primary)))

        with col_clear:
            if st.button("Clear"):
                st.session_state.symptom_input_reset += 1
 
    # ---------------- ABOUT ----------------
    elif st.session_state.section == "about":
        st.markdown(
        "<h1 style='text-align:center; color:#2c5aa0; font-size:3em; margin-bottom:10px;'>🩺 About PredictNCure</h1>",
        unsafe_allow_html=True
        )

        about_html = """
        <div style='font-family: "Segoe UI", sans-serif; max-width: 800px; margin: 0 auto;'>
        <p style='font-size: 1.3em; line-height: 1.6; color: #333; margin-bottom: 30px;'>
           PredictNCure 🌿 is your calm companion for health insights that turns symptoms into possible diseases and provides clear and gentle guidance. 
        </p>

        <div style='background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
                    padding: 25px; border-radius: 15px; margin: 20px 0;'>
            <h2 style='color: #f39c12; font-size: 1.8em; margin-bottom: 15px;'>✨ What We Do</h2>
            <ul style='font-size: 1.2em; line-height: 1.8; color: #555;'>
                <li>🩺 Smart symptom matching with fuzzy search</li>
                <li>📊 Disease predictions + confidence scores</li>
                <li>💡 Description, Medications, Diets, Precautions & Workout tips</li>
            </ul>
        </div>

        <div style='background: #fff3cd; padding: 20px; border-left: 5px solid #ffc107;
                    border-radius: 8px; font-size: 1.1em; line-height: 1.6; color: #856404;'>
            <strong>❤ Important:</strong> PredictNCure supports awareness —<em> not a doctor replacement</em>.
            Always consult healthcare professionals for diagnosis & treatment.
        </div>
        </div>
        """

        st.markdown(about_html, unsafe_allow_html=True)
   
    # ---------------- RATE ----------------
    elif st.session_state.section == "rate":
        st.subheader("⭐ Rate Our Service")
        with sqlite3.connect("database.db") as conn:
            c = conn.cursor()
            c.execute("SELECT COUNT(*) FROM ratings WHERE user_id=?", (st.session_state.user_id,))
            already_rated = c.fetchone()[0] > 0
        if already_rated:
            st.info("You have already rated our service. Thank you! ⭐")
        else:
            cols_rate = st.columns(5)
            for i in range(5):
                if cols_rate[i].button("★" if i < st.session_state.temp_rating else "☆", key=f"star_{i}"):
                    st.session_state.temp_rating = i + 1
            stars_html = "".join([f'<span style="color:{"#ffb400" if i<st.session_state.temp_rating else "#ddd"}; font-size:3rem;">★</span>' for i in range(5)])
            card(stars_html, bg="#fff8e1", padding=12)
            if st.button("Submit Rating"):
                if st.session_state.temp_rating > 0:
                    with sqlite3.connect("database.db") as conn:
                        c = conn.cursor()
                        c.execute("INSERT INTO ratings(user_id,rating) VALUES (?,?)", (st.session_state.user_id, st.session_state.temp_rating))
                        conn.commit()
                    st.success(f"Thank you for rating {st.session_state.temp_rating}★!")
                    st.session_state.temp_rating = 0
                else:
                    st.warning("Please select a rating first.")
                    
# ---------------- MAIN ----------------
def main():
    if not st.session_state.logged_in:
        if st.session_state.page == "login":
            show_login()
        elif st.session_state.page == "register":
            show_register()
        elif st.session_state.page == "forgot":
            show_forgot()
    else:
        if st.session_state.role == "admin":
            show_admin_dashboard()
        else:
            show_user_website()

if __name__ == "__main__":
    main()