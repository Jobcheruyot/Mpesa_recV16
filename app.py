import streamlit as st
import pandas as pd
import zipfile
import io
from datetime import datetime

# App Configuration
st.set_page_config(page_title="M-Pesa Reconciliation", layout="wide")
st.title("📊 M-Pesa Transaction Reconciliation")
st.write("""
This app reconciles M-Pesa transactions between Aspire and Safaricom reports.
Upload your files below to generate a reconciliation report.
""")

# File Upload Section
with st.expander("📁 Upload Files", expanded=True):
    col1, col2, col3 = st.columns(3)
    with col1:
        aspire_file = st.file_uploader("Aspire CSV", type=['csv'], key="aspire")
    with col2:
        safaricom_file = st.file_uploader("Safaricom CSV", type=['csv'], key="safaricom")
    with col3:
        key_file = st.file_uploader("Store Key (Excel)", type=['xlsx'], key="key")

# Main Processing Function
def process_files(aspire_file, safaricom_file, key_file):
    try:
        # Load files
        aspire = pd.read_csv(aspire_file)
        safaricom = pd.read_csv(safaricom_file)
        key = pd.read_excel(key_file)
        
        # --- Data Processing ---
        # 1. Fix Safaricom column headers
        new_columns = safaricom.columns[1:].tolist() + ['EXTRA']
        safaricom.columns = new_columns
        safaricom = safaricom.drop(columns='EXTRA')
        
        # 2. Select relevant columns
        saf_cols = [
            'STORE_NAME', 'RECEIPT_NUMBER', 'TRANSACTION_TYPE',
            'START_TIMESTAMP', 'CREDIT_AMOUNT', 'DEBIT_AMOUNT'
        ]
        safaricom = safaricom[[col for col in saf_cols if col in safaricom.columns]]
        
        # 3. Clean store names using mapping key
        key.columns = ['Original_STORE_NAME', 'Clean_STORE_NAME']
        store_map = dict(zip(key['Original_STORE_NAME'], key['Clean_STORE_NAME']))
        safaricom['Store_amend'] = safaricom['STORE_NAME'].map(store_map)
        
        # 4. Transaction matching
        valid_ids = set(aspire['TRANSACTION_ID'])
        safaricom['code_check'] = safaricom['RECEIPT_NUMBER'].apply(
            lambda x: "VALID" if x in valid_ids else "UNMATCHED"
        )
        
        # 5. Add reference columns
        safaricom['Ref1'] = safaricom['RECEIPT_NUMBER'].str[:3]
        aspire['Ref1'] = aspire['TRANSACTION_ID'].str[:3]
        
        # --- Analysis ---
        matched = safaricom[safaricom['code_check'] == "VALID"].shape[0]
        unmatched = safaricom[safaricom['code_check'] == "UNMATCHED"].shape[0]
        match_rate = (matched / (matched + unmatched)) * 100
        
        # --- Results Display ---
        st.success("✅ Files processed successfully!")
        
        # Summary Metrics
        st.subheader("Reconciliation Summary")
        col1, col2, col3 = st.columns(3)
        col1.metric("Total Aspire Transactions", len(aspire))
        col2.metric("Total Safaricom Transactions", len(safaricom))
        col3.metric("Match Rate", f"{match_rate:.1f}%")
        
        # Detailed Results
        with st.expander("🔍 View Detailed Results"):
            tab1, tab2 = st.tabs(["Matched Transactions", "Unmatched Transactions"])
            
            with tab1:
                st.dataframe(
                    safaricom[safaricom['code_check'] == "VALID"].head(100),
                    use_container_width=True
                )
            
            with tab2:
                st.dataframe(
                    safaricom[safaricom['code_check'] == "UNMATCHED"].head(100),
                    use_container_width=True
                )
        
        # --- Report Generation ---
        st.subheader("📥 Download Reports")
        
        # Create Excel report
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            aspire.to_excel(writer, sheet_name='Aspire Data', index=False)
            safaricom.to_excel(writer, sheet_name='Safaricom Data', index=False)
            
            summary = pd.DataFrame({
                'Metric': ['Aspire Transactions', 'Safaricom Transactions', 
                          'Matched', 'Unmatched', 'Match Rate'],
                'Count': [len(aspire), len(safaricom), matched, 
                         unmatched, f"{match_rate:.1f}%"]
            })
            summary.to_excel(writer, sheet_name='Summary', index=False)
        
        # Create ZIP file
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'a', zipfile.ZIP_DEFLATED, False) as zip_file:
            zip_file.writestr('reconciliation_report.xlsx', output.getvalue())
            zip_file.writestr(
                'processing_log.txt', 
                f"Processed on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            )
        
        # Download button
        st.download_button(
            label="⬇️ Download Full Report (ZIP)",
            data=zip_buffer.getvalue(),
            file_name=f'mpesa_reconciliation_{datetime.now().strftime("%Y%m%d")}.zip',
            mime='application/zip',
            help="Contains Excel report with all data and summary"
        )
        
    except Exception as e:
        st.error(f"❌ Error processing files: {str(e)}")

# Run processing when files are uploaded
if aspire_file and safaricom_file and key_file:
    process_files(aspire_file, safaricom_file, key_file)
else:
    st.warning("⚠️ Please upload all required files to begin processing.")
