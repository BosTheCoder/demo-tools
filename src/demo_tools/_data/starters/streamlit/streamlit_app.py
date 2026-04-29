import streamlit as st

st.title("Hello from Streamlit")
st.write("Edit `streamlit_app.py` to build your demo.")

name = st.text_input("Your name", "world")
st.write(f"Hello, {name}!")
