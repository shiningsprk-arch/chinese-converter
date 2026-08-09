"""繁简转换工具核心单元测试（standalone，不依赖 MyBooks）。

Usage: python tests/test_converter_core.py   (or pytest tests/)
"""

import os
import sys
import tempfile
import zipfile

# Allow running from the repo root without installing the webserver package
_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.abspath(os.path.join(_HERE, ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from webserver.toolbox.chinese_converter import epub_converter  # noqa: E402
from webserver.toolbox.chinese_converter.opencc_engine import OpenCC  # noqa: E402

A5_PATH = os.path.join(_ROOT, "webserver", "toolbox", "chinese_converter", "a5_phrases.txt")

# ── 引擎测试 ─────────────────────────────────────────────────

def test_t2s_basic():
    oc = OpenCC("t2s")
    assert oc.convert("作為一個發展中的國家。") == "作为一个发展中的国家。"
    assert oc.convert("後台管理員的頭髮很長，為人低調。") == "后台管理员的头发很长，为人低调。"


def test_t2s_phrase_priority():
    # 词组优先：後台 → 后台（而非 後→后、台→台 的拼接）
    oc = OpenCC("t2s")
    assert oc.convert("後台") == "后台"
    assert oc.convert("電腦") == "电脑"


def test_t2s_punctuation_preserved():
    oc = OpenCC("t2s")
    text = "「你好」，世界！——測試…"
    assert oc.convert(text) == "「你好」，世界！——测试…"


def test_tw2s():
    oc = OpenCC("tw2s")
    # 臺→台（TWVariantsRev 字级映射）
    assert oc.convert("臺灣的軟體業者") == "台湾的软体业者"


def test_s2t():
    oc = OpenCC("s2t")
    assert oc.convert("作为发展中的国家，软件产业蓬勃发展。") == "作爲發展中的國家，軟件產業蓬勃發展。"
    assert oc.convert("后台管理员的头发很长。") == "後臺管理員的頭髮很長。"


def test_s2tw():
    oc = OpenCC("s2tw")
    assert oc.convert("作为发展中的国家。") == "作為發展中的國家。"


def test_t2tw_and_tw2t_work():
    oc1 = OpenCC("t2tw")
    assert "體驗" in oc1.convert("這個軟件的用戶體驗很好。")
    oc2 = OpenCC("tw2t")
    assert "體驗" in oc2.convert("這個軟體的用戶體驗很好。")


def test_a5_enhancement():
    # 不带增强词表：幹麼 → 干么（OpenCC 默认）
    plain = OpenCC("t2s")
    assert plain.convert("幹麼這樣？") == "干么这样？"
    # 带增强词表：幹麼 → 干嘛（a5 个人修正词条优先）
    enhanced = OpenCC("t2s", extra_dicts=[A5_PATH])
    assert enhanced.convert("幹麼這樣？") == "干嘛这样？"


def test_a5_ignored_for_s2t():
    # 增强词表是繁→简词条，注入 s2t 不应干扰（键为繁体，输入为简体不会命中）
    oc = OpenCC("s2t", extra_dicts=[A5_PATH])
    assert oc.convert("软件产业") == "軟件產業"


def test_invalid_direction_raises():
    try:
        OpenCC("no_such_direction")
    except (IOError, ValueError, OSError):
        return
    raise AssertionError("invalid direction should raise")


def test_no_conversion():
    oc = OpenCC("t2s")
    oc.set_conversion("no_conversion")
    assert oc.convert("繁體中文") == "繁體中文"
    oc.set_conversion("t2s")
    assert oc.convert("繁體中文") == "繁体中文"


# ── EPUB 测试 ─────────────────────────────────────────────────

CH1 = """<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml">
<head><title>第一章</title></head>
<body>
<p>作為一個發展中的國家，電腦產業蓬勃發展。</p>
<p>後台管理員的頭髮很長。</p>
<script type="text/javascript">var msg = "作為";</script>
</body>
</html>
"""

OPF = """<?xml version="1.0" encoding="utf-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="uid">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:identifier id="uid">urn:uuid:test</dc:identifier>
    <dc:title>繁體測試書</dc:title>
  </metadata>
  <manifest>
    <item id="ch1" href="ch1.xhtml" media-type="application/xhtml+xml"/>
    <item id="css" href="style.css" media-type="text/css"/>
  </manifest>
  <spine>
    <itemref idref="ch1"/>
  </spine>
</package>
"""

CONTAINER = """<?xml version="1.0" encoding="utf-8"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles>
    <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>
  </rootfiles>
</container>
"""

CSS = b".test { content: \"\xe4\xbd\x9c\xe7\x82\xba\"; }"  # .test { content: "作為"; }
PNG = b"\x89PNG\r\n\x1a\n" + b"fake-image-bytes"


def _make_epub(path):
    with zipfile.ZipFile(path, "w") as z:
        z.writestr(zipfile.ZipInfo("mimetype"), b"application/epub+zip")
        z.writestr("META-INF/container.xml", CONTAINER)
        z.writestr("OEBPS/content.opf", OPF)
        z.writestr("OEBPS/ch1.xhtml", CH1)
        z.writestr("OEBPS/style.css", CSS)
        z.writestr("OEBPS/cover.png", PNG)


def test_epub_conversion():
    with tempfile.TemporaryDirectory() as tmp:
        src = os.path.join(tmp, "in.epub")
        out = os.path.join(tmp, "out.epub")
        _make_epub(src)

        oc = OpenCC("t2s")
        epub_converter.convert_epub(src, out, oc.convert, convert_metadata=True)

        with zipfile.ZipFile(out, "r") as z:
            names = z.namelist()
            # mimetype 必须为第一项且不压缩（EPUB 规范）
            assert names[0] == "mimetype"
            assert z.getinfo("mimetype").compress_type == zipfile.ZIP_STORED
            assert z.read("mimetype") == b"application/epub+zip"

            html = z.read("OEBPS/ch1.xhtml").decode("utf-8")
            assert "作为一个发展中的国家" in html
            assert "后台管理员的头发很长" in html
            assert "第一章" in html  # <title> 文本也被转换
            # script 内容不得被转换
            assert 'var msg = "作為";' in html
            # XML 声明应保留
            assert html.lstrip().startswith("<?xml")

            opf = z.read("OEBPS/content.opf").decode("utf-8")
            assert "<dc:title>繁体测试书</dc:title>" in opf

            # 非文档条目字节级保留
            assert z.read("OEBPS/style.css") == CSS
            assert z.read("OEBPS/cover.png") == PNG


def test_epub_metadata_off():
    with tempfile.TemporaryDirectory() as tmp:
        src = os.path.join(tmp, "in.epub")
        out = os.path.join(tmp, "out.epub")
        _make_epub(src)

        oc = OpenCC("t2s")
        epub_converter.convert_epub(src, out, oc.convert, convert_metadata=False)

        with zipfile.ZipFile(out, "r") as z:
            opf = z.read("OEBPS/content.opf").decode("utf-8")
            assert "<dc:title>繁體測試書</dc:title>" in opf
            html = z.read("OEBPS/ch1.xhtml").decode("utf-8")
            assert "作为一个发展中的国家" in html


# ── TXT 测试 ──────────────────────────────────────────────────

def test_txt_utf8_conversion():
    with tempfile.TemporaryDirectory() as tmp:
        src = os.path.join(tmp, "in.txt")
        out = os.path.join(tmp, "out.txt")
        with open(src, "w", encoding="utf-8") as f:
            f.write("作為一個發展中的國家。\n後台管理員的頭髮很長。\n")
        oc = OpenCC("t2s")
        enc = epub_converter.convert_txt_file(src, out, oc.convert)
        assert enc == "utf-8"
        with open(out, encoding="utf-8") as f:
            assert f.read() == "作为一个发展中的国家。\n后台管理员的头发很长。\n"


def test_txt_gb18030_detection():
    with tempfile.TemporaryDirectory() as tmp:
        src = os.path.join(tmp, "in.txt")
        out = os.path.join(tmp, "out.txt")
        with open(src, "wb") as f:
            f.write("作為一個發展中的國家。".encode("gb18030"))
        oc = OpenCC("t2s")
        enc = epub_converter.convert_txt_file(src, out, oc.convert)
        assert enc == "gb18030"
        with open(out, encoding="utf-8") as f:
            assert f.read() == "作为一个发展中的国家。"


def test_detect_encoding():
    assert epub_converter.detect_encoding("你好".encode("utf-8")) == "utf-8"
    assert epub_converter.detect_encoding(b"\xef\xbb\xbf" + "你好".encode("utf-8")) == "utf-8-sig"
    assert epub_converter.detect_encoding("繁體中文".encode("gb18030")) == "gb18030"


if __name__ == "__main__":
    failures = 0
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for t in tests:
        try:
            t()
            print("PASS  %s" % t.__name__)
        except Exception as err:
            failures += 1
            import traceback
            print("FAIL  %s: %s" % (t.__name__, err))
            traceback.print_exc()
    print("\n%d/%d tests passed" % (len(tests) - failures, len(tests)))
    sys.exit(1 if failures else 0)
