
import streamlit as st
import pandas as pd
from datetime import datetime, date
import json
from google import genai
from google.genai import types
from PIL import Image
import os

# --- Page Config ---
st.set_page_config(
    page_title="VibeLedger",
    page_icon="💸",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# --- Custom Styling ---
st.markdown("""
    <style>
    .stTextInput > div > div > input {
        background-color: #1E1E1E;
        color: #E0E0E0;
        border-radius: 12px;
        border: 1px solid #333;
    }
    .stButton > button {
        border-radius: 12px;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 1px;
    }
    .metric-card {
        background-color: #262730;
        padding: 15px;
        border-radius: 10px;
        border: 1px solid #333;
        text-align: center;
    }
    </style>
""", unsafe_allow_html=True)

# --- Setup & State ---
if "transactions" not in st.session_state:
    st.session_state.transactions = []

if "messages" not in st.session_state:
    st.session_state.messages = []

# Initialize Gemini Client
# Expects st.secrets["GOOGLE_API_KEY"] to be set
api_key = os.environ.get("GOOGLE_API_KEY") or st.secrets.get("GOOGLE_API_KEY")

if not api_key:
    st.error("🔑 Missing Google API Key. Please add it to .streamlit/secrets.toml")
    st.stop()

client = genai.Client(api_key=api_key)
MODEL_ID = "gemini-2.0-flash-exp" # Using the latest fast model

# --- Helper Functions ---

def parse_receipt_or_text(text_input, image_input, trip_mode):
    """
    Uses Gemini to extract structured data from text or image.
    Features: Natural Language Logging, Smart Category, Cat-egory Logic, Receipt Vision
    """
    
    current_date = date.today().isoformat()
    
    prompt = f"""
    You are a financial transaction parser. Extract the following JSON fields:
    - date: YYYY-MM-DD (default to {current_date} if not found)
    - amount: number (positive for expense, negative for income)
    - description: string (short summary)
    - category: string (one of: Food, Transport, Shopping, Bills, Entertainment, Health, Pet Care, Travel, Salary, Other)
    - type: string (Shared or Personal) - Guess based on context. "Dinner" is usually Shared. "Makeup" is Personal.
    - is_subscription: boolean (true if it looks like Netflix, Spotify, or a recurring bill)

    Special Rules:
    1. If the text mentions 'cats', 'kitten', or 'litter', force category to 'Pet Care'.
    2. If trip_mode is True, append "🇲🇽 " to the start of the description.
    3. If it's a receipt image, extract the total.

    Input context: Trip Mode is {'ON' if trip_mode else 'OFF'}.
    """

    contents = []
    if text_input:
        contents.append(text_input)
    if image_input:
        contents.append(image_input)
    
    contents.append(prompt)

    try:
        response = client.models.generate_content(
            model=MODEL_ID,
            contents=contents,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema={
                    "type": "OBJECT",
                    "properties": {
                        "date": {"type": "STRING"},
                        "amount": {"type": "NUMBER"},
                        "description": {"type": "STRING"},
                        "category": {"type": "STRING"},
                        "type": {"type": "STRING", "enum": ["Shared", "Personal"]},
                        "is_subscription": {"type": "BOOLEAN"}
                    },
                    "required": ["amount", "description", "category", "type"]
                }
            )
        )
        return json.loads(response.text)
    except Exception as e:
        st.error(f"AI Error: {e}")
        return None

def get_vibe_check(transactions):
    """
    Feature: Vibe Check Summary & Advisor Logic
    """
    if not transactions:
        return "No vibes yet. Start spending!"
    
    tx_summary = json.dumps(transactions[-10:]) # Send last 10
    
    prompt = f"""
    Analyze these recent transactions and give a 'Vibe Check' summary in 2 sentences.
    Be casual and witty. Mention if we are spending too much on food or if we are doing good.
    Data: {tx_summary}
    """
    
    response = client.models.generate_content(
        model=MODEL_ID,
        contents=prompt
    )
    return response.text

# --- UI Layout ---

st.title("💸 VibeLedger")
st.caption("Tracking money, one vibe at a time.")

# 1. Input Section
with st.container():
    st.subheader("New Vibe")
    
    col1, col2 = st.columns([3, 1])
    with col1:
        text_vibe = st.text_input("What did you spend?", placeholder="e.g. $45 on Sushi for dinner")
    with col2:
        trip_mode = st.toggle("Trip Mode 🇲🇽", help="Tag expenses for Mexico")
    
    uploaded_file = st.file_uploader("Or snap a receipt", type=["jpg", "png", "jpeg"], label_visibility="collapsed")
    
    if st.button("Log Entry", type="primary", use_container_width=True):
        image_part = None
        if uploaded_file:
            image = Image.open(uploaded_file)
            image_part = image
            
        if not text_vibe and not image_part:
            st.warning("Feed me text or a receipt!")
        else:
            with st.spinner("Analyzing vibe..."):
                data = parse_receipt_or_text(text_vibe, image_part, trip_mode)
                
                if data:
                    st.session_state.transactions.append(data)
                    st.toast(f"Logged: {data['description']} (${data['amount']})")
                    # Clear input hack (requires rerun or session state manips, simplified here)

# 2. Dashboard Section
if st.session_state.transactions:
    st.divider()
    
    # Feature: Predictive Balance & Shared Pulse
    df = pd.DataFrame(st.session_state.transactions)
    
    # Simple projection: If this daily rate continues...
    total_spent = df['amount'].sum()
    days_active = 1 # Simplified
    projected = total_spent * 30 
    
    # Feature: Subscription Hunter
    subs = df[df['is_subscription'] == True]
    
    col_a, col_b, col_c = st.columns(3)
    with col_a:
        st.metric("Total Spent", f"${total_spent:.2f}")
    with col_b:
        shared_pct = len(df[df['type'] == 'Shared']) / len(df) * 100
        st.metric("Shared Pulse", f"{shared_pct:.0f}%")
    with col_c:
        st.metric("Month Forecast", f"${projected:.0f}")

    if not subs.empty:
        st.info(f"👀 Subscription Hunter found: {', '.join(subs['description'].tolist())}")

    # Feature: Vibe Check Summary
    st.info(f"✨ **Current Vibe:** {get_vibe_check(st.session_state.transactions)}")

    # Recent Vibes Table
    st.subheader("Recent Vibes")
    st.dataframe(
        df[['date', 'description', 'category', 'amount', 'type']].sort_values(by='date', ascending=False),
        use_container_width=True,
        hide_index=True
    )

# 3. Advisor Bot (Chat)
st.divider()
st.subheader("💬 Ask the Advisor")

# Display chat messages
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if prompt := st.chat_input("Can we afford a new iPad?"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        context = json.dumps(st.session_state.transactions)
        advisor_prompt = f"""
        You are a financial advisor for a couple. You have access to their transaction history: {context}.
        Answer the user's question: "{prompt}".
        Be helpful, slightly cautious about money, but supportive of good vibes.
        """
        
        response = client.models.generate_content(
            model=MODEL_ID,
            contents=advisor_prompt
        )
        st.markdown(response.text)
        st.session_state.messages.append({"role": "assistant", "content": response.text})

# --- Footer ---
st.markdown("---")
st.caption("VibeLedger v1.0 • Built with Streamlit & Gemini")
