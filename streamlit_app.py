# streamlit_app.py
import streamlit as st
import sqlite3
import math
from datetime import datetime, timedelta, timezone

st.set_page_config(page_title="Paytm Nudge Engine", page_icon="⚡", layout="centered")

# --- 1. In-Memory SQLite Setup (Runs automatically on boot) ---
@st.cache_resource
def init_database():
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    cursor = conn.cursor()
    
    cursor.execute("""
    CREATE TABLE merchants (
        store_id TEXT PRIMARY KEY,
        name TEXT,
        lat REAL,
        lon REAL,
        store_aov REAL,
        margin_cap REAL,
        remaining_budget REAL
    )
    """)
    cursor.execute("""
    CREATE TABLE transactions (
        txn_id TEXT PRIMARY KEY,
        store_id TEXT,
        customer_token TEXT,
        amount REAL,
        created_at TIMESTAMP
    )
    """)
    
    # Insert Store
    cursor.execute("INSERT INTO merchants VALUES ('store_gupta_01', 'Gupta General Store', 28.6315, 77.2167, 200.0, 0.15, 1500.0)")
    
    # Insert Transactions
    now = datetime.now(timezone.utc)
    # Ramesh (Regular - 22 visits)
    for i in range(1, 23):
        t_date = now - timedelta(days=i, hours=2)
        cursor.execute("INSERT INTO transactions VALUES (?, 'store_gupta_01', 'cust_ramesh', 65.0, ?)", (f"txn_r_{i}", t_date.isoformat()))
    # Anil (Lapsed - 35+ days)
    for i in [35, 42, 50]:
        t_date = now - timedelta(days=i)
        cursor.execute("INSERT INTO transactions VALUES (?, 'store_gupta_01', 'cust_anil', 180.0, ?)", (f"txn_a_{i}", t_date.isoformat()))
    # Priya (New - 0 visits)
    
    conn.commit()
    return conn

conn = init_database()

# --- 2. 5-Gate Logic ---
def evaluate_coupon(customer_token: str, user_lat: float, user_lon: float):
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM merchants WHERE store_id = 'store_gupta_01'")
    store = cursor.fetchone()
    store_lat, store_lon, store_aov, margin_cap, budget = store[2], store[3], store[4], store[5], store[6]
    
    # Gate 1: Geofence
    R = 6371.0
    dlat = math.radians(user_lat - store_lat)
    dlon = math.radians(user_lon - store_lon)
    a = math.sin(dlat / 2)**2 + math.cos(math.radians(store_lat)) * math.cos(math.radians(user_lat)) * math.sin(dlon / 2)**2
    distance = R * (2 * math.atan2(math.sqrt(a), math.sqrt(1 - a)))
    
    if distance > 1.0:
        return {"issue": False, "segment": "Out-of-range", "val": 0, "min_basket": 0, "reason": f"Customer is {distance:.2f}km away"}

    # Fetch history
    cursor.execute("SELECT created_at FROM transactions WHERE customer_token = ?", (customer_token,))
    rows = cursor.fetchall()
    now = datetime.now(timezone.utc)
    
    visits_30d = 0
    days_since = None
    if rows:
        dates = [datetime.fromisoformat(r[0]) for r in rows]
        visits_30d = sum(1 for d in dates if (now - d).days <= 30)
        days_since = (now - dates[0]).days

    # Gate 3: Classify
    if visits_30d >= 8:
        segment = "Habitual"
        return {"issue": False, "segment": segment, "val": 0, "min_basket": 0, "reason": f"Suppressed: Regular customer ({visits_30d} visits/30d)"}
    elif days_since is None:
        segment = "New"
        val = 25.0
        min_basket = store_aov
    elif days_since >= 21:
        segment = "Lapsed"
        val = 18.0
        min_basket = store_aov
    else:
        segment = "Occasional"
        val = 12.0
        min_basket = store_aov * 1.35

    return {"issue": True, "segment": segment, "val": val, "min_basket": min_basket, "reason": f"Targeted offer for {segment} shopper"}

# --- 3. UI Dashboard ---
st.title("⚡ Paytm Nudge: Smart Coupon Engine")
st.caption("Auto-deployed via GitHub | Pay only for customers you win")

persona = st.selectbox(
    "Select Demo Persona:",
    ("🥛 Ramesh Uncle (Daily Morning Regular)", "🚶 Priya (New Resident to Area)", "😴 Anil (Lapsed Customer - 35 days absent)")
)

mapping = {
    "🥛 Ramesh Uncle (Daily Morning Regular)": "cust_ramesh",
    "🚶 Priya (New Resident to Area)": "cust_priya",
    "😴 Anil (Lapsed Customer - 35 days absent)": "cust_anil"
}

if st.button("Evaluate Coupon Eligibility", type="primary"):
    res = evaluate_coupon(mapping[persona], 28.6316, 77.2168)
    
    col1, col2 = st.columns(2)
    col1.metric("Segment", res["segment"])
    col2.metric("Coupon Value", f"₹{res['val']}")
    
    if res["issue"]:
        st.success(f"🎉 **Coupon Issued!** {res['reason']}")
        st.info(f"🛒 **Min Basket Required:** ₹{res['min_basket']}")
    else:
        st.error(f"🛑 **Coupon Blocked!** {res['reason']}")
        st.warning("💰 **Merchant Margin Saved:** ₹25.00")