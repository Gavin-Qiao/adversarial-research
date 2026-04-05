from __future__ import annotations


def test_manage_entrypoint_delegates_to_package_main(monkeypatch) -> None:
    called: dict[str, bool] = {}

    def fake_main() -> None:
        called["ok"] = True

    monkeypatch.setattr("principia.cli.manage.main", fake_main)

    import scripts.manage as manage

    manage.main()

    assert called["ok"] is True
