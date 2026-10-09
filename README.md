# Smart Data Analytics Dashboard

An interactive Streamlit app for exploring, cleaning, analyzing and visualizing tabular data.
No API keys or paid services are required.

## Features
- Upload CSV and Excel (.xlsx) files, with sheet selection for Excel
- Data preview, row/column counts and data types
- Missing-value and duplicate analysis
- Safe cleaning options applied to a copy (the original upload is never modified)
- Descriptive statistics and correlation matrix
- Interactive Plotly charts: histogram, box, scatter, line, bar, pie, heatmap
- Download cleaned data as CSV or Excel
- Clear messages for empty files, unsupported formats and read errors

## Run locally
```bash
pip install -r requirements.txt
streamlit run app.py
```

## Deploy on Streamlit Community Cloud
1. Push this folder to a new GitHub repository (app.py at the repository root).
2. Go to https://share.streamlit.io and sign in with GitHub.
3. Click **Create app**, choose the repository and branch, and set the main file to `app.py`.
4. Under **Advanced settings**, select Python 3.12.
5. Click **Deploy**.

## Tech stack
Python 3.12, Streamlit, pandas, NumPy, Plotly, openpyxl.

## Limitations
- Only `.csv` and `.xlsx` are supported (legacy `.xls` is not).
- Very large files are limited by the memory of the hosting environment.
