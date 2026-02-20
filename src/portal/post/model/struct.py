# =============================================================================
# Post 패키지 Struct 진입점 (Composite Struct / Singleton)
# =============================================================================
# 호출 예시:
#   struct = wiz.model("portal/post/struct")
#   struct.post.search(text="검색어", page=1, dump=20)
#   post = struct.post(post_id)   # 인스턴스화
#   post.data                      # 게시물 데이터
#   struct.comment.list(post_id)   # 댓글 목록
# =============================================================================

class Struct:
    def __init__(self):
        self.orm = wiz.model("portal/season/orm")
        self.session = wiz.model("portal/season/session").use()

        # Sub-Struct 클래스 로드
        self._Post = wiz.model("portal/post/struct/post")
        self._Comment = wiz.model("portal/post/struct/comment")

        # 테이블 자동 생성 (없으면 생성)
        self._init_tables()

    def _init_tables(self):
        """DB 테이블이 없으면 자동 생성"""
        for name in ["post", "comment"]:
            try:
                db = self.orm.use(name, module="post")
                db.orm.create_table(safe=True)
            except Exception:
                pass

    def db(self, name):
        """ORM Wrapper 반환 (portal/post/model/db/{name}.py)"""
        return self.orm.use(name, module="post")

    def getUserId(self):
        """현재 세션 사용자 ID"""
        return self.session.get("id", "")

    def getUserName(self):
        """현재 세션 사용자 이름"""
        return self.session.get("name", "")

    def isAdmin(self):
        """관리자 여부 확인"""
        return self.session.get("role") == "admin"

    @property
    def post(self):
        """Post Sub-Struct 접근 (호출마다 새 인스턴스)"""
        return self._Post(self)

    @property
    def comment(self):
        """Comment Sub-Struct 접근"""
        return self._Comment(self)

Model = Struct()
