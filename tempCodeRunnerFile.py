import mysql.connector
from mysql.connector import Error

def create_connection():
    try:
        connection = mysql.connector.connect(
            host="localhost",        # usually localhost
            user="root",             # your MySQL username
            password="Veena@1999", # your MySQL password
            database="retaildb"      # the database you created for this project
        )
        if connection.is_connected():
            print("Connected to the database")
            return connection
    except Error as e:
        print(f"Error connecting to MySQL: {e}")
        return None

# Example usage
if __name__ == "__main__":
    conn = create_connection()
    if conn:
        conn.close()
