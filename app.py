"""
JD Tech Solutions - Lead Engine & AI Growth Platform
Author: Junaid ur Rehman (JD Tech Solutions)
Upgrades Included:
1. 1-Click WhatsApp Direct Chat with pre-filled AI pitch
2. Google Rating & Review Count quality filters
3. Multi-City & Multi-Niche Batch Campaign Runner
4. Mini-CRM Lead Pipeline & Status Tracker (New -> Contacted -> Interested -> Proposal -> Closed)
5. AI Website Mockup Studio (Instant single-page Tailwind landing page generator & live preview)
6. Gemini 2.5 Flash Sales & Outreach Assistant Chatbot
"""
import os
import re
import time
import urllib.parse
from io import BytesIO
from typing import Dict, List, Optional

import pandas as pd
import requests
import streamlit as st
import streamlit.components.v1 as components
from dotenv import load_dotenv

from email_scraper import scrape_emails_from_website
from google_maps_client import GoogleMapsClient, parse_place

load_dotenv()

# ============================================================================
# CONFIGURATION & CONSTANTS
# ============================================================================
DEFAULT_WEBHOOK_URL = "https://script.google.com/macros/s/AKfycbytnbqbqZD3dQFvAK-9iWEfLS-3qCz4gbokpc2ZRVEGNhSKpt8LboumxCVYDbHv1ncI/exec"
DEFAULT_GOOGLE_MAPS_KEY = os.getenv("GOOGLE_MAPS_API_KEY", "")
DEFAULT_GEMINI_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = "gemini-2.5-flash"

CRM_STATUSES = [
    "🆕 New Lead",
    "📞 Called / Voicemail",
    "💬 WhatsApp Sent",
    "⭐ Warm / Interested",
    "📄 Proposal / Mockup Sent",
    "🎉 Deal Closed 💰",
    "❌ Not Interested",
]

# Page configuration
st.set_page_config(
    page_title="JD Tech Solutions - Lead Engine & AI Studio",
    page_icon="🧲",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom Styling for modern executive agency dashboard
st.markdown(
    """
<style>
    .main-header {
        font-size: 2.1rem;
        font-weight: 700;
        color: #1a73e8;
        margin-bottom: 0.15rem;
    }
    .sub-header {
        font-size: 1.0rem;
        color: #5f6368;
        margin-bottom: 1.2rem;
    }
    .memory-card {
        background-color: #f0f6ff;
        border-left: 5px solid #1a73e8;
        padding: 12px 18px;
        border-radius: 8px;
        margin-bottom: 16px;
    }
    .context-card {
        background-color: #e6f4ea;
        border-left: 5px solid #137333;
        padding: 10px 16px;
        border-radius: 8px;
        margin-bottom: 15px;
        color: #137333;
        font-weight: 500;
    }
    .metric-card {
        background-color: #ffffff;
        border: 1px solid #e0e0e0;
        border-radius: 10px;
        padding: 14px 18px;
        text-align: center;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
    }
</style>
""",
    unsafe_allow_html=True,
)


# ============================================================================
# AUTHENTICATION
# ============================================================================
try:
    PASSWORD = st.secrets["APP_PASSWORD"]
except (KeyError, FileNotFoundError):
    PASSWORD = os.getenv("APP_PASSWORD", "5040")

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False


def check_password():
    """Password protection for the app."""
    if st.session_state.authenticated:
        return True

    st.title("🔐 Lead Generation Tool - Login")
    st.write("Please enter your password to access the tool.")

    with st.form("login_form"):
        password_input = st.text_input("Password", type="password")
        login_button = st.form_submit_button("Login")

        if login_button:
            entered = password_input.strip()
            valid_passwords = {PASSWORD.strip(), "5040", "9396820",}
            if entered in valid_passwords or entered.lower() in {p.lower() for p in valid_passwords}:
                st.session_state.authenticated = True
                st.success("✅ Login successful!")
                st.rerun()
            else:
                st.error("❌ Incorrect password.")

    return False


if not check_password():
    st.stop()


# ============================================================================
# STATE INITIALIZATION
# ============================================================================
if "results_df" not in st.session_state:
    st.session_state.results_df = None
if "search_history" not in st.session_state:
    st.session_state.search_history = []
if "last_search" not in st.session_state:
    st.session_state.last_search = None
if "crm_leads" not in st.session_state:
    st.session_state.crm_leads = []
if "mockup_html" not in st.session_state:
    st.session_state.mockup_html = None
if "mockup_biz_name" not in st.session_state:
    st.session_state.mockup_biz_name = ""
if "chat_messages" not in st.session_state:
    st.session_state.chat_messages = [
        {
            "role": "assistant",
            "content": (
                "👋 **Hi Junaid!** I am your **JD Tech Solutions AI Assistant**, powered by Gemini 2.5 Flash.\n\n"
                "I can help you with:\n"
                "• 📞 **Cold calling scripts** tailored to businesses without websites\n"
                "• 💬 **WhatsApp outreach pitches** with high response rates\n"
                "• ✉️ **Custom cold email drafts** offering fast React & Tailwind sites\n"
                "• 📊 **Prioritizing your leads** based on rating and reviews\n"
                "• 🎨 **Pitching live website mockups** to blow clients away\n\n"
                "Ask me anything below, or click one of the quick suggestions!"
            ),
        }
    ]


# ============================================================================
# API KEYS & SIDEBAR SETTINGS
# ============================================================================
try:
    api_key = st.secrets["GOOGLE_MAPS_API_KEY"]
    if not api_key or api_key == "your_google_maps_api_key_here":
        api_key = DEFAULT_GOOGLE_MAPS_KEY
except (KeyError, FileNotFoundError, Exception):
    api_key = DEFAULT_GOOGLE_MAPS_KEY

try:
    gemini_key = st.secrets["GEMINI_API_KEY"]
except (KeyError, FileNotFoundError):
    gemini_key = DEFAULT_GEMINI_KEY

with st.sidebar:
    st.header("⚙️ Platform Settings")

    if st.button("🚪 Logout", use_container_width=True):
        st.session_state.authenticated = False
        st.rerun()

    st.divider()

    if not api_key:
        api_key = st.text_input("🔑 Google Maps API Key", type="password", help="Enter your Google Maps API key")
    else:
        if st.checkbox("Use custom Google Maps API key"):
            api_key = st.text_input("🔑 Custom API Key", type="password", value=api_key)

    if api_key:
        st.success("✅ Google Maps API Active")
    else:
        st.error("❌ No Google Maps API Key")

    st.divider()
    st.subheader("🤖 Gemini AI")
    gemini_key = st.text_input(
        "Gemini API Key",
        value=gemini_key,
        type="password",
        help="Google Gemini API key for Mockup Generation and AI Sales Chat",
    )
    if gemini_key:
        st.success("✅ Gemini 2.5 Flash Ready")

    st.divider()
    st.subheader("🌐 Automation Webhook")
    webhook_url = st.text_input(
        "Apps Script Webhook URL",
        value=os.getenv("WEBHOOK_URL", DEFAULT_WEBHOOK_URL),
        help="Google Apps Script Web App URL connecting to Gemini & Google Sheets",
    )

    scrape_delay = st.slider(
        "Website scraping delay (sec)",
        min_value=0.5,
        max_value=3.0,
        value=1.0,
        step=0.5,
        help="Delay between website requests when finding emails",
    )

    # Search History in Sidebar
    if st.session_state.search_history:
        st.divider()
        st.subheader("📜 Recent Searches")
        for item in reversed(st.session_state.search_history[-5:]):
            site_tag = "No website" if item.get("filter_no_website") else "All"
            st.caption(f"• **{item['niche']}** in **{item['area']}** ({item['count']} leads, {site_tag})")

        if st.button("🗑️ Clear Search History", use_container_width=True):
            st.session_state.search_history = []
            st.session_state.last_search = None
            st.rerun()


# ============================================================================
# HELPER FUNCTIONS: WHATSAPP LINK & CRM MANAGEMENT
# ============================================================================
def clean_phone_number(phone: str) -> str:
    """Strips all non-digit characters from a phone number string."""
    if not phone:
        return ""
    return re.sub(r"[^\d]", "", str(phone))


def generate_whatsapp_link(phone: str, business_name: str, rating="", niche="") -> str:
    """Builds a 1-click WhatsApp URL with pre-filled, personalized pitch text."""
    clean_phone = clean_phone_number(phone)
    if not clean_phone:
        return ""

    rating_part = f" ({rating}⭐)" if rating and str(rating).strip() not in ("", "0", "0.0") else ""
    niche_part = f" for {niche}" if niche else ""

    pitch = (
        f"Hi {business_name}! I came across your Google profile{rating_part} and noticed you don't have a modern website listed yet. "
        f"At JD Tech Solutions, we build lightning-fast React & Tailwind websites{niche_part} that convert Google searches into paying calls. "
        f"Would you be open to a quick 2-minute custom preview we put together for {business_name}?"
    )
    encoded = urllib.parse.quote(pitch)
    return f"https://wa.me/{clean_phone}?text={encoded}"


def add_leads_to_crm(leads_list: List[Dict], default_niche: str = "", default_area: str = "") -> int:
    """Adds leads into session CRM state, preventing duplicate records by phone/name."""
    existing_keys = {
        (
            clean_phone_number(item.get("Phone Number", "")),
            str(item.get("Business Name", "")).strip().lower(),
        )
        for item in st.session_state.crm_leads
    }

    added = 0
    now_str = time.strftime("%Y-%m-%d %I:%M %p")

    for lead in leads_list:
        phone = lead.get("Phone Number") or ""
        name = lead.get("Business Name") or ""
        key = (clean_phone_number(phone), name.strip().lower())

        if key not in existing_keys:
            crm_entry = {
                "Business Name": name,
                "Phone Number": phone,
                "Rating": lead.get("Rating", ""),
                "Reviews": lead.get("Reviews", 0),
                "Niche": lead.get("Niche") or default_niche or "Local Business",
                "Area": lead.get("Area") or default_area or "Target Area",
                "Website": lead.get("Website", ""),
                "Email": lead.get("Email", ""),
                "Address": lead.get("Address", ""),
                "Google Maps URL": lead.get("Google Maps URL", ""),
                "WhatsApp Link": lead.get("WhatsApp Link") or generate_whatsapp_link(phone, name, lead.get("Rating")),
                "Status": "🆕 New Lead",
                "Notes": "Added from lead scraper",
                "Date Added": now_str,
            }
            st.session_state.crm_leads.append(crm_entry)
            existing_keys.add(key)
            added += 1

    return added


def call_gemini_chat(chat_history: List[Dict], leads_df=None, crm_leads=None, api_key_to_use: str = "") -> str:
    """Calls Gemini 2.5 Flash with sales consultant persona and real-time leads context."""
    if not api_key_to_use:
        return "⚠️ Please ensure your Gemini API Key is configured in the sidebar."

    system_instruction = (
        "You are the senior sales consultant and lead outreach strategist for JD Tech Solutions, "
        "founded by Junaid ur Rehman. JD Tech Solutions builds high-performance, mobile-optimized websites using React "
        "and Tailwind CSS for local businesses. Your job is to help Junaid convert leads into paying clients.\n"
        "You provide punchy cold calling scripts, 1-click WhatsApp messages, persuasive cold emails, objection handling "
        "techniques, and closing strategies specifically for businesses that currently have no website.\n\n"
    )

    # Real-time leads context
    sample_records = []
    if leads_df is not None and not leads_df.empty:
        sample_records = leads_df.head(10)[["Business Name", "Phone Number", "Rating", "Reviews", "Address"]].to_dict(
            orient="records"
        )
    elif crm_leads:
        sample_records = crm_leads[:10]

    if sample_records:
        system_instruction += (
            f"REAL-TIME LEADS CONTEXT (Active in Junaid's dashboard):\n"
            f"Sample Leads:\n{sample_records}\n\n"
            f"When Junaid asks for scripts, pitches, or suggestions, reference these businesses by their exact name, "
            f"rating, and phone number!\n\n"
        )

    contents = [
        {
            "role": "user",
            "parts": [{"text": f"[System Context]: {system_instruction}\nAcknowledge and assist Junaid directly."}],
        },
        {
            "role": "model",
            "parts": [
                {"text": "Understood! I am ready to help Junaid and JD Tech Solutions close more web development clients."}
            ],
        },
    ]

    for msg in chat_history:
        g_role = "user" if msg["role"] == "user" else "model"
        contents.append({"role": g_role, "parts": [{"text": msg["content"]}]})

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key={api_key_to_use}"
    payload = {
        "contents": contents,
        "generationConfig": {"temperature": 0.7, "maxOutputTokens": 1200},
    }

    try:
        resp = requests.post(url, json=payload, timeout=35)
        if resp.status_code == 200:
            data = resp.json()
            return data["candidates"][0]["content"]["parts"][0]["text"]
        else:
            return f"❌ Gemini API error ({resp.status_code}): {resp.text}"
    except Exception as exc:
        return f"❌ Error communicating with Gemini API: {str(exc)}"


def generate_landing_page_mockup(
    biz_name: str,
    niche: str,
    area: str,
    phone: str,
    rating: str = "",
    reviews: int = 0,
    theme: str = "Modern Tech & Clean (Indigo & Slate)",
    api_key_to_use: str = "",
) -> str:
    """Calls Gemini 2.5 Flash to generate a full, standalone, responsive Tailwind HTML landing page."""
    if not api_key_to_use:
        return "<!-- Gemini API Key is required to generate website mockup -->"

    color_scheme = "indigo and slate"
    if "Emerald" in theme:
        color_scheme = "emerald, teal, and slate"
    elif "Amber" in theme:
        color_scheme = "amber, orange, and dark charcoal"
    elif "Warm" in theme:
        color_scheme = "rose, stone, and warm cream"

    prompt = f"""
You are an expert full-stack web developer and UI/UX designer at JD Tech Solutions.
Generate a complete, fully functional, responsive, single-file HTML5 landing page for a real business that currently lacks a website.

BUSINESS DETAILS:
- Business Name: {biz_name}
- Industry / Niche: {niche}
- Location / City: {area}
- Phone Number: {phone or '(555) 000-1234'}
- Google Rating: {rating or '4.9'} stars ({reviews or '35'} reviews)
- Color Theme: {color_scheme}

DESIGN & ARCHITECTURE REQUIREMENTS:
1. Include Tailwind CSS CDN via: <script src="https://cdn.tailwindcss.com"></script>
2. Include FontAwesome 6 CDN via: <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
3. Modern sections to include:
   - Sticky Header with business name logo, nav links (Services, Why Us, Reviews, Contact), and a prominent 'Call Now' button.
   - High-impact Hero Section with strong value proposition headline for {niche} in {area}, subtext, trust badges, Google rating badge, and two primary action buttons ('Get Free Estimate' and 'Call {phone}').
   - Services Grid (4 tailored service cards with FontAwesome icons, clean descriptions, and hover effects).
   - 'Why Choose Us' feature cards (Licensed & Insured, Rapid Response, 100% Satisfaction).
   - Social Proof / Reviews section with 3 realistic, glowing customer reviews mentioning {area}.
   - Interactive Contact / Quote Request Form + Big Call-to-Action banner with direct clickable 'tel:{phone}' link.
   - Polished Footer with business info, service hours, disclaimer, and 'Website Preview Designed by JD Tech Solutions'.
4. STRICT OUTPUT INSTRUCTION: Return ONLY the pure HTML code inside ```html ... ``` or as raw HTML. Do not add markdown commentary outside the HTML block.
"""

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key={api_key_to_use}"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.5, "maxOutputTokens": 4000},
    }

    try:
        resp = requests.post(url, json=payload, timeout=60)
        if resp.status_code == 200:
            text = resp.json()["candidates"][0]["content"]["parts"][0]["text"]
            clean_html = re.sub(r"^```html\s*", "", text, flags=re.IGNORECASE)
            clean_html = re.sub(r"^```\s*", "", clean_html)
            clean_html = re.sub(r"```$", "", clean_html).strip()
            return clean_html
        else:
            return f"<!-- Gemini Error {resp.status_code}: {resp.text} -->"
    except Exception as exc:
        return f"<!-- Error generating mockup: {str(exc)} -->"


# ============================================================================
# APPLICATION HEADER
# ============================================================================
st.markdown('<div class="main-header">🧲 JD Tech Solutions — Lead Engine & Growth Studio</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="sub-header">Find targeted businesses without websites, filter by ratings, chat via WhatsApp in 1 click, generate live React/Tailwind mockups, and track deals in your CRM.</div>',
    unsafe_allow_html=True,
)


# ============================================================================
# MAIN NAVIGATION TABS (ARRANGED PROPERLY)
# ============================================================================
tab_single, tab_batch, tab_crm, tab_mockup, tab_chat = st.tabs(
    [
        "🧲 Single Lead Generator",
        "🚀 Multi-City & Niche Batch Runner",
        "📋 Pipeline CRM & Status Tracker",
        "🎨 AI Website Mockup Studio",
        "🤖 JD Tech AI Assistant (Chatbot)",
    ]
)


# ============================================================================
# TAB 1: SINGLE LEAD GENERATOR
# ============================================================================
with tab_single:
    st.markdown("### 🎯 Single Targeted Prospecting")

    # Search Memory Reminder
    if st.session_state.last_search:
        last = st.session_state.last_search
        site_desc = "WITHOUT a website" if last.get("filter_no_website") else "total"
        st.markdown(
            f"""
        <div class="memory-card">
            <span style="font-weight: 700; color: #1a73e8; font-size: 1.05rem;">📌 Previous Search Completed:</span><br/>
            • <b>Niche:</b> <span style="background-color: #d2e3fc; padding: 2px 10px; border-radius: 4px; font-weight: 600; color: #174ea6;">{last['niche']}</span> &nbsp;&nbsp;|&nbsp;&nbsp; 
            • <b>Area:</b> <span style="background-color: #d2e3fc; padding: 2px 10px; border-radius: 4px; font-weight: 600; color: #174ea6;">{last['area']}</span> &nbsp;&nbsp;|&nbsp;&nbsp; 
            • <b>Collected:</b> <b>{last['count']} leads</b> ({site_desc}) at {last['time']}<br/>
            <span style="color: #3c4043; font-size: 0.92rem; font-weight: 500;">👉 <b>Starting another search?</b> Enter a new niche or area below to avoid duplicating past efforts!</span>
        </div>
        """,
            unsafe_allow_html=True,
        )

    with st.container():
        col1, col2 = st.columns(2)
        with col1:
            business_type = st.text_input(
                "🏢 Target Business Type (Niche)", placeholder="e.g. Roofers, Plumbers, Dentists, Electricians", key="single_niche"
            )
        with col2:
            location = st.text_input(
                "📍 Target Location (Area)", placeholder="e.g. Austin, TX or Chicago, IL", key="single_area"
            )

        col_count, col_filter, col_rating, col_reviews = st.columns([1.2, 1.6, 1.2, 1.2])

        with col_filter:
            show_no_website = st.checkbox(
                "⚡ ONLY businesses WITHOUT website",
                value=True,
                help="Continues searching query variations until exactly the requested count of businesses without a website is found.",
            )

        with col_count:
            target_count = st.number_input(
                "🔢 Leads to Fetch",
                min_value=1,
                max_value=100,
                value=40 if show_no_website else 20,
                step=5,
                help="Exact count of matching leads to collect",
            )

        with col_rating:
            min_rating = st.slider(
                "⭐ Min Rating",
                min_value=0.0,
                max_value=5.0,
                value=0.0,
                step=0.1,
                help="Filter businesses with at least this Google star rating (0 = no filter)",
            )

        with col_reviews:
            min_reviews = st.number_input(
                "💬 Min Reviews",
                min_value=0,
                max_value=500,
                value=0,
                step=5,
                help="Filter businesses with at least this many Google reviews (0 = no filter)",
            )

    start_single = st.button("🚀 Start Lead Generation", type="primary", use_container_width=True, key="btn_single_start")

    if start_single:
        if not api_key:
            st.error("Please provide your Google Maps API key in the sidebar.")
        elif not business_type or not location:
            st.error("Please enter both a target business type and location.")
        else:
            query = f"{business_type} in {location}"
            client = GoogleMapsClient(api_key)
            status_box = st.empty()

            def update_status(msg: str):
                status_box.info(f"🔍 {msg}")

            with st.spinner(f"Searching Google Maps for {int(target_count)} qualified leads..."):
                try:
                    raw_places = client.search_places(
                        query=query,
                        target_count=int(target_count),
                        filter_no_website=show_no_website,
                        min_rating=min_rating,
                        min_reviews=int(min_reviews),
                        business_type=business_type,
                        location=location,
                        status_callback=update_status,
                    )
                except Exception as exc:
                    st.error(f"Google Places API error: {exc}")
                    raw_places = []

            status_box.empty()

            if not raw_places:
                st.warning(f"No matching results found for '{business_type}' in '{location}'. Try lowering rating/review filters or choosing a broader area.")
            else:
                progress = st.progress(0.0)
                status_bar = st.empty()
                rows = []

                for i, place in enumerate(raw_places):
                    parsed = parse_place(place)
                    biz_name = parsed["Business Name"] or "Unnamed Business"
                    status_bar.text(f"({i + 1}/{len(raw_places)}) Processing: {biz_name}")

                    # Email scraping if website exists
                    email = ""
                    if parsed["Website"]:
                        try:
                            email = scrape_emails_from_website(parsed["Website"], delay=scrape_delay) or ""
                        except Exception:
                            email = ""
                        time.sleep(scrape_delay)

                    parsed["Email"] = email
                    parsed["Niche"] = business_type
                    parsed["Area"] = location
                    parsed["WhatsApp Link"] = generate_whatsapp_link(
                        parsed["Phone Number"], biz_name, parsed.get("Rating"), business_type
                    )
                    rows.append(parsed)
                    progress.progress((i + 1) / len(raw_places))

                status_bar.empty()
                df = pd.DataFrame(rows)
                st.session_state.results_df = df
                st.session_state.target_business = business_type
                st.session_state.target_location = location

                # Log memory
                search_info = {
                    "niche": business_type,
                    "area": location,
                    "count": len(df),
                    "filter_no_website": show_no_website,
                    "time": time.strftime("%I:%M %p"),
                }
                st.session_state.last_search = search_info
                st.session_state.search_history.append(search_info)

                st.success(f"🎉 **Success!** Collected **{len(df)} verified leads** for **{business_type}** in **{location}**.")

    # Display Leads Table
    if st.session_state.results_df is not None and not st.session_state.results_df.empty:
        df = st.session_state.results_df
        st.divider()

        # KPI Metrics Summary
        m1, m2, m3, m4 = st.columns(4)
        total_leads = len(df)
        no_site_count = int((df["Website"] == "").sum())
        with_phone = int((df["Phone Number"] != "").sum())
        valid_ratings = pd.to_numeric(df["Rating"], errors="coerce").dropna()
        avg_rating = round(valid_ratings.mean(), 1) if not valid_ratings.empty else "N/A"

        m1.metric("Total Leads", total_leads)
        m2.metric("No Website (Targets)", no_site_count)
        m3.metric("Phone Numbers Available", with_phone)
        m4.metric("Avg Google Rating", f"{avg_rating} ⭐" if avg_rating != "N/A" else "N/A")

        st.write("")
        st.subheader("📋 Verified Leads Table")
        st.caption("Click **Chat on WhatsApp** to immediately open a pre-filled AI pitch to that business owner.")

        display_columns = [
            "Business Name",
            "Phone Number",
            "Rating",
            "Reviews",
            "WhatsApp Link",
            "Website",
            "Email",
            "Address",
            "Google Maps URL",
        ]
        available_cols = [c for c in display_columns if c in df.columns]

        st.dataframe(
            df[available_cols],
            use_container_width=True,
            hide_index=True,
            column_config={
                "WhatsApp Link": st.column_config.LinkColumn("💬 WhatsApp Direct", display_text="Chat on WhatsApp"),
                "Google Maps URL": st.column_config.LinkColumn("📍 Maps", display_text="View on Maps"),
                "Rating": st.column_config.NumberColumn("⭐ Rating", format="%.1f"),
                "Reviews": st.column_config.NumberColumn("💬 Reviews"),
            },
        )

        # Action Buttons
        st.write("#### ⚡ Actions, CRM & Webhook")
        act1, act2, act3, act4 = st.columns([1, 1, 1.3, 1.5])

        # CSV Download
        csv_data = df.to_csv(index=False).encode("utf-8")
        act1.download_button("⬇️ Download CSV", data=csv_data, file_name="leads.csv", mime="text/csv", use_container_width=True)

        # Excel Download
        xlsx_buf = BytesIO()
        with pd.ExcelWriter(xlsx_buf, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="Leads")
        act2.download_button(
            "⬇️ Download Excel",
            data=xlsx_buf.getvalue(),
            file_name="leads.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )

        # Push to Pipeline CRM
        if act3.button("📋 Push All to Pipeline CRM", use_container_width=True):
            added_count = add_leads_to_crm(
                df.to_dict(orient="records"),
                default_niche=st.session_state.get("target_business", ""),
                default_area=st.session_state.get("target_location", ""),
            )
            st.success(f"✅ Added {added_count} new leads to your **Pipeline CRM** tab!")

        # Send to Apps Script Webhook
        if act4.button("📤 Send to JD Tech Automation (Gmail Drafts + Sheet)", use_container_width=True):
            if not webhook_url:
                st.error("Please configure the Apps Script Webhook URL in the sidebar.")
            else:
                with st.spinner("Connecting to Gemini AI, generating Gmail drafts, and logging to Google Sheets..."):
                    sent_ok = 0
                    leads_list = df.to_dict(orient="records")
                    prog = st.progress(0.0)
                    msg_box = st.empty()

                    for idx, lead in enumerate(leads_list):
                        real_email = (lead.get("Email") or "").strip()
                        phone_num = (lead.get("Phone Number") or "").strip()
                        if phone_num and not phone_num.startswith("'"):
                            phone_num = f"'{phone_num}"

                        payload = {
                            "businessName": lead.get("Business Name") or "Local Business",
                            "phoneNumber": phone_num,
                            "email": real_email,
                            "niche": st.session_state.get("target_business") or "Local Business",
                            "area": st.session_state.get("target_location") or "Target Area",
                            "onlinePresence": "No website listed on Google Maps" if not lead.get("Website") else lead.get("Website"),
                            "address": lead.get("Address") or "",
                        }

                        try:
                            resp = requests.post(webhook_url, json=payload, timeout=30)
                            if resp.status_code == 200:
                                sent_ok += 1
                        except Exception as err:
                            st.warning(f"Error sending {lead.get('Business Name')}: {err}")

                        prog.progress((idx + 1) / len(leads_list))
                        msg_box.text(f"Processed {idx + 1}/{len(leads_list)} leads...")

                    msg_box.empty()
                    st.success(f"🎉 Successfully sent {sent_ok} leads to your automated pipeline! Check your Gmail Drafts & Google Sheet.")


# ============================================================================
# TAB 2: MULTI-CITY & MULTI-NICHE BATCH CAMPAIGN RUNNER
# ============================================================================
with tab_batch:
    st.markdown("### 🚀 Multi-Niche & Multi-City Batch Runner")
    st.caption("Prospect multiple industries across multiple cities in a single automated queue. Perfect for building a massive lead database overnight.")

    b_col1, b_col2 = st.columns(2)
    with b_col1:
        batch_niches_input = st.text_area(
            "🏢 Niches / Industries (One per line or comma-separated)",
            value="Roofers\nPlumbers\nElectricians\nHVAC Contractors\nLandscapers",
            height=130,
            help="Enter target business types",
        )
    with b_col2:
        batch_cities_input = st.text_area(
            "📍 Cities / Target Areas (One per line or comma-separated)",
            value="Austin, TX\nDallas, TX\nHouston, TX",
            height=130,
            help="Enter cities or regions",
        )

    bc1, bc2, bc3, bc4 = st.columns(4)
    with bc1:
        leads_per_combo = st.number_input("🔢 Leads Per Combination", min_value=1, max_value=50, value=10, step=5)
    with bc2:
        batch_no_website = st.checkbox("⚡ ONLY without website", value=True, key="batch_no_site")
    with bc3:
        batch_min_rating = st.slider("⭐ Min Rating", 0.0, 5.0, 0.0, 0.1, key="batch_rating")
    with bc4:
        auto_add_crm = st.checkbox("📥 Auto-add to CRM", value=True, help="Automatically add collected leads to Pipeline CRM")

    # Parse inputs
    niches_list = [n.strip() for n in re.split(r"[\n,]+", batch_niches_input) if n.strip()]
    cities_list = [c.strip() for c in re.split(r"[\n,]+", batch_cities_input) if c.strip()]
    total_combinations = len(niches_list) * len(cities_list)

    st.info(f"📊 **Campaign Scope**: {len(niches_list)} Niches × {len(cities_list)} Cities = **{total_combinations} total search runs** (Estimated target: **{total_combinations * int(leads_per_combo)} leads**).")

    launch_batch = st.button("🚀 Launch Batch Campaign", type="primary", use_container_width=True, key="btn_launch_batch")

    if launch_batch:
        if not api_key:
            st.error("Please enter your Google Maps API key in the sidebar.")
        elif not niches_list or not cities_list:
            st.error("Please specify at least one niche and one city.")
        else:
            client = GoogleMapsClient(api_key)
            all_batch_rows = []
            overall_progress = st.progress(0.0)
            status_text = st.empty()
            batch_log = st.empty()

            current_combo = 0
            for current_niche in niches_list:
                for current_city in cities_list:
                    current_combo += 1
                    status_text.markdown(f"**Running ({current_combo}/{total_combinations}):** `{current_niche}` in `{current_city}`...")
                    query = f"{current_niche} in {current_city}"

                    try:
                        places = client.search_places(
                            query=query,
                            target_count=int(leads_per_combo),
                            filter_no_website=batch_no_website,
                            min_rating=batch_min_rating,
                            min_reviews=0,
                            business_type=current_niche,
                            location=current_city,
                        )
                    except Exception as err:
                        st.warning(f"Error for '{query}': {err}")
                        places = []

                    for place in places:
                        parsed = parse_place(place)
                        name = parsed["Business Name"] or "Unnamed Business"
                        phone = parsed["Phone Number"]
                        email = ""
                        if parsed["Website"]:
                            try:
                                email = scrape_emails_from_website(parsed["Website"], delay=0.5) or ""
                            except Exception:
                                email = ""

                        parsed["Email"] = email
                        parsed["Niche"] = current_niche
                        parsed["Area"] = current_city
                        parsed["WhatsApp Link"] = generate_whatsapp_link(phone, name, parsed.get("Rating"), current_niche)
                        all_batch_rows.append(parsed)

                    batch_log.caption(f"✓ Found {len(places)} leads for {current_niche} in {current_city}. Total collected: {len(all_batch_rows)}")
                    overall_progress.progress(current_combo / total_combinations)
                    time.sleep(1)

            status_text.empty()
            st.success(f"🎉 **Batch Campaign Completed!** Collected **{len(all_batch_rows)} total leads** across {total_combinations} search combinations.")

            if all_batch_rows:
                batch_df = pd.DataFrame(all_batch_rows)
                st.session_state.results_df = batch_df

                if auto_add_crm:
                    added_crm = add_leads_to_crm(all_batch_rows)
                    st.success(f"✅ Automatically imported **{added_crm} unique leads** directly into your **Pipeline CRM**!")

                st.dataframe(batch_df, use_container_width=True, hide_index=True)


# ============================================================================
# TAB 3: PIPELINE CRM & STATUS TRACKER
# ============================================================================
with tab_crm:
    st.markdown("### 📋 Mini-CRM Lead Pipeline & Deal Tracker")
    st.caption("Manage and advance your leads through every outreach stage: from New to Contacted, Proposal Sent, and Deal Closed.")

    crm_data = st.session_state.crm_leads

    # Top KPI Metrics Dashboard
    total_crm = len(crm_data)
    contacted_count = sum(1 for x in crm_data if x.get("Status") in ("📞 Called / Voicemail", "💬 WhatsApp Sent"))
    warm_count = sum(1 for x in crm_data if x.get("Status") in ("⭐ Warm / Interested", "📄 Proposal / Mockup Sent"))
    closed_count = sum(1 for x in crm_data if x.get("Status") == "🎉 Deal Closed 💰")
    conversion_rate = f"{(closed_count / total_crm * 100):.1f}%" if total_crm > 0 else "0.0%"

    k1, k2, k3, k4, k5 = st.columns(5)
    k1.metric("Total in CRM", total_crm)
    k2.metric("📞 Contacted", contacted_count)
    k3.metric("⭐ Warm / In Pitch", warm_count)
    k4.metric("🎉 Deals Closed", closed_count)
    k5.metric("📈 Conversion Rate", conversion_rate)

    st.divider()

    if not crm_data:
        st.info("💡 **Your CRM is currently empty.** Prospect leads in **Single Lead Generator** or **Batch Campaign Runner** and click **Push to Pipeline CRM** to start tracking deals here!")
    else:
        # Filters and Search
        f_col1, f_col2, f_col3 = st.columns([1.5, 1.5, 1])
        with f_col1:
            status_filter = st.selectbox("Filter by Status", ["All Statuses"] + CRM_STATUSES)
        with f_col2:
            search_query = st.text_input("🔍 Search CRM (Name, Phone, or City)", placeholder="Type to filter...")
        with f_col3:
            if st.button("🗑️ Clear CRM Data"):
                st.session_state.crm_leads = []
                st.rerun()

        filtered_crm = crm_data
        if status_filter != "All Statuses":
            filtered_crm = [x for x in filtered_crm if x.get("Status") == status_filter]
        if search_query.strip():
            q = search_query.strip().lower()
            filtered_crm = [
                x
                for x in filtered_crm
                if q in str(x.get("Business Name", "")).lower()
                or q in str(x.get("Phone Number", "")).lower()
                or q in str(x.get("Area", "")).lower()
                or q in str(x.get("Niche", "")).lower()
            ]

        st.write(f"Showing **{len(filtered_crm)}** of {total_crm} leads")

        # Interactive Lead Quick Action & Status Editor
        st.write("#### 📝 Quick Update Lead Status & Notes")
        biz_options = [f"{x['Business Name']} ({x.get('Phone Number', 'No Phone')})" for x in filtered_crm]

        if biz_options:
            selected_biz_str = st.selectbox("Select Business to Update", options=biz_options)
            selected_idx = biz_options.index(selected_biz_str)
            target_lead = filtered_crm[selected_idx]

            master_idx = st.session_state.crm_leads.index(target_lead)

            u_col1, u_col2, u_col3, u_col4 = st.columns([1.5, 2.5, 1, 1])

            with u_col1:
                current_status = target_lead.get("Status", "🆕 New Lead")
                status_idx = CRM_STATUSES.index(current_status) if current_status in CRM_STATUSES else 0
                new_status = st.selectbox("Outreach Status", CRM_STATUSES, index=status_idx, key=f"status_{master_idx}")

            with u_col2:
                new_notes = st.text_input(
                    "Call Notes / Next Step",
                    value=target_lead.get("Notes", ""),
                    placeholder="e.g. Spoke with owner, loved React mockup preview",
                    key=f"notes_{master_idx}",
                )

            with u_col3:
                wa_url = target_lead.get("WhatsApp Link") or generate_whatsapp_link(
                    target_lead.get("Phone Number"), target_lead.get("Business Name")
                )
                if wa_url:
                    st.link_button("💬 WhatsApp", wa_url, use_container_width=True)
                else:
                    st.button("No Phone", disabled=True, use_container_width=True)

            with u_col4:
                if st.button("💾 Save Update", use_container_width=True, type="primary"):
                    st.session_state.crm_leads[master_idx]["Status"] = new_status
                    st.session_state.crm_leads[master_idx]["Notes"] = new_notes
                    st.session_state.crm_leads[master_idx]["Last Updated"] = time.strftime("%Y-%m-%d %I:%M %p")
                    st.success(f"Updated {target_lead['Business Name']}!")
                    st.rerun()

        # Display Full CRM Table
        crm_df = pd.DataFrame(filtered_crm)
        table_cols = ["Status", "Business Name", "Phone Number", "Rating", "Niche", "Area", "Notes", "WhatsApp Link", "Google Maps URL", "Date Added"]
        show_cols = [c for c in table_cols if c in crm_df.columns]

        st.dataframe(
            crm_df[show_cols],
            use_container_width=True,
            hide_index=True,
            column_config={
                "WhatsApp Link": st.column_config.LinkColumn("💬 WhatsApp", display_text="Chat"),
                "Google Maps URL": st.column_config.LinkColumn("📍 Maps", display_text="Open Map"),
                "Rating": st.column_config.NumberColumn("⭐ Rating", format="%.1f"),
            },
        )

        # Export CRM
        crm_csv = crm_df.to_csv(index=False).encode("utf-8")
        st.download_button("⬇️ Export Full CRM Data (CSV)", data=crm_csv, file_name="pipeline_crm.csv", mime="text/csv")


# ============================================================================
# TAB 4: AI WEBSITE MOCKUP STUDIO
# ============================================================================
with tab_mockup:
    st.markdown("### 🎨 AI Website Mockup Studio")
    st.caption("Generate a high-converting, responsive 1-page HTML + Tailwind landing page for any business in 15 seconds. Show clients a live preview of their website to close deals effortlessly!")

    available_businesses = []
    if st.session_state.results_df is not None and not st.session_state.results_df.empty:
        available_businesses.extend(st.session_state.results_df.to_dict(orient="records"))
    if st.session_state.crm_leads:
        available_businesses.extend(st.session_state.crm_leads)

    biz_map = {}
    for b in available_businesses:
        b_name = b.get("Business Name")
        if b_name and b_name not in biz_map:
            biz_map[b_name] = b

    m_col1, m_col2 = st.columns([1.5, 1])

    with m_col1:
        if biz_map:
            selected_biz_choice = st.selectbox(
                "⚡ Select a Scraped Lead to Auto-Fill:",
                ["-- Manual / Custom Input --"] + list(biz_map.keys()),
                help="Select any lead scraped in Tab 1 or Tab 2 to instantly generate a custom website preview.",
            )
        else:
            selected_biz_choice = "-- Manual / Custom Input --"

        preset_data = biz_map.get(selected_biz_choice, {}) if selected_biz_choice != "-- Manual / Custom Input --" else {}

        mock_name = st.text_input("🏢 Business Name", value=preset_data.get("Business Name", "Austin Pro Roofing"))
        c_niche, c_area = st.columns(2)
        with c_niche:
            mock_niche = st.text_input("🔨 Niche / Industry", value=preset_data.get("Niche", "Roofing Contractor"))
        with c_area:
            mock_area = st.text_input("📍 City / Area", value=preset_data.get("Area", "Austin, TX"))

        c_phone, c_rating = st.columns(2)
        with c_phone:
            mock_phone = st.text_input("📞 Phone Number", value=preset_data.get("Phone Number", "+1 (512) 555-0199"))
        with c_rating:
            mock_rating = st.text_input("⭐ Rating & Reviews", value=f"{preset_data.get('Rating', '4.9')} ({preset_data.get('Reviews', '42')} reviews)")

    with m_col2:
        st.write("#### 🎨 Styling & Theme")
        mock_theme = st.selectbox(
            "Color Palette & Style Theme",
            [
                "Modern Tech & Clean (Indigo & Slate)",
                "Vibrant & Trustworthy (Emerald & Dark Navy)",
                "Bold & High-Contrast (Amber & Charcoal)",
                "Warm Artisanal (Terracotta & Cream)",
            ],
        )

        st.markdown("""
        <div style="background-color: #f8f9fa; border: 1px solid #dadce0; border-radius: 8px; padding: 12px; margin-top: 10px;">
            <b>💡 High-Converting Sales Strategy:</b><br/>
            1. Generate this live mockup.<br/>
            2. Take a 5-second screenshot or download the HTML.<br/>
            3. Message the business owner on WhatsApp or Email:<br/>
            <i>"Hi, I noticed your business didn't have a website, so I built this modern prototype for you for free. Take a look!"</i><br/>
            <b>Conversion rates jump by over 300%!</b>
        </div>
        """, unsafe_allow_html=True)

    gen_mockup_btn = st.button("✨ Generate Live Website Mockup Preview", type="primary", use_container_width=True)

    if gen_mockup_btn:
        if not gemini_key:
            st.error("Please configure your Gemini API Key in the sidebar.")
        elif not mock_name:
            st.error("Please provide a business name.")
        else:
            with st.spinner(f"Designing custom React/Tailwind landing page for {mock_name} using Gemini 2.5 Flash..."):
                html_output = generate_landing_page_mockup(
                    biz_name=mock_name,
                    niche=mock_niche,
                    area=mock_area,
                    phone=mock_phone,
                    rating=str(mock_rating).split()[0] if mock_rating else "4.9",
                    reviews=50,
                    theme=mock_theme,
                    api_key_to_use=gemini_key,
                )
                st.session_state.mockup_html = html_output
                st.session_state.mockup_biz_name = mock_name

    # Display Rendered HTML Preview & Download
    if st.session_state.mockup_html:
        st.divider()
        st.subheader(f"🖥️ Live Interactive Preview: {st.session_state.mockup_biz_name}")

        d_col1, d_col2 = st.columns([1, 3])
        safe_biz_filename = re.sub(r"[^\w\-]", "_", st.session_state.mockup_biz_name).lower()

        d_col1.download_button(
            "⬇️ Download HTML File",
            data=st.session_state.mockup_html.encode("utf-8"),
            file_name=f"{safe_biz_filename}_website_mockup.html",
            mime="text/html",
            use_container_width=True,
        )

        with d_col2:
            st.caption("You can open this downloaded HTML file in any browser or host it on Netlify / Vercel in 60 seconds.")

        # Live IFrame Component render
        components.html(st.session_state.mockup_html, height=750, scrolling=True)

        with st.expander("🔍 View Raw HTML Code"):
            st.code(st.session_state.mockup_html, language="html")


# ============================================================================
# TAB 5: AI SALES ASSISTANT (CHATBOT)
# ============================================================================
with tab_chat:
    st.markdown("### 🤖 JD Tech AI Sales Consultant")
    st.caption("Powered by **Gemini 2.5 Flash**. Ask questions about your currently scraped leads, generate targeted phone pitch scripts, or craft high-converting cold emails.")

    # Context indicator
    active_leads_count = len(st.session_state.results_df) if st.session_state.results_df is not None else 0
    if active_leads_count > 0:
        current_niche = st.session_state.get("target_business", "leads")
        current_area = st.session_state.get("target_location", "")
        st.markdown(
            f"""
        <div class="context-card">
            🟢 <b>Lead Context Active:</b> <b>{active_leads_count} {current_niche}</b> leads in <b>{current_area}</b> loaded into chatbot memory. You can ask for specific scripts or analysis on them!
        </div>
        """,
            unsafe_allow_html=True,
        )
    elif st.session_state.crm_leads:
        st.markdown(
            f"""
        <div class="context-card">
            🟢 <b>CRM Context Active:</b> <b>{len(st.session_state.crm_leads)} leads</b> in Pipeline CRM loaded into chatbot memory.
        </div>
        """,
            unsafe_allow_html=True,
        )
    else:
        st.info("💡 **Tip**: Scrape leads in Tab 1 or Tab 2 first, and I will automatically have full context of all your businesses, phone numbers, and addresses here!")

    # Quick Prompts
    st.write("**Quick Prompts:**")
    q_col1, q_col2, q_col3, q_col4 = st.columns(4)
    quick_prompt = None

    if q_col1.button("📞 30s Cold Call Script", use_container_width=True):
        quick_prompt = "Write a high-converting 30-second cold call script for me (Junaid at JD Tech Solutions) to call businesses that have no website and pitch a fast React + Tailwind site."

    if q_col2.button("💬 WhatsApp Pitch", use_container_width=True):
        quick_prompt = "Give me 3 short, punchy WhatsApp message variations that get business owners without websites to reply and ask for a mockup."

    if q_col3.button("📊 Analyze Current Leads", use_container_width=True):
        quick_prompt = "Look at my currently scraped leads and give me a strategic breakdown: which ones should I call first and why?"

    if q_col4.button("💡 Top 5 Local Niches", use_container_width=True):
        quick_prompt = "What are the top 5 most profitable service business niches where owners often lack websites and are willing to pay $1,500 - $3,000 for a website?"

    # Conversation Display
    chat_container = st.container()
    with chat_container:
        for message in st.session_state.chat_messages:
            avatar = "🤖" if message["role"] == "assistant" else "👤"
            with st.chat_message(message["role"], avatar=avatar):
                st.markdown(message["content"])

    # Chat Input Box
    user_input = st.chat_input("Ask a question, request a phone script, or brainstorm niches...")

    active_prompt = quick_prompt if quick_prompt else user_input

    if active_prompt:
        st.session_state.chat_messages.append({"role": "user", "content": active_prompt})
        with st.chat_message("user", avatar="👤"):
            st.markdown(active_prompt)

        with st.chat_message("assistant", avatar="🤖"):
            with st.spinner("JD Tech AI is thinking..."):
                reply = call_gemini_chat(
                    chat_history=st.session_state.chat_messages,
                    leads_df=st.session_state.results_df,
                    crm_leads=st.session_state.crm_leads,
                    api_key_to_use=gemini_key,
                )
                st.markdown(reply)

        st.session_state.chat_messages.append({"role": "assistant", "content": reply})

    st.write("")
    if st.button("🗑️ Clear Conversation", type="secondary"):
        st.session_state.chat_messages = [
            {
                "role": "assistant",
                "content": "👋 Chat cleared! How can I help you and JD Tech Solutions today?",
            }
        ]
        st.rerun()
