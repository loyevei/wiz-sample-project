import peewee as pw

orm = wiz.model("portal/season/orm")
base = orm.base("base")

class Model(base):
    class Meta:
        db_table = "user"

    id = pw.CharField(max_length=32, primary_key=True)
    email = pw.CharField(max_length=128, unique=True)
    password = pw.CharField(max_length=200)
    name = pw.CharField(max_length=50)
    mobile = pw.CharField(max_length=20, default="")
    role = pw.CharField(max_length=16, default="user", index=True)
    created = pw.DateTimeField(index=True)
    updated = pw.DateTimeField()
