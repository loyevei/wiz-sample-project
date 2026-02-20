struct = wiz.model("struct")
session = wiz.model("portal/season/session").use()

def get():
    user_id = session.get("id")
    if not user_id:
        wiz.response.status(401, message="로그인이 필요합니다.")

    user = struct.user.get(id=user_id)
    if user is None:
        wiz.response.status(404, message="사용자를 찾을 수 없습니다.")

    wiz.response.status(200, user)

def update_profile():
    user_id = session.get("id")
    if not user_id:
        wiz.response.status(401, message="로그인이 필요합니다.")

    name = wiz.request.query("name", "")
    mobile = wiz.request.query("mobile", "")

    if not name:
        wiz.response.status(400, message="이름을 입력해주세요.")

    struct.user.update_profile(user_id, name=name, mobile=mobile)

    # 세션도 갱신
    session.set(name=name)

    wiz.response.status(200)

def change_password():
    user_id = session.get("id")
    if not user_id:
        wiz.response.status(401, message="로그인이 필요합니다.")

    current_password = wiz.request.query("current_password", "")
    new_password = wiz.request.query("new_password", "")

    if not current_password:
        wiz.response.status(400, message="현재 비밀번호를 입력해주세요.")
    if not new_password:
        wiz.response.status(400, message="새 비밀번호를 입력해주세요.")

    result = struct.user.change_password(user_id, current_password, new_password)
    if not result:
        wiz.response.status(400, message="현재 비밀번호가 올바르지 않습니다.")

    wiz.response.status(200)
