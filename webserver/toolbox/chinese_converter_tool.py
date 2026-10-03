"""
繁简转换工具

对书库中的书籍（EPUB / TXT）执行简体↔繁体中文转换：
- 引擎：移植自 opencc-python（Apache 2.0），字典数据来自 OpenCC（Apache 2.0）
- 增强词表：a5566123s/Calibre-BIG5toGBK 个人修正版（繁体→简体，可选项）
- EPUB 采用 zip 条目级无损处理（仅转换正文 HTML 与 OPF/NCX 标题文本，
  样式、图片、字体等原样保留）；TXT 自动探测编码后转换。
- 输出方式：另存为新书入库（默认，保留原书，完整继承原书元数据）或替换原书（可选备份）。

@author: 黏菌, 2026
"""
import logging
import os
import shutil
import threading
import time
import traceback
from typing import Optional

from webserver import utils
from webserver.constants import (
    CALIBRE_COLUMN_CATEGORY,
    CALIBRE_COLUMN_EXT_LINK,
    CALIBRE_COLUMN_LOCATION,
    CALIBRE_COLUMN_DYNAMIC_COVER,
)
from webserver.i18n import _
from webserver.models import Item
from webserver.services import AsyncService
from webserver.services.background_service import BackgroundService, BackgroundTask
from webserver.toolbox.base_tool import BaseTool
from webserver.toolbox.chinese_converter.epub_converter import convert_epub, convert_txt_file
from webserver.toolbox.chinese_converter.opencc_engine import DIRECTION_LABELS, OpenCC

# 支持的方向（与 opencc 配置一致）
DIRECTIONS = ("t2s", "tw2s", "tw2sp", "s2t", "s2tw", "s2twp", "t2tw", "tw2t")

# 方向 → 目标语言代码（calibre 语言码：zh=简体，zht=繁体）
DIRECTION_LANG = {
    "t2s": "zh",
    "tw2s": "zh",
    "tw2sp": "zh",
    "s2t": "zht",
    "s2tw": "zht",
    "s2twp": "zht",
    "t2tw": "zht",
    "tw2t": "zht",
}

# 增强词表仅对繁体→简体方向生效
A5_DIRECTIONS = ("t2s", "tw2s")

# 另存为新书时的标题后缀（入库标题，固定文案）
NEW_BOOK_SUFFIX = {"zh": "（简体版）", "zht": "（繁體版）"}

A5_PHRASES_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                               "chinese_converter", "a5_phrases.txt")


class ChineseConverterTool(BaseTool):
    """对指定书籍执行繁简中文转换。"""

    service_item_name = "繁简转换"

    _convert_lock = threading.Lock()
    _last_task_id: Optional[int] = None

    @classmethod
    def is_running(cls) -> bool:
        task = cls.get_last_task()
        return bool(task and task.get("status") == BackgroundTask.STATUS_RUNNING)

    @classmethod
    def get_last_task(cls) -> Optional[dict]:
        if cls._last_task_id is None:
            return None
        return BackgroundService().get_task(cls._last_task_id)

    @staticmethod
    def info() -> dict:
        return {
            "tool_id": "chinese_converter",
            "name": "繁简转换",
            "description": "对书库中的书籍执行简体↔繁体中文转换（支持 EPUB/TXT，8 种转换方向，可选增强词表），"
                           "可另存为新书（完整继承原书元数据）或替换原书（可选备份）",
            "revision": "0.1.0",
            "author": "黏菌",
            "publish_date": "2026-08-09",
        }

    # ── 引擎构造 ────────────────────────────────────────────

    def _build_engine(self, direction: str, use_a5: bool) -> OpenCC:
        if direction not in DIRECTIONS:
            raise ValueError(_("不支持的转换方向：%s") % direction)
        extra = [A5_PHRASES_FILE] if (use_a5 and direction in A5_DIRECTIONS) else []
        return OpenCC(direction, extra_dicts=extra)

    # ── 转换（后台服务）─────────────────────────────────────

    @AsyncService.register_service
    def convert(self, book_id: int, direction: str, mode: str,
                use_a5: bool, convert_title: bool, backup: bool,
                user_id: int) -> None:
        """执行繁简转换，通过 register_service 在后台线程中运行。

        :param book_id:       Calibre 书籍 ID
        :param direction:     转换方向（t2s/tw2s/tw2sp/s2t/s2tw/s2twp/t2tw/tw2t）
        :param mode:          "book"=另存为新书（默认），"replace"=替换原书
        :param use_a5:        是否启用增强词表（仅繁→简方向生效）
        :param convert_title: 是否转换书名/目录等元数据文本
        :param backup:        替换模式下是否备份原文件
        :param user_id:       操作用户 ID（记录日志用）
        """
        if not ChineseConverterTool._convert_lock.acquire(blocking=False):
            logging.warning("[ChineseConverterTool] Already running, skipping convert for book_id=%d [uid:%d]",
                            book_id, user_id)
            return

        # create_task 等全部放入 try：若中途抛异常，finally 仍会释放锁
        task_id = None
        error_message = None
        book_title = "Unknown"

        try:
            task_id = self.create_task(progress_data={
                "status": "starting", "book_id": book_id,
                "direction": direction, "mode": mode,
            })
            ChineseConverterTool._last_task_id = task_id

            books = self.api.calibre.get_data_as_dict([book_id])
            if not books:
                error_message = _("书籍不存在：ID=%d") % book_id
                logging.error("[ChineseConverterTool] Book not found: ID=%d [uid:%d]", book_id, user_id)
                return

            book = books[0]
            book_title = book.get("title", "Unknown")
            fmts = [f.upper() for f in (book.get("available_formats") or [])]
            fmt = next((f for f in ("EPUB", "TXT") if f in fmts), None)
            if fmt is None:
                error_message = _("该书籍没有 EPUB / TXT 格式，无法转换")
                logging.error("[ChineseConverterTool] No EPUB/TXT format for book_id=%d [uid:%d]", book_id, user_id)
                return

            src_path = self.api.calibre.format_abspath(book_id, fmt)
            if not src_path or not os.path.exists(src_path):
                error_message = _("找不到 %s 文件，可能已被移除") % fmt
                logging.error("[ChineseConverterTool] %s file missing for book_id=%d [uid:%d]",
                              fmt, book_id, user_id)
                return

            self.update_task_progress(task_id, 5, {"status": "running", "stage": "reading"})
            work_dir = self.get_work_dir(str(book_id))
            out_path = os.path.join(work_dir, "converted." + fmt.lower())

            engine = self._build_engine(direction, use_a5)

            def progress_cb(percent, stage):
                # 转换阶段占比 5%~90%
                self.update_task_progress(task_id, min(5 + int(percent * 0.85), 90), {
                    "status": "running", "stage": stage, "direction": direction,
                })

            if fmt == "EPUB":
                convert_epub(src_path, out_path, engine.convert,
                             convert_metadata=convert_title,
                             progress_cb=progress_cb)
            else:
                convert_txt_file(src_path, out_path, engine.convert)
                progress_cb(100, "converting")

            self.update_task_progress(task_id, 92, {"status": "running", "stage": "saving"})

            if mode == "replace":
                new_book_id = self._replace_format(book_id, fmt, out_path, backup, work_dir)
                target_id = new_book_id or book_id
                if convert_title:
                    self._apply_title_conversion(target_id, direction, engine)
                else:
                    self._set_language(target_id, direction)
                self.add_msg(user_id, "success",
                             _("《%s》已转换为%s并替换原文件%s") % (
                                 book_title, self._direction_label(direction),
                                 _("（原文件已备份）") if backup else ""))
            else:
                new_book_id = self._import_as_new_book(book_id, fmt, out_path, direction,
                                                       convert_title, engine, user_id)
                self.add_msg(user_id, "success",
                             _("《%s》已转换为%s并另存为新书，可在书库中查看") % (
                                 book_title, self._direction_label(direction)))

            self.update_task_progress(task_id, 100, {
                "status": "completed", "book_id": book_id,
                "new_book_id": new_book_id, "direction": direction,
            })

        except Exception as err:
            error_message = str(err)
            self.add_msg(user_id, "danger",
                         _("《%s》繁简转换失败：%s") % (book_title, str(err)))
            logging.error("[ChineseConverterTool] Convert failed for book_id=%d: %s", book_id, err)
            logging.error(traceback.format_exc())
        finally:
            # create_task 失败时 task_id 为 None，跳过任务收尾（锁仍必须释放）
            if task_id is not None:
                self.complete_task(task_id, error_message=error_message)
            ChineseConverterTool._convert_lock.release()

    # ── 输出处理 ────────────────────────────────────────────

    def _replace_format(self, book_id: int, fmt: str, out_path: str,
                        backup: bool, work_dir: str) -> Optional[int]:
        """替换原书格式；可选备份；返回新 book_id（None 表示原位替换）。

        备份保存在独立持久目录（``get_work_dir("backups")``），不随 work_dir
        清理，避免成功路径清理临时目录时误删备份。
        """
        if backup:
            backup_dir = self.get_work_dir("backups")
            backup_path = os.path.join(
                backup_dir, "backup_%d_%s_%d.%s" % (
                    book_id, fmt.lower(), int(time.time()), fmt.lower()))
            calibre_path = self.api.calibre.format_abspath(book_id, fmt)
            if calibre_path and os.path.exists(calibre_path):
                shutil.copy2(calibre_path, backup_path)
                logging.info("[ChineseConverterTool] Backed up %s to %s", fmt, backup_path)
        with open(out_path, "rb") as f:
            self.api.calibre.add_format(book_id, fmt, f)
        logging.info("[ChineseConverterTool] Replaced %s for book_id=%d", fmt, book_id)
        try:
            os.remove(out_path)
        except OSError:
            pass
        return None

    def _import_as_new_book(self, book_id: int, fmt: str, out_path: str,
                            direction: str, convert_title: bool, engine,
                            user_id: int) -> int:
        """将转换产物另存为新书入库，完整继承原书元数据（标签、系列、评分、
        评论、语言、封面、自定义列等），返回新书 book_id。"""
        # get_metadata 每次返回全新对象，可直接原地修改（勿 deepcopy，
        # 其内部挂有指向 Cache 的代理，深拷贝不安全）
        mi = self.api.calibre.get_metadata(book_id, get_cover=True, cover_as_data=True)

        suffix = NEW_BOOK_SUFFIX.get(DIRECTION_LANG.get(direction, "zh"), "（新版本）")
        title = (mi.title or "Unknown").strip()
        if convert_title:
            title = engine.convert(title)
        mi.title = utils.super_strip(title) + suffix
        mi.title_sort = utils.get_title_sort(mi.title)
        if convert_title and mi.authors:
            mi.authors = [engine.convert(a) for a in mi.authors]
            mi.author_sort = None  # 名字已转换，排序键由 calibre 按新名字重算
        if convert_title:
            # 简介/出版社/丛书/标签同步转换（简介可能含 HTML：opencc 逐字符
            # 转换，标签与实体为 ASCII 不受影响）
            if mi.comments:
                mi.comments = engine.convert(mi.comments)
            if mi.publisher:
                mi.publisher = engine.convert(mi.publisher)
            if mi.series:
                mi.series = engine.convert(mi.series)
            if mi.tags:
                mi.tags = [engine.convert(t) for t in mi.tags]
        mi.languages = [DIRECTION_LANG.get(direction, "zh")]
        mi.uuid = None  # 新书应使用独立 UUID，避免与原书冲突

        new_book_id = self.api.calibre.import_book(mi, [out_path])
        if new_book_id is None:
            raise RuntimeError(_("导入文件失败，Calibre未返回书籍ID"))

        try:
            item = Item()
            item.book_id = new_book_id
            item.collector_id = user_id
            item.save()
        except Exception as err:
            logging.error("[ChineseConverterTool] Failed to create Item record for book_id=%s: %s",
                          new_book_id, err)

        # 兜底：显式复制 MyBooks 自定义列（实体书类型/数量除外，
        # 避免新书既有实体书标记又有格式文件的状态冲突）
        for col in (CALIBRE_COLUMN_CATEGORY, CALIBRE_COLUMN_EXT_LINK,
                    CALIBRE_COLUMN_LOCATION, CALIBRE_COLUMN_DYNAMIC_COVER):
            try:
                val = self.api.calibre.get_custom(book_id, col)
            except Exception as err:
                logging.warning("[ChineseConverterTool] Failed to read %s of book_id=%d: %s",
                                col, book_id, err)
                continue
            if val in (None, ""):
                continue
            try:
                self.api.calibre.set_custom(col, {new_book_id: val})
            except Exception as err:
                logging.warning("[ChineseConverterTool] Failed to copy %s to new book_id=%d: %s",
                                col, new_book_id, err)

        self.cleanup_work_dir(os.path.dirname(out_path))

        try:
            os.remove(out_path)
        except OSError:
            pass

        logging.info("[ChineseConverterTool] Imported converted %s as new book_id=%d (from %d)",
                     fmt, new_book_id, book_id)
        return new_book_id

    def _apply_title_conversion(self, book_id: int, direction: str, engine) -> None:
        """替换模式下同步库内标题/作者/语言（不加后缀），保持与转换后文件一致。
        封面不受影响：set_metadata 只会更新提供的封面、从不删除现有封面。"""
        try:
            mi = self.api.calibre.get_metadata(book_id)
            if mi.title:
                mi.title = engine.convert(mi.title)
            mi.title = mi.title or "Unknown"
            mi.title_sort = utils.get_title_sort(mi.title)
            if mi.authors:
                mi.authors = [engine.convert(a) for a in mi.authors]
                mi.author_sort = None  # 名字已转换，排序键由 calibre 按新名字重算
            # 简介/出版社/丛书/标签同步转换（简介可能含 HTML：opencc 逐字符
            # 转换，标签与实体为 ASCII 不受影响）
            if mi.comments:
                mi.comments = engine.convert(mi.comments)
            if mi.publisher:
                mi.publisher = engine.convert(mi.publisher)
            if mi.series:
                mi.series = engine.convert(mi.series)
            if mi.tags:
                mi.tags = [engine.convert(t) for t in mi.tags]
            mi.languages = [DIRECTION_LANG.get(direction, "zh")]
            self.api.calibre.set_metadata(book_id, mi, force_changes=True)
            logging.info("[ChineseConverterTool] Updated title/authors/language for book_id=%d", book_id)
        except Exception as err:
            logging.warning("[ChineseConverterTool] Failed to update title for book_id=%d: %s",
                            book_id, err)

    def _set_language(self, book_id: int, direction: str) -> None:
        lang = DIRECTION_LANG.get(direction, "zh")
        try:
            self.set_book_language(book_id, lang)
        except Exception as err:
            logging.warning("[ChineseConverterTool] Failed to set language for book_id=%d: %s",
                            book_id, err)

    @staticmethod
    def _direction_label(direction: str) -> str:
        return DIRECTION_LABELS.get(direction, direction)


if __name__ == "__main__":
    import sys

    if len(sys.argv) not in (3, 4):
        print("Usage: python -m webserver.toolbox.chinese_converter_tool <direction> <epub|txt_path> [--a5]")
        sys.exit(1)

    direction = sys.argv[1]
    path = sys.argv[2]
    use_a5 = "--a5" in sys.argv[3:]
    out = os.path.splitext(path)[0] + ".converted" + os.path.splitext(path)[1]
    engine = ChineseConverterTool()._build_engine(direction, use_a5)
    if path.lower().endswith(".txt"):
        convert_txt_file(path, out, engine.convert)
    else:
        convert_epub(path, out, engine.convert, convert_metadata=True)
    print("converted -> %s" % out)
