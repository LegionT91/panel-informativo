import pymysql.cursors

class MySQLConnection:
    def __init__(self, db):
        connection = pymysql.connect(
            host='localhost',
            user='root',
            password='password',
            db=db,
            charset='utf8mb4',
            cursorclass=pymysql.cursors.DictCursor,
            autocommit=False  # Cambiado a False para control manual
        )
        self.connection = connection
    
    def query_db(self, query, data=None):
        with self.connection.cursor() as cursor:
            try:
                query_str = cursor.mogrify(query, data)
                print("Running Query:", query_str)
                
                cursor.execute(query, data)
                
                if query.lower().find("insert") >= 0:
                    self.connection.commit()
                    return cursor.lastrowid
                elif query.lower().find("select") >= 0:
                    result = cursor.fetchall()
                    return result
                else:
                    # UPDATE, DELETE, etc.
                    self.connection.commit()
                    return True
                    
            except Exception as e:
                print("Something went wrong", e)
                self.connection.rollback()
                return False
    
    def close(self):
        """Método para cerrar la conexión manualmente"""
        if self.connection:
            self.connection.close()
    
    def __del__(self):
        """Cerrar la conexión cuando el objeto se destruye"""
        self.close()

def connectToMySQL(db):
    return MySQLConnection(db)