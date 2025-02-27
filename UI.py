import streamlit as st
import requests
import os
from Config_Data import load_config_data
# from dotenv import load_dotenv
# load_dotenv()

# COMPLIANCE_CHECK_API = os.getenv("COMPLIANCE_CHECK_API")
# UPDATED_DOCUMENT_API = os.getenv("UPDATED_DOCUMENT_API")

COMPLIANCE_CHECK_API = load_config_data["COMPLIANCE_CHECK_API"]
UPDATED_DOCUMENT_API = load_config_data["UPDATED_DOCUMENT_API"]

st.title("📄 Document Compliance Checker")

uploaded_file = st.file_uploader("Upload a PDF or DOCX file", type=["pdf", "docx"])

if uploaded_file:
    st.write(f"✅ **Uploaded File:** {uploaded_file.name}")

    status_col1, update_col2, clear_col3 = st.columns(3)
    
    if status_col1.button("Check Compliance Status"):
        with st.spinner("Checking compliance..."):
            files = {"file": uploaded_file.getvalue()}
            response = requests.post(COMPLIANCE_CHECK_API, files={"file": uploaded_file}, timeout=30)
            
            if response.status_code == 200:
                compliance_status = response.json().get("compliance_status", "No status returned")
                st.success(f"**Compliance Status:** {compliance_status}")
            else:
                st.error(f"Error: {response.json()}")

    if update_col2.button("Update Document"):
        with st.spinner("Updating document..."):
            files = {"file": uploaded_file.getvalue()}
            response = requests.post(UPDATED_DOCUMENT_API, files={"file": uploaded_file}, timeout=30)

            if response.status_code == 200:
                processed_filename = f"Processed_{uploaded_file.name}"
                with open(processed_filename, "wb") as f:
                    f.write(response.content)
                
                with open(processed_filename, "rb") as f:
                    st.download_button(label="Download Updated Document", data=f, file_name=processed_filename, mime="application/octet-stream")
                os.remove(processed_filename)
            else:
                st.error(f"Error: {response.json()}")

    if clear_col3.button("Clear"):
        st.rerun()
