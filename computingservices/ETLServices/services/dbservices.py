import psycopg2
from datetime import date

# --- Configuration ---
DATE_COLUMN = "created_at"  # Name of the timestamp column to filter daily updates

def get_daily_new_data(table_name, connection, date_column=DATE_COLUMN, given_date=None):
    """Fetches new created data for the current day from a specific table."""
    if given_date is None:
        given_date = str(date.today())

    try:
        query = f"""
            SELECT *
            FROM "{table_name}"
            WHERE {date_column} >= %s;
        """
        cursor = connection.cursor()
        cursor.execute(query, (given_date,))
        columns = [desc[0] for desc in cursor.description]
        data = [dict(zip(columns, row)) for row in cursor.fetchall()]
        return data
    except Exception as e:
        print(f"Error querying new data: {e}")
        return None

def get_daily_data(table_name, connection, date_column1, date_column2, given_date=None):
    """Fetches new created and updated data for the current day from a specific table."""
    if given_date is None:
        given_date = str(date.today())

    try:
        query = f"""
            SELECT *
            FROM "{table_name}"
            WHERE {date_column1} >= %s OR {date_column2} >= %s;
        """
        cursor = connection.cursor()
        cursor.execute(query, (given_date, given_date))
        columns = [desc[0] for desc in cursor.description]
        data = [dict(zip(columns, row)) for row in cursor.fetchall()]
        return data
    except Exception as e:
        print(f"Error querying daily data: {e}")
        return None

def get_all_data(table_name, connection):
    """Fetches all data from a specific table."""
    try:
        query = f"""
            SELECT *
            FROM "{table_name}";
        """
        cursor = connection.cursor()
        cursor.execute(query)
        columns = [desc[0] for desc in cursor.description]
        data = [dict(zip(columns, row)) for row in cursor.fetchall()]
        return data
    except Exception as e:
        print(f"Error querying all data: {e}")
        return None

def get_table_list(connection):
    """
    Retrieves data from PostgreSQL tables that were created or updated today.

    Args:
        conn_params (dict): Database connection parameters.

    Returns:
        dict: Table names as keys, lists of rows as values.
    """
    table_list = {
        "table_with_created_completed_on": [],  #special case for Payments table
        "table_with_created_at": [],
        "table_with_created_updated_at": [],
        "table_with_createdat": [],
        "table_with_none": []
    }

    try:
        cur = connection.cursor()

        cur.execute("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
              AND table_type = 'BASE TABLE';
        """)
        tables = [row[0] for row in cur.fetchall()]

        for table_name in tables:
            cur.execute(f"""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name = '{table_name}'
                  AND column_name IN ('created_at', 'updated_at', 'createdat', 'created_on', 'completed_on');
            """)
            columns = [row[0] for row in cur.fetchall()]

            if 'created_on' in columns and 'completed_on' in columns:
                table_list["table_with_created_completed_on"].append(table_name)
            elif 'created_at' in columns and 'updated_at' in columns:
                table_list["table_with_created_updated_at"].append(table_name)
            elif 'created_at' in columns:
                table_list["table_with_created_at"].append(table_name)
            elif 'createdat' in columns:
                table_list["table_with_createdat"].append(table_name)
            else:
                table_list["table_with_none"].append(table_name)

        cur.close()
        # connection.close()
        return table_list

    except psycopg2.Error as e:
        print(f"Error querying PostgreSQL: {e}")
        return table_list