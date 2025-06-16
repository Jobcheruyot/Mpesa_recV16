import streamlit as st
import papermill as pm
from io import BytesIO
import pandas as pd

st.set_page_config(page_title="Mpesa Reconciliation App", layout="wide")
st.title("📊 Mpesa Notebook Runner")

run_button = st.button("▶️ Run Reconciliation Notebook")

if run_button:
    with st.spinner("Running notebook..."):
        pm.execute_notebook(
            'MpesaV13062025.ipynb',      # input notebook
            'output_notebook.ipynb',     # output notebook
            parameters=dict()            # pass dynamic params if needed
        )
        st.success("✅ Notebook run complete")

    # After it's run, load Excel report (if notebook generated it)
    try:
        with open("mpesa_reconciliation_report.xlsx", "rb") as f:
            st.download_button(
                label="⬇️ Download Report",
                data=f,
                file_name="mpesa_reconciliation_report.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
    except FileNotFoundError:
        st.warning("Notebook ran, but no report found.")
