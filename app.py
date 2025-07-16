import streamlit as st
from openai import OpenAI
import sqlite3
import pandas as pd
import plotly.express as px
import tempfile
import os

# Load OpenAI key from secrets
client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

st.set_page_config(page_title="NL2SQL Studio", layout="centered")
st.title("Ask Your Database Anything")

# Check if built-in DB exists
built_in_db_exists = os.path.exists("MiniCRM.db")

# Step 1: Choose Database
st.subheader("📦 Choose your database")

options = []
if built_in_db_exists:
    options.append("Use built-in MiniCRM.db")
options.append("Upload your own .db file")

db_option = st.radio("Select database source:", options)

# Step 2: Load selected DB
if db_option == "Upload your own .db file":
    uploaded_file = st.file_uploader("📤 Upload your SQLite `.db` file", type="db")
    if uploaded_file:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".db") as tmp_file:
            tmp_file.write(uploaded_file.read())
            db_path = tmp_file.name
    else:
        st.warning("👆 Please upload a `.db` file to continue.")
        st.stop()
else:
    db_path = "MiniCRM.db"
    if not built_in_db_exists:
        st.error("Built-in MiniCRM.db not found. Please create or upload it first.")
        st.stop()

# Step 3: Connect to SQLite
conn = sqlite3.connect(db_path)

# Step 4: Show schema in sidebar
st.sidebar.header("Database Schema")
def get_schema(conn):
    tables = pd.read_sql(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';", conn
    )
    schema = ""
    for table in tables["name"]:
        df = pd.read_sql(f"PRAGMA table_info({table})", conn)
        schema += f"Table: {table}\n{df.to_string(index=False)}\n\n"
    return schema

schema = get_schema(conn)

# Show tables & columns in sidebar
tables = pd.read_sql(
    "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';", conn
)
for table in tables["name"]:
    with st.sidebar.expander(f"📄 {table}"):
        columns = pd.read_sql(f"PRAGMA table_info({table})", conn)
        for col in columns["name"]:
            st.markdown(f"- {col}")

# Step 5: Ask natural language query
nl_query = st.text_input("Ask your question (e.g., 'Top 5 customers by total revenue')")

# Step 6: Generate SQL using OpenAI
def generate_sql(nl_query, schema):
    system_prompt = f"""
You are a helpful assistant that translates natural language questions into SQL queries for an SQLite database.
Here is the database schema:
{schema}
Generate only the SQL query, no explanation or markdown formatting.
"""
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": nl_query},
        ],
    )
    sql = response.choices[0].message.content.strip()
    return sql.replace("```sql", "").replace("```", "").strip()

# Step 7: Run query and visualize
if nl_query:
    try:
        sql_query = generate_sql(nl_query, schema)

        if st.button("👁️ Show Generated SQL"):
            st.code(sql_query, language="sql")

        df = pd.read_sql(sql_query, conn)
        st.dataframe(df)

        if len(df.columns) >= 2:
            fig = px.bar(df, x=df.columns[0], y=df.columns[1])
            st.plotly_chart(fig, use_container_width=True)

    except Exception as e:
        st.error(f" Error: {e}")

conn.close()
