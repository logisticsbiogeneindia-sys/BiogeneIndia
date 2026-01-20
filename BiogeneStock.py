import streamlit as st
import pandas as pd
import os
import re
from datetime import datetime
import pytz
import requests
import base64
import io

# -------------------------
# Helpers
# -------------------------
def normalize(s: str) -> str:
    return re.sub(r'[^a-z0-9]', '', str(s).lower())

def find_column(df: pd.DataFrame, candidates: list):
    norm_map = {normalize(col): col for col in df.columns}
    for cand in candidates:
        key = normalize(cand)
        if key in norm_map:
            return norm_map[key]
    for cand in candidates:
        key = normalize(cand)
        for norm_col, orig in norm_map.items():
            if key in norm_col or norm_col in key:
                return orig
    return None

# -------------------------
# Page Config
# -------------------------
st.set_page_config(
    page_title="Biogene India - Inventory Viewer",
    layout="wide"
)

# -------------------------
# Header
# -------------------------
st.markdown("""
<style>
.navbar {
    background:#004a99;
    padding:10px 20px;
    color:white;
    border-radius:8px;
    font-size:24px;
    font-weight:bold;
}
.footer {
    position:fixed;
    bottom:0;
    width:100%;
    background:#004a99;
    color:white;
    text-align:center;
    padding:6px;
}
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="navbar">📦 Biogene India - Inventory Viewer</div>', unsafe_allow_html=True)

# -------------------------
# Sidebar
# -------------------------
st.sidebar.header("⚙️ Settings")

inventory_type = st.sidebar.selectbox(
    "Choose Inventory Type",
    ["Group Stock Sheet", "New Stock Sheet"]
)

password = st.sidebar.text_input("Enter Password", type="password")
correct_password = st.secrets["PASSWORD"]

UPLOAD_PATH = "Master-Stock Sheet Original.xlsx"

# -------------------------
# GitHub Config
# -------------------------
OWNER = "logisticsbiogeneindia-sys"
REPO = "Biogeneindia"
BRANCH = "main"
TOKEN = st.secrets["GITHUB_TOKEN"]

headers = {
    "Authorization": f"Bearer {TOKEN}",
    "Accept": "application/vnd.github+json"
}

# -------------------------
# Load Excel
# -------------------------
@st.cache_data
def load_excel():
    url = f"https://raw.githubusercontent.com/{OWNER}/{REPO}/{BRANCH}/{UPLOAD_PATH.replace(' ', '%20')}"
    r = requests.get(url)
    return pd.ExcelFile(io.BytesIO(r.content))

xl = load_excel()

# -------------------------
# Allowed Sheets
# -------------------------
allowed_sheets = [
    s for s in
    ["Group Stock Sheet", "New Stock Sheet", "Dispatches"]
    if s in xl.sheet_names
]

sheet_name = inventory_type
df = xl.parse(sheet_name)

# -------------------------
# Clean Dummy Zero Row
# -------------------------
customer_col = find_column(df, ["Customer name", "Customer"])
qty_col = find_column(df, ["Qty", "Quantity"])

if customer_col and qty_col:
    df = df[
        ~(
            (df[customer_col].astype(str).str.strip() == "0") &
            (df[qty_col].astype(str).str.strip() == "0")
        )
    ]

# -------------------------
# Check Column Normalize
# -------------------------
check_col = find_column(df, ["Check", "Status", "Type"])

check_vals = df[check_col].astype(str).str.strip().str.lower()

check_vals = check_vals.replace({
    "stock": "stock",
    "local": "local",
    "outstation": "outstation",
    "out station": "outstation",
    "unknown": "unknown"
})

# -------------------------
# Tabs
# -------------------------
tab1, tab2, tab3, tab4, tab5 = st.tabs(
    ["📦 Stock", "🚚 Outstation", "🏠 Local", "❓ Unknown / Other", "🔍 Search"]
)

with tab1:
    st.dataframe(df[check_vals == "stock"], use_container_width=True, height=600)

with tab2:
    st.dataframe(df[check_vals == "outstation"], use_container_width=True, height=600)

with tab3:
    st.dataframe(df[check_vals == "local"], use_container_width=True, height=600)

with tab4:
    st.dataframe(
        df[~check_vals.isin(["stock", "outstation", "local"])],
        use_container_width=True,
        height=600
    )

# -------------------------
# SEARCH
# -------------------------
with tab5:
    st.subheader("🔍 Search Inventory")

    search_sheet = st.selectbox("Select Sheet", allowed_sheets)
    search_df = xl.parse(search_sheet)

    customer_col = find_column(search_df, ["Customer name", "Customer"])
    brand_col = find_column(search_df, ["Brand"])
    remarks_col = find_column(search_df, ["Remarks", "Mohit Remarks"])
    invoice_col = find_column(search_df, ["Invoice Number", "Invoice"])
    date_col = find_column(search_df, ["Goods Recd. Date", "Date"])

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        s_customer = st.text_input("Customer")
    with col2:
        s_brand = st.text_input("Brand")
    with col3:
        s_invoice = st.text_input("Invoice")
    with col4:
        s_remarks = st.text_input("Remarks")

    filtered = search_df.copy()
    searched = False

    if s_customer and customer_col:
        filtered = filtered[filtered[customer_col].astype(str).str.contains(s_customer, case=False, na=False)]
        searched = True

    if s_brand and brand_col:
        filtered = filtered[filtered[brand_col].astype(str).str.contains(s_brand, case=False, na=False)]
        searched = True

    if s_invoice and invoice_col:
        filtered = filtered[filtered[invoice_col].astype(str).str.contains(s_invoice, case=False, na=False)]
        searched = True

    if s_remarks and remarks_col:
        filtered = filtered[filtered[remarks_col].astype(str).str.contains(s_remarks, case=False, na=False)]
        searched = True

    if searched:
        if filtered.empty:
            st.warning("No matching records found.")
        else:
            st.dataframe(filtered, use_container_width=True, height=600)

# -------------------------
# Footer
# -------------------------
st.markdown(
    '<div class="footer">© 2025 Biogene India | Created by Mohit Sharma</div>',
    unsafe_allow_html=True
)
