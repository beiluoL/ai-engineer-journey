# Day24：AI Agent 工程化进阶

# Memory【记忆】、Planning【规划】、Reflection【反思】、Self-Improvement【自我改进】

前面 Day22～Day23：

你已经掌握：

```text
单Agent

↓

Multi-Agent

↓

Workflow

↓

MCP

↓

AI数字员工
```

但是企业真正落地 Agent，会遇到一个问题：

> 为什么很多 Agent Demo 看起来很聪明，真正上线却经常失败？

原因：

缺少：

- 记忆
    
- 规划
    
- 纠错
    
- 经验积累
    

今天进入：

# Advanced Agent Engineering【高级智能体工程】

---

# 一、普通 Agent 的问题

简单 Agent：

```text

用户

↓

LLM

↓

Tool

↓

回答
```

问题：

---

## 问题1：没有记忆

昨天：

用户说：

> 我的岗位是 Java 高级工程师。

今天：

AI：

不知道。

---

## 问题2：复杂任务容易乱

用户：

> 帮我开发一个AI知识库。

Agent：

可能：

```text
写代码

↓

忘记数据库

↓

忘记测试

↓

忘记部署
```

---

## 问题3：错误不会自己发现

生成：

错误代码。

直接返回。

---

企业 Agent：

需要：

```text

Memory

+

Planning

+

Reflection

+

Learning
```

---

# 二、Agent完整认知架构

高级 Agent：

```text

                 User


                  |

                  ↓


              Agent Core


                  |

      +-----------+-----------+

      |           |           |


  Memory     Planning    Reflection


      |           |           |


      ↓           ↓           ↓


  History      Task Plan    Critic


                  |

                  ↓


              Tool Calling


                  |

                  ↓


              Result

```

---

# 三、Memory【记忆系统】

## 什么是 Memory？

让 Agent：

记住过去。

类似：

人的：

长期记忆。

---

# 四、Memory分类

企业通常分4类。

---

# 1. Conversation Memory【对话记忆】

保存：

当前聊天。

例如：

用户：

> 我是Java开发。

后续：

AI知道。

---

实现：

Redis。

结构：

```json
{
conversationId:"10001",

messages:[

"user:我是Java开发",

"assistant:你好"

]

}
```

---

# 2. User Memory【用户记忆】

长期保存用户信息。

例如：

你的 AI Interview Agent：

记录：

```json
{
userId:"001",

skills:[

"Java",

"Spring",

"RAG"

],

weakness:[

"AQS",

"Agent"

]

}
```

---

数据库：

MySQL。

---

# 3. Knowledge Memory【知识记忆】

企业知识。

例如：

```text

产品文档

技术文档

规范
```

存：

Vector DB。

---

# 4. Episodic Memory【经验记忆】

Agent自己的历史经验。

例如：

之前：

任务失败。

记录：

```json
{
task:

"生成报告",

failure:

"数据缺失",

solution:

"先检查数据库"

}
```

---

# 五、Memory架构

企业：

```text

             Agent


               |

        +------+------+

        |             |


 Short Memory   Long Memory


        |             |


 Redis        MySQL/VectorDB

```

---

# 六、你的 Interview Agent Memory设计

升级前：

```text
用户

↓

问题

↓

回答

↓

评分
```

升级：

```text

用户

↓

Agent


↓

读取用户画像


↓

生成针对性问题


↓

评分


↓

更新能力模型

```

---

例如：

第一次：

用户：

AQS：

60分。

保存。

下一次：

AI：

> 上次AQS理解不足，今天继续训练。

---

# 七、Planning【规划能力】

## 为什么需要规划？

复杂任务：

不能一步完成。

例如：

用户：

> 帮我做一个AI知识库系统。

需要：

```text

1. 需求分析

2. 架构设计

3. 数据库

4. 后端

5. 前端

6. 部署
```

---

# 八、Planning模式

## 1. Plan-and-Execute

最经典。

流程：

```text

目标


↓

Planner


↓

生成计划


↓

Executor执行


↓

结果

```

---

例如：

输出：

```json
{
steps:[

{
id:1,

task:"设计数据库"
},

{
id:2,

task:"创建接口"
}

]
}
```

---

# 九、ReAct模式

现在 Agent 常用。

ReAct：

## Reasoning + Acting

中文：

推理 + 行动。

流程：

```text

Thought

思考


↓

Action

行动


↓

Observation

观察结果


↓

Thought

继续思考
```

---

例子：

用户：

查询订单。

Agent：

Thought：

需要订单信息。

Action：

调用：

queryOrder。

Observation：

返回订单。

Thought：

生成回答。

---

# 十、Reflection【反思机制】

人：

犯错后总结。

Agent：

也需要。

---

普通：

```text

生成答案

↓

结束
```

Reflection：

```text

生成答案

↓

Critic检查

↓

发现问题

↓

重新生成
```

---

# 十一、Reflection架构

```text

             Generator Agent


                    |

                    ↓


                Draft Answer


                    |

                    ↓


              Critic Agent


                    |

          +---------+---------+

          |                   |


        Pass               Fail


          |                   |


       Return          Improve

```

---

# 十二、Self-Correction【自我纠错】

例如：

代码生成。

第一次：

```java
代码错误
```

Critic：

发现：

空指针。

修改。

第二次：

正确。

---

流程：

```text

生成

↓

测试

↓

发现错误

↓

修复

↓

重新测试
```

---

# 十三、企业 Agent Evaluation

不能：

感觉聪明。

需要指标。

---

## Task Success Rate

任务成功率。

例如：

100任务：

成功85。

85%。

---

## Tool Success Rate

工具调用成功率。

---

## Cost

成本。

---

## Latency

延迟。

---

# 十四、Self-Improvement【自我改进】

注意：

不是模型自动训练。

更多是：

经验优化。

---

例如：

Agent发现：

经常搜索失败。

记录：

```text

失败原因：

关键词太短


优化：

增加Query Rewrite
```

---

形成：

Agent Memory。

---

# 十五、Agent长期运行架构

企业数字员工：

不是一次请求。

而是：

7×24小时运行。

---

架构：

```text

             Scheduler


                 |

                 ↓


              Agent


                 |

       +---------+---------+

       |                   |


     Memory            Workflow


       |

       ↓


    Experience
```

---

例如：

每天：

9点：

销售Agent：

自动生成日报。

---

# 十六、你的 BlogAgent升级

你现在：

浏览器截图

↓

文章生成

↓

AI审核

升级：

## Content Agent System

```text

Content Supervisor


        |

+-------+--------+--------+

|       |        |        |


Research Writer Image Reviewer


Agent    Agent   Agent    Agent


        |

        ↓


Memory

```

---

它可以：

记住：

- 你的写作风格
    
- 常用结构
    
- 喜欢的图片风格
    
- 历史文章反馈
    

---

# 十七、Spring Boot实现架构

新增模块：

```text

agent-platform


├── agent-core


├── memory


├── planning


├── reflection


├── workflow


├── tool


├── evaluation


└── mcp
```

---

# 十八、面试回答

## Q1：

> Agent为什么需要Memory？

回答：

> Memory用于保存用户上下文、历史任务和知识经验，使Agent能够进行连续交互和个性化服务。短期Memory通常保存当前会话，长期Memory可以结合数据库和向量数据库保存用户画像和历史经验。

---

## Q2：

> Agent如何提高任务成功率？

回答：

> 可以通过Planning拆解复杂任务，通过Workflow控制执行过程，通过Reflection机制让Agent对结果进行检查和修正，同时结合Evaluation指标持续优化。

---

## Q3：

> Agent和普通LLM有什么区别？

回答：

> LLM主要负责语言理解和生成，而Agent增加了目标驱动、规划、工具调用、记忆和反馈闭环能力，可以自主完成复杂任务。

---

# 十九、Day24能力地图

现在你的 Agent 理解：

```text

LLM


 ↓


Tool Calling


 ↓


Agent


 ↓


Memory


 ↓


Planning


 ↓


Reflection


 ↓


Self Improvement


 ↓


Autonomous Agent
```

---

# 二十、下一节 Day25

建议进入：

# 《Day25：企业级 AI Agent 开发实战：LangGraph / LangChain4j 构建可控 Agent》

重点：

从理论进入代码：

实现：

```text
Spring Boot

+

LangChain4j

+

Agent State

+

Workflow

+

Memory

+

Tool

+

MCP
```

完成一个真正企业级 Agent。

目标：

> 不只是会调用 Agent，而是能设计和开发 Agent 平台。