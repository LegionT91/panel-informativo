"""
Modelo de Aviso/Noticia
"""
from datetime import datetime

class Notice:
    """Modelo para avisos/noticias"""
    
    def __init__(self, id=None, title=None, description=None, image_url=None, 
                 start_date=None, end_date=None, created_at=None):
        self.id = id
        self.title = title
        self.description = description
        self.image_url = image_url
        self.start_date = start_date
        self.end_date = end_date
        self.created_at = created_at or datetime.now()
    
    def to_dict(self):
        """Convierte el objeto a diccionario"""
        return {
            'id': self.id,
            'title': self.title,
            'description': self.description,
            'image_url': self.image_url,
            'start_date': self.start_date,
            'end_date': self.end_date,
            'created_at': self.created_at
        }
    
    @classmethod
    def from_dict(cls, data):
        """Crea una instancia desde un diccionario"""
        return cls(
            id=data.get('id'),
            title=data.get('title'),
            description=data.get('description'),
            image_url=data.get('image_url'),
            start_date=data.get('start_date'),
            end_date=data.get('end_date'),
            created_at=data.get('created_at')
        )

