"""
Servidor principal usando la estructura modular
"""
from flask_app import create_app
import os

# Crear la aplicación
app = create_app()

if __name__ == '__main__':
    app.run(debug=True)
