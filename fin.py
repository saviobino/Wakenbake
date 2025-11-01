# app.py
import streamlit as st
import mysql.connector
from mysql.connector import pooling
import hashlib
from datetime import datetime

st.set_page_config(page_title="Wake 'n Bake", layout="centered")

# ---------- CONFIG ----------
def get_db_config():
    if "mysql" in st.secrets:
        s = st.secrets["mysql"]
        return {
            "host": s.get("host", "localhost"),
            "user": s.get("user", "root"),
            "password": s.get("password", ""),
            "database": s.get("database", "WakeNBake"),
            "port": int(s.get("port", 3306)),
        }
    else:
        # Local fallback
        return {
            "host": "localhost",
            "user": "root",
            "password": "your_password",   # <-- change this
            "database": "WakeNBake",
            "port": 3306,
        }

DB_CONFIG = get_db_config()

# ---------- DB CONNECTION ----------
if "db_pool" not in st.session_state:
    st.session_state.db_pool = pooling.MySQLConnectionPool(
        pool_name="wake_pool", pool_size=3, **DB_CONFIG
    )

def get_conn():
    return st.session_state.db_pool.get_connection()

# ---------- UTILS ----------
def hash_password(plain):
    return hashlib.sha256(plain.encode("utf-8")).hexdigest()

def verify_password(plain, hashed):
    return hash_password(plain) == hashed

# ---------- TABLE SETUP ----------
def ensure_tables():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INT AUTO_INCREMENT PRIMARY KEY,
        username VARCHAR(100) UNIQUE,
        password VARCHAR(255),
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );
    """)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS orders (
        id INT AUTO_INCREMENT PRIMARY KEY,
        username VARCHAR(100),
        item_name VARCHAR(255),
        quantity INT,
        price DECIMAL(10,2),
        total_price DECIMAL(10,2),
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );
    """)
    conn.commit()
    cur.close()
    conn.close()

ensure_tables()

# ---------- DB HELPERS ----------
def create_user(username, password):
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("INSERT INTO users (username, password) VALUES (%s, %s)", (username, hash_password(password)))
        conn.commit()
        return True
    except mysql.connector.IntegrityError:
        return False
    finally:
        cur.close()
        conn.close()

def check_credentials(username, password):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT password FROM users WHERE username=%s", (username,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    if row and verify_password(password, row[0]):
        return True
    return False

def insert_order(username, item_name, qty, price):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO orders (username, item_name, quantity, price, total_price) VALUES (%s, %s, %s, %s, %s)",
        (username, item_name, qty, price, qty * price)
    )
    conn.commit()
    cur.close()
    conn.close()

def fetch_orders(username):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT item_name, quantity, price, total_price, created_at FROM orders WHERE username=%s ORDER BY created_at DESC", (username,))
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows

# ---------- MENU ----------
dictpastries = {
    1: ["Moist chocolate fudge pastry", 150],
    2: ["Belgian chocolate pastry", 175],
    3: ["Red velvet pastry", 125],
    4: ["Blueberry cheese pastry", 100],
    5: ["Wake 'n Bake special truffle pastry", 200]
}
dictcakes = {
    1: ["Blueberry Cheese Cake", 350],
    2: ["Hazelnut Ferrero Cake", 400],
    3: ["Dark Chocolate Excess Cake", 300],
    4: ["Dark Chocolate mousse Cake", 275],
    5: ["Red velvet Cake", 300]
}
dictbev = {
    1: ["Jamaican chocolate frappe", 100],
    2: ["Viennese cold coffee", 150],
    3: ["Vanilla oreo shake", 150],
    4: ["Salted caramel shake", 125],
    5: ["Butterscotch Ice cream shake", 150]
}

# ---------- STATE ----------
if "page" not in st.session_state:
    st.session_state.page = "login"
if "user" not in st.session_state:
    st.session_state.user = None
if "cart" not in st.session_state:
    st.session_state.cart = []

# ---------- PAGES ----------
def login_page():
    st.title("🔐 Login to Wake 'n Bake")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")
    if st.button("Login"):
        if check_credentials(username, password):
            st.session_state.user = username
            st.session_state.page = "home"
            st.success("Login successful!")
            st.experimental_rerun()
        else:
            st.error("Invalid username or password.")

    st.write("Don't have an account?")
    if st.button("Create an account"):
        st.session_state.page = "signup"
        st.experimental_rerun()

def signup_page():
    st.title("🧁 Create Your Account")
    username = st.text_input("Choose a username")
    password = st.text_input("Choose a password", type="password")
    if st.button("Sign Up"):
        if not username or not password:
            st.warning("Please fill out all fields.")
        elif create_user(username, password):
            st.success("Account created! Please login.")
            st.session_state.page = "login"
            st.experimental_rerun()
        else:
            st.error("Username already exists. Try another.")

    if st.button("Back to Login"):
        st.session_state.page = "login"
        st.experimental_rerun()

def home_page():
    st.title("🍰 Wake 'n Bake Menu")
    st.write(f"Welcome, **{st.session_state.user}**!")
    if st.button("Logout"):
        st.session_state.user = None
        st.session_state.page = "login"
        st.experimental_rerun()

    # Helper to render categories
    def render_category(menu, title):
        st.subheader(title)
        cols = st.columns([3,1,1,1])
        cols[0].write("Item")
        cols[1].write("Price")
        cols[2].write("Qty")
        cols[3].write("Add")
        for key, (name, price) in menu.items():
            with st.container():
                c0, c1, c2, c3 = st.columns([3,1,1,1])
                c0.write(name)
                c1.write(f"₹{price}")
                qty = c2.number_input("", min_value=1, max_value=10, value=1, key=f"{title}_{key}_qty")
                if c3.button("Add", key=f"add_{title}_{key}"):
                    st.session_state.cart.append({"item": name, "qty": qty, "price": price})
                    st.success(f"Added {qty} x {name} to cart.")

    render_category(dictpastries, "PASTRIES")
    render_category(dictcakes, "CAKES")
    render_category(dictbev, "BEVERAGES")

    st.write("---")
    st.subheader("🛒 Your Cart")
    if not st.session_state.cart:
        st.info("Cart is empty.")
    else:
        total = 0
        for i, item in enumerate(st.session_state.cart):
            total += item["qty"] * item["price"]
            st.write(f"{item['item']} — {item['qty']} × ₹{item['price']} = ₹{item['qty']*item['price']}")
        st.markdown(f"**Grand Total: ₹{total}**")
        if st.button("Place Order"):
            for item in st.session_state.cart:
                insert_order(st.session_state.user, item["item"], item["qty"], item["price"])
            st.success("Order placed successfully!")
            st.session_state.cart = []
            st.experimental_rerun()

    st.write("---")
    st.subheader("📜 Previous Orders")
    orders = fetch_orders(st.session_state.user)
    if not orders:
        st.info("No orders yet.")
    else:
        for o in orders:
            st.write(f"{o[0]} — {o[1]} × ₹{o[2]} = ₹{o[3]} ({o[4]})")

# ---------- NAVIGATION ----------
if st.session_state.page == "login":
    login_page()
elif st.session_state.page == "signup":
    signup_page()
elif st.session_state.page == "home":
    if not st.session_state.user:
        st.session_state.page = "login"
        st.experimental_rerun()
    home_page()
