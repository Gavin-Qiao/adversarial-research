import json
from pathlib import Path


def test_codex_plugin_manifest_exists() -> None:
    plugin_path = Path('harnesses/codex/.codex-plugin/plugin.json')
    assert plugin_path.exists()

    manifest = json.loads(plugin_path.read_text())
    assert manifest['name'] == 'principia'
    assert manifest['skills'] == './skills/'
    assert manifest['interface']['displayName'] == 'Principia'
    assert manifest['interface']['category'] == 'Productivity'
    assert "repo-local" in manifest['interface']['shortDescription']
    assert "full Principia checkout" in manifest['interface']['longDescription']
    assert "unsupported" in manifest['interface']['longDescription']


def test_marketplace_exposes_principia_plugin() -> None:
    marketplace = json.loads(Path('.agents/plugins/marketplace.json').read_text())
    assert marketplace['interface']['displayName'] == 'Principia'

    plugin = next(plugin for plugin in marketplace['plugins'] if plugin['name'] == 'principia')
    assert plugin['source']['source'] == 'local'
    assert plugin['source']['path'] == './harnesses/codex'
    assert plugin['policy']['installation'] == 'AVAILABLE'
    assert plugin['policy']['authentication'] == 'ON_INSTALL'
    assert plugin['category'] == 'Productivity'
