from zwiggy_dwh.config import DbTarget, settings


def test_dbtarget_masked_repr():
    target = DbTarget(
        host="localhost",
        port=5432,
        dbname="test_db",
        user="myuser",
        password="secretpassword"
    )
    repr_str = target.masked_repr()
    assert "secretpassword" not in repr_str
    assert "***" in repr_str
    assert "myuser" in repr_str
    assert "test_db" in repr_str


def test_settings_default_load():
    s = settings()
    assert s.pg_host is not None
    assert s.pg_port > 0
    assert s.source_target is not None
    assert s.warehouse_target is not None
