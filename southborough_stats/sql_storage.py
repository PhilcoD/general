
import sqlite3

def db_fixture_id_fetch(conn: sqlite3.Connection):
    
    """
    
    Creates a list of all Play-Cricket fixture IDs within database of your choosing
    
    Args:
        conn: sqlite3.Connection to the match storage database
    
    """

    cursorObj = conn.cursor()
    cursorObj.execute('SELECT PlayCricket from Match')
    return [i[0] for i in cursorObj.fetchall()]