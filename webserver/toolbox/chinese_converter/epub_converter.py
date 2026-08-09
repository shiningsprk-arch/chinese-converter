# -*- coding: utf-8 -*-
"""EPUB / TXT 无损转换核心（不依赖 MyBooks，可独立测试）。

转换策略
--------
EPUB 本质是 ZIP 容器，这里采用“条目级”处理保证无损：
- 仅对 ``.html/.xhtml/.htm`` 做 HTML 解析，转换所有文本节点
  （跳过 ``script/style/noscript`` 子树，避免破坏脚本与样式）；
- 对 OPF（``.opf``）与 NCX（``.ncx``）做 XML 解析，转换其中的标题类文本
  （``dc:title``、``navLabel`` 等）；
- CSS、图片、字体等其余条目字节原样保留；
- 重新打包时 ``mimetype`` 置首且 ``ZIP_STORED``（EPUB 规范要求），
  其余条目沿用原压缩方式（``ZIP_DEFLATED``）。

TXT 为纯文本：自动探测编码（UTF-8 → GB18030），转换后统一以 UTF-8 输出。

转换逻辑通过 ``converter`` 可调用对象注入（``text -> text``），
方便在测试中用简单替换函数验证，也便于解耦引擎。
"""

import os
import zipfile

from bs4 import BeautifulSoup

# 参与正文转换的 HTML 扩展名
HTML_EXTS = (".html", ".xhtml", ".htm")
# 解析为 XML 并转换标题类文本的扩展名
XML_EXTS = (".opf", ".ncx")
# 正文解析时跳过的子树（脚本 / 样式 / 注释区）
SKIP_TAGS = {"script", "style", "noscript"}


def convert_epub(epub_path, out_path, converter, convert_metadata=True, progress_cb=None):
    """转换 EPUB 并写出新文件。

    :param epub_path:        源 EPUB 路径
    :param out_path:         输出 EPUB 路径
    :param converter:        ``(str) -> str`` 文本转换函数
    :param convert_metadata: 是否转换 OPF/NCX 中的标题类文本（默认 True）
    :param progress_cb:      可选进度回调 ``(percent: int, stage: str) -> None``
    """
    if not os.path.isfile(epub_path):
        raise IOError("EPUB 文件不存在: %s" % epub_path)

    with zipfile.ZipFile(epub_path, "r") as zin:
        infos = zin.infolist()
        entries = {info.filename: zin.read(info.filename) for info in infos}
        # mimetype 必须保持原始字节（EPUB 规范：第一项、不压缩）
        mimetype_data = entries.get("mimetype", b"application/epub+zip")

    total_docs = sum(
        1 for name in entries
        if name.lower().endswith(HTML_EXTS) or name.lower().endswith(XML_EXTS)
    )
    done_docs = 0

    for name, data in entries.items():
        lower = name.lower()
        if lower.endswith(HTML_EXTS):
            new_data = _convert_html_doc(data, converter)
        elif convert_metadata and lower.endswith(XML_EXTS):
            new_data = _convert_xml_doc(data, converter)
        else:
            continue
        entries[name] = new_data
        done_docs += 1
        if progress_cb and total_docs:
            progress_cb(int(done_docs * 100 / total_docs), "converting")

    _write_epub(out_path, entries, mimetype_data)
    if progress_cb:
        progress_cb(100, "packing")


def _convert_html_doc(data, converter):
    """转换单个 HTML/XHTML 文档的所有文本节点。"""
    if not data.strip():
        return data
    text = data.decode("utf-8", errors="replace")
    soup = BeautifulSoup(text, "html.parser")
    _convert_text_nodes(soup, converter)
    return soup.encode("utf-8")


def _convert_xml_doc(data, converter):
    """转换 OPF/NCX 中的标题类文本（仅文本节点，不动属性）。"""
    if not data.strip():
        return data
    text = data.decode("utf-8", errors="replace")
    soup = BeautifulSoup(text, "xml")
    if soup.find() is None:
        # 不是合法 XML，原样返回
        return data
    for node in soup.find_all(string=True):
        node.replace_with(converter(str(node)))
    return soup.encode("utf-8")


def _convert_text_nodes(soup, converter):
    """遍历并转换文本节点；跳过 SKIP_TAGS 子树。"""
    for parent in soup.find_all():
        if parent.name in SKIP_TAGS:
            continue
        for child in parent.find_all(string=True, recursive=False):
            child.replace_with(converter(str(child)))


def _write_epub(out_path, entries, mimetype_data):
    """按 EPUB 规范写 zip：mimetype 首项且 STORED，其余 DEFLATED。"""
    names = list(entries.keys())
    ordered = [n for n in names if n != "mimetype"]
    ordered.sort()

    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as zout:
        zinfo = zipfile.ZipInfo("mimetype")
        zinfo.compress_type = zipfile.ZIP_STORED
        zout.writestr(zinfo, mimetype_data)
        for name in ordered:
            zout.writestr(name, entries[name])


def convert_txt_file(src_path, out_path, converter):
    """转换 TXT 文件；编码自动探测（UTF-8 → GB18030），输出统一 UTF-8。

    :return: 检测到的源编码（如 'utf-8' / 'gb18030'）
    """
    with open(src_path, "rb") as f:
        data = f.read()
    encoding = detect_encoding(data)
    text = data.decode(encoding, errors="replace")
    converted = converter(text)
    with open(out_path, "w", encoding="utf-8", newline="") as f:
        f.write(converted)
    return encoding


def detect_encoding(data: bytes) -> str:
    """探测文本编码：UTF-8（含 BOM）→ GB18030 → UTF-8 兜底。"""
    if data.startswith(b"\xef\xbb\xbf"):
        return "utf-8-sig"
    try:
        data.decode("utf-8")
        return "utf-8"
    except UnicodeDecodeError:
        pass
    try:
        data.decode("gb18030")
        return "gb18030"
    except UnicodeDecodeError:
        return "utf-8"
