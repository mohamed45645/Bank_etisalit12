"""Smart Data Analytics Dashboard - a Streamlit app for exploring and cleaning data."""

import io

import pandas as pd
import plotly.express as px
import streamlit as st

st.set_page_config(
    page_title="Smart Data Analytics Dashboard",
    page_icon="📊",
    layout="wide",
)

PAGES = [
    "🏠 Upload & Overview",
    "🔍 Data Quality",
    "🧹 Data Cleaning",
    "📈 Statistics",
    "📊 Charts",
    "⬇️ Export",
]
CSV_ENCODINGS = ("utf-8-sig", "utf-8", "cp1256", "latin-1")


# ---------------------------------------------------------------- Loading
@st.cache_data(show_spinner=False)
def read_csv_bytes(content: bytes) -> pd.DataFrame:
    """Read CSV bytes trying several encodings and auto-detecting the separator."""
    last_error = None
    for encoding in CSV_ENCODINGS:
        try:
            return pd.read_csv(io.BytesIO(content), encoding=encoding, sep=None, engine="python")
        except UnicodeDecodeError as exc:
            last_error = exc
    raise ValueError(f"Could not decode the CSV file: {last_error}")


@st.cache_data(show_spinner=False)
def list_excel_sheets(content: bytes) -> list:
    return pd.ExcelFile(io.BytesIO(content), engine="openpyxl").sheet_names


@st.cache_data(show_spinner=False)
def read_excel_bytes(content: bytes, sheet_name: str) -> pd.DataFrame:
    return pd.read_excel(io.BytesIO(content), sheet_name=sheet_name, engine="openpyxl")


def load_uploaded_file(uploaded):
    """Return (DataFrame or None, error message or None)."""
    name = uploaded.name.lower()
    content = uploaded.getvalue()
    if not content:
        return None, "The uploaded file is empty."
    try:
        if name.endswith(".csv"):
            df = read_csv_bytes(content)
        elif name.endswith(".xlsx"):
            sheets = list_excel_sheets(content)
            sheet = st.sidebar.selectbox("Excel sheet", sheets) if len(sheets) > 1 else sheets[0]
            df = read_excel_bytes(content, sheet)
        else:
            return None, "Unsupported format. Please upload a .csv or .xlsx file."
    except pd.errors.EmptyDataError:
        return None, "The file contains no data."
    except Exception as exc:  # noqa: BLE001 - show a friendly message to the user
        return None, f"Error while reading the file: {exc}"
    if df.empty or df.shape[1] == 0:
        return None, "The file was read but contains no rows or columns."
    df.columns = [str(c).strip() for c in df.columns]
    return df, None


# ---------------------------------------------------------------- Helpers
def numeric_columns(df: pd.DataFrame) -> list:
    return df.select_dtypes(include="number").columns.tolist()


def categorical_columns(df: pd.DataFrame) -> list:
    return df.select_dtypes(exclude="number").columns.tolist()


def missing_summary(df: pd.DataFrame) -> pd.DataFrame:
    missing = df.isna().sum()
    summary = pd.DataFrame(
        {"Missing values": missing, "Missing %": (missing / len(df) * 100).round(2)}
    )
    return summary[summary["Missing values"] > 0].sort_values("Missing values", ascending=False)


def clean_dataframe(df, strip_text, drop_dupes, drop_cols_threshold, numeric_strategy,
                    text_strategy, drop_missing_rows):
    """Return a cleaned COPY of df; the original is never modified."""
    result = df.copy()
    if strip_text:
        for col in categorical_columns(result):
            if result[col].dtype == object:
                result[col] = result[col].apply(lambda v: v.strip() if isinstance(v, str) else v)
    if drop_cols_threshold < 100:
        keep = result.columns[result.isna().mean() * 100 <= drop_cols_threshold]
        result = result[keep]
    if drop_dupes:
        result = result.drop_duplicates()
    if drop_missing_rows:
        result = result.dropna()
    else:
        for col in numeric_columns(result):
            if result[col].isna().any():
                fills = {"mean": result[col].mean(), "median": result[col].median(), "zero": 0}
                if numeric_strategy in fills:
                    result[col] = result[col].fillna(fills[numeric_strategy])
        for col in categorical_columns(result):
            if result[col].isna().any():
                if text_strategy == "mode" and not result[col].mode().empty:
                    result[col] = result[col].fillna(result[col].mode().iloc[0])
                elif text_strategy == "Unknown":
                    result[col] = result[col].fillna("Unknown")
    return result.reset_index(drop=True)


def to_csv_bytes(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False).encode("utf-8-sig")


def to_excel_bytes(df: pd.DataFrame) -> bytes:
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Cleaned data")
    return buffer.getvalue()


# ---------------------------------------------------------------- Pages
def page_overview(df: pd.DataFrame):
    st.subheader("Data overview")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Rows", f"{df.shape[0]:,}")
    c2.metric("Columns", f"{df.shape[1]:,}")
    c3.metric("Numeric columns", len(numeric_columns(df)))
    c4.metric("Memory (MB)", f"{df.memory_usage(deep=True).sum() / 1024**2:.2f}")
    max_rows = min(500, len(df))
    if max_rows > 5:
        rows = st.slider("Rows to preview", 5, max_rows, min(20, max_rows))
    else:
        rows = max_rows
    st.dataframe(df.head(rows), use_container_width=True)
    st.markdown("**Column data types**")
    dtypes = pd.DataFrame({"Column": df.columns, "Type": df.dtypes.astype(str).values,
                           "Unique values": df.nunique().values})
    st.dataframe(dtypes, use_container_width=True, hide_index=True)


def page_quality(df: pd.DataFrame):
    st.subheader("Missing values & duplicates")
    summary = missing_summary(df)
    c1, c2 = st.columns(2)
    c1.metric("Total missing cells", int(df.isna().sum().sum()))
    dup_count = int(df.duplicated().sum())
    c2.metric("Duplicate rows", dup_count)
    if summary.empty:
        st.success("No missing values found.")
    else:
        st.dataframe(summary, use_container_width=True)
        plot_data = summary.rename_axis("Column").reset_index()
        fig = px.bar(plot_data, x="Column", y="Missing values", title="Missing values per column")
        st.plotly_chart(fig, use_container_width=True)
    if dup_count:
        with st.expander("Show duplicate rows"):
            st.dataframe(df[df.duplicated(keep=False)].head(200), use_container_width=True)


def page_cleaning(df: pd.DataFrame):
    st.subheader("Safe data cleaning")
    st.caption("Cleaning is applied to a copy. Your uploaded file is never changed.")
    with st.form("cleaning_form"):
        strip_text = st.checkbox("Trim whitespace in text columns", value=True)
        drop_dupes = st.checkbox("Remove duplicate rows", value=False)
        drop_cols_threshold = st.slider("Drop columns with missing % above", 0, 100, 100,
                                        help="100 keeps every column.")
        drop_missing_rows = st.checkbox("Drop all rows that contain missing values", value=False)
        numeric_strategy = st.selectbox("Fill missing numeric values with",
                                        ["none", "mean", "median", "zero"])
        text_strategy = st.selectbox("Fill missing text values with", ["none", "mode", "Unknown"])
        submitted = st.form_submit_button("Apply cleaning")
    if submitted:
        st.session_state["clean_df"] = clean_dataframe(
            df, strip_text, drop_dupes, drop_cols_threshold,
            numeric_strategy, text_strategy, drop_missing_rows)
        st.success("Cleaning applied to a copy of the data.")
    if st.button("Reset to original data"):
        st.session_state["clean_df"] = df.copy()
        st.info("Cleaned data reset to the original.")
    cleaned = st.session_state.get("clean_df", df)
    c1, c2 = st.columns(2)
    c1.metric("Rows (original → cleaned)", f"{len(df):,} → {len(cleaned):,}",
              delta=len(cleaned) - len(df))
    c2.metric("Columns (original → cleaned)", f"{df.shape[1]} → {cleaned.shape[1]}",
              delta=cleaned.shape[1] - df.shape[1])
    st.dataframe(cleaned.head(50), use_container_width=True)


def page_statistics(df: pd.DataFrame):
    st.subheader("Descriptive statistics")
    num_cols = numeric_columns(df)
    if num_cols:
        st.markdown("**Numeric columns**")
        st.dataframe(df[num_cols].describe().T, use_container_width=True)
    cat_cols = categorical_columns(df)
    if cat_cols:
        st.markdown("**Non-numeric columns**")
        st.dataframe(df[cat_cols].astype(str).describe().T, use_container_width=True)
    if len(num_cols) >= 2:
        st.markdown("**Correlation matrix**")
        st.dataframe(df[num_cols].corr().round(3), use_container_width=True)


def page_charts(df: pd.DataFrame):
    st.subheader("Interactive charts")
    num_cols, cat_cols = numeric_columns(df), categorical_columns(df)
    all_cols = df.columns.tolist()
    chart = st.selectbox("Chart type", ["Histogram", "Box plot", "Scatter", "Line", "Bar",
                                        "Pie", "Correlation heatmap"])
    fig = None
    if chart in ("Histogram", "Box plot"):
        if not num_cols:
            st.warning("This chart needs at least one numeric column.")
            return
        col = st.selectbox("Numeric column", num_cols)
        color = st.selectbox("Color by (optional)", [None] + cat_cols)
        fig = (px.histogram(df, x=col, color=color, marginal="box") if chart == "Histogram"
               else px.box(df, y=col, color=color))
    elif chart in ("Scatter", "Line"):
        if not num_cols:
            st.warning("This chart needs numeric columns.")
            return
        x = st.selectbox("X axis", all_cols)
        y = st.selectbox("Y axis", num_cols)
        color = st.selectbox("Color by (optional)", [None] + cat_cols)
        fig = (px.scatter(df, x=x, y=y, color=color) if chart == "Scatter"
               else px.line(df.sort_values(x), x=x, y=y, color=color))
    elif chart in ("Bar", "Pie"):
        if not cat_cols:
            st.warning("This chart needs at least one non-numeric column.")
            return
        cat = st.selectbox("Category column", cat_cols)
        value = st.selectbox("Value column", ["(count)"] + num_cols)
        agg = st.selectbox("Aggregation", ["sum", "mean", "median"]) if value != "(count)" else None
        top_n = st.slider("Top categories", 3, 30, 10)
        if value == "(count)":
            data = df[cat].astype(str).value_counts().head(top_n).reset_index()
            data.columns = [cat, "count"]
            value_col = "count"
        else:
            data = (df.groupby(df[cat].astype(str))[value].agg(agg)
                    .sort_values(ascending=False).head(top_n).reset_index())
            value_col = value
        fig = (px.bar(data, x=cat, y=value_col) if chart == "Bar"
               else px.pie(data, names=cat, values=value_col))
    else:
        if len(num_cols) < 2:
            st.warning("The heatmap needs at least two numeric columns.")
            return
        selected = st.multiselect("Columns", num_cols, default=num_cols[:10])
        if len(selected) < 2:
            st.info("Select at least two columns.")
            return
        fig = px.imshow(df[selected].corr(), text_auto=".2f", aspect="auto",
                        color_continuous_scale="RdBu_r", zmin=-1, zmax=1)
    if fig is not None:
        st.plotly_chart(fig, use_container_width=True)


def page_export(df: pd.DataFrame):
    st.subheader("Download cleaned data")
    cleaned = st.session_state.get("clean_df", df)
    st.write(f"Rows: **{len(cleaned):,}** | Columns: **{cleaned.shape[1]}**")
    c1, c2 = st.columns(2)
    c1.download_button("⬇️ Download CSV", to_csv_bytes(cleaned),
                       file_name="cleaned_data.csv", mime="text/csv")
    c2.download_button("⬇️ Download Excel", to_excel_bytes(cleaned),
                       file_name="cleaned_data.xlsx",
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


# ---------------------------------------------------------------- Main
def main():
    st.title("📊 Smart Data Analytics Dashboard")
    st.caption("Upload a CSV or Excel file to explore, clean, analyze and visualize your data.")
    st.sidebar.header("Navigation")
    page = st.sidebar.radio("Go to", PAGES)
    st.sidebar.divider()
    uploaded = st.sidebar.file_uploader("Upload CSV or Excel (.xlsx)", type=["csv", "xlsx"])

    if uploaded is None:
        st.info("👈 Upload a file from the sidebar to get started.")
        return

    df, error = load_uploaded_file(uploaded)
    if error:
        st.error(error)
        return

    file_key = f"{uploaded.name}-{uploaded.size}"
    if st.session_state.get("file_key") != file_key:
        st.session_state["file_key"] = file_key
        st.session_state["clean_df"] = df.copy()

    pages = {
        PAGES[0]: page_overview, PAGES[1]: page_quality, PAGES[2]: page_cleaning,
        PAGES[3]: page_statistics, PAGES[4]: page_charts, PAGES[5]: page_export,
    }
    source = st.session_state["clean_df"] if page in (PAGES[3], PAGES[4]) else df
    pages[page](source)


if __name__ == "__main__":
    main()
