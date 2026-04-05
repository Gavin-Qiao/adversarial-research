import json
from pathlib import Path


def test_codex_plugin_manifest_exists() -> None:
    plugin_path = Path('harnesses/codex/.codex-plugin/plugin.json')
    assert plugin_path.exists()

    manifest = json.loads(plugin_path.read_text())
    assert manifest['name'] == 'principia'
    assert manifest['skills'] == './skills/'


def test_marketplace_exposes_principia_plugin() -> None:
    marketplace = json.loads(Path('.agents/plugins/marketplace.json').read_text())
    plugin_names = [plugin['name'] for plugin in marketplace['plugins']]
    assert 'principia' in plugin_names
