# LEARNING — Project 02 Engineering AI Assistant

> 这份文件只记录**「我是否真的掌握」**，仓库里写了什么请去看 `README.md` / `PROGRESS.md`。
>
> 铁律：**文档就绪 ≠ 已学习，参考答案跑通 ≠ 我会了。**
>
> 生成这份清单的人（AI）**不会替你打任何勾**。下面每一个框起点都是 ⬜，
> 只有你本人做完题、能讲清楚「为什么」之后，**由你**把它填成 ✅。

## 怎么用

三条线同时过才算掌握一章：

1. **自测题** —— 每章 3–5 道问答题，考的是「为什么」，不是「用没用过」。答题要点折在 `<details>` 里，答完再展开对照
2. **动手验证** —— 去 `exercises/` 里真的写代码，跑 `exercises/grade.py`；先自己写，卡住了再看 `answers.py` 里**卡住的那一个函数**
3. **自评** —— 诚实地填自己在哪一档

## 总览表

| # | Milestone | 自测题 | 动手验证 | 我掌握了 |
|---|---|---|---|---|
| 00 | [类与 OOP](milestones/00-classes-and-oop.md) | ⬜ | ⬜ `01-oop` A1–A3 | ⬜ |
| 01 | [async / await](milestones/01-async-await.md) | ⬜ | ⬜ `02-async` A1–A3 | ⬜ |
| 02 | [异步 HTTP 客户端](milestones/02-async-http-client.md) | ⬜ | ⬜ `02-async` B1–B3 | ⬜ |
| 03 | [类型注解](milestones/03-type-hints.md) | ⬜ | ⬜ `01-oop` B1–B3 | ⬜ |
| 04 | [dataclass](milestones/04-dataclass.md) | ⬜ | ⬜ `01-oop` C1–C3 | ⬜ |
| 05 | [配置与环境](milestones/05-config-and-environment.md) | ⬜ | ⬜ `02-async` C1–C3 | ⬜ |
| 06 | [日志](milestones/06-logging.md) | ⬜ | ⬜ `03-ops` A1–A3 | ⬜ |
| 07 | [测试与调试](milestones/07-testing-and-debugging.md) | ⬜ | ⬜ `03-ops` B1–B3 | ⬜ |
| 08 | [打包](milestones/08-packaging.md) | ⬜ | ⬜ `03-ops` C1–C2 | ⬜ |
| 09 | [FastAPI](milestones/09-fastapi.md) | ⬜ | ⬜ `03-ops` D1–D3 | ⬜ |

---

## M00 类与 OOP

**动手验证**：`exercises/01-oop-dataclass-typehints` A1–A3

**自测题**

- ⬜ Q1 `__init__` 和 `__post_init__` 分别在什么时机被调用？如果在一个 `@dataclass(frozen=True)` 的类里手写 `__setattr__` 强行赋值，会发生什么？
- ⬜ Q2 为什么 `Conversation.turns` 要 `return list(self._turns)` 返回副本？直接返回内部 list 会在什么场景下出 bug？**返回元组的算对吗？**
- ⬜ Q3 `@property` 和「直接把属性写成 `public`」相比，多换来了什么？**代价**是什么？
- ⬜ Q4 `c.add` 不括号就能传走，这背后是什么机制？为什么 `Turn.add` 和 `Conversation().add` 的行为不同？
- ⬜ Q5 「组合优先于继承」在本项目里具体体现在哪一处？举一个「用继承会坏掉」的反例。

<details><summary>判分要点</summary>

- Q1：能说出 `__post_init__` 在 `__init__` 末尾被调用（所以能在 dataclass 生成的 `__init__` 之后做校验/派生字段）。能说出 frozen 下 `__setattr__` 会走 `object.__setattr__` 或直接抛 `FrozenInstanceError`，而不是「静默成功」。
- Q2：能举出「调用方 append 后内部状态被改」的具体场景。能指出**元组也不彻底**——元组的引用不可变，但元素本身可变，真正的安全要么副本要么深拷贝。答不出「元组不算彻底解决」的给半档。
- Q3：好处是「读时可以插入逻辑 + 之后加校验不影响调用方」；代价是每处访问都多一次函数调用，且调试时要意识到这是个函数不是字段。
- Q4：绑定方法，`__self__` 属性指向实例。能说出「描述符协议」额外加分。
- Q5：能指着 `service.py` 里「Service 持有 client 而不是继承 client」说清楚：换 LLM 厂商只需换一个实现了同样接口的对象。

</details>

**自评**：⬜ 还没看过 · ⬜ 看过但不会写代码 · ⬜ 会写代码但讲不清为什么 · ⬜ 能讲清并举例

---

## M01 async / await

**动手验证**：`exercises/02-async-http-and-config` A1–A3

**自测题**

- ⬜ Q1 调用 `async def f()` 之后得到的那个对象叫什么？为什么它「既不执行也不报错」？
- ⬜ Q2 为什么「并发真的省时间」这件事必须用**墙钟时间**证明，而不是靠日志顺序？如果替身的 `sleep` 被写成 `time.sleep()` 会怎样？
- ⬜ Q3 `asyncio.gather` 默认遇异常会怎么处理？和 `return_exceptions=True` 的差别适合什么场景？
- ⬜ Q4 「在 async 函数里调用阻塞式 IO」为什么比「在同步函数里调用」危害更大？

<details><summary>判分要点</summary>

- Q1：协程对象（coroutine）。只有被事件循环驱动（await / create_task / gather / run）才执行；不驱动会有 RuntimeWarning 而非异常。
- Q2：`time.sleep` 阻塞整个事件循环线程，所有协程一起卡住 → 并发退化成串行，**比值会接近 1 甚至更差**。能说出「比值为 1 就是并发没生效」给满分。
- Q3：默认第一个异常立刻向上抛，其余任务被取消（但可能已经执行过）；`return_exceptions=True` 会把异常当结果收集。适合「逐条容错汇总」场景。
- Q4：同步代码里阻塞只挡自己这一个线程；async 里阻塞挡的是**整个事件循环**，会把同 loop 上所有任务都拖死。

</details>

**自评**：⬜ 还没看过 · ⬜ 看过但不会写代码 · ⬜ 会写代码但讲不清为什么 · ⬜ 能讲清并举例

---

## M02 异步 HTTP 客户端

**动手验证**：`exercises/02-async-http-and-config` B1–B3

**自测题**

- ⬜ Q1 为什么要把 client 抽象成 `BaseLLMClient`，上层只依赖抽象？如果哪天要接第二个厂商，**哪一层不需要改**？
- ⬜ Q2 `FakeClient(fail_times=2)` 这种「测试替身」的作用是**模拟失败**还是**模拟成功**？它凭什么能让上层代码不需要分叉？
- ⬜ Q3 重试策略里「哪些错误值得重试、哪些绝不能重试」怎么分？为什么 401 不该重试而 429 应该？
- ⬜ Q4 为什么 `aclose()` 必须被显式调用？只靠 GC 会漏掉什么资源？

<details><summary>判分要点</summary>

- Q1：能说出「替换只需要换一个子类，service 层零改动」。答不出「哪一层不需要改」这句话给半档。
- Q2：两者都能模拟，关键在让上层代码路径与真实一致。凭「同样实现 BaseLLMClient 接口」获得可替换性。
- Q3：401/403 是鉴权/权限错误，重试只会重复失败还可能触发封禁；429/5xx/超时是暂时性的，配合退避重试合理。能提到「指数退避 + jitter」加分。
- Q4：连接池里的 TCP 连接不释放会造成连接泄漏（fd 耗尽）。即使 httpx 支持 async context manager，显式关闭在长期服务里仍是必要的。

</details>

**自评**：⬜ 还没看过 · ⬜ 看过但不会写代码 · ⬜ 会写代码但讲不清为什么 · ⬜ 能讲清并举例

---

## M03 类型注解

**动手验证**：`exercises/01-oop-dataclass-typehints` B1–B3

**自测题**

- ⬜ Q1 Python 的类型注解运行时**为什么不报错**？那它到底有什么用（至少说出两个真实用途）？
- ⬜ Q2 `Optional[str]` 和「返回 `str`，没值时返回 `""`」相比，语义上差在哪？
- ⬜ Q3 `TypedDict` / `dict[str, str]` / `Message = dict` 三种写法分别在什么场合合适？本项目里 `memory.py` 选了哪种，为什么？
- ⬜ Q4 `runtime_checkable` 的 `Protocol` 做 `isinstance` 检查时，**检查的是方法名还是签名**？

<details><summary>判分要点</summary>

- Q1：注解存在 `__annotations__`，解释器不做检查。用途：静态检查（mypy/pyright）、IDE 补全、文档、`get_type_hints()` 运行时读取（本项目判卷脚本就用这个）。
- Q2：`""` 是「有一个空字符串值」，`None` 是「没有值」——二者语义不可混。答不出具体误用后果的给半档。
- Q3：答出任两种即可；能指出本项目用 `Message = dict` 是为了快速迭代、代价是失去字段检查，给满分。
- Q4：**只检查方法名存在与否**，不检查签名。这是最容易记错的坑（1.x 里 behavior 有差异，务必自己跑一遍）。

</details>

**自评**：⬜ 还没看过 · ⬜ 看过但不会写代码 · ⬜ 会写代码但讲不清为什么 · ⬜ 能讲清并举例

---

## M04 dataclass

**动手验证**：`exercises/01-oop-dataclass-typehints` C1–C3

**自测题**

- ⬜ Q1 为什么配置对象要 `@dataclass(frozen=True)`？如果不 frozen，什么场景下会踩坑？
- ⬜ Q2 `dataclasses.replace()` 会修改原对象吗？它和「深拷贝再改」的语义差别是什么？
- ⬜ Q3 为什么 `api_key` 要写 `field(repr=False)`？不写会发生什么事故？能用 Python 复述这行代码的意图吗？
- ⬜ Q4 frozen + `eq=True` 的对象可以直接放进 set / dict 吗？为什么 Python 要连带处理 `__hash__`？

<details><summary>判分要点</summary>

- Q1：配置应当「启动读一次之后谁也改不了」；不 frozen 时某个并发任务偷偷改了 timeout/temperature 会造成难复现的 bug。
- Q2：不改原对象，返回新对象。和深拷贝的差异在于它是**显式构造**且只替换指定字段。
- Q3：`repr=False` 让生成的 `__repr__` 不含该字段 —— 因为 repr 会被 logging 逐字打出来，密钥一旦进 `__repr__` 就必然泄进日志文件。
- Q4：可以。因为可变对象 hash 后会变，放进哈希表就再也找不到；Python 让 frozen+eq 的类自动生成 `__hash__`（并让 eq 的类默认 `__hash__ = None`）。

</details>

**自评**：⬜ 还没看过 · ⬜ 看过但不会写代码 · ⬜ 会写代码但讲不清为什么 · ⬜ 能讲清并举例

---

## M05 配置与环境

**动手验证**：`exercises/02-async-http-and-config` C1–C3

**自测题**

- ⬜ Q1 三档优先级「真实环境变量 > .env 文件 > 代码默认值」在 `load_dotenv` 里是靠哪个 API 实现的？写成 `os.environ[k] = v` 会错在哪？
- ⬜ Q2 为什么**不在模块顶层执行 `from_env()`**？它具体会让哪个环节崩掉？
- ⬜ Q3 校验失败该在什么时候抛异常？为什么本项目选「构造 Settings 时就抛」而不是「第一次发请求时才抛」？
- ⬜ Q4 并发场景下 frozen 配置安全的真正理由是什么？换成 mutable 会具体坏在哪？

<details><summary>判分要点</summary>

- Q1：`setdefault`（不覆盖已有的真实环境变量）。直接赋值会让 `.env` **反过来覆盖**真实环境变量，优先级正好颠倒。
- Q2：import 阶段就抛异常 → pytest 收集阶段直接 fail，连测试都跑不起来。
- Q3：早失败（fail fast）。拖到发请求才发现配置错，会浪费重试次数并且把问题推迟到运行期才暴露。
- Q4：不可变对象无需加锁；mutable 的话并发 `replace` 之外还可能有人就地改字段，导致读取到「半新半旧」的配置。

</details>

**自评**：⬜ 还没看过 · ⬜ 看过但不会写代码 · ⬜ 会写代码但讲不清为什么 · ⬜ 能讲清并举例

---

## M06 日志

**动手验证**：`exercises/03-service-and-ops` A1–A3

**自测题**

- ⬜ Q1 为什么必须做脱敏，而且是在**写日志之前**做？「先把完整 headers 打出来、之后再清理日志」为什么不可行？
- ⬜ Q2 `redact_headers` 为什么要**返回新字典**而不是就地修改？
- ⬜ Q3 结构化日志（JSON）相对纯文本的优势在哪？什么场景下纯文本反而更好？
- ⬜ Q4 为什么要在 logger 上挂 `extra` 而不是把字段拼进 message 字符串？

<details><summary>判分要点</summary>

- Q1：日志会落到文件、采集到 ELK、同步给第三方；**一旦写出就很难彻底收回**。密钥进日志 = 事故。
- Q2：调用方可能还要用原 headers 真的去发请求 —— 就地改会把 Authorization 弄成 `***` 发出去。
- Q3：结构化便于检索聚合（按 request_id 聚合）；本地调试时纯文本可读性更好。
- Q4：拼字符串会破坏可查询性且要处理转义；`extra` 的字段可被 Formatter 单独提取成 JSON 键。

</details>

**自评**：⬜ 还没看过 · ⬜ 看过但不会写代码 · ⬜ 会写代码但讲不清为什么 · ⬜ 能讲清并举例

---

## M07 测试与调试

**动手验证**：`exercises/03-service-and-ops` B1–B3

**自测题**

- ⬜ Q1 `raise X from e` 和不写 `from` 的区别？分别会在 `__cause__` / `__context__` 上留下什么？
- ⬜ Q2 为什么**失败路径也要写断言**？只测成功路径的测试套件掩盖了哪类 bug？
- ⬜ Q3 什么叫「测试真的在拦错误」？你怎么证明你的用例不是空转的？
- ⬜ Q4 测试为什么必须能离线跑（用 `FakeClient` 而不是真实模型）？说出至少两条理由。

<details><summary>判分要点</summary>

- Q1：写了 `from` 时 `__cause__` 指向原始异常，traceback 显式标注 direct cause；不写则只保留 `__context__` 且需要 with-block 上下文。
- Q2：错误处理、限流、超时这些路径恰恰是生产事故高发区；只测成功路径会让这些逻辑在重构中悄悄失效。
- Q3：把断言写反（或注入一个假实现）跑一遍，确认测试**确实 fail** —— 在本 exercise 的 B1 里就是这么做的。
- Q4：成本（每次跑都烧 token）、确定性（真实模型输出不稳定导致随机挂）、可离线 CI。

</details>

**自评**：⬜ 还没看过 · ⬜ 看过但不会写代码 · ⬜ 会写代码但讲不清为什么 · ⬜ 能讲清并举例

---

## M08 打包

**动手验证**：`exercises/03-service-and-ops` C1–C2

**自测题**

- ⬜ Q1 `pyproject.toml` 里 `[project]` 与 `[build-system]` 各自负责什么？把依赖写错到 `build-system.requires` 会怎样？
- ⬜ Q2 `pip install -e .` 和普通安装的区别是什么？为什么开发期要用 editable？
- ⬜ Q3 `__all__` 的作用边界在哪？它**不能**阻止什么？
- ⬜ Q4 console script 入口点（如 `ai-assistant = ...:main`）是怎么变成一条命令的？

<details><summary>判分要点</summary>

- Q1：`[project]` 描述元数据与运行时依赖；`[build-system]` 描述构建时依赖。前者进最终 wheel，后者只在打包时用到。
- Q2：editable 不复制源码，直接指向工作目录，改代码即时生效。
- Q3：只影响 `from x import *` 的行为；**不能**阻止 `import x.hidden` 的显式导入。
- Q4：安装器在 bin 目录生成一个 shim，shim 里 import 指定模块并调用指定函数。

</details>

**自评**：⬜ 还没看过 · ⬜ 看过但不会写代码 · ⬜ 会写代码但讲不清为什么 · ⬜ 能讲清并举例

---

## M09 FastAPI

**动手验证**：`exercises/03-service-and-ops` D1–D3

**自测题**

- ⬜ Q1 依赖注入（Depends）解决的核心问题是什么？如果直接在路由里 `Service(...)` 会失去什么？
- ⬜ Q2 `TestClient` 能跑路由而**不开端口**，它内部用的是什么机制？
- ⬜ Q3 为什么底层抛业务异常时，接口层要把它映射成 HTTP 语义（如 429 / 502）？直接返回 500 有什么坏处？
- ⬜ Q4 入参校验放在哪一层最好？为什么把「空字符串」也当成非法输入而不是交给模型处理？

<details><summary>判分要点</summary>

- Q1：解耦「谁来创建依赖」与「谁来使用」；测试时可替换成假实现。直接在路由里 new 会让测试无法注入替身，且每个路由都要重复装配。
- Q2：基于 httpx + ASGI 传输（ASGITransport）在**进程内**直接调用 app，不经过 socket。（这也是判卷脚本的离线哨兵允许它跑通的原因。）
- Q3：让客户端能据此做正确的重试/退避/提示；一律 500 会把「用户传错」和「我方故障」混为一谈，排障成本暴涨。
- Q4：边界校验最外层拦截，省掉一次无意义的模型调用与费用，也让错误可预期。

</details>

**自评**：⬜ 还没看过 · ⬜ 看过但不会写代码 · ⬜ 会写代码但讲不清为什么 · ⬜ 能讲清并举例

---

## 自测完成度自查

> 全部 ⬜ 是起点。诚实填，这里只对你自己负责 —— 自欺欺人等于没学。

| 环节 | 状态 |
|---|---|
| 10 章 milestone 读过 | ⬜ |
| 29 道题亲手敲过（未对照答案独立完成） | ⬜ |
| `exercises/grade.py` 跑看过自己版本的输出 | ⬜ |
| 自测题能不看书答出要点 | ⬜ |
| 能给第二个人讲清楚「为什么这么设计」 | ⬜ |

**只有最后三项都能打 ✅ 时，这个 Project 才算「已学习」。**
