import streamlit as st
import fitz  # PyMuPDF
import requests
import json
from PIL import Image
import base64

st.title("Invoice Amount Extractor ✨")

# --- API key handling ---
params = st.query_params
api_key = params.get("api_key", "")

if not api_key:
    api_key = st.text_input("Enter your OpenRouter API Key:", type="password")

# --- Model selection ---
st.subheader("Select AI Model")
available_models = [
    "meta-llama/llama-4-maverick:free",
    "google/gemini-2.5-flash-image-preview:free",
    "mistralai/mistral-small-3.2-24b-instruct:free"
]
selected_model = st.selectbox("Choose model", options=available_models, index=0)

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
            import io
            buffered = io.BytesIO()
            images[0].save(buffered, format="PNG")
            b64_img = base64.b64encode(buffered.getvalue()).decode("utf-8")

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
                "model": selected_model,
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

            # Extract model output safely
            try:
                raw_text = data["choices"][0]["message"]["content"]

                # Sometimes model wraps JSON in ```json ... ```
                if "```" in raw_text:
                    start = raw_text.find("```")
                    end = raw_text.rfind("```")
                    if start != -1 and end != -1 and start != end:
                        raw_text = raw_text[start+3:end]
                        if raw_text.lower().startswith("json"):
                            raw_text = raw_text[4:].strip()

                extracted_json = json.loads(raw_text.strip())
                st.session_state['extracted_json'] = extracted_json
                st.session_state['extraction_done'] = True

            except Exception as e:
                extracted_json = {"error": str(e), "raw": data}
                st.session_state['extracted_json'] = extracted_json
                st.session_state['extraction_done'] = True

    # Show extracted amount if it exists in session state
    if 'extraction_done' in st.session_state and st.session_state['extraction_done']:
        extracted_json = st.session_state.get('extracted_json', {})

        # Debug window
        with st.expander("Show Extracted JSON (Debug)"):
            st.json(extracted_json)

        # Show main extracted amount
        if "invoice_amount" in extracted_json:
            amount = extracted_json["invoice_amount"]

            original_amount_container = st.container()
            with original_amount_container:
                st.success(f"**Extracted Invoice Amount:** 💰 **${amount}**")

            # --- Rule application section ---
            st.markdown("---")
            st.subheader("Apply Processing Rules")

            default_rules = """If amount > 500 apply 15% discount
If amount > 200 and amount <= 500 apply 10% discount
If amount > 100 and amount <= 200 apply 5% discount
If amount <= 100 no discount"""

            rules = st.text_area(
                "Enter rules in English (you can modify the default rules):",
                value=default_rules,
                height=120,
                help="Write business rules in plain English. The AI will interpret and apply them."
            )

            if st.button("🔧 Apply Processing Rules", type="secondary"):
                if rules:
                    with st.spinner("Processing rules..."):
                        rule_prompt = f"""
                        You are a financial rule engine.
                        Given the extracted invoice amount: {amount},
                        and the rules: '{rules}',
                        calculate the final processed amount after applying the rules.
                        Show your calculation steps.
                        Respond strictly in JSON like:
                        {{ "original_amount": {amount}, "processed_amount": <calculated_value>, "discount_applied": <percentage_or_amount>, "explanation": "<detailed explanation of calculation>" }}
                        """

                        rule_payload = {
                            "model": selected_model,
                            "messages": [
                                {"role": "user", "content": rule_prompt}
                            ],
                        }
                        url = "https://openrouter.ai/api/v1/chat/completions"
                        headers = {
                            "Authorization": f"Bearer {api_key}",
                            "Content-Type": "application/json",
                        }
                        resp2 = requests.post(url, headers=headers, data=json.dumps(rule_payload))
                        data2 = resp2.json()

                        try:
                            content2 = data2["choices"][0]["message"]["content"]

                            if "```" in content2:
                                start = content2.find("```")
                                end = content2.rfind("```")
                                if start != -1 and end != -1 and start != end:
                                    content2 = content2[start+3:end]
                                    if content2.lower().startswith("json"):
                                        content2 = content2[4:].strip()

                            processed_json = json.loads(content2.strip())
                            st.session_state['processed_json'] = processed_json
                            st.session_state['processing_done'] = True

                        except Exception as e:
                            processed_json = {"error": str(e), "raw_response": content2 if 'content2' in locals() else data2}
                            st.session_state['processed_json'] = processed_json
                            st.session_state['processing_done'] = True

            # Show processed amount if it exists
            if 'processing_done' in st.session_state and st.session_state['processing_done']:
                processed_json = st.session_state.get('processed_json', {})

                with st.expander("Processed JSON (Debug)"):
                    st.json(processed_json)

                if "processed_amount" in processed_json:
                    col1, col2 = st.columns(2)
                    with col1:
                        st.metric(
                            label="Original Amount",
                            value=f"${processed_json.get('original_amount', amount)}"
                        )
                    with col2:
                        original_val = float(str(processed_json.get('original_amount', amount)).replace('$','').replace(',',''))
                        processed_val = float(str(processed_json['processed_amount']).replace('$','').replace(',',''))
                        delta = processed_val - original_val
                        st.metric(
                            label="Processed Amount",
                            value=f"${processed_json['processed_amount']}",
                            delta=f"${delta:.2f}" if delta != 0 else None,
                            delta_color="normal" if delta < 0 else "inverse"
                        )
                    if "discount_applied" in processed_json:
                        st.info(f"💡 **Discount Applied:** {processed_json['discount_applied']}")
                    if "explanation" in processed_json:
                        st.info(f"📝 **Explanation:** {processed_json['explanation']}")
                elif "error" in processed_json:
                    st.error(f"Error processing rules: {processed_json['error']}")
        else:
            st.error("Could not extract invoice amount from the document.")

# Reset button
if st.sidebar.button("🔄 Reset Application"):
    for key in ['extracted_json', 'extraction_done', 'processed_json', 'processing_done']:
        if key in st.session_state:
            del st.session_state[key]
    st.rerun()