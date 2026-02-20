import season

class Controller(wiz.controller("base")):
    def __init__(self):
        super().__init__()

        if wiz.session.has("id") == False:
            wiz.response.status(401)

        # TODO: 실제 구현 시 사용자 접근 권한 검증
        # struct = wiz.model("portal/{pkg}/struct")
        # struct.user(wiz.session.get("id")).access()
