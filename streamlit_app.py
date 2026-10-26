# streamlit_app.py
import streamlit as st
import sqlite3
import math
import random
from datetime import datetime, timedelta, timezone

st.set_page_config(page_title="Paytm Nudge Engine", page_icon="⚡", layout="centered")

# --- 1. In-Memory Database Initialization ---
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
    # Seed Gupta General Store (AOV: ₹200, Margin Cap: 15%, Budget: ₹1500)
    cursor.execute("INSERT INTO merchants VALUES ('store_gupta_01', 'Gupta General Store', 28.6315, 77.2167, 200.0, 0.15, 1500.0)")
    conn.commit()
    return conn

conn = init_database()

# --- 2. Core Decision Engine Logic (5-Gate Pipeline) ---
def run_engine(visits_30d: int, days_since: int, distance_km: float):
    cursor = conn.cursor()
    cursor.execute("SELECT store_aov, margin_cap, remaining_budget FROM merchants WHERE store_id = 'store_gupta_01'")
    store_aov, margin_cap, budget = cursor.fetchone()

    # Gate 1: Geofence Check (1.0 km radius)
    if distance_km > 1.0:
        return {
            "issue": False,
            "segment": "Out-of-range",
            "val": 0.0,
            "min_basket": 0.0,
            "habit_score": 0.0,
            "reason": f"Customer is {distance_km:.2f} km away (store geofence limit: 1.0 km)"
        }

    # Gate 2 & 3: Relationship Classification
    if visits_30d >= 8:
        segment = "Habitual"
        return {
            "issue": False,
            "segment": segment,
            "val": 0.0,
            "min_basket": 0.0,
            "habit_score": 1.0,
            "reason": f"Suppressed: Customer has strong organic habit ({visits_30d} visits in last 30 days)"
        }
    elif days_since == 999:  # Convention for brand-new customer
        segment = "New"
        val = 25.0
        min_basket = store_aov
        habit_score = 0.0
    elif days_since >= 21:
        segment = "Lapsed"
        val = 18.0
        min_basket = store_aov
        habit_score = 0.10
    else:
        segment = "Occasional"
        norm_freq = min(visits_30d / 12.0, 1.0)
        norm_rec = max(0.0, 1.0 - (days_since / 30.0))
        habit_score = round(0.5 * norm_freq + 0.5 * norm_rec, 2)
        val = round(25.0 * (1.0 - habit_score), 0)
        min_basket = round(store_aov * 1.35, 0)

    # Gate 4 & 5: Margin Guardrail & Budget Protection
    max_discount = store_aov * margin_cap
    final_val = min(val, max_discount, budget)

    return {
        "issue": True,
        "segment": segment,
        "val": round(final_val, 0),
        "min_basket": round(min_basket, 0),
        "habit_score": habit_score,
        "reason": f"Targeted incentive issued for {segment} shopper"
    }

# --- 3. Streamlit User Interface ---
st.title("⚡ Paytm Nudge: Smart Coupon Engine")
st.caption("Don't pay for habits. Pay only for the customers you win.")

tab1, tab2, tab3 = st.tabs(["👥 Pre-built Personas", "🎛️ Test Custom Customer", "📊 1,000 Customer Simulator"])

# --- TAB 1: STORY PERSONAS ---
with tab1:
    st.subheader("Step 1: Evaluate Real-World Shoppers")
    persona = st.selectbox(
        "Choose a Story Persona to Test:",
        [
            "🥛 Ramesh Uncle (Daily Morning Regular - 22 visits)",
            "🚶 Priya (New Resident to Area - 0 visits)",
            "😴 Anil (Lapsed Shopper - 35 days absent)",
            "🛒 Vikram (Occasional Shopper - 2 visits/month)",
            "📍 Sneha (Outside Geofence - 2.5 km away)"
        ]
    )
    
    presets = {
        "🥛 Ramesh Uncle (Daily Morning Regular - 22 visits)": {"visits": 22, "days": 1, "dist": 0.2},
        "🚶 Priya (New Resident to Area - 0 visits)": {"visits": 0, "days": 999, "dist": 0.1},
        "😴 Anil (Lapsed Shopper - 35 days absent)": {"visits": 3, "days": 35, "dist": 0.4},
        "🛒 Vikram (Occasional Shopper - 2 visits/month)": {"visits": 2, "days": 8, "dist": 0.3},
        "📍 Sneha (Outside Geofence - 2.5 km away)": {"visits": 0, "days": 999, "dist": 2.5}
    }
    
    if st.button("Evaluate Persona", type="primary"):
        data = presets[persona]
        res = run_engine(data["visits"], data["days"], data["dist"])
        
        c1, c2 = st.columns(2)
        c1.metric("Classified Segment", res["segment"])
        c2.metric("Coupon Issued", f"₹{res['val']}")
        
        if res["issue"]:
            st.success(f"🎉 **Coupon Issued!** {res['reason']}")
            st.info(f"🛒 **Minimum Basket Required:** ₹{res['min_basket']} (Protects merchant gross margin)")
        else:
            st.error(f"🛑 **Coupon Suppressed!** {res['reason']}")
            st.warning("💰 **Merchant Margin Saved:** ₹25.00")
            
        st.caption(f"Calculated Habit Score: `{res['habit_score']} / 1.0`")

# --- TAB 2: INTERACTIVE CUSTOM SLIDERS ---
with tab2:
    st.subheader("Step 2: Simulate Any Arbitrary Shopper")
    st.write("Adjust the parameters to watch the decision engine react in real time:")
    
    custom_visits = st.slider("Past Visits in Last 30 Days:", min_value=0, max_value=30, value=1)
    custom_days = st.slider("Days Since Last Visit:", min_value=1, max_value=60, value=7)
    custom_dist = st.slider("Distance to Store (km):", min_value=0.1, max_value=4.0, value=0.4, step=0.1)
    
    if st.button("Run Engine on Custom Input"):
        res = run_engine(custom_visits, custom_days, custom_dist)
        
        c1, c2 = st.columns(2)
        c1.metric("Segment", res["segment"])
        c2.metric("Coupon Value", f"₹{res['val']}")
        
        if res["issue"]:
            st.success(f"🎉 **Issued!** {res['reason']}")
            st.info(f"🛒 **Minimum Basket:** ₹{res['min_basket']}")
        else:
            st.error(f"🛑 **Blocked!** {res['reason']}")
            st.warning("💰 **Margin Saved:** ₹25.00")
            
        st.caption(f"Calculated Habit Score: `{res['habit_score']} / 1.0`")

# --- TAB 3: 1,000 CUSTOMER MONTE CARLO SIMULATOR ---
with tab3:
    st.subheader("Step 3: Monte Carlo Simulation (1,000 Customers)")
    st.write("Simulate an entire month of neighborhood footfall: **Old Blind Engine vs. Paytm Nudge Engine**.")
    
    if st.button("Run 1,000-Customer Simulation", type="primary"):
        num_customers = 1000
        flat_coupon = 20.0
        
        # 1. Generate 1,000 synthetic neighborhood shoppers
        customers = []
        for _ in range(num_customers):
            p = random.random()
            if p < 0.55:
                profile = "habitual"
                p_organic, p_coupon = 0.95, 0.98
            elif p < 0.80:
                profile = "occasional"
                p_organic, p_coupon = 0.25, 0.55
            elif p < 0.90:
                profile = "lapsed"
                p_organic, p_coupon = 0.05, 0.35
            else:
                profile = "new"
                p_organic, p_coupon = 0.02, 0.40
            customers.append({"profile": profile, "p_org": p_organic, "p_coup": p_coupon})
        
        # 2. Run Old Blind Engine
        old_spend = num_customers * flat_coupon
        old_wasted = sum(flat_coupon for c in customers if c["profile"] == "habitual")
        old_acquired = sum(1 for c in customers if c["profile"] in ["new", "lapsed"] and random.random() < c["p_coup"])
        
        # 3. Run Paytm Nudge Engine
        smart_spend = 0.0
        smart_wasted = 0.0
        smart_acquired = 0
        for c in customers:
            if random.random() < 0.10:  # 10% Holdout Control Group
                continue
            if c["profile"] == "habitual":
                coupon = 0.0
                visited = random.random() < c["p_org"]
            elif c["profile"] == "occasional":
                coupon = 12.0
                visited = random.random() < c["p_coup"]
            elif c["profile"] == "lapsed":
                coupon = 15.0
                visited = random.random() < c["p_coup"]
            else:  # New
                coupon = 20.0
                visited = random.random() < c["p_coup"]
                
            smart_spend += coupon
            if visited and c["profile"] in ["new", "lapsed"]:
                smart_acquired += 1
                
        old_cac = old_spend / max(old_acquired, 1)
        smart_cac = smart_spend / max(smart_acquired, 1)
        
        # 4. Display Results Table & Metrics
        col1, col2, col3 = st.columns(3)
        col1.metric("Budget Spent", f"₹{smart_spend:,.0f}", delta=f"-₹{old_spend - smart_spend:,.0f} Saved", delta_color="normal")
        col2.metric("Wasted on Regulars", f"₹{smart_wasted:,.0f}", delta=f"-₹{old_wasted:,.0f} Eliminated", delta_color="normal")
        col3.metric("Cost Per Acquisition", f"₹{smart_cac:.1f}", delta=f"-₹{old_cac - smart_cac:.1f} Cheaper", delta_color="normal")
        
        efficiency_multiplier = old_cac / max(smart_cac, 1)
        st.success(f"🎯 **Acquisition Efficiency Gain:** Acquired new and lapsed customers **{efficiency_multiplier:.1f}x cheaper** compared to the old engine!")
        
        # Summary Data Table
        st.table({
            "Metric": [
                "Total Budget Spent",
                "Cashback Wasted on Regulars",
                "New / Lapsed Customers Won",
                "Cost per Acquired Customer"
            ],
            "Old Engine": [
                f"₹{old_spend:,.0f}",
                f"₹{old_wasted:,.0f}",
                f"{old_acquired}",
                f"₹{old_cac:.1f}"
            ],
            "Paytm Nudge Engine": [
                f"₹{smart_spend:,.0f}",
                f"₹{smart_wasted:,.0f}",
                f"{smart_acquired}",
                f"₹{smart_cac:.1f}"
            ]
        })
