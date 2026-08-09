# 繁简转换（Chinese Converter）

MyBooks Toolbox 工具：对书库中的书籍执行 **简体 ↔ 繁体中文转换**。

> 工具 ID：`chinese_converter`
> 版本：0.1.0
> 支持格式：EPUB / TXT
> 使用：书库 → 工具箱 → 繁简转换 → 选择书籍、配置方向与选项 → 开始转换

---

## 功能特性

1. **6 种转换方向**（OpenCC 标准配置）
   - `t2s` 繁体 → 简体（默认）
   - `tw2s` 台湾繁体 → 简体
   - `s2t` 简体 → 繁体
   - `s2tw` 简体 → 台湾繁体
   - `t2tw` 繁体 → 台湾繁体
   - `tw2t` 台湾繁体 → 繁体
2. **增强词表**（可选）：a5566123s/Calibre-BIG5toGBK 个人修正版，约 5000 条繁→简词条
   （如 `幹麼→干嘛`、`達文西密碼→《达·芬奇密码》`），优先于默认词表匹配；仅对繁→简方向生效
3. **EPUB 无损处理**：zip 条目级处理，仅转换正文 HTML 文本节点与 OPF/NCX 标题文本；
   样式、图片、字体等原样保留；重新打包符合 EPUB 规范（`mimetype` 置首、不压缩）
4. **TXT 编码自动探测**：UTF-8（含 BOM）/ GB18030，输出统一 UTF-8
5. **两种输出方式**：
   - **另存为新书**（默认）：转换结果作为新书籍入库（标题加「（简体版）/（繁體版）」后缀），完整继承原书元数据（标签、系列、评分、评论、语言、封面、自定义列等），保留原书
   - **替换原书**：覆盖原 EPUB/TXT 文件（book_id 不变），可选备份原文件到工具工作目录
6. **后台任务**：右上角查看进度，完成/失败消息通知

## 目录结构

```
webserver/
├── handlers/toolbox.py          (修改) +2 handler +2 路由
└── toolbox/
    ├── toolset.py               (修改) import + register
    ├── chinese_converter_tool.py (新增) Tool 类（BaseTool + 后台转换服务）
    └── chinese_converter/       (新增) 核心包（standalone，可独立测试）
        ├── opencc_engine.py     移植 opencc-python 引擎（Apache 2.0）
        ├── epub_converter.py    EPUB/TXT 无损转换
        ├── a5_phrases.txt       增强词表（解析自 a5566123s csr）
        ├── config/              6 个转换方向配置 json
        └── dictionary/          OpenCC 字典数据
app/
├── src/pages/toolbox/chinese_converter.vue   (新增) Vuetify 2 页面
└── locales/{en,zh,zh-TW}.json                (修改) chineseConverter 块
tests/test_converter_core.py                  (新增) 16 个单元测试
```

## 安装部署（3 处修改 + 1 处新增页面）

> 面向 mybooks 仓库（`webserver/` 与 `app/` 均为其子目录）。将本目录内容合并到 mybooks 项目根目录：

```bash
# 1. 复制新增文件（保持相对路径）
cp -r webserver/  <mybooks>/webserver/
cp -r app/        <mybooks>/app/
cp -r tests/      <mybooks>/tests/
```

### 修改 1：`webserver/toolbox/toolset.py`

`collect_tools()` 中新增两行：

```python
from .chinese_converter_tool import ChineseConverterTool        # import 区
...
ToolSet.register(ChineseConverterTool.info())              # register 区
```

### 修改 2：`webserver/handlers/toolbox.py`

1. import 区新增：`from webserver.toolbox.chinese_converter_tool import ChineseConverterTool`
2. 新增 2 个 handler：`AdminChineseConverterConvert`（POST）、`AdminChineseConverterProgress`（GET）
3. `routes()` 新增 2 条：

```python
(r"/api/toolbox/chinese_converter/convert", AdminChineseConverterConvert),
(r"/api/toolbox/chinese_converter/progress", AdminChineseConverterProgress),
```

> 说明：交付物中的 `toolbox.py` / `toolset.py` / `locales/*.json` 已包含全部修改，
> 如直接覆盖需确认与你的 mybooks 版本一致（基于 mybooks-develop 2026-08 快照）。

### 修改 3：`app/locales/{en,zh,zh-TW}.json`

新增顶层 `chineseConverter` 块（见 `app/locales/` 交付文件）。

### 页面路由

Nuxt 2 自动路由：`/toolbox/chinese_converter`（由 `app/src/pages/toolbox/chinese_converter.vue` 自动生成，无需配置路由）。

## 接口

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/toolbox/chinese_converter/convert` | 启动转换（book_id / direction / mode / use_a5 / convert_title / backup） |
| GET  | `/api/toolbox/chinese_converter/progress` | 轮询进度（status / progress / stage / direction / new_book_id） |

所有响应 `err === "ok"` 表示成功（遵循 MyBooks 约定）。

## 运行测试

```bash
python tests/test_converter_core.py
# 16/16 tests passed
```

也可命令行试用转换效果：

```bash
python -m webserver.toolbox.chinese_converter_tool t2s some_book.epub --a5
python -m webserver.toolbox.chinese_converter_tool s2t some_book.txt
```

## 上游与许可

- **opencc-python 引擎**：https://github.com/yichen0831/opencc-python （Apache License 2.0），
  经 Hopkins1/TradSimpChinese（calibre 插件）修订移植
- **OpenCC 字典与配置数据**：https://github.com/BYVoid/OpenCC （Apache License 2.0）
- **增强词表**：https://github.com/a5566123s/Calibre-BIG5toGBK 的 csr 查找替换表
  （繁转简个人修正版，原帖 hi-pda 论坛），仅供个人使用，使用前请自行评估
- 详见 `LICENSE.md`

## 已知限制

- 台湾地区词汇（如 `軟體→软件`）不在 opencc-python 词典的转换链上（数据版本限制），
  部分已由增强词表覆盖；如需完整词汇转换请自行补充词条
- s2t 多音字按 OpenCC 词典默认候选处理（与原版 opencc-python 行为一致）
