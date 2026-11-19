"""ADR-0027 互換の約束: ndl_version の検査 (D5)、バージョン (D6)、エクスポーターの meta"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pydantic
import pytest

import mlndl
from mlndl import LANGUAGE_VERSION, MLNDLTopology, UnsupportedVersionError, __version__, parse
from mlndl.exporter import cytoscape
from mlndl.version import check_ndl_version

ROOT = Path(__file__).parent.parent


class TestRequired:
    def test_missing(self):
        with pytest.raises(ValueError, match="ndl_version は必須です") as exc:
            parse(b"layer1:\n  nodes: [{id: a}]\n")
        assert not isinstance(exc.value, UnsupportedVersionError)

    def test_null(self):
        with pytest.raises(ValueError, match="ndl_version は必須です"):
            parse(b"ndl_version:\n")

    def test_model_validate_also_checks(self):
        """parse を通さずにモデルを作っても同じ検査が効く (保険)"""
        with pytest.raises(pydantic.ValidationError, match="ndl_version は必須です"):
            MLNDLTopology.model_validate({})


class TestFormat:
    @pytest.mark.parametrize("raw", ["1.0", "1.10", "1"])
    def test_unquoted_number(self, raw):
        with pytest.raises(ValueError, match="引用符で囲んで"):
            parse(f"ndl_version: {raw}\n")

    @pytest.mark.parametrize("raw", ['"abc"', '"1"', '"1.0.0"', '"v1.0"', '" 1.0"'])
    def test_bad_format(self, raw):
        with pytest.raises(ValueError, match="<メジャー>.<マイナー>"):
            parse(f"ndl_version: {raw}\n")

    def test_older_major(self):
        with pytest.raises(ValueError, match="この mlndl では読めません") as exc:
            parse(b'ndl_version: "0.9"\n')
        assert not isinstance(exc.value, UnsupportedVersionError)


class TestCompare:
    def test_same_version_reads(self):
        assert parse(f'ndl_version: "{LANGUAGE_VERSION}"\n'.encode()).ndl_version == LANGUAGE_VERSION

    def test_newer_minor(self):
        with pytest.raises(UnsupportedVersionError, match=r"ndl_version 1\.1 以上を必要とします") as exc:
            parse(b'ndl_version: "1.1"\n')
        assert "下げても読めます" in str(exc.value)
        assert f"この mlndl ({__version__})" in str(exc.value)

    def test_newer_major(self):
        with pytest.raises(UnsupportedVersionError, match="2.x の mlndl で読みます"):
            parse(b'ndl_version: "2.0"\n')

    def test_numeric_comparison(self, monkeypatch):
        """マイナーは数として比べる: 1.10 は 1.9 より新しい"""
        monkeypatch.setattr("mlndl.version.LANGUAGE_VERSION", "1.9")
        check_ndl_version({"ndl_version": "1.9"})
        check_ndl_version({"ndl_version": "1.2"})
        with pytest.raises(UnsupportedVersionError):
            check_ndl_version({"ndl_version": "1.10"})

    def test_version_error_comes_before_unknown_keys(self):
        """新しいバージョンの YAML の未知のキーは、バージョンの違いの error 1 本にまとまる"""
        with pytest.raises(UnsupportedVersionError):
            parse(b'ndl_version: "1.1"\nlayer3:\n  interfaces:\n    - {id: a-l3, node: a, mtu: 9000}\n')

    def test_is_value_error(self):
        """except ValueError で捕まえていたコードは壊れない"""
        assert issubclass(UnsupportedVersionError, ValueError)


class TestVersions:
    def test_public(self):
        assert {"LANGUAGE_VERSION", "UnsupportedVersionError"} <= set(mlndl.__all__)
        assert re.fullmatch(r"\d+\.\d+", LANGUAGE_VERSION)

    def test_pyproject_matches(self):
        text = (ROOT / "pyproject.toml").read_text()
        assert re.search(r'^version = "([^"]+)"', text, re.M).group(1) == __version__


class TestExportMeta:
    def test_meta_has_input_version(self):
        out = cytoscape.export(parse(b'ndl_version: "1.0"\n'))
        assert list(out) == ["meta", "nodes", "edges"]
        assert out["meta"] == {"ndl_version": "1.0", "mlndl_version": __version__}

    def test_input_meta_is_not_exported(self):
        """入力の meta (下流のツールの設定) は出力に流れない (ADR-0027 D7)"""
        out = cytoscape.export(parse(b'ndl_version: "1.0"\nmeta:\n  name: x\n  ndl-viz: {layout: grid}\n'))
        assert out["meta"] == {"ndl_version": "1.0", "mlndl_version": __version__}


def test_cli_version_error_has_no_schema_note(tmp_path):
    """CLI: バージョンの違いは 1 本の ERROR だけ。「スキーマの段階で」の注記は付けない"""
    f = tmp_path / "t.yaml"
    f.write_text('ndl_version: "1.1"\nlayer1:\n  nodes: [{id: a, future_key: 1}]\n')
    r = subprocess.run([sys.executable, "-m", "mlndl", "validate", str(f)], capture_output=True, text=True)
    assert r.returncode == 1
    lines = r.stderr.strip().splitlines()
    assert len(lines) == 1 and lines[0].startswith("ERROR") and "1.1 以上を必要とします" in lines[0]
