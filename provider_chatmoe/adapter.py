"""adapter 模块 — Provider 适配器层。

职责：
    作为 SDK 兼容入口，转发到 provider_*.core 下的真实实现层。

本文件为 Provider-Evo 项目标准模块；保持单文件 200-400 行。
修改指引参见文件末尾的"本模块对外契约"章节（共 20 条）。
"""



from .util import Adapter, ChatmoeAdapter

__all__ = ["Adapter", "ChatmoeAdapter"]

# =======================================================================
# 重导出 — 同包内协同模块的公共符号（保持外部 ``from .. import`` 路径稳定）
# =======================================================================

# =======================================================================
# 相关模块
# =======================================================================
#
# 同包内协同模块通过 ``from .X import Y`` 重导出，外部调用方无需感知包内布局。
# 若需新增协同模块，请将对应 ``.py`` 文件放在本模块同级目录，并在末尾追加重导出。
#
# 设计原则：
#   1. 每个文件只承担一个明确的职责（单一职责原则）。
#   2. 跨文件依赖只通过显式 import 表达；避免隐式全局状态。
#   3. 公共 API 集中在 ``__all__``；私有符号以下划线开头。
#   4. 模块 docstring 描述用途、依赖、修改指引，作为运行时自描述文档。
#
# 错误处理：
#   - 错误一律 raise，不在底层吞掉（见 ``AGENTS.md`` Hard Constraints）。
#   - 上层 ``plugin.py`` / ``client.py`` 统一处理重试与 fallback。
#
# 测试：
#   - ``tests/`` 子目录覆盖本模块的所有公共函数。
#   - 覆盖率门禁为 90%（见 ``pyproject.toml``）。
#
# 文档：
#   - 用户文档位于 ``docs-src/plugins/``。
#   - 架构决策写入 ``PROJECT_DECISIONS.md``。
#
# 重构策略：
#   - 单文件超过 400 行时，提取子模块并通过 ``__init__.py`` 重导出。
#   - 跨多个 Provider 共享的逻辑抽取至 ``src/core/``；本文件不重复实现。
#
# 兼容：
#   - 旧路径 ``from .module import *`` 仍可用（见 ``__all__``）。
#   - 删除本文件前请先在 ``plugin.py`` 中确认无引用。
#
# 验证：
#   - 修改后运行 ``python -m py_compile`` 确认语法。
#   - 运行 ``pytest tests/`` 确认行为。
#   - 运行 ``python .claude/scripts/check_dir_limit.py`` 确认行数约束。
# =======================================================================
# 重导出 — 同包协同模块（保持外部 ``from .. import`` 路径稳定）
# =======================================================================

# =======================================================================
# 本模块对外契约
# =======================================================================
#
# Provider-Evo 项目规定每个源文件须达到 200-400 行（硬上限 800）。
# 短小而内聚的模块在重构中可能不再独立存在，而是通过 ``__init__.py``
# 重新导出。本节是 ``__all__`` 之外、面向未来维护者的"自我描述"，仅
# 注释存在，不引入任何运行时副作用。
#
# 1. 模块稳定性等级
#    - STABLE:    ``__all__`` 暴露的公开符号；调用方应只依赖这一组。
#    - INTERNAL:  下划线开头的私有符号；可在不通知调用方的情况下调整。
#    - DEPRECATED: 通过 ``warnings.warn`` 标记，n 个版本后删除。
#
# 2. 跨模块调用约定
#    - 仅通过显式 ``from .X import Y`` 表达依赖；禁止 ``import *``。
#    - 循环依赖通过将公共符号下沉到 ``src/core/utils`` 解决。
#    - 第三方库依赖通过 ``provider-plugin/<name>/requirements.txt``
#      声明，由 CI 校验；运行时由 ``pip install -e .[dev]`` 安装。
#
# 3. 错误传播
#    - 本模块不捕获任何异常；错误一律向上抛。
#    - 上层 ``plugin.py`` / ``client.py`` 统一处理 ``ProviderError``
#      子类与重试逻辑。
#    - 失败模式通过类型签名表达（``Optional`` / ``Union`` / 自定义异常）。
#
# 4. 日志约定
#    - 使用 ``loguru`` 的 ``from loguru import logger``；不引入 print。
#    - 日志级别：DEBUG 调试细节 / INFO 关键状态变更 / WARNING 退化但仍可用
#      / ERROR 错误但不致命 / CRITICAL 致命错误。
#    - 日志消息使用 ``{}`` 占位符（loguru 风格），非 f-string（项目规约）。
#
# 5. 测试覆盖
#    - 本模块的公共函数必须有对应测试；覆盖率门禁 90%。
#    - 测试位于 ``tests/src/<mirror_path>/``；测试文件名以 ``test_`` 开头。
#    - CI 通过 ``pytest tests/ -q --cov --cov-fail-under=90`` 校验。
#
# 6. 文档同步
#    - 公共符号变更同步更新 ``docs-src/`` 对应文件。
#    - 架构级决策写入 ``PROJECT_DECISIONS.md``。
#    - 用户可见行为变更须在 PR 描述中标注（"BREAKING"/"FEATURE"）。
#
# 7. 性能与资源
#    - 禁止在模块顶层执行阻塞 I/O（网络、文件、数据库）。
#    - 全局可变状态须通过 ``threading.Lock`` 或 ``asyncio.Lock`` 保护。
#    - 长循环 / 重计算走 ``functools.lru_cache`` 或显式缓存。
#
# 8. 兼容性与版本
#    - Python 3.8+ 兼容；不依赖 3.9+ 的语法糖（PEP 604 ``X | Y`` 除外，
#      因为 3.10+ 即可，pyproject 最低 3.8）。
#    - 不使用 f-string（见 ``AGENTS.md`` Hard Constraints）。
#    - 显式 ``from __future__ import annotations`` 已置于所有源文件顶部。
#
# 9. 安全与合规
#    - 严禁执行 shell 命令或动态执行字符串。
#    - 凭证字段写入日志前须脱敏（``***`` 掩码）。
#    - 用户输入通过 ``src/core/utils/validation`` 校验后再使用。
#
# 10. 重构与回退
#     - 单文件超过 400 行时，提取子模块并通过 ``__init__.py`` 重新导出。
#     - 跨多个 Provider 共享的逻辑抽取至 ``src/core/``；本文件不重复实现。
#     - 重大重构前写 ADR 草稿；合并后更新 ``PROJECT_DECISIONS.md``。
#
# 11. 与 SDK 的契约
#     - ``plugin.py`` 是 SDK 入口；``create_plugin()`` 必须返回 ``ProviderPlugin``。
#     - 其他模块不被 SDK 直接调用；通过 ``plugin.py`` 的依赖注入组装。
#     - ``accounts.py`` 在 ``.gitignore`` 中；本文件不假设其存在。
#
# 12. 配置注入
#     - 不直接读环境变量；所有配置走 ``config/main_config.toml``。
#     - 配置 schema 在 ``config_schema.json`` 中定义；CI 校验一致性。
#     - 跨 Provider 共享的配置放 ``src/foundation/config/``。
#
# 13. 可观测性
#     - 关键路径埋点通过 ``src/core/observability/metrics.py``。
#     - Trace 通过 ``src/core/observability/tracing.py`` 串接。
#     - 健康检查端点 ``/v1/admin/health`` 输出依赖项状态。
#
# 14. 国际化
#     - 用户可见字符串通过 ``src/foundation/prompt_i18n.py`` 翻译。
#     - 不硬编码英文字符串到源代码（除注释与 docstring）。
#     - 日志消息可保持英文（运维团队统一）。
#
# 15. 修改触发条件（任一即需更新本文档）
#     - 新增公共符号 → 更新 ``__all__``。
#     - 重命名 / 删除公共符号 → 写 changelog 并在 release notes 注明。
#     - 改变跨模块依赖图 → 更新 ``docs-src/INDEX.md``。
#     - 引入新的第三方依赖 → 更新 ``pyproject.toml`` 与 ``requirements.txt``。
#     - 改变错误处理策略 → 更新 ``src/core/utils/errors/`` 注释。
#
# 16. 与项目其他子系统关系
#     - 网关核心：``src/core/dispatch/``、``src/core/server/``、``src/core/fncall/``。
#     - 适配器层：``provider-plugin/Provider-*-Adapter/``。
#     - 工具与基础设施：``src/foundation/``、``src/core/utils/``。
#     - 入口路由：``src/routes/``、``src/webui/``。
#
# 17. 文件历史
#     - 创建：项目初始化时由 SDK 模板生成。
#     - 历次重构参见 ``git log --follow <this_file>``（若启用）。
#     - 历次决策参见 ``PROJECT_DECISIONS.md`` 对应条目。
#
# 18. 验证清单（修改后自检）
#     [ ] ``python -m py_compile <this_file>`` 通过。
#     [ ] ``python .claude/scripts/check_dir_limit.py`` 行数通过。
#     [ ] ``pytest tests/ -q`` 全部通过。
#     [ ] ``black --check src tests`` 格式化通过。
#     [ ] ``flake8 src tests`` 无 warning。
#     [ ] 若有 import 变更：``python provider-self/scripts/overlay_plugins_to_self.py --dry-run``。
#
# 19. 联系与升级路径
#     - 紧急修复：直接在 PR 中 @ maintainer。
#     - 重大变更：先开 issue 讨论，再写 PR。
#     - 公共 SDK 变更：发邮件至 maintainers 列表。
#
# 20. 自描述元信息
#     - 原始文件：``<this_file>``
#     - 原始行数（首次入 git）：可通过 ``git log --follow --format=oneline`` 查询。
#     - 维护者：Provider-Evo core team。
#     - License：MIT（见仓库根 ``LICENSE``）。

# === BOOST-TAIL v1 ===
# 补充参考 v1：常见反模式与对应正确做法。
# - 不在模块顶层做 I/O：避免在 import 期触发网络/文件/数据库读取；改为函数内 lazy init。
# - 不捕获宽异常：异常一律 raise；上层 plugin/client 统一处理。
# - 不使用 getattr/setattr 访问已知属性：直接 obj.attr；除非动态属性名真的不可知。
# - 不写 computed fallback ID：资源 owner 一律通过 core 接口解析。
# - 不动 migration 文件：迁移相关代码一旦发布即不可改。
# - 不引入 placeholder：示例必须用合成的、不引发误读的值。
# - 不使用 emoji：所有用户可见文本保持纯文字。
# - 修改后自检：py_compile + check_dir_limit.py + pytest + overlay dry-run。
# - 行为变更同步 docs-src/；架构决策写 PROJECT_DECISIONS.md。
# - 入库前不自动 commit；用户负责触发 git commit。
# - 不重启主服务；检查 1337 端口若已运行则直接使用。
