审计事件改成因果时钟之后，并发写入被当成先后关系，回滚顺序算反了：其一，比较只累加各节点计数之和，不同分布的时钟被误判为有先后；其二，先于判定只检查全部分量不大于，漏掉至少一个分量严格更小，相等也被当成先于；其三，并发判定把任一分量更大当成并发，使用或而不是与，先后关系被误判；其四，合并只遍历一侧已有节点，不补齐缺失节点，稀疏时钟合并后丢失分量；其五，合并把缺失节点按一参与而不是零，结果整体偏大；其六，推进本地事件时把其他节点也加一，本节点事件被放大成全局事件；其七，稀疏化直接丢弃折叠值，与保留节点冲突时没有提示；其八，校验不检查负数计数，回退时钟被接受；其九，批量推进复用上一事件的时钟，各事件之间变成串行；其十，比较在相等时返回并发，幂等判断失效。engine/causal/clock.py 是核心，tests/causal/test_clock.py 15个红。要修的是：按上面的顺序把 10 个缺陷逐个修掉。

## 运行方式

在仓库根目录执行：

    python -m pytest tests -q

初始状态必须恰好为：

    15 failed

这 15 个失败必须全部来自 engine/causal/clock.py 中 8 个桩函数抛出的 NotImplementedError，不允许 collection error、import error、syntax error，也不允许 skip、xfail 或修改测试来制造绿色。

## 字段表

| 字段 | 取值 |
| --- | --- |
| 所属领域 | 安全 |
| 子方向 | 漏洞检测与攻防 |
| 任务类型 | Bugfix |
| 语言/框架 | Python 3, pytest |
| 环境可复现等级 | 无外部依赖 |

## 目录

    sec-vector-clock/
      README.md
      conftest.py
      engine/__init__.py
      engine/causal/__init__.py
      engine/causal/clock.py
      tests/causal/test_clock.py

## engine 嵌套布局

实现文件只能放在 engine/causal/clock.py。engine 与 engine/causal 都是正式包，各自通过 __init__.py 声明，因此导入路径必须是 engine.causal.clock，不能把 clock.py 拍平到仓库根目录，也不能把实现塞进测试文件。

tests/causal/test_clock.py 镜像实现侧的因果层级。根目录 conftest.py 只负责把仓库根加入 sys.path，让嵌套包能够被导入；它不包含任何实现或测试替身。

## 核心语义

普通时钟是节点名到非负整数的映射，缺失节点严格按零参与比较与合并。显式零与缺失等价，节点缺席本身不构成因果关系。

稀疏时钟把未保留节点放进保留键 __summary__ 下的映射，例如 a 保留为三、b 为二、c 为一，保留 a 后写作 a 为三，__summary__ 为 b 二与 c 一。汇总值必须是映射而不是单个标量，否则多个节点被压成一个数后无法正确合并，也无法与完整时钟保持相同的比较结果。同一节点同时出现在顶层与 __summary__ 中属于 summary:conflict，校验必须报出。

compare 的返回值只能是小写字符串 before、after、equal、concurrent。before 要求全部分量不大于且至少一个分量严格更小；after 对称；equal 要求全部分量相等；concurrent 要求双方各有一个分量严格更大。先于是严格关系，相等不满足先于；并发判定必须同时检查两个方向。happens_before 与 concurrent 必须分别与上述语义一致，不能用分量和、分量个数或单一方向代替。

compact 必须保留 keep 中列出的每个节点，缺失者补零，并把其余所有节点连同计数折叠进 __summary__，不能丢弃折叠值。merge 先把稀疏表示展开，再对所有节点逐分量取最大值，结果是不含保留键的普通时钟，并保留显式零分量。

validate_clock 返回按字典序排列的问题字符串列表，覆盖负数计数、非整数计数、空节点名、非字符串节点名、非法 summary 与 summary 冲突。布尔值虽然继承自 int，也不能当作合法计数。

clock_batch 的 events 是包含 clock 与 node 的映射列表，policy 是包含布尔键 merge_results 的映射。每个事件必须从自己的 clock 推进，不能复用上一事件的结果；返回 results 按输入顺序保存每个事件的独立结果，merge_results 为真时 merged 是所有结果的合并，否则为空时钟。

## 测试构成

tests/causal/test_clock.py 恰好 15 个测试。前 10 个按题面顺序逐一钉住 10 个缺陷，另外 5 个分别验证：同节点连续两次推进后严格先于、合并的幂等交换结合性质、并发双方互不先于、稀疏合并后的比较与完整时钟一致、两批独立推进与逐个单独推进相同。

## tests 不可修改

tests/causal/test_clock.py 是不可修改的验收标准。不要编辑测试、增加 skip 或 xfail、放宽断言、改测试数据，也不要通过 monkeypatch、动态替换模块或条件导入绕过实现。唯一允许改动以实现为目标的文件是 engine/causal/clock.py。

## 约束

只使用 Python 标准库与 pytest，离线运行，不联网，不引入第三方依赖，不使用随机数。所有函数保持确定性，不修改传入的时钟、事件、policy 或 keep。初始仓库中 8 个函数全部为桩，修复时按题面缺陷顺序逐个实现，并保持 15 个测试全部转绿。