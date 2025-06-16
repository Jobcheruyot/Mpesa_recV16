
import streamlit as st
import pandas as pd
from io import BytesIO

st.set_page_config(page_title="Mpesa Reconciliation App", layout="wide")
st.title("📊 Mpesa Reconciliation App")

# Uploads
uploaded_key = st.file_uploader("🔑 Upload Key File", type=["csv", "xlsx"])
uploaded_aspire = st.file_uploader("📁 Upload Aspire File", type=["csv", "xlsx"])
uploaded_safaricom = st.file_uploader("📁 Upload Safaricom File", type=["csv", "xlsx"])

if uploaded_key and uploaded_aspire and uploaded_safaricom:
    st.success("✅ All files uploaded. Click the button below to start processing.")

    if st.button("▶️ Start Processing"):
        # Load files
        key = pd.read_csv(uploaded_key) if uploaded_key.name.endswith('.csv') else pd.read_excel(uploaded_key)
        aspire = pd.read_csv(uploaded_aspire) if uploaded_aspire.name.endswith('.csv') else pd.read_excel(uploaded_aspire)
        safaricom = pd.read_csv(uploaded_safaricom) if uploaded_safaricom.name.endswith('.csv') else pd.read_excel(uploaded_safaricom)

        # Preview
        st.subheader("📨 Safaricom Sample")
        st.dataframe(safaricom.head())

        st.subheader("🧾 Aspire Sample")
        st.dataframe(aspire.head())

        st.subheader("🗂️ Key Sample")
        st.dataframe(key.head())

        # ------------------- GENERATE REPORTS -------------------

        # Daily Reversals
        safaricom['DEBIT_AMOUNT'] = pd.to_numeric(safaricom['DEBIT_AMOUNT'], errors='coerce')
        reversal_rows = safaricom[
            safaricom['LINKED_TRANSACTION_ID'].notna() & (safaricom['DEBIT_AMOUNT'] > 0)
        ]
        daily_reversals = reversal_rows[['Store_amend', 'TRANSACTION_PARTY_DETAILS', 'DEBIT_AMOUNT', 'LINKED_TRANSACTION_ID']].copy()

        # Previous Day Utilized
        aspire['TRANSACTION_TYPE'] = aspire['TRANSACTION_TYPE'].fillna('').astype(str).str.strip()
        preferred_types = ['POS CASH SALE', 'DEPOSIT RECEIVED']
        dupes = aspire[aspire.duplicated('TRANSACTION_ID', keep=False)].copy()
        dupes['priority'] = dupes['TRANSACTION_TYPE'].apply(lambda x: 0 if x in preferred_types else (1 if x else 2))
        cleaned_dupes = (
            dupes.sort_values(by='priority')
            .drop_duplicates(subset='TRANSACTION_ID', keep='first')
            .drop(columns='priority')
        )
        aspire_unique = aspire[~aspire['TRANSACTION_ID'].isin(dupes['TRANSACTION_ID'])]
        aspire = pd.concat([aspire_unique, cleaned_dupes], ignore_index=True)
        most_common_ref1 = safaricom['Ref1'].mode()[0]
        valid_types = ['POS CASH SALE', 'DEPOSIT RECEIVED']
        filtered_aspire = aspire[
            (aspire['Ref1'] != most_common_ref1) &
            (aspire['TRANSACTION_TYPE'].isin(valid_types))
        ]
        prev_day_utilized = filtered_aspire[['STORE_NAME', 'TRANSACTION_ID', 'AMOUNT', 'SYSTEM_ENTRY_DATE', 'TRANSACTION_TYPE']].copy()

        # Unutilized (Cashed Out)
        aspire['AMOUNT'] = pd.to_numeric(aspire['AMOUNT'], errors='coerce')
        aspire['SYSTEM_ENTRY_DATE'] = pd.to_datetime(aspire['SYSTEM_ENTRY_DATE'], errors='coerce')
        excluded_types = ['POS CASH SALE', 'DEPOSIT RECEIVED']
        most_common_ref1 = aspire['Ref1'].mode()[0]
        asp_pending = aspire[
            (aspire['Ref1'] == most_common_ref1) &
            (~aspire['TRANSACTION_TYPE'].isin(excluded_types))
        ].copy()
        asp_pending['VENDOR_TIME'] = asp_pending['SYSTEM_ENTRY_DATE'].dt.strftime('%H:%M')
        asp_pending['VENDOR_DAY'] = asp_pending['SYSTEM_ENTRY_DATE'].dt.strftime('%d/%m/%Y')
        asp_export = asp_pending[['VENDOR_TIME', 'STORE_NAME', 'TRANSACTION_ID', 'VENDOR_DAY', 'AMOUNT']].copy()
        safaricom['CREDIT_AMOUNT'] = pd.to_numeric(safaricom['CREDIT_AMOUNT'], errors='coerce')
        safaricom['START_TIMESTAMP'] = pd.to_datetime(safaricom['START_TIMESTAMP'], errors='coerce')
        most_common_ref1_saf = safaricom['Ref1'].mode()[0]
        unsync = safaricom[
            (safaricom['ACCOUNT_TYPE_NAME'] == 'Merchant Account') &
            (safaricom['code_check'] == 'XX') &
            (safaricom['Ref1'] == most_common_ref1_saf) &
            (safaricom['LINKED_TRANSACTION_ID'].isna())
        ].copy()
        unsync['VENDOR_TIME'] = unsync['START_TIMESTAMP'].dt.strftime('%H:%M')
        unsync['VENDOR_DAY'] = unsync['START_TIMESTAMP'].dt.strftime('%d/%m/%Y')
        unsync_export = unsync[['VENDOR_TIME', 'Store_amend', 'RECEIPT_NUMBER', 'VENDOR_DAY', 'CREDIT_AMOUNT']].copy()
        unsync_export.columns = ['VENDOR_TIME', 'STORE_NAME', 'TRANSACTION_ID', 'VENDOR_DAY', 'AMOUNT']
        store_map = dict(zip(key['Col_1'], key['Col_2']))
        asp_export['STORE_NAME'] = asp_export['STORE_NAME'].map(store_map).fillna(asp_export['STORE_NAME'])
        unsync_export['STORE_NAME'] = unsync_export['STORE_NAME'].map(store_map).fillna(unsync_export['STORE_NAME'])
        cashed_out = pd.concat([asp_export, unsync_export], ignore_index=True)
        cashed_out = cashed_out.sort_values(by=['STORE_NAME', 'AMOUNT'], ascending=[True, False])

        # Summary (simulate using daily_reversals grouped)
        store_summary = daily_reversals.groupby('Store_amend').agg({'DEBIT_AMOUNT': 'sum'}).reset_index()
        store_summary.columns = ['Store', 'Total_Reversed']

        # ------------------- EXPORT TO EXCEL -------------------
        output = BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            if isinstance(daily_reversals, pd.DataFrame):
                daily_reversals.to_excel(writer, sheet_name='Daily_Reversals', index=False)
            if isinstance(prev_day_utilized, pd.DataFrame):
                prev_day_utilized.to_excel(writer, sheet_name='Prev_Day_Utilized', index=False)
            if isinstance(cashed_out, pd.DataFrame):
                cashed_out.to_excel(writer, sheet_name='Unutilized_Transactions', index=False)
            if isinstance(store_summary, pd.DataFrame):
                store_summary.to_excel(writer, sheet_name='Summary', index=False)
        output.seek(0)

        st.download_button(
            label="📥 Download Mpesa Reports (Excel Workbook)",
            data=output,
            file_name="mpesa_reconciliation_report.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
