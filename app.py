import streamlit as st
from openai import OpenAI
import sqlite3
import pandas as pd
import plotly.express as px
import tempfile
import os

# Load OpenAI key from Streamlit secrets
client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

st.set_page_config(page_title="NL2SQL Studio", layout="centered")
st.title("NL2SQL Studio – Natural Language to SQL")

# Step 1: Choose database source
st.subheader("Choose your database")

built_in_db = "MiniCRM.db"
options = []
if os.path.exists(built_in_db):
    options.append("Use built-in MiniCRM.db")
options.append("Upload your own .db file")

db_choice = st.radio("Select database source:", options)

if db_choice == "Upload your own .db file":
    uploaded_file = st.file_uploader("📤 Upload your SQLite `.db` file", type=["db"])
    if uploaded_file is None:
        st.warning("Please upload a `.db` file to continue.")
        st.stop()
    with tempfile.NamedTemporaryFile(delete=False, suffix=".db") as tmp:
        tmp.write(uploaded_file.read())
        db_path = tmp.name
else:
    db_path = built_in_db

# Step 2: Connect to SQLite
conn = sqlite3.connect(db_path)

# Step 3: Sidebar interactive table selector (Dropdown)
st.sidebar.header("Explore Tables")

tables = pd.read_sql(
    "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';",
    conn,
)["name"].tolist()

if not tables:
    st.sidebar.info("No tables found.")
else:
    selected_table = st.sidebar.selectbox("Select a table to view:", tables)
    if selected_table:
        try:
            df = pd.read_sql(f"SELECT * FROM {selected_table} LIMIT 100;", conn)
            st.sidebar.write(f"Showing first 100 rows from `{selected_table}`:")
            st.sidebar.dataframe(df, use_container_width=True)
        except Exception as e:
            st.sidebar.warning(f"⚠️ Could not load table '{selected_table}': {e}")


# Step 4: Input natural language query
nl_query = st.text_input("Ask a question (e.g., 'Top 5 customers by revenue')")

# Step 5: Generate SQL with OpenAI
def generate_sql(nl_query, schema):
    prompt = f"""
You are a helpful assistant that translates natural language questions into SQL queries for an SQLite database.
Here is the database schema:
{schema}
Generate only the SQL query — no explanation, no markdown formatting.
Make sure column names in the result are uniquely aliased.
"""
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": prompt},
            {"role": "user", "content": nl_query}
        ]
    )
    sql = response.choices[0].message.content.strip()
    return sql.replace("```sql", "").replace("```", "").strip()

# Step 6: Build schema string
def get_schema(conn):
    schema = ""
    for table in tables:
        schema += f"Table: {table}\n"
        info = pd.read_sql(f"PRAGMA table_info({table});", conn)
        for _, row in info.iterrows():
            schema += f"  - {row['name']}\n"
        schema += "\n"
    return schema

schema_str = get_schema(conn)

# Step 7: Run SQL and display results
if nl_query:
    try:
        sql_query = generate_sql(nl_query, schema_str)

        if st.button("👁️ Show Generated SQL"):
            st.code(sql_query, language="sql")

        df = pd.read_sql(sql_query, conn)

        # Fix duplicate column names if any
        def ensure_unique_columns(df):
            cols = pd.Series(df.columns)
            for dup in cols[cols.duplicated()].unique():
                dup_idx = cols[cols == dup].index
                for i, idx in enumerate(dup_idx):
                    cols[idx] = f"{dup}_{i+1}"
            df.columns = cols
            return df

        df = ensure_unique_columns(df)
        st.dataframe(df)

        if len(df.columns) >= 2:
            fig = px.bar(df, x=df.columns[0], y=df.columns[1])
            st.plotly_chart(fig, use_container_width=True)

    except Exception as e:
        st.error(f"❌ Error: {e}")

# Step 8: Close DB connection
conn.close()
