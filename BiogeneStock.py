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

def find_column(df: pd.DataFrame, candidates: list) -> str | None:
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
# Config & Styling
# -------------------------
st.set_page_config(page_title="Biogene India - Inventory Viewer", layout="wide")
st.markdown("""
<style>
body {background-color: #f8f9fa; font-family: "Helvetica Neue", sans-serif;}
.navbar { display: flex; align-items: center; background-color: #004a99; padding: 8px 16px; border-radius: 8px; color: white; position: sticky; top: 0; z-index: 1000; }
.navbar img { height: 50px; margin-right: 15px; }
.navbar h1 { font-size: 24px; margin: 0; font-weight: 700; }
.footer { position: fixed; left: 0; bottom: 0; width: 100%; background-color: #004a99; color: white; text-align: center; padding: 8px; font-size: 14px; }
</style>
""", unsafe_allow_html=True)

# -------------------------
# Logo + Title Navbar
# -------------------------
logo_path = "logonew.png"
if os.path.exists(logo_path):
    logo_html = f'<img src="data:image/png;base64,{base64.b64encode(open(logo_path,"rb").read()).decode()}" alt="Logo">'
else:
    logo_html = ""

st.markdown(f"""
<div class="navbar">
    {logo_html}
    <h1>📦 Biogene India - Inventory Viewer</h1>
</div>
""", unsafe_allow_html=True)

# -------------------------
# Sidebar
# -------------------------
st.sidebar.header("⚙️ Settings")
inventory_type = st.sidebar.selectbox("Choose Inventory Type", ["Current Inventory", "Item Wise Current Inventory"])
password = st.sidebar.text_input("Enter Password to Upload/Download File", type="password")
correct_password = st.secrets["PASSWORD"]

UPLOAD_PATH = "Master-Stock Sheet Original.xlsx"
TIMESTAMP_PATH = "timestamp.txt"
FILENAME_PATH = "uploaded_filename.txt"

def save_timestamp(timestamp):
    with open(TIMESTAMP_PATH, "w") as f:
        f.write(timestamp)

def save_uploaded_filename(filename):
    with open(FILENAME_PATH, "w") as f:
        f.write(filename)

def load_uploaded_filename():
    if os.path.exists(FILENAME_PATH):
        with open(FILENAME_PATH, "r") as f:
            return f.read().strip()
    return "uploaded_inventory.xlsx"

# -------------------------
# GitHub Config
# -------------------------
OWNER = "logisticsbiogeneindia-sys"
REPO = "BiogeneIndia"
BRANCH = "main"
TOKEN = st.secrets["GITHUB_TOKEN"]
headers = {"Authorization": f"Bearer {TOKEN}", "Accept": "application/vnd.github+json"}

def check_github_auth():
    r = requests.get("https://api.github.com/user", headers=headers)
    if r.status_code == 200:
        st.sidebar.success(f"🔑 GitHub Auth OK: {r.json().get('login')}")
    else:
        st.sidebar.error(f"❌ GitHub Auth failed: {r.status_code}")

check_github_auth()

# -------------------------
# GitHub Push Function
# -------------------------
def push_to_github(local_file, remote_path, commit_message="Update file"):
    try:
        with open(local_file, "rb") as f:
            content = base64.b64encode(f.read()).decode("utf-8")
        url = f"https://api.github.com/repos/{OWNER}/{REPO}/contents/{remote_path}"
        r = requests.get(url, headers=headers)
        sha = r.json().get("sha") if r.status_code == 200 else None
        payload = {"message": commit_message, "content": content, "branch": BRANCH}
        if sha:
            payload["sha"] = sha
        r = requests.put(url, headers=headers, json=payload)
        if r.status_code in [200, 201]:
            st.sidebar.success(f"✅ {os.path.basename(local_file)} pushed to GitHub successfully!")
        else:
            st.sidebar.error(f"❌ GitHub push failed for {local_file}: {r.json()}")
    except Exception as e:
        st.sidebar.error(f"Error pushing file {local_file}: {e}")

# -------------------------
# GitHub Timestamp
# -------------------------
def get_github_file_timestamp():
    try:
        url = f"https://raw.githubusercontent.com/{OWNER}/{REPO}/{BRANCH}/timestamp.txt"
        r = requests.get(url)
        if r.status_code == 200:
            return r.text.strip()
        else:
            return "No GitHub timestamp found."
    except Exception as e:
        return f"Error fetching timestamp: {e}"

github_timestamp = get_github_file_timestamp()
st.markdown(f"🕒 **Last Updated (from GitHub):** {github_timestamp}")

# -------------------------
# Upload & Download Section
# -------------------------
if password == correct_password:
    uploaded_file = st.sidebar.file_uploader("Upload Excel File", type=["xlsx", "xls"])

    if uploaded_file is not None:
        with st.spinner("Uploading file..."):
            with open(UPLOAD_PATH, "wb") as f:
                f.write(uploaded_file.getbuffer())

            timezone = pytz.timezone("Asia/Kolkata")
            upload_time = datetime.now(timezone).strftime("%d-%m-%Y %H:%M:%S")
            save_timestamp(upload_time)
            save_uploaded_filename(uploaded_file.name)

            st.sidebar.success(f"✅ File uploaded at {upload_time}")
            push_to_github(UPLOAD_PATH, "Master-Stock Sheet Original.xlsx", commit_message=f"Uploaded {uploaded_file.name}")
            push_to_github(TIMESTAMP_PATH, "timestamp.txt", commit_message="Updated timestamp")

    if os.path.exists(UPLOAD_PATH):
        with open(UPLOAD_PATH, "rb") as f:
            st.sidebar.download_button(
                label="⬇️ Download Uploaded Excel File",
                data=f,
                file_name=load_uploaded_filename(),
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
else:
    if password:
        st.sidebar.error("❌ Incorrect password!")

# -------------------------
# Load Excel
# -------------------------
@st.cache_data
def load_data_from_github():
    url = f"https://raw.githubusercontent.com/{OWNER}/{REPO}/{BRANCH}/{UPLOAD_PATH.replace(' ', '%20')}"
    r = requests.get(url)
    return pd.ExcelFile(io.BytesIO(r.content))

if not os.path.exists(UPLOAD_PATH):
    try:
        xl = load_data_from_github()
    except Exception as e:
        st.error(f"❌ Error loading Excel from GitHub: {e}")
        st.stop()  # Stops further execution if file loading fails
else:
    xl = pd.ExcelFile(UPLOAD_PATH)

# -------------------------
# Allowed sheets
# -------------------------
allowed_sheets = [s for s in ["Current Inventory", "Item Wise Current Inventory", "Dispatches"] if s in xl.sheet_names]
if not allowed_sheets:
    st.error("❌ No valid sheets found in file! Please upload a file with the required sheets.")
    st.stop()  # Stop further execution if no valid sheets are found

sheet_name = inventory_type
if sheet_name not in xl.sheet_names:
    st.error(f"❌ Sheet '{sheet_name}' not found in the uploaded file!")
    st.stop()

df = xl.parse(sheet_name)

# Handle missing columns
check_col = find_column(df, ["Check", "Location", "Status", "Type", "StockType"])
if not check_col:
    st.warning("❌ 'Check' column not found in the data. Please check the file for missing columns.")
    st.stop()  # Stop further execution if critical column is missing

# -------------------------
# Tabs
# -------------------------
tab1, tab2, tab3, tab4 = st.tabs(["🏠 Local", "🚚 Outstation", "📦 Other", "🔍 Search"])

if check_col and sheet_name != "Dispatches":
    check_vals = df[check_col].astype(str).str.strip().str.lower()
    with tab1:
        st.subheader("🏠 Local Inventory")
        st.dataframe(df[check_vals == "local"], use_container_width=True, height=600)
    with tab2:
        st.subheader("🚚 Outstation Inventory")
        st.dataframe(df[check_vals == "outstation"], use_container_width=True, height=600)
    with tab3:
        st.subheader("📦 Other Inventory")
        st.dataframe(df[~check_vals.isin(["local", "outstation"])], use_container_width=True, height=600)
else:
    with tab1:
        st.subheader("📄 No Inventory Data Available")

# -------------------------
# Search Tab
# -------------------------
with tab4:
    search_text = st.text_input("Search Inventory", placeholder="Search by any field (e.g. name, type, etc.)")
    if search_text:
        df_filtered = df[df.apply(lambda row: row.astype(str).str.contains(search_text, case=False).any(), axis=1)]
        if df_filtered.empty:
            st.warning("No matching records found.")
        else:
            st.dataframe(df_filtered, use_container_width=True, height=600)


# -------------------------
# Footer
# -------------------------
st.markdown("""
<div class="footer">
    © 2025 Biogene India | Created By Mohit Sharma
</div>
""", unsafe_allow_html=True)
