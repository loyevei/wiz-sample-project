import math

struct = wiz.model("portal/post/struct")

def categories():
    """카테고리 목록 조회"""
    cats = struct.post.categories()
    wiz.response.status(200, cats)

def search():
    """게시물 목록 검색 (페이징, 카테고리 필터, 텍스트 검색)"""
    page = int(wiz.request.query("page", 1))
    dump = int(wiz.request.query("dump", 20))
    text = wiz.request.query("text", "")
    category = wiz.request.query("category", "")

    rows, total = struct.post.search(text=text, category=category, page=page, dump=dump)
    wiz.response.status(200, rows=rows, total=total)
