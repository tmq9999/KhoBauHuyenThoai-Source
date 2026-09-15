import importlib.util
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "tools" / "apk-recovery" / "index-settings.py"


def load_module():
    spec = importlib.util.spec_from_file_location("index_settings", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


FIXTURE = r'''
// Static data only; a parser must never execute the trailing expression.
window._CCSettings = {
  launchScene: "db://assets/ui/logo_scene.fire",
  orientation: "landscape",
  scenes: [
    {url: "db://assets/ui/logo_scene.fire", uuid: "scene/uuid+1"},
    {url:'db://assets/ui/home_scene.fire',uuid:'scene-2'}
  ],
  rawAssets: {assets: {
    "0": ["img/hero.png", 1],
    "ab": ["sound/click.mp3", 2]
  }},
  jsList: ["assets/scripts/a.js", 'assets/scripts/b.js']
};
globalThis.SHOULD_NOT_RUN = true;
'''


def test_indexes_supported_static_settings_fields_without_executing_js():
    module = load_module()
    result = module.index_settings(FIXTURE, source_name="fixture.decoded")

    assert result["launchScene"] == "db://assets/ui/logo_scene.fire"
    assert result["orientation"] == "landscape"
    assert result["scenes"] == [
        {"index": 0, "url": "db://assets/ui/logo_scene.fire", "uuid": "scene/uuid+1"},
        {"index": 1, "url": "db://assets/ui/home_scene.fire", "uuid": "scene-2"},
    ]
    assert result["rawAssets"] == [
        {"id": "0", "path": "img/hero.png"},
        {"id": "ab", "path": "sound/click.mp3"},
    ]
    assert result["jsList"] == ["assets/scripts/a.js", "assets/scripts/b.js"]
    assert result["counts"] == {"scenes": 2, "rawAssets": 2, "jsList": 2}
    assert result["source"]["name"] == "fixture.decoded"
    assert len(result["source"]["sha256"]) == 64
    assert "text" not in result["source"]


def test_rejects_input_without_ccsettings_assignment():
    module = load_module()
    try:
        module.index_settings("const settings = {};", source_name="bad.js")
    except module.ParseError as exc:
        assert "window._CCSettings" in str(exc)
    else:
        raise AssertionError("expected ParseError")


def test_cli_writes_json_and_scene_csv_in_approved_root(tmp_path, monkeypatch, capsys):
    module = load_module()
    monkeypatch.setattr(module, "ROOT", tmp_path)
    source = tmp_path / "settings.decoded"
    json_output = tmp_path / "docs" / "reverse-engineering" / "index.json"
    csv_output = tmp_path / "docs" / "reverse-engineering" / "scenes.csv"
    source.write_text(FIXTURE, encoding="utf-8")

    assert module.main([
        str(source), "--json-output", str(json_output), "--scene-csv-output", str(csv_output),
    ]) == 0

    assert json.loads(capsys.readouterr().out)["counts"]["scenes"] == 2
    assert json.loads(json_output.read_text(encoding="utf-8"))["counts"]["scenes"] == 2
    assert csv_output.read_text(encoding="utf-8").splitlines() == [
        "index,url,uuid",
        "0,db://assets/ui/logo_scene.fire,scene/uuid+1",
        "1,db://assets/ui/home_scene.fire,scene-2",
    ]


def test_cli_refuses_existing_or_input_alias_outputs_without_altering_them(tmp_path, monkeypatch, capsys):
    module = load_module()
    monkeypatch.setattr(module, "ROOT", tmp_path)
    source = tmp_path / "settings.decoded"
    source.write_text(FIXTURE, encoding="utf-8")
    safe_dir = tmp_path / "docs" / "reverse-engineering"
    safe_dir.mkdir(parents=True)
    existing = safe_dir / "index.json"
    existing.write_text("keep existing", encoding="utf-8")
    csv_output = safe_dir / "scenes.csv"

    with pytest.raises(SystemExit) as exit_info:
        module.main([str(source), "--json-output", str(existing), "--scene-csv-output", str(csv_output)])
    assert exit_info.value.code == 2
    assert existing.read_text(encoding="utf-8") == "keep existing"
    assert not csv_output.exists()
    assert "exists" in capsys.readouterr().err

    with pytest.raises(SystemExit) as exit_info:
        module.main([str(source), "--json-output", str(source), "--scene-csv-output", str(csv_output)])
    assert exit_info.value.code == 2
    assert source.read_text(encoding="utf-8") == FIXTURE
    assert not csv_output.exists()


def test_rejects_output_aliases_protected_trees_and_reparse_ancestry(tmp_path, monkeypatch):
    module = load_module()
    monkeypatch.setattr(module, "ROOT", tmp_path)
    source = tmp_path / "settings.decoded"
    source.write_text(FIXTURE, encoding="utf-8")
    docs = tmp_path / "docs" / "reverse-engineering"
    docs.mkdir(parents=True)
    csv_output = docs / "scenes.csv"

    for protected in (
        tmp_path / "APK" / "index.json",
        tmp_path / "work" / "apk-vn" / "20260914T180000Z" / "index.json",
        csv_output,
    ):
        with pytest.raises(ValueError, match="output|APK|baseline|distinct"):
            module.validate_output_paths(source, protected, csv_output)

    outside = tmp_path / "outside"
    outside.mkdir()
    link = docs / "linked"
    try:
        link.symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("symlink creation is unavailable on this Windows test host")
    with pytest.raises(ValueError, match="symlink|reparse"):
        module.validate_output_paths(source, link / "index.json", csv_output)
