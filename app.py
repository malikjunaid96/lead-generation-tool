"""
Lead Generation Tool - Streamlit app.

Search Google Maps (via the Places API (New)) for a business type + area,
then look up a public contact email for each result by scanning its website,
and export everything to CSV or Excel.
"""
import os
import time
from io import BytesIO

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

from email_scraper import scrape_emails_from_website
from google_maps_client import GoogleMapsClient, parse_place

load_dotenv()

COLUMN_ORDER = ["Business Name", "Phone Number", "Website", "Email", "Address", "Google Maps URL"]

st.set_page_config(page_title="Lead Generation Tool", page_icon="🧲", layout="wide")

# Password protection - Use Streamlit secrets or environment variables
try:
    PASSWORD = st.secrets["APP_PASSWORD"]
except (KeyError, FileNotFoundError):
    PASSWORD = os.getenv("APP_PASSWORD", "Junaid8085")

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

def check_password():
    """Password protection for the app."""
    if st.session_state.authenticated:
        return True
    
    st.title("🔐 Lead Generation Tool - Login")
    st.write("Please enter the password to access the Lead Generation Tool.")
    
    password_input = st.text_input("Password", type="password", key="password_input")
    login_button = st.button("Login")
    
    if login_button:
        if password_input == PASSWORD:
            st.session_state.authenticated = True
            st.success("✅ Login successful! Redirecting...")
            st.rerun()
        else:
            st.error("❌ Incorrect password. Please try again.")
    
    return False

# Check authentication before showing main app
if not check_password():
    st.stop()

# Main app starts here
st.title("🧲 Lead Generation Tool")
st.caption("Find businesses on Google Maps, then automatically look up their public email address.")

if "results_df" not in st.session_state:
    st.session_state.results_df = None

# API key - Try to get from Streamlit secrets first (for cloud), then environment, then allow manual input
try:
    api_key = st.secrets["GOOGLE_MAPS_API_KEY"]
except (KeyError, FileNotFoundError):
    api_key = os.getenv("GOOGLE_MAPS_API_KEY", "")

with st.sidebar:
    st.header("Settings")
    
    # Logout button
    if st.button("🚪 Logout", use_container_width=True):
        st.session_state.authenticated = False
        st.rerun()
    
    st.divider()
    
    # Allow manual API key input if not set
    if not api_key:
        api_key = st.text_input("🔑 Google Maps API Key", type="password", help="Enter your Google Maps API key")
    else:
        if st.checkbox("Use custom API key"):
            api_key = st.text_input("🔑 Custom Google Maps API Key", type="password", value=api_key)
    
    # Show API key status
    if api_key:
        st.success("✅ API Key Active")
    else:
        st.error("❌ No API Key Found")
    
    # UPDATED: Changed value=20 to value=60 so it defaults to fetching the maximum amount.
    max_results = st.slider("Max businesses to fetch", min_value=5, max_value=60, value=60, step=5)
    
    scrape_delay = st.slider(
        "Delay between website visits (seconds)", min_value=0.5, max_value=5.0, value=1.5, step=0.5
    )
    st.caption("A short delay between site visits is more polite and less likely to get blocked.")
    
    st.divider()
    st.subheader("Filters")
    show_no_website = st.checkbox(
        "Show only businesses WITHOUT a website",
        value=False,
        help="Filter to show only businesses that don't have a listed website"
    )

col1, col2 = st.columns(2)
with col1:
    business_type = st.text_input("Target Business", placeholder="e.g. Roofers, Coffee Shops")
with col2:
    location = st.text_input("Target Area", placeholder="e.g. Austin, TX")

start = st.button("🚀 Start Lead Generation", type="primary", use_container_width=True)

if start:
    if not api_key:
        st.error("Please enter your Google Maps API key in the sidebar.")
    elif not business_type or not location:
        st.error("Please enter both a target business and a target area.")
    else:
        query = f"{business_type} in {location}"
        client = GoogleMapsClient(api_key)
        places = []

        with st.spinner(f"Searching Google Maps for \u201c{query}\u201d..."):
            try:
                places = client.search_places(query, max_results=max_results)
            except Exception as exc:
                st.error(f"Couldn't reach the Google Places API: {exc}")

        if not places:
            st.warning("No results found (or the search failed above) - try a different business type or area.")
        else:
            st.success(f"Found {len(places)} businesses. Now looking up emails on their websites...")
            progress = st.progress(0.0)
            status = st.empty()
            rows = []

            for i, place in enumerate(places):
                row = parse_place(place)
                status.text(f"({i + 1}/{len(places)}) {row['Business Name'] or 'Unnamed business'}")

                email = ""
                if row["Website"]:
                    try:
                        email = scrape_emails_from_website(row["Website"], delay=scrape_delay) or ""
                    except Exception:
                        email = ""

                row["Email"] = email
                rows.append(row)
                progress.progress((i + 1) / len(places))
                time.sleep(scrape_delay)

            status.empty()
            df = pd.DataFrame(rows)[COLUMN_ORDER]
            st.session_state.results_df = df
            st.success("Done!")

if st.session_state.results_df is not None:
    df = st.session_state.results_df
    
    # Apply filters
    filtered_df = df.copy()
    if show_no_website:
        filtered_df = filtered_df[filtered_df["Website"] == ""]
    
    found_emails = int((filtered_df["Email"] != "").sum())
    
    # Show filter status if applied
    if show_no_website:
        st.subheader(f"Results ({len(filtered_df)} leads without website)")
        st.caption(f"Showing {len(filtered_df)} of {len(df)} total businesses (no website). {found_emails} had a findable email.")
    else:
        st.subheader(f"Results ({len(filtered_df)} leads)")
        st.caption(f"{found_emails} of {len(filtered_df)} businesses had a findable public email address.")
    
    st.dataframe(filtered_df, use_container_width=True, hide_index=True)

    dl_col1, dl_col2 = st.columns(2)

    csv_bytes = filtered_df.to_csv(index=False).encode("utf-8")
    dl_col1.download_button(
        "\u2b07\ufe0f Download as CSV",
        data=csv_bytes,
        file_name="leads.csv",
        mime="text/csv",
        use_container_width=True,
    )

    xlsx_buffer = BytesIO()
    with pd.ExcelWriter(xlsx_buffer, engine="openpyxl") as writer:
        filtered_df.to_excel(writer, index=False, sheet_name="Leads")
    dl_col2.download_button(
        "\u2b07\ufe0f Download as Excel",
        data=xlsx_buffer.getvalue(),
        file_name="leads.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )
