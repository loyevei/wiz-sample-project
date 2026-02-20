import json
import datetime

struct = wiz.model("struct")

def overview():
    """대시보드 통계 및 최근 게시물"""
    # Post 통계 (패키지 Struct 접근)
    post_struct = struct.post
    total_posts = post_struct.post.db.count() or 0
    published_posts = post_struct.post.db.count(status="published") or 0
    draft_posts = post_struct.post.db.count(status="draft") or 0

    # User 통계 (로컬 Struct)
    total_members = struct.user.count()

    stats = [
        {"label": "전체 게시물", "value": str(total_posts), "change": 0, "icon": "📄", "bgColor": "bg-blue-50"},
        {"label": "공개 게시물", "value": str(published_posts), "change": 0, "icon": "✅", "bgColor": "bg-green-50"},
        {"label": "임시저장", "value": str(draft_posts), "change": 0, "icon": "✏️", "bgColor": "bg-yellow-50"},
        {"label": "멤버", "value": str(total_members), "change": 0, "icon": "👥", "bgColor": "bg-purple-50"},
    ]

    # 최근 게시물 5건
    recent = post_struct.post.db.rows(orderby="created", order="DESC", page=1, dump=5)
    colors = [
        "bg-indigo-100 text-indigo-700",
        "bg-pink-100 text-pink-700",
        "bg-green-100 text-green-700",
        "bg-amber-100 text-amber-700",
        "bg-cyan-100 text-cyan-700",
    ]
    for i, r in enumerate(recent):
        r["author"] = r.get("author_name", "")
        r["date"] = str(r.get("created", ""))[:10]
        r["avatarColor"] = colors[i % len(colors)]

    wiz.response.status(200, stats=stats, recent=recent)
