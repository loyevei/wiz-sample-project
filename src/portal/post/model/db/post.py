import peewee as pw

orm = wiz.model("portal/season/orm")
base = orm.base("post")

class Model(base):
    class Meta:
        db_table = "post"

    id = pw.CharField(max_length=32, primary_key=True)
    title = pw.CharField(max_length=200)
    content = pw.TextField(default="")
    category = pw.CharField(max_length=50, default="", index=True)
    author_id = pw.CharField(max_length=32, default="")
    author_name = pw.CharField(max_length=50, default="")
    status = pw.CharField(max_length=16, default="draft", index=True)
    created = pw.DateTimeField(index=True)
    updated = pw.DateTimeField()
