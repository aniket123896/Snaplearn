
from google import genai
from google.genai import types
import streamlit as st
import json

from twilio.rest import Client as TwilioClient

from prompts import SYSTEM_PROMPT, WELCOME_MESSAGE_TEMPLATE,SUMMARY_REQUEST_PROMPT
GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
TWILIO_ACCOUNT_SID = st.secrets["TWILIO_ACCOUNT_SID"]
TWILIO_AUTH_TOKEN = st.secrets["TWILIO_AUTH_TOKEN"]
TWILIO_WHATSAPP_FROM = st.secrets["TWILIO_WHATSAPP_FROM"]
TWILIO_CONTENT_SID = st.secrets["TWILIO_CONTENT_SID"]

MODEL_NAME = "gemini-3.8-flash"

def clean_whatsapp_text(text):
    if not text:
        return "No any study summary is available for today."
    text = " ".join(text.split())
    return text[:1500] + "..." if len(text) > 1500 else text

def send_whatsapp(to_number,user_name, summary):
    try:
        content_variables = json.dumps(
            {"1" : user_name, "2": clean_whatsapp_text(summary)}, ensure_ascii=False
        )
        message = twilio_client.messages.create(
            from_=TWILIO_WHATSAPP_FROM,
            to=f"whatsapp:{to_number}",
            content_sid=TWILIO_CONTENT_SID,
            content_variables=content_variables,
        )
        return True, message.sid
    except Exception as e:
        return False, str(e)

@st.cache_resource
def get_gemini_client():
    return genai.Client(api_key = GEMINI_API_KEY)

@st.cache_resource
def get_twilio_client():
    return TwilioClient(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
twilio_client = get_twilio_client()

gemini_client = get_gemini_client()
def render_message(message):
    with st.chat_message(message["role"]):
        if message["kind"] == "text":
            st.markdown(message["content"])
        elif message["kind"] == "image":
            st.image(message["content"])
        elif message["kind"] == "video":
            st.video(message["content"])
        elif message["kind"] == "audio":
            st.audio(message["content"])
        else:
            st.warning(f"Unknown message kind: {message['kind']}")
def add_message(role, kind, content):
    st.session_state.messages.append({
        "role": role,
        "kind": kind,
        "content": content
    })
    render_message(st.session_state.messages[-1])
def ask_gemini(parts):
    try: 
        return st.session_state.chat.send_message(parts).text
    except Exception as error:
        return f"Sorry, Something went wrong: {error}"
    

# s1 : onboarding form (uusername and learning goals)
if 'onboarded' not in st.session_state:
    st.title("SnapLearn AI 🚀")
    st.caption("Turn Every Snap into a Learning Experience")
    
    with st.form("onboarding_form"):
        st.write("Welcome to SnapLearn AI! Please provide the following information to get started:")
        name = st.text_input("Name")
        whatsapp_number = st.text_input("WhatsApp Number",placeholder="e.g., +91 8668988344")
        email = st.text_input("Email")
        learning_goals = st.text_area("Learning Goals")
        
        submitted = st.form_submit_button("Lets's Go!😉")
        
        if submitted:
            if not name or not email or not learning_goals or not whatsapp_number:
                st.error("Please fill in all fields.😊")
            else:
                st.session_state['onboarded'] = True
                st.session_state['name'] = name.strip()
                st.session_state['whatsapp_number'] = whatsapp_number.strip()
                st.session_state['email'] = email.strip()
                st.session_state['learning_goals'] = learning_goals
                st.success("Thank you for onboarding! You can now use SnapLearn AI. Best Regards, Team Aniket🦋")
                # Activate my AI 
                st.session_state.chat = gemini_client.chats.create(
                    model=MODEL_NAME,
                    config=types.GenerateContentConfig(system_instruction=SYSTEM_PROMPT),
                    
                )
                st.session_state.messages = []
                st.session_state.onborded = True
                st.rerun()
        st.stop()
        
        # Creating the chat interface for the students.!        
        
header_col, button_col = st.columns([5,2], vertical_alignment="center")

with header_col:
    st.title("SnapLearn AI 🚀")
    
with button_col:
    send_disabled = len(st.session_state.messages) <= 1
    if st.button("📩 Send to WhatsApp", disabled=send_disabled, use_container_width = True):
        with st.spinner("Summarizing your day..."):
            summary = ask_gemini ([SUMMARY_REQUEST_PROMPT])
        success, info = send_whatsapp(st.session_state.whatsapp_number, st.session_state.name , summary)
        
        if success:
            st.success("Message sent successfully! ✅")
        else:
            st.error(f"Failed to send message. Error: {info}")
            
st.caption(f"Logged in as: {st.session_state.name} - updates go to {st.session_state.whatsapp_number}  ")
if not st.session_state.messages:
    add_message("assistant", "text", WELCOME_MESSAGE_TEMPLATE.format(name=st.session_state.name))
else:
    for message in st.session_state.messages:
        render_message(message)
        
user_input = st.chat_input(
    "Type your message here...",
    accept_file=True,
    file_type=["jpg", "jpeg", "png"],
)

if user_input:
    parts = []
    text = user_input.text
    files = user_input.files

    # 1. Handle image upload if provided
    if files:
        photo = files[0]
        photo_bytes = photo.getvalue()
        add_message("user", "image", photo_bytes)
        parts.append(types.Part.from_bytes(data=photo_bytes, mime_type=photo.type))

    # 2. Handle text prompt
    if text:
        add_message("user", "text", text)
        parts.append(text)
    elif files:
        fallback_prompt = "What should I write the answer to this image? Please summarize it in a few lines."
        parts.append(fallback_prompt)

    # 3. Request response from Gemini
    if parts:
        with st.spinner("Generating response..."):
            answer = ask_gemini(parts)
        add_message("assistant", "text", answer)