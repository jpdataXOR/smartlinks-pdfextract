import streamlit as st
import fitz  # PyMuPDF
import requests
import json
from PIL import Image
import base64

st.title("Invoice Amount Extractor ✨")

# --- API key handling ---
params = st.query_params
api_key = params.get("api_key", [None])[0]

if not api_key:
    api_key = st.text_input("Enter your OpenRouter API Key:", type="password")

# Upload PDF
uploaded_file = st.file_uploader("Upload Invoice PDF", type=["pdf"])
if uploaded_file and api_key:
    # Open PDF with PyMuPDF
    doc = fitz.open(stream=uploaded_file.read(), filetype="pdf")

    # Preview thumbnails (better resolution)
    st.subheader("Preview Pages")
    images = []
    for i, page in enumerate(doc):
        pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))  # high res
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        st.image(img, caption=f"Page {i+1}", use_container_width=True)
        images.append(img)

    # --- Extract with AI ---
    if st.button("✨ Extract Invoice Amount", type="primary"):
        with st.spinner("Calling AI to extract invoice amount..."):
            # Convert first page image to base64
            buffered = images[0]
            buffered.save("temp.png")
            with open("temp.png", "rb") as f:
                b64_img = base64.b64encode(f.read()).decode("utf-8")

            # Call OpenRouter API
            url = "https://openrouter.ai/api/v1/chat/completions"
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            }
            prompt = """
            You are an information extraction AI. 
            Extract the invoice total amount from this invoice image.
            Respond strictly in JSON like:
            { "invoice_amount": "216.69" }
            """
            payload = {
                "model": "google/gemini-2.5-flash-image-preview:free",
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64_img}"}}
                        ],
                    }
                ],
            }

            resp = requests.post(url, headers=headers, data=json.dumps(payload))
            data = resp.json()

            # Extract model output
            # Extract model output safely
            try:
                raw_text = data["choices"][0]["message"]["content"]

                # Sometimes model wraps JSON in ```json ... ```
                if raw_text.startswith("```"):
                    raw_text = raw_text.strip("`")  # remove backticks
                    if raw_text.lower().startswith("json"):
                        raw_text = raw_text[4:]  # drop "json" hint

                extracted_json = json.loads(raw_text.strip())
            except Exception as e:
                extracted_json = {"error": str(e), "raw": data}


            # Debug window
            with st.expander("Show Extracted JSON (Debug)"):
                st.json(extracted_json)

            # Show main extracted amount
            if "invoice_amount" in extracted_json:
                amount = float(extracted_json["invoice_amount"])
                st.markdown(f"**Extracted Invoice Amount:** 💰 **{amount}**")

                # --- Rule application ---
                st.subheader("Apply Processing Rules")
                rules = st.text_area(
                    "Enter rules in English (example: 'If amount > 200 apply 10% discount, else no discount')"
                )
                if rules:
                    rule_prompt = f"""
                    You are a financial rule engine.
                    Given the extracted JSON: {json.dumps(extracted_json)},
                    and the rules: '{rules}',
                    calculate the final processed amount.
                    Respond strictly in JSON like:
                    {{ "processed_amount": <value>, "explanation": "<why>" }}
                    """
                    rule_payload = {
                        "model": "google/gemini-2.5-flash:free",
                        "messages": [{"role": "user", "content": [{"type": "text", "text": rule_prompt}]}],
                    }

                    resp2 = requests.post(url, headers=headers, data=json.dumps(rule_payload))
                    data2 = resp2.json()

                    try:
                        content2 = data2["choices"][0]["message"]["content"][0]["text"]
                        processed_json = json.loads(content2)
                    except Exception as e:
                        processed_json = {"error": str(e), "raw": data2}

                    with st.expander("Processed JSON (Debug)"):
                        st.json(processed_json)

                    if "processed_amount" in processed_json:
                        st.markdown(
                            f"✅ **Processed Amount:** 💲 **{processed_json['processed_amount']}**"
                        )
                        if "explanation" in processed_json:
                            st.info(processed_json["explanation"])