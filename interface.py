import streamlit as st
import openai
import re
from dotenv import load_dotenv
import os

from io import BytesIO
import PyPDF2
import docx

load_dotenv(".env")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
client = openai.OpenAI(api_key=OPENAI_API_KEY)

st.set_page_config(page_title="AI-powered Compliance Checker", layout="wide", page_icon="✅")

col1, spacer, col2 = st.sidebar.columns([4, 2, 5])
with col1:
    st.markdown("### ⚙️ Settings")
with col2:
    st.image("Logo.jpg", width=100)

model = st.sidebar.selectbox("Choose GPT model:", ["gpt-3.5-turbo", "gpt-4o", "gpt-4.1"])

st.sidebar.markdown("### Choose Compliance Rules (default on Rule 5)")
rules_options = [
    "Must be based on principles of fair dealing and good faith.",
    "Must be fair and balanced.",
    "Must provide a sound basis for evaluating the facts.",
    "Cannot omit any material fact or qualification, which would cause the communication to be misleading.",
    "Cannot make any false, exaggerated, unwarranted, promissory or misleading statement or claim."
]
selected_rules = []
for i, rule in enumerate(rules_options):
    if st.sidebar.checkbox(f"Rule {i+1}: {rule}", value=False, key=f"rule_{i}"):
        selected_rules.append(rule)

apply_custom_rule = st.sidebar.checkbox("Apply custom rule")
custom_additional = st.sidebar.text_area("Write your custom rule here:", value="", height=80)

all_selected_rules = selected_rules.copy()
if apply_custom_rule and custom_additional.strip():
    all_selected_rules.append(custom_additional.strip())
if not all_selected_rules:
    all_selected_rules = [rules_options[4]]
final_rule_prompt = " AND ".join(all_selected_rules)


st.title("AI-powered Compliance Checker")
st.markdown(
    """
    You can either **paste** your material below or **upload** a PDF/Word document.
    The AI will extract the text (if you uploaded a file) and check for compliance
    based on your selected rule(s).

    - If **compliant**: you'll see a green success message.
    - If **noncompliant**: the red-flagged part, reason, and a revised version will be shown.
    """
)


file_uploader = st.file_uploader(
    "Upload a PDF or Word document (optional):",
    type=["pdf", "docx"],
    help="If you upload a file, its entire text will be extracted and checked."
)


material = ""

def extract_text_from_pdf(uploaded_file: BytesIO) -> str:
    """Extracts all text from a PDF file using PyPDF2."""
    pdf_reader = PyPDF2.PdfReader(uploaded_file)
    full_text = []
    for page in pdf_reader.pages:
        text = page.extract_text()
        if text:
            full_text.append(text)
    return "\n".join(full_text)

def extract_text_from_docx(uploaded_file: BytesIO) -> str:
    """Extracts all text from a .docx file using python-docx."""
    doc = docx.Document(uploaded_file)
    full_text = []
    for para in doc.paragraphs:
        if para.text:
            full_text.append(para.text)
    return "\n".join(full_text)


if file_uploader is not None:
    file_extension = file_uploader.name.split(".")[-1].lower()
    try:
        if file_extension == "pdf":
            with BytesIO(file_uploader.read()) as pdf_buffer:
                extracted_text = extract_text_from_pdf(pdf_buffer)
        elif file_extension == "docx":

            extracted_text = extract_text_from_docx(file_uploader)
        else:
            st.error("Unsupported file type. Please upload a PDF or .docx file.")
            extracted_text = ""

        if not extracted_text.strip():
            st.warning("No text could be extracted from the file. Please check the file contents.")
        else:
            st.markdown("### 📄 Extracted Text Preview")
 
            st.text_area("Preview (first 500 chars):", extracted_text[:500] + ("..." if len(extracted_text) > 500 else ""), height=150)

            material = extracted_text

    except Exception as e:
        st.error(f"Error extracting text from file: {e}")
        material = ""
else:

    material = st.text_area("Or paste your material here:", height=200)


if st.button("Check Compliance"):
    if not material.strip():
        st.warning("Please either upload a file or paste some material to check.")
    else:
        with st.spinner("Checking compliance..."):
            SYSTEM_PROMPT = f"""
Is the following sentence compliant with financial service advertising regulations that {final_rule_prompt}

For each input material:
1. If compliant, reply:
    - "Compliant: The material is compliant."
2. If noncompliant, reply in this format:
    - "Noncompliant: The material is noncompliant."
    - "Red-flagged part(s): [display the whole input material and highlight only problematic words or sentence by wrapping them in <span style='color:red; font-weight:bold'> ... </span>]"
    - "Reason: [explain why it's noncompliant]"
    - "Revised Version: [rewrite the provided material to make it compliant and show the whole revised material]"
Only use HTML <span style='color:red; font-weight:bold'> ... </span> to highlight.
Only output this structure; no extra explanation.
            """

            try:
                response = client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": material}
                    ],
                    max_tokens=4096
                )
                reply = response.choices[0].message.content.strip()


                if "Compliant: The material is compliant." in reply:
                    st.success("✅ The material is compliant.")
                else:

                    red_flagged = re.search(
                        r"Red-flagged part\(s\):\s*(.*?)\s*Reason:",
                        reply, re.DOTALL | re.IGNORECASE
                    )
                    reason = re.search(
                        r"Reason:\s*(.*?)\s*Revised Version:",
                        reply, re.DOTALL | re.IGNORECASE
                    )
                    revision = re.search(
                        r"Revised Version:\s*(.*)",
                        reply, re.DOTALL | re.IGNORECASE
                    )

                    if red_flagged:
                        st.markdown("### 🚩 Red-flagged Part")
                        st.markdown(red_flagged.group(1).strip(), unsafe_allow_html=True)

                    if reason:
                        st.markdown("### ⚠️ Reason")
                        st.info(reason.group(1).strip())

                    if revision:
                        st.markdown("### ✅ Revised Version")
                        st.success(revision.group(1).strip())
                        st.code(revision.group(1).strip(), language="markdown")

                    if not (red_flagged or reason or revision):
                        st.warning("⚠️ Could not parse the response. Try checking your prompt or input format.")

            except Exception as e:
                st.error(f"An error occurred: {e}")
