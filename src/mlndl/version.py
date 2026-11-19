"""バージョン (ADR-0027 D5・D6)

- LANGUAGE_VERSION: この mlndl が読める最も新しい ndl_version (言語のバージョン)
- __version__: パッケージのバージョン。メジャー.マイナーは LANGUAGE_VERSION と同じにする (1.0 のリリースから)

YAML の ndl_version は「この YAML を読むのに要る、最も古い mlndl のバージョン」を表す。
YAML のマイナーが LANGUAGE_VERSION より新しければ、未知のキーの error より先に
UnsupportedVersionError で止める。
"""

from __future__ import annotations

import re
from typing import Any

LANGUAGE_VERSION = "1.0"
__version__ = "0.1.0"

_FORMAT = re.compile(r"^(\d+)\.(\d+)$")


class UnsupportedVersionError(ValueError):
    """YAML の ndl_version が、この mlndl の読めるバージョンより新しい (ADR-0027 D5)"""


def _parse(ver: str) -> tuple[int, int] | None:
    m = _FORMAT.match(ver)
    return (int(m.group(1)), int(m.group(2))) if m else None


def check_ndl_version(data: Any) -> None:
    """YAML を辞書にしたものの ndl_version を検査する (ADR-0027 D5)

    - 書いていない / 文字列でない / 書式が違う / メジャーが 1 より古い: ValueError
    - この mlndl より新しい (メジャーかマイナー): UnsupportedVersionError
    辞書でなければ何もしない (スキーマの検査に任せる)
    """
    if not isinstance(data, dict):
        return
    if "ndl_version" not in data or data["ndl_version"] is None:
        raise ValueError(
            "ndl_version は必須です。この YAML を読むのに要る、最も古い mlndl のバージョンを、"
            '先頭に ndl_version: "1.0" のように書いてください。書いておくと、古い mlndl で読んだときに'
            "バージョンの違いを知らせて止まります (ADR-0027)"
        )
    ver = data["ndl_version"]
    if not isinstance(ver, str):
        raise ValueError(
            f'ndl_version は文字列です。"{LANGUAGE_VERSION}" のように引用符で囲んで書いてください。'
            f"引用符がないと、YAML は 1.10 を数の 1.1 と読みます (いま読んだ値: {ver!r}) (ADR-0027)"
        )
    got = _parse(ver)
    if got is None:
        raise ValueError(
            f'ndl_version は "<メジャー>.<マイナー>" の形で書いてください (例: "{LANGUAGE_VERSION}")。'
            f"いま書いてある値: {ver!r} (ADR-0027)"
        )
    known = _parse(LANGUAGE_VERSION)
    if got[0] < known[0]:
        raise ValueError(
            f"ndl_version {ver} はこの mlndl では読めません。この mlndl が読めるのは ndl_version "
            f"{known[0]}.x です (ADR-0027)"
        )
    if got > known:
        hint = (f"{ver} で足したキーを使っていないなら、ndl_version を下げても読めます"
                if got[0] == known[0] else f"ndl_version {got[0]}.x の YAML は {got[0]}.x の mlndl で読みます")
        raise UnsupportedVersionError(
            f"この YAML は ndl_version {ver} 以上を必要としますが、この mlndl ({__version__}) が読めるのは "
            f"ndl_version {LANGUAGE_VERSION} までです。mlndl を更新してください。{hint} (ADR-0027)"
        )
