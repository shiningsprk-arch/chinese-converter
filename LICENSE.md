# 版权与许可声明

## 本工具代码

本工具（MyBooks「繁简转换」Toolbox 插件）以 **BSD 2-Clause** 许可分发
（与上游 MyBooks 项目许可证一致），代码作者：黏菌。

BSD 2-Clause License：

> Copyright (c) 2026, 黏菌
>
> Redistribution and use in source and binary forms, with or without
> modification, are permitted provided that the following conditions are met:
>
> 1. Redistributions of source code must retain the above copyright notice,
>    this list of conditions and the following disclaimer.
> 2. Redistributions in binary form must reproduce the above copyright notice,
>    this list of conditions and the following disclaimer in the documentation
>    and/or other materials provided with the distribution.
>
> THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
> AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
> IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
> ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE
> LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
> CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
> SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
> INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
> CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
> ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
> POSSIBILITY OF SUCH DAMAGE.

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

**总结**：本工具中 `opencc_engine.py`（含修改）与字典数据为 Apache 2.0 组件；
工具整体组织与集成代码（Tool 类、EPUB/TXT 转换、Vue 页面等）为 BSD 2-Clause。
若您希望以 Apache 2.0 单独使用转换引擎与数据，可直接提取
`webserver/toolbox/chinese_converter/` 包（该包本身不依赖 MyBooks）。
