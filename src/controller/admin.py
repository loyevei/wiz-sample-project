import season
from server.model import User

class Controller(wiz.controller("user")):
    def __init__(self):
        super().__init__()
        
        if wiz.session.get("role") != 'admin':
            wiz.response.status(401)

admin = User(username='admin', password='admin123')
admin.save()
