import season

class Controller(wiz.controller("user")):
    def __init__(self):
        super().__init__()
        
        if wiz.session.get("role") != 'admin':
            wiz.response.status(401)
