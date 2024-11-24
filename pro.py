
from openai import OpenAI
import streamlit as st
import json
import base64
import streamlit_authenticator as stauth
import yaml
import bcrypt
import os
import datetime

# Load the configuration from the YAML file
with open("doc/credentialss.yaml") as file:
    config = yaml.safe_load(file)

# Initialize the authenticator
authenticator = stauth.Authenticate(
    config['credentialss'],
    config['cookie']['name'],
    config['cookie']['key'],
    config['cookie']['expiry_days'],
    config['preauthorized']
)

# Attempt to authenticate the user
name, authentication_status, username = authenticator.login('main')

# Check for admin login - replace 'admin_password_hash' with the actual hash
admin_username = 'admin'
admin_password_hash = config['credentialss']['usernames']['admin']['password']
if username == admin_username and bcrypt.checkpw('admin'.encode('utf-8'), admin_password_hash.encode('utf-8')):
    name, authentication_status, username = (admin_username, True, admin_username)

json_files = {
    "דיווח אחיד": "doc/pro.json",
}

def reset_topic_after_timeout():
    current_time = datetime.datetime.now()
    last_interaction = st.session_state.get('last_interaction', current_time)
    
    # Check if more than 5 minutes have passed since last interaction
    if (current_time - last_interaction).total_seconds() > 300:
        st.session_state.current_topic = 'default'
        print("Topic reset to default due to inactivity.")
    
    # Update the last interaction time
    st.session_state.last_interaction = current_time

def load_stop_words(file_path):
    with open(file_path, 'r', encoding='utf-8') as file:
        return [line.strip() for line in file.readlines()]

stop_words_path = "doc/heb_stopwords.txt"  
stop_words = load_stop_words(stop_words_path)

def load_data():
    for key in json_files:
        if key != "default":
            selected_option = key
            break
    json_file_path = json_files[selected_option]

    with open(json_file_path, 'r', encoding='utf-8') as file:
        json_data = json.load(file)

    json_documents = extract_text_from_json(json_data)

    return json_documents, json_data

def extract_text_from_json(json_data):
    text_list = []
    def extract_text(obj):
        if isinstance(obj, dict):
            for key, value in obj.items():
                extract_text(value)
        elif isinstance(obj, list):
            for item in obj:
                extract_text(item)
        elif isinstance(obj, str):
            text_list.append(obj)

    extract_text(json_data)
    return text_list

documents, json_data = load_data()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

guidance_data = json_data

def json_to_string(data, depth=0):
    output = []
    if isinstance(data, dict):
        for key, value in data.items():
            output.append(" " * depth + str(key) + ":")
            output.append(json_to_string(value, depth + 2))
    elif isinstance(data, list):
        for item in data:
            output.append(json_to_string(item, depth + 2))
    else:
        return " " * depth + str(data)
    return "\n".join(output)

guidance_string = json_to_string(guidance_data)

if 'conversation_history' not in st.session_state:
    st.session_state.conversation_history = ""

MAX_EXCHANGES = 6
def update_conversation_history(history, user_input, ai_response):
    exchanges = history.split('\n\n')
    # Use the user's full name instead of "Human"
    new_exchange = f"{st.session_state.username}: {user_input}\nAI Assistant: {ai_response}"
    exchanges.append(new_exchange)
    recent_exchanges = exchanges[-MAX_EXCHANGES:]

    with open("doc/inputs_and_outputs", 'a', encoding='utf-8') as file:
        file.write(new_exchange + "\n\n")

    return '\n\n'.join(recent_exchanges)

if 'current_topic' not in st.session_state:
    st.session_state.current_topic = "default"

def load_input_json_mapping(file_path):
    mapping = {}
    with open(file_path, 'r', encoding='utf-8') as file:
        for line in file:
            parts = line.strip().split(':')
            if len(parts) == 2:
                keywords, json_file = parts
                for keyword in keywords.split(','):
                    mapping[keyword.strip()] = json_file.strip()
    return mapping

def langchain_bot(user_input, conversation_history, client, guidance_string, user_full_name):
    # If no direct match found, use the OpenAI client to generate a response
    lm_response = stream_openai_response(conversation_history, user_input, client, guidance_string, user_full_name)

    # Update the conversation history with the new exchange
    updated_history = update_conversation_history(conversation_history, user_input, lm_response)
    st.session_state.conversation_history = updated_history
    return lm_response

if authentication_status is None:
    st.warning('נא להזין שם משתמש וסיסמה')

elif authentication_status is False:
    st.error('Username/password is incorrect')

if authentication_status:
    user_full_name = config['credentialss']['usernames'].get(username, {}).get('name', 'Unknown User')
    print("Authenticated user's full name:", user_full_name)

    def load_custom_css():
        custom_css = """
        <style>
        /* Style for the spinner */
        .stSpinner {
            position: fixed;  /* Fixed position */
            top: 20%;        /* Place it in the middle vertically */
            left: 35%;       /* Place it in the middle horizontally */
            transform: translate(-50%, -50%); /* Adjust the position accurately */
            z-index: 100;    /* Ensure it's on top */
        }

        /* Increase the size of the spinner */
        .stSpinner > div {
            width: 800px;    /* Width of the spinner */
            height: 400px;   /* Height of the spinner */
        }
        </style>
        """
        st.markdown(custom_css, unsafe_allow_html=True)

    # Call this function at the beginning of your app to load the custom styles
    load_custom_css()

    def set_images_and_background(logo_path: str, tamal_path: str):
        with open(logo_path, "rb") as logo_file:
            logo_encoded = base64.b64encode(logo_file.read()).decode()
        with open(tamal_path, "rb") as tamal_file:
            tamal_encoded = base64.b64encode(tamal_file.read()).decode()

        css = """
        <style>
        .logo-section {
            position: fixed;
            right: 35px;
            bottom: -20px;
            z-index: 10;
        }
        .tamal-section {
            position: absolute;
            left: -660px;
            top: 0px;
            z-index: 10;
        }
        .color-section {
            position: fixed;
            left: 0;
            top: 0;
            width: 25%;
            height: 100vh;
            background-color: rgb(88,165,200);
            z-index: 5;
        }
        .stApp {
            direction: rtl;
            z-index: 1;
        }
        .stChatMessage {
            direction: rtl;
            text-align: right;
        }
        </style>
        """
        st.markdown(css, unsafe_allow_html=True)
        st.markdown('<div class="color-section"></div>', unsafe_allow_html=True)
        st.markdown(f'<div class="logo-section"><img src="data:image/png;base64,{logo_encoded}" alt="Logo" width="400px" height="300px"></div>', unsafe_allow_html=True)
        st.markdown(f'<div class="tamal-section"><img src="data:image/png;base64,{tamal_encoded}" alt="Tamal"></div>', unsafe_allow_html=True)

    # Apply custom styles and images
    set_images_and_background("images/logo.png", "images/tamal.png")

    if 'chat_history' not in st.session_state:
        st.session_state.chat_history = []

    if 'display_chat' not in st.session_state:
        st.session_state.display_chat = True

    if 'user_full_name' not in st.session_state:
        st.session_state.user_full_name = config['credentialss']['usernames'].get(username, {}).get('name', 'Unknown User')

    def stream_openai_response(conversation_history, user_input, client, guidance_string, user_full_name):
        response_placeholder = st.empty()

        background_info = f"My name is {st.session_state.user_full_name}."

        # Only add the user's name at the start of the conversation for context.
        if not conversation_history:
            user_input = f"My name is {user_full_name}. " + user_input

        # Now, concatenate the guidance string with the conversation history and the current user input
        full_input = f"{background_info}\n{guidance_string}\n{conversation_history}\nUser: {user_input}"

        full_response = ""
        try:
            for response in client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "system", "content": full_input}, {"role": "user", "content": user_input}],
                max_tokens=3000,
                temperature=0.9,
                stream=True,
            ):
                delta_content = response.choices[0].delta.content if response.choices[0].delta.content else ""
                full_response += delta_content
                response_placeholder.markdown(full_response)

        except Exception as e:
            st.error(f"An error occurred: {e}")

        return full_response

    # Title of the app
    st.title("💬 טמל-A.I")

    # Display chat history
    if st.session_state.display_chat:
        for msg in st.session_state.chat_history:
            role = msg["role"]
            content = msg["content"]
            st.chat_message(role).write(content)

    # User input section
    prompt = st.chat_input("כתוב כאן:")
    if prompt:
        # Call the reset function immediately after receiving prompt to manage session state
        reset_topic_after_timeout()

        # Display the user's message
        with st.chat_message("user"):
            st.markdown(prompt)

        assistant_response = ""

        with st.chat_message("assistant"):
            st.markdown(assistant_response)

        if prompt:
            st.session_state.chat_history.append({"role": "user", "content": prompt})
            st.session_state.display_chat = False
            with st.spinner('מקליד/ה..'):
                lm_response = langchain_bot(prompt, st.session_state.conversation_history, client, guidance_string, user_full_name)

                json_file_path = json_files.get(st.session_state.current_topic)
                    
                if json_file_path:
                    json_data = json.load(open(json_file_path, "r", encoding="utf-8"))
                    guidance_string = json.dumps(json_data)
                    
                st.session_state.chat_history.append({"role": "assistant", "content": lm_response})
                
            st.session_state.display_chat = True
