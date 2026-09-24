# Day22：打造企业级 AI Agent 平台

# Multi-Agent【多智能体】、Workflow【工作流】、MCP【模型上下文协议】

前面 Day1～Day21：

你已经完成：

```text
Java工程

↓

LLM

↓

RAG

↓

Agent

↓

Tool Calling

↓

模型部署

↓

企业AI平台

↓

MLOps
```

今天进入当前企业 AI 应用最热门方向：

> **从单 Agent 升级到 Multi-Agent 系统。**

---

# 一、为什么需要 Multi-Agent？

先看普通 Agent。

## 单 Agent

架构：

```text
用户

↓

Agent

↓

LLM

↓

Tool

↓

结果
```

例如：

用户：

> 帮我分析这份Java项目代码。

Agent：

调用：

```text
代码分析Tool
```

返回。

---

问题：

企业任务越来越复杂。

例如：

用户：

> 帮我分析公司今年销售情况，生成报告，并发送给老板。

这个任务包含：

1. 获取数据
    
2. 数据分析
    
3. 生成报告
    
4. 制作PPT
    
5. 发送邮件
    

一个Agent：

容易混乱。

---

所以：

拆分：

```text
任务

↓

多个专业Agent

↓

协作完成
```

---

# 二、Multi-Agent是什么？

Multi-Agent：

**Multiple Agents【多个智能体】**

多个具有不同职责的AI Agent。

类似公司团队：

```text
公司

|

+------------+------------+

|            |            |


产品经理     开发工程师    测试工程师

```

AI系统：

```text
AI团队


Planner Agent

规划任务


        ↓


Research Agent

搜索资料


        ↓


Writer Agent

生成内容


        ↓


Reviewer Agent

审核质量
```

---

# 三、企业级 Agent 架构

完整架构：

```text
                     用户


                       |

                       ↓


                Supervisor Agent


                       |

          +------------+------------+

          |            |            |


          ↓            ↓            ↓


     Research       Writer       Reviewer


       Agent        Agent          Agent


          |            |            |


          ↓            ↓            ↓


       Tools        Tools        Tools

```

---

# 四、核心角色设计

企业常见：

---

# 1. Supervisor Agent【主管智能体】

职责：

任务分配。

类似：

项目经理。

例如：

用户：

> 写一篇技术博客

Supervisor：

拆：

```text
1. 搜索资料

2. 生成大纲

3. 写文章

4. 审核

5. 发布
```

---

# 2. Planner Agent【规划智能体】

负责：

制定计划。

输入：

目标。

输出：

步骤。

例如：

```json
{
tasks:[
"查询资料",

"分析内容",

"生成文章"
]
}
```

---

# 3. Research Agent【研究智能体】

负责：

信息收集。

工具：

- 搜索
    
- RAG
    
- 数据库
    

---

# 4. Writer Agent【写作智能体】

负责：

生成内容。

例如：

- 博客
    
- 报告
    
- 邮件
    

---

# 5. Reviewer Agent【审核智能体】

负责：

质量检查。

检查：

- 正确性
    
- 格式
    
- 安全
    

---

# 五、Multi-Agent执行流程

例如：

自动生成技术博客。

用户：

> 写一篇RAG教程

流程：

```text
用户

↓

Supervisor Agent


↓

Planner Agent


↓

拆任务


↓

Research Agent

↓

RAG查询资料


↓

Writer Agent

↓

生成文章


↓

Reviewer Agent

↓

质量审核


↓

返回用户
```

---

# 六、Multi-Agent和Workflow区别

这是面试高频。

---

## Workflow【工作流】

固定流程。

例如：

```text
上传文件

↓

解析

↓

切Chunk

↓

Embedding

↓

入库
```

流程固定。

---

## Agent

动态决策。

例如：

```text
用户需求

↓

AI判断下一步做什么
```

---

区别：

||Workflow|Agent|
|---|---|---|
|流程|固定|动态|
|控制|代码|模型|
|适合|业务流程|复杂任务|

---

# 七、企业为什么需要 Workflow？

很多场景：

不需要Agent。

例如：

合同处理。

流程：

```text
上传合同

↓

OCR

↓

抽取字段

↓

风险检测

↓

生成报告
```

固定。

使用：

Workflow。

---

# 八、Agent + Workflow结合

企业最佳实践：

不是：

全部Agent。

而是：

```text
        用户


          |

          ↓


    Supervisor Agent


          |

          ↓


      Workflow


          |

 +--------+--------+

 |                 |


RAG流程          审批流程

```

---

# 九、MCP是什么？

重点来了。

MCP：

## Model Context Protocol

中文：

> 模型上下文协议

由 Anthropic 推出。

目标：

统一：

AI模型访问外部工具的方式。

---

以前：

每家公司：

自己写Tool。

例如：

OpenAI：

```text
function calling
```

LangChain：

```text
Tool
```

各种方式不同。

---

MCP：

统一协议。

---

# 十、MCP架构

传统：

```text
LLM

↓

Tool

↓

数据库
```

---

MCP：

```text
              LLM


               |

               ↓


          MCP Client


               |

               ↓


          MCP Server


        +------+------+


        |             |


     Database      API

```

---

# 十一、MCP三个核心概念

## 1. MCP Client

客户端。

例如：

Claude Desktop。

负责：

连接MCP Server。

---

## 2. MCP Server

工具提供方。

例如：

数据库MCP。

提供：

```text
查询用户

查询订单

搜索文档
```

---

## 3. Resource

资源。

例如：

文件。

---

## 4. Tool

工具。

例如：

```json
{
name:
"queryOrder",

description:
"查询订单状态"
}
```

---

# 十二、为什么企业需要 MCP？

因为：

工具越来越多。

例如：

公司：

```text
CRM

ERP

数据库

Git

Jira

邮件

文件系统
```

如果每个Agent：

自己开发连接。

维护困难。

MCP：

统一。

---

# 十三、你的 Java AI 项目升级

之前：

单Agent：

```text
Interview Agent

↓

Tool

↓

RAG
```

升级：

Multi-Agent：

```text
                    用户


                      |

                      ↓


              Interview Supervisor


                      |

       +--------------+--------------+

       |              |              |


       ↓              ↓              ↓


Question        Evaluation      Learning


Agent            Agent          Agent


       |              |              |


       ↓              ↓              ↓


    RAG Tool     Score Tool     Planner Tool

```

---

# 十四、Spring Boot实现思路

模块：

```text
agent-platform


├── supervisor

├── planner

├── researcher

├── writer

├── reviewer

├── tool

├── workflow

└── mcp
```

---

# 十五、Agent状态管理

复杂Agent需要：

Memory。

例如：

```json
{
taskId:"001",

status:"researching",

steps:[

"search",

"write",

"review"

]

}
```

---

存储：

Redis。

---

# 十六、企业级 Agent 必须考虑

## 1. 最大步骤限制

防止无限循环。

```yaml
max_steps:10
```

---

## 2. Tool权限

Agent不能：

随便调用。

---

## 3. 人工审批 Human-in-the-loop

重要操作：

需要人确认。

例如：

发送邮件。

流程：

```text
Agent

↓

生成邮件

↓

人工确认

↓

发送
```

---

# 十七、真实企业案例

## AI客服 Agent

Multi-Agent：

```text
用户

↓

客服Supervisor


↓

+-----------+------------+

|           |            |


订单Agent  售后Agent  投诉Agent

```

---

## AI研发助手

```text
需求Agent

↓

代码Agent

↓

测试Agent

↓

Review Agent
```

---

## AI内容生产

```text
Topic Agent

↓

Research Agent

↓

Writing Agent

↓

Image Agent

↓

Video Agent
```

---

# 十八、面试回答

## Q：

> Agent和Multi-Agent有什么区别？

回答：

> 单Agent通常由一个模型负责理解任务和调用工具，适合简单任务。Multi-Agent会将复杂任务拆分成多个专业Agent，例如规划、检索、生成、审核，通过协作完成复杂流程，提高系统可维护性和任务成功率。

---

## Q：

> MCP解决什么问题？

回答：

> MCP是一种标准化模型连接外部工具和数据源的协议，通过统一的Client和Server架构，让模型可以更方便、安全地访问数据库、文件系统和业务API，减少每个应用重复开发工具接口。

---

# 十九、你的 AI 能力升级

现在：

```text
AI Application Engineer


        |

        +----------------+

        |                |


Single Agent        Multi-Agent


        |                |


Tool Calling       MCP


RAG                Workflow

```

---

# 下一节 Day23

建议进入：

# 《Day23：企业 AI 自动化平台实战：Agent + Workflow + MCP 打造数字员工》

目标：

做一个真正企业场景：

> AI数字员工

例如：

- 自动读取邮件
    
- 分析附件
    
- 查询数据库
    
- 生成报告
    
- 自动发送结果
    

技术：

```text
Spring Boot

+

LangChain4j

+

Agent

+

Workflow

+

MCP

+

RAG

+

vLLM
```

这一步会非常接近 2026 年企业 AI Agent 岗位实际工作。