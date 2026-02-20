import json

struct = wiz.model("portal/post/struct")

def get():
    """게시물 단건 조회"""
    id = wiz.request.query("id", "")
    if not id:
        wiz.response.status(400, message="ID가 필요합니다.")

    post = struct.post.get(id)
    if post is None:
        wiz.response.status(404, message="게시물을 찾을 수 없습니다.")

    wiz.response.status(200, post)

def save():
    """게시물 저장 (생성 또는 수정)"""
    raw = wiz.request.query("data", "{}")
    data = json.loads(raw) if isinstance(raw, str) else raw

    post_id = data.get("id", "")

    if not post_id or post_id == "new":
        # 신규 생성
        post_id = struct.post.create(data)
        data["id"] = post_id
    else:
        # 수정
        struct.post.update(data, id=post_id)

    wiz.response.status(200, data)

def delete():
    """게시물 삭제 (연관 댓글도 함께 삭제)"""
    id = wiz.request.query("id", "")
    if not id:
        wiz.response.status(400, message="ID가 필요합니다.")

    struct.post.delete(id)
    wiz.response.status(200)
