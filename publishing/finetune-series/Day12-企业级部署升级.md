# Day12 企业级部署升级

# Docker Compose + vLLM + Nginx + HTTPS + API鉴权 + 监控

昨天 Day11 我们完成了：

> **单台 GPU 服务器运行 Qwen + vLLM + Spring Boot 调用**

但是那个版本更像：

> “开发环境 Demo”

企业不会直接这样上线。

今天升级目标：

从：

```text
 id="a1lq7g"
Spring Boot

↓

vLLM

↓

Qwen

↓

GPU
```

升级为：

```text
 id="n3bq4j"
                 用户

                  |

                  ↓

              HTTPS


                  |

                  ↓


              Nginx


                  |

        +---------+----------+

        |                    |


        ↓                    ↓


   Spring Boot          vLLM API


        |                    |

        ↓                    ↓


    业务逻辑          Qwen模型


                         |

                         ↓


                      GPU


                         |

                         ↓


              Prometheus监控

                         |

                         ↓

                    Grafana

```

---

# 一、今天完成什么？

今天完成：

|能力|状态|
|---|---|
|Docker Compose部署|✅|
|vLLM容器化|✅|
|Nginx反向代理|✅|
|HTTPS证书|✅|
|API Key鉴权|✅|
|访问日志|✅|
|GPU监控|✅|
|模型服务监控|✅|

---

# 二、为什么企业不用直接运行 vLLM？

昨天：

```bash
vllm serve xxx
```

问题：

### 1. 服务挂了怎么办？

没有自动恢复。

---

### 2. 服务器重启怎么办？

模型不会自动启动。

---

### 3. 如何管理多个服务？

例如：

```text
Spring Boot

Redis

Milvus

vLLM

Nginx
```

手动启动很麻烦。

---

所以使用：

# Docker Compose

---

# 三、生产目录设计

服务器：

创建：

```bash
mkdir -p /opt/ai-platform

cd /opt/ai-platform
```

目录：

```text
 id="7bzqwr"
/opt/ai-platform

├── docker-compose.yml

├── nginx

│   └── nginx.conf


├── models

│   └── qwen2.5-7b


├── prometheus

│   └── prometheus.yml


└── logs
```

---

# 四、Docker Compose是什么？

简单理解：

以前：

启动服务：

```bash
docker run xxx
docker run xxx
docker run xxx
```

现在：

一个文件：

```yaml
docker-compose.yml
```

定义：

```text
有什么服务

用什么镜像

多少资源

怎么连接
```

然后：

一句：

```bash
docker compose up
```

全部启动。

---

# 五、部署 vLLM 容器

创建：

```bash
vim docker-compose.yml
```

第一版：

```yaml
version: "3.8"


services:

  vllm:

    image:
      vllm/vllm-openai:latest


    container_name:
      qwen-vllm


    restart:
      always


    runtime:
      nvidia


    ports:

      - "8000:8000"


    volumes:

      - ./models:/models


    command:

      >
      --model /models/qwen2.5-7b

      --host 0.0.0.0

      --port 8000

      --dtype auto
```

---

解释：

## image

```yaml
vllm/vllm-openai
```

官方 vLLM 镜像。

---

## runtime

```yaml
nvidia
```

允许：

Docker使用GPU。

---

## volumes

```yaml
./models:/models
```

宿主机：

```text
/models
```

映射：

容器：

```text
/models
```

---

# 六、启动 vLLM

执行：

```bash
docker compose up -d
```

查看：

```bash
docker ps
```

应该：

```text
qwen-vllm

Up
```

---

日志：

```bash
docker logs -f qwen-vllm
```

看到：

```text
Model loaded
Application startup complete
```

成功。

---

# 七、增加 Spring Boot 服务

docker-compose：

增加：

```yaml
springboot:

  image:
    java-ai-agent:latest


  container_name:
    java-agent


  ports:

    - "8080:8080"


  depends_on:

    - vllm
```

现在：

两个服务：

```text
 id="k5qzbh"
docker-compose

├── vllm

└── springboot
```

---

# 八、Nginx作为入口

为什么需要？

不要让用户直接访问：

```
服务器IP:8000
```

应该：

```text
https://ai.xxx.com
```

---

安装：

```bash
mkdir nginx
```

创建：

```bash
vim nginx/nginx.conf
```

---

配置：

```nginx
server {


listen 80;


server_name ai.example.com;



location / {


proxy_pass 
http://vllm:8000;



proxy_set_header Host $host;


proxy_set_header X-Real-IP $remote_addr;


}

}
```

---

现在：

链路：

```text
用户

↓

Nginx

↓

vLLM
```

---

# 九、HTTPS

生产：

必须 HTTPS。

推荐：

Let's Encrypt 免费证书。

安装：

```bash
apt install certbot
```

申请：

```bash
certbot --nginx
```

成功：

得到：

```text
https://ai.example.com
```

---

# 十、API鉴权

现在：

任何人：

都可以调用模型。

危险。

需要：

API Key。

例如：

请求：

```http
Authorization:

Bearer sk-java-ai-xxxx
```

---

Nginx：

增加：

```nginx
location /v1 {


if ($http_authorization = "") {

return 401;

}


proxy_pass
http://vllm:8000;

}
```

---

更企业化：

增加：

Spring Boot Gateway。

流程：

```text
用户

↓

API Gateway

↓

验证Token

↓

调用vLLM
```

---

# 十一、限流

为什么？

防止：

一个用户：

无限请求。

例如：

1000个请求：

瞬间打爆GPU。

---

Nginx：

```nginx
limit_req_zone

$binary_remote_addr

zone=ai_limit:10m

rate=5r/s;
```

表示：

一个IP：

每秒最多5次。

---

# 十二、监控系统

企业必须知道：

模型状态。

监控：

## GPU

例如：

显存：

```text
20GB / 24GB
```

GPU利用率：

```text
95%
```

---

## vLLM

监控：

- 请求数
    
- 延迟
    
- Token速度
    
- 队列长度
    

---

## Prometheus

架构：

```text
 id="m6rj88"
vLLM

↓

Metrics接口

↓

Prometheus

↓

Grafana

↓

Dashboard
```

---

# 十三、Prometheus部署

docker-compose增加：

```yaml
prometheus:

 image:
  prom/prometheus


 ports:

  - "9090:9090"


 volumes:

  - ./prometheus:/etc/prometheus
```

---

配置：

prometheus.yml

```yaml
scrape_configs:


- job_name:
  vllm


  static_configs:


  - targets:

    - vllm:8000
```

---

# 十四、Grafana

增加：

```yaml
grafana:

 image:
  grafana/grafana


 ports:

 - "3000:3000"
```

访问：

```text
http://服务器:3000
```

添加：

Prometheus数据源。

---

# 十五、生产级模型服务完整链路

现在：

```text
 id="0p88aj"
用户

↓

HTTPS

↓

Nginx

↓

API鉴权

↓

Spring Boot

↓

LangChain4j

↓

vLLM API

↓

Qwen

↓

GPU

↓

返回
```

---

# 十六、成本估算

## 个人项目

RTX4090：

运行：

8小时/天

费用：

```text
约500元/月
```

---

## 小团队

A10：

24小时运行：

```text
2000～5000元/月
```

---

## 企业生产

A100：

```text
10000元+/月
```

---

# 十七、现在你的能力升级

之前：

> 我会调用大模型 API。

现在：

你可以说：

> 我完成过开源大模型私有化部署，基于 vLLM 提供 OpenAI 兼容接口，通过 Docker Compose 管理服务，使用 Nginx 做 HTTPS 网关和鉴权，并通过 Prometheus/Grafana 对模型服务进行监控。

这就是：

**AI Application Engineer【AI应用工程师】级别能力。**

---

# 下一节 Day13

## 《企业级 LoRA 微调部署：数据 → QLoRA训练 → 模型合并 → vLLM加载 → 灰度发布》

我们会完成：

```text
业务数据

↓

LLaMA-Factory

↓

QLoRA

↓

LoRA Adapter

↓

合并模型

↓

vLLM部署

↓

线上A/B测试
```

这一步就是：

**真正企业的大模型定制流程。**