import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.time.Duration;

/**
 * 方案 A 的最小验证：Java 标准库 HttpClient 直接调 Python 的 FastAPI 服务。
 *
 * 先启动 Python 服务：
 *   uvicorn text_service:app --host 127.0.0.1 --port 8000
 * 再运行本文件（Java 11+ 单文件源码模式，无需 javac）：
 *   java HttpCallDemo.java
 *
 * 这里刻意不用 Spring，就是为了证明一件事：
 * 跨语言调用的复杂度 100% 在网络与协议上，跟框架无关。
 * Spring 的 RestClient / WebClient 只是把下面这段换成 Bean 而已。
 */
public class HttpCallDemo {

    public static void main(String[] args) throws Exception {
        HttpClient client = HttpClient.newBuilder()
                .connectTimeout(Duration.ofSeconds(3))   // 连不上要快速失败
                .build();

        String body = """
                {"text":"Spring Boot calls Python over HTTP. Python answers with JSON. HTTP is the firewall between two worlds.","top_k":3}
                """;

        HttpRequest request = HttpRequest.newBuilder(URI.create("http://127.0.0.1:8000/v1/analyze"))
                .header("Content-Type", "application/json")
                .timeout(Duration.ofSeconds(10))          // 整体超时，必须设
                .POST(HttpRequest.BodyPublishers.ofString(body))
                .build();

        long start = System.currentTimeMillis();
        HttpResponse<String> response = client.send(request, HttpResponse.BodyHandlers.ofString());
        long cost = System.currentTimeMillis() - start;

        System.out.println("HTTP status : " + response.statusCode());
        System.out.println("Cost        : " + cost + " ms");
        System.out.println("Response    : " + response.body());
    }
}
