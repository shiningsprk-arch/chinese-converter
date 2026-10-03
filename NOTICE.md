# NOTICE / 来源与许可说明

本工具（MyBooks「繁简转换」Toolbox 插件）以 **AGPL-3.0** 许可分发（全文见 [LICENSE.md](LICENSE.md)），
代码作者：黏菌（shiningsprk-arch）。2026-10-03 之前的版本以 BSD 2-Clause 分发（见 git 历史）。

## 上游组件（保留各自许可）

### 1. opencc-python 引擎 — Apache License 2.0

`webserver/toolbox/chinese_converter/opencc_engine.py` 移植自：

- https://github.com/yichen0831/opencc-python （作者 Yichen Huang, 2016）
- 经 Hopkins1/TradSimpChinese（calibre 编辑器插件，作者 Hopkins）
  修订（StringTree 最长匹配、多组字典链、词典缓存），2022
- 本工具在此基础上移除了 calibre 资源加载抽象，改为直接读取包内
  `config/` 与 `dictionary/` 目录，并新增 `extra_dicts` 增强词表注入机制

Apache License 2.0 全文：https://www.apache.org/licenses/LICENSE-2.0

### 2. OpenCC 字典与配置数据 — Apache License 2.0

`webserver/toolbox/chinese_converter/config/*.json` 与
`webserver/toolbox/chinese_converter/dictionary/*.txt` 数据来自：

- https://github.com/BYVoid/OpenCC （作者 Carbo Kuo 及贡献者）
- 数据文件头部均保留 OpenCC 的 License/Source 注释，未做改动

Apache License 2.0 全文：https://www.apache.org/licenses/LICENSE-2.0

### 3. 增强词表 — 个人修正版（来源注明，使用前自行评估）

`webserver/toolbox/chinese_converter/a5_phrases.txt` 解析自：

- https://github.com/a5566123s/Calibre-BIG5toGBK
- 文件：`Calibre繁转简修正版by a5.csr`（Calibre 查找&替换规则，繁体→简体）
- 原帖：hi-pda 论坛「繁体转简体批处理-增强扩展词组个人修正版」（原帖已不可见）
- 该词表为作者个人修正的查找替换词条集合，非官方标准数据；
  仅供学习与个人使用，使用时请自行评估其质量与适用范围

## 字体与图片

本工具未包含任何字体或图片资源。

---

**总结**：本工具中 `opencc_engine.py`（含修改）与字典数据为 Apache 2.0 组件，保留各自许可；
工具整体组织与集成代码（Tool 类、EPUB/TXT 转换、Vue 页面等）以 AGPL-3.0 分发。
若您希望以 Apache 2.0 单独使用转换引擎与数据，可直接提取
`webserver/toolbox/chinese_converter/` 包（该包本身不依赖 MyBooks）。
