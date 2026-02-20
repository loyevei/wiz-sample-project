import peewee as pw

orm = wiz.model("portal/season/orm")
base = orm.base("post")

class Model(base):
    class Meta:
        db_table = "comment"

    id = pw.CharField(max_length=32, primary_key=True)
    post_id = pw.CharField(max_length=32, index=True)
    author_id = pw.CharField(max_length=32, default="")
    author_name = pw.CharField(max_length=50, default="")
    content = pw.TextField(default="")
    created = pw.DateTimeField()
