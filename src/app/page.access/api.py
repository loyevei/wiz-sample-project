session = wiz.model("portal/season/session").use()
struct = wiz.model("struct")

def login():
    email = wiz.request.query("email", "")
    password = wiz.request.query("password", "")

    if not email or not password:
        wiz.response.status(400, message="이메일과 비밀번호를 입력해주세요.")

    user = struct.user.authenticate(email, password)
    if user is None:
        wiz.response.status(401, message="이메일 또는 비밀번호가 올바르지 않습니다.")

    session.set(id=user['id'], email=user['email'], name=user['name'], role=user['role'])
    wiz.response.status(200)
