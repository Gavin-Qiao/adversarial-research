def test_package_and_legacy_modules_share_build_function() -> None:
    from db import build_db as legacy_build_db
    from principia.core.db import build_db as package_build_db

    assert legacy_build_db is package_build_db
