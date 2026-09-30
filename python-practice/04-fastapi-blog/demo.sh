#!/usr/bin/env bash
# 04-fastapi-blog 可复现演示：真的起一个 uvicorn 服务，用 curl 打真请求。
#
#   bash demo.sh > assets/run.txt
# 然后把 run.txt 按分隔线切成两张截图（见文件末尾注释）。
#
# 为什么用 curl 而不是 TestClient：截图的读者要看到「HTTP 状态码 / 响应头 /
# JSON 体」这些协议层面的东西。TestClient 是给测试用的（见 test_api.py）。
#
# 实现上刻意不用 `bash -c "$字符串"` 来「回显并执行」——那样：
#   1) 命令里的 `*` 会被内层 shell 当通配符展开（--noproxy '*' 直接失效）
#   2) JSON 里的双引号和外层引号打架，中文内容被吃掉
# 所以下面「一个动作一个函数」，参数老实走 "$@"，不回炉重造字符串。
set +m          # 关掉作业控制提示，免得结尾冒一句 "Terminated: 15"
set -u
cd "$(dirname "$0")"

PY="${PY:-python3}"
PORT="${PORT:-8130}"
BASE="http://127.0.0.1:$PORT"
CT="Content-Type: application/json"
SEP='echo "─────────────── ✂ 截图切分线 ───────────────"'

WORK="$(mktemp -d)"
export BLOG_DB="$WORK/blog.db"        # 临时库，不污染项目目录
UV_PID=""

cleanup() {
    if [ -n "$UV_PID" ]; then
        kill "$UV_PID" 2>/dev/null
        wait "$UV_PID" 2>/dev/null
    fi
    rm -rf "$WORK"
}
trap cleanup EXIT

# ---------- 展示 + 执行 ----------

api() {    # api <METHOD> <path> [json-body] —— 回显命令，打印状态码 + 美化后的响应体
    local method="$1" path="$2" body="${3:-}" code
    local -a args
    if [ -n "$body" ]; then
        printf '$ curl -s -X %s %s%s -H %s -d %s\n' "$method" "$BASE" "$path" "'$CT'" "'$body'"
        args=(-X "$method" "$BASE$path" -H "$CT" -d "$body")
    else
        printf '$ curl -s %s%s\n' "$BASE" "$path"
        args=("$BASE$path")
    fi
    code=$(curl -s --noproxy '*' -o "$WORK/resp.json" -w '%{http_code}' "${args[@]}")
    printf 'HTTP %s\n' "$code"
    "$PY" jsonpp.py < "$WORK/resp.json"
    printf '\n'
}

apilines() {   # 列表接口：一行一条
    printf '$ curl -s %s/posts | python3 jsonpp.py --lines\n' "$BASE"
    printf 'HTTP %s\n' "$(curl -s --noproxy '*' -o "$WORK/resp.json" -w '%{http_code}' "$BASE/posts")"
    "$PY" jsonpp.py --lines < "$WORK/resp.json"
    printf '\n'
}

apiquery() {   # 带中文的查询参数必须 URL 编码，否则 uvicorn 直接回 "Invalid HTTP request"
    printf '$ curl -sG --data-urlencode %s %s/posts\n' "'q=$1'" "$BASE"
    printf 'HTTP %s\n' "$(curl -s --noproxy '*' -G --data-urlencode "q=$1" \
        -o "$WORK/resp.json" -w '%{http_code}' "$BASE/posts")"
    "$PY" jsonpp.py < "$WORK/resp.json"
    printf '\n'
}

apihead() {    # apihead <METHOD> <path> [json-body] [head-n] —— 完整响应头（看 Location / 204）
    local method="$1" path="$2" body="${3:-}" n="${4:-7}"
    if [ -n "$body" ]; then
        printf '$ curl -si -X %s %s%s -H %s -d %s\n' "$method" "$BASE" "$path" "'$CT'" "'$body'"
        curl -s --noproxy '*' -i -X "$method" "$BASE$path" -H "$CT" -d "$body" | head -"$n"
    else
        printf '$ curl -si -X %s %s%s\n' "$method" "$BASE" "$path"
        curl -s --noproxy '*' -i -X "$method" "$BASE$path" | head -"$n"
    fi
    printf '\n'
}

# ---------- 开场 ----------

echo "# 04 FastAPI 博客 API —— 起真服务，用 curl 打真请求"
echo
echo "\$ python3 -m uvicorn app:app --port $PORT    (后台启动)"
"$PY" -m uvicorn app:app --host 127.0.0.1 --port "$PORT" --log-level warning \
    >"$WORK/uvicorn.log" 2>&1 &
UV_PID=$!

for _ in $(seq 1 80); do
    if curl -s --noproxy '*' -o /dev/null "$BASE/health" 2>/dev/null; then break; fi
    sleep 0.25
done
echo "服务已就绪 → $BASE   （交互式文档：$BASE/docs）"
echo

# ---------- 截图 A：增 → 查 → 改 → 搜 ----------

api GET /health
apihead POST /posts '{"title":"为什么要把重复的周报自动化","content":"每周一手工合并 CSV，两小时。","author":"阿罗","tags":["自动化","pandas"]}' 7
api POST /posts '{"title":"爬虫与礼貌","content":"先看 robots.txt，别把别人的服务器当靶子。","author":"阿罗","tags":["爬虫"]}'
api GET /posts/1
api PUT /posts/1 '{"title":"把周报自动化之后，我每周多出两小时"}'
apiquery 爬虫

eval "$SEP"

# ---------- 截图 B：边界情况 + 自动文档 ----------

echo "# 边界情况：校验失败、删除、查不到 —— 这些才是一个接口真正的「设计」"
echo

api POST /posts '{"title":"","content":"正文"}'
apihead DELETE /posts/2 '' 4

echo "# 删掉之后再查，必须是 404 —— 而不是静默返回空对象"
echo
api GET /posts/2
api PUT /posts/999 '{"title":"x"}'

echo "# 剩下这一条：列表接口（一行一条）"
echo
apilines

echo '$ curl -s '"$BASE"'/openapi.json | python3 list_endpoints.py'
curl -s --noproxy '*' "$BASE/openapi.json" | "$PY" list_endpoints.py
echo

# 截图切分线在 run.txt 里的行号：
#   python3 ../../scripts/render_terminal.py <(sed -n '1,34p'  assets/run.txt) \
#       --out assets/term-04-api.png    --title "bash — 04-fastapi-blog/demo.sh"
#   python3 ../../scripts/render_terminal.py <(sed -n '36,$p'  assets/run.txt) \
#       --out assets/term-04-errors.png --title "bash — 04-fastapi-blog/demo.sh"
