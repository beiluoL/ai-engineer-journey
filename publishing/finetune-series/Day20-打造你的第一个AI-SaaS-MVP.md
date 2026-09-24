# Day20：打造你的第一个 AI SaaS MVP

# 从 PRD → 架构 → 数据库 → API → 开发计划

前面 Day1～Day19：

你已经完成：

```text
Java工程能力

↓

LLM基础

↓

RAG

↓

Agent

↓

Tool Calling

↓

模型部署

↓

LoRA微调

↓

MLOps

↓

AI产品设计
```

今天开始进入真正 Builder 阶段：

> **设计一个可以开发、上线、获得用户反馈的 AI SaaS 产品。**

项目：

# AI Interview Coach

## AI 技术面试教练平台

目标：

30天完成 MVP。

---

# 一、产品定位（PRD第一部分）

## 产品名称

暂定：

```
InterviewAI
```

中文：

```
AI技术面试教练
```

---

# 二、产品一句话介绍

> 面向 Java / AI 工程师的智能面试训练平台，通过 AI Agent 模拟真实面试、分析回答质量、生成个性化学习计划。

---

# 三、目标用户

## 用户1：Java开发者

年龄：

2～8年。

痛点：

- 不知道面试重点
    
- 技术会但是不会表达
    
- 缺少高级面试训练
    

---

## 用户2：AI转型开发者

痛点：

- 不知道RAG/Agent怎么学
    
- 不知道企业面试要求
    

---

## 用户3：培训机构

需求：

- 批量训练学生
    
- 自动评分
    

---

# 四、MVP核心功能

不要一开始做复杂。

第一版只做：

# 核心闭环

```text
注册

↓

选择目标岗位

↓

AI生成面试

↓

用户回答

↓

AI评分

↓

生成报告

↓

学习建议

↓

再次训练
```

---

# 五、功能模块设计

## Module 1：用户系统

功能：

- 注册
    
- 登录
    
- 用户资料
    
- 技术方向
    

保存：

```text
Java
Spring
AI
```

---

## Module 2：岗位画像

用户选择：

例如：

```
Java高级工程师
```

系统生成：

能力模型：

```json
{
"Java基础":90,

"JVM":80,

"Spring":70,

"AI":50
}
```

---

## Module 3：AI模拟面试

流程：

用户：

点击：

开始面试

AI：

```
你好，现在开始Java高级工程师面试。

问题1：

ConcurrentHashMap为什么线程安全？
```

---

## Module 4：回答分析

用户回答：

文本/语音。

AI输出：

```json
{
score:85,

correct:true,

weakness:[
"AQS源码不足"
],

suggestion:
"学习CLH队列"
}
```

---

## Module 5：学习计划

根据历史：

生成：

```text
Day1:

复习HashMap


Day2:

学习AQS


Day3:

练习RAG
```

---

# 六、整体系统架构

MVP架构：

```text
                         用户

                          |

                          ↓


                       Vue3


                          |

                          ↓


                  Spring Boot API


                          |

        +-----------------+----------------+

        |                 |                |


        ↓                 ↓                ↓


 Interview          User Service       Report


 Service


        |

        ↓


 LangChain4j Agent


        |

 +------+------+


 |             |


RAG          LLM


 |             |


Milvus       Qwen

```

---

# 七、技术选型

## 前端

选择：

```
Vue3
+
TypeScript
+
Element Plus
```

原因：

快速开发。

---

## 后端

```
Spring Boot 3

Java 17+

MySQL

Redis
```

---

## AI层

```
LangChain4j

Qwen

vLLM

Milvus
```

---

## 部署

开发：

Docker Compose。

生产：

Kubernetes。

---

# 八、数据库设计

核心：

6张表。

---

# 1. 用户表

user

```sql
CREATE TABLE user
(
 id bigint,

 username varchar(50),

 password varchar(255),

 target_job varchar(100),

 created_time datetime
);
```

---

# 2. 面试记录表

interview_session

```sql
CREATE TABLE interview_session
(
 id bigint,

 user_id bigint,

 job varchar(100),

 status varchar(20),

 score int,

 created_time datetime
);
```

---

# 3. 面试问题表

question

```sql
CREATE TABLE question
(
 id bigint,

 session_id bigint,

 content text,

 category varchar(50)
);
```

---

# 4. 用户回答表

answer

```sql
CREATE TABLE answer
(
 id bigint,

 question_id bigint,

 content text,

 score int,

 feedback text
);
```

---

# 5. 知识薄弱点

weak_point

```sql
CREATE TABLE weak_point
(
 id bigint,

 user_id bigint,

 knowledge varchar(100),

 level int
);
```

---

# 6. 学习计划

learning_plan

```sql
CREATE TABLE learning_plan
(
 id bigint,

 user_id bigint,

 content text,

 status varchar(20)
);
```

---

# 九、AI Agent设计

核心：

Interview Agent。

---

## Agent能力

Tools：

---

### Tool1：GenerateQuestion

生成面试题。

输入：

```json
{
job:"Java高级"
}
```

输出：

问题。

---

### Tool2：EvaluateAnswer

分析回答。

输入：

```json
{
question:"",
answer:""
}
```

输出：

评分。

---

### Tool3：SearchKnowledge

RAG。

查询：

- Java源码
    
- AI知识
    

---

### Tool4：GeneratePlan

生成学习计划。

---

完整流程：

```text
用户

↓

Interview Agent

↓

判断任务


       |

 +-----+------+


 |            |


生成问题     评分


 |            |


Question    Evaluation

```

---

# 十、API设计

## 用户

### 注册

```
POST

/api/user/register
```

---

### 登录

```
POST

/api/user/login
```

---

# 面试

## 创建面试

```
POST

/api/interview/start
```

请求：

```json
{
"job":
"Java高级工程师"
}
```

返回：

```json
{
sessionId:10001
}
```

---

## 获取问题

```
GET

/api/interview/{id}/question
```

---

## 提交回答

```
POST

/api/interview/answer
```

请求：

```json
{
questionId:1,

answer:
"ConcurrentHashMap..."
}
```

---

返回：

```json
{
score:85,

feedback:
"缺少扩容分析"
}
```

---

# 十一、AI调用流程

一次回答：

```text
用户提交答案

↓

Spring Boot

↓

Interview Service

↓

LangChain4j

↓

Agent判断


↓

Evaluate Tool


↓

RAG查询


↓

Prompt组装


↓

Qwen


↓

JSON评分


↓

保存MySQL

↓

返回用户
```

---

# 十二、项目目录设计

后端：

```
ai-interview-agent

├── user

├── interview

├── agent

├── rag

├── model

├── evaluation

├── common

└── infrastructure
```

---

AI Prompt：

```
prompts/

├── interviewer.txt

├── evaluator.txt

├── planner.txt
```

---

# 十三、30天开发计划

## Week1：基础系统

完成：

✅ 用户系统

✅ 登录

✅ 面试流程

✅ 基础聊天

---

## Week2：AI能力

完成：

✅ LangChain4j

✅ Agent

✅ Tool Calling

✅ Prompt

---

## Week3：RAG

完成：

✅ 文档上传

✅ Chunk

✅ Embedding

✅ Milvus

✅ 检索

---

## Week4：产品化

完成：

✅ 评分报告

✅ 数据分析

✅ Docker部署

✅ 域名HTTPS

---

# 十四、MVP成本

开发阶段：

最低：

```
0～300元/月
```

方案：

- 本地 Ollama
    
- 免费额度API
    
- 按小时GPU
    

---

上线：

小规模：

```
500～2000元/月
```

包括：

- GPU
    
- 数据库
    
- 服务器
    
- 域名
    

---

# 十五、面试项目包装

简历：

不要：

❌

> 做了一个AI聊天机器人

改：

✅

> 设计并开发一套 AI 技术面试训练 SaaS 平台，通过 Agent 模拟真实面试流程，结合 RAG 私有知识库和大模型能力，实现自动出题、回答评估、能力画像和个性化学习路径推荐。

---

# 十六、下一阶段开发顺序

接下来不要继续学概念。

开始 Coding。

推荐：

# Day21：AI SaaS 项目初始化

内容：

## 后端

- Spring Boot 3 项目创建
    
- Maven模块设计
    
- MySQL设计
    
- Redis配置
    
- LangChain4j接入
    

## 前端

- Vue3初始化
    
- 登录页面
    
- 面试页面
    

## AI

- 第一个 Agent
    
- 第一个 Tool
    
- 第一个 Prompt
    

目标：

> 7天内跑起来一个真实 AI SaaS MVP。

下一节进入：

# Day21：《从0搭建 AI SaaS 工程：Spring Boot + Vue3 + LangChain4j + Docker 项目初始化》