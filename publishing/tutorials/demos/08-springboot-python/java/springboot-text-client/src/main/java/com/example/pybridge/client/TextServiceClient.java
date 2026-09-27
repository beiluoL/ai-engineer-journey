package com.example.pybridge.client;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.fasterxml.jackson.databind.PropertyNamingStrategies;
import com.fasterxml.jackson.databind.annotation.JsonNaming;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.web.client.ClientHttpRequestFactories;
import org.springframework.boot.web.client.ClientHttpRequestFactorySettings;
import org.springframework.http.HttpStatusCode;
import org.springframework.http.MediaType;
import org.springframework.http.client.ClientHttpRequestFactory;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestClient;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.util.List;
import java.util.Map;

/**
 * Python 服务的 Java 客户端：Spring Boot 3.2+ 的 RestClient。
 *
 * 四件事是必须的，缺一件生产就会出事：
 *   1. 连接超时 + 读取超时（配置化，不写死）
 *   2. 非 2xx 转成自己的异常（否则 RestClient 抛的异常里没有响应体，排查时抓瞎）
 *   3. 有限次重试 + 退避（Python 重启、模型冷启动的抖动要能扛过去）
 *   4. 关键日志（耗时、重试次数、失败原因）
 */
@Component
public class TextServiceClient {

    private static final Logger log = LoggerFactory.getLogger(TextServiceClient.class);

    private final RestClient restClient;
    private final int maxRetries;
    private final long backoffMs;

    public TextServiceClient(RestClient.Builder builder,
                             @Value("${python.service.base-url}") String baseUrl,
                             @Value("${python.service.connect-timeout-ms}") int connectTimeoutMs,
                             @Value("${python.service.read-timeout-ms}") int readTimeoutMs,
                             @Value("${python.service.max-retries}") int maxRetries,
                             @Value("${python.service.backoff-ms}") long backoffMs) {

        ClientHttpRequestFactorySettings settings = ClientHttpRequestFactorySettings.DEFAULTS
                .withConnectTimeout(Duration.ofMillis(connectTimeoutMs))
                .withReadTimeout(Duration.ofMillis(readTimeoutMs));
        ClientHttpRequestFactory factory = ClientHttpRequestFactories.get(settings);

        this.restClient = builder
                .baseUrl(baseUrl)
                .requestFactory(factory)
                .defaultStatusHandler(HttpStatusCode::isError, (request, response) -> {
                    String body;
                    try {
                        byte[] bytes = response.getBody().readAllBytes();
                        body = bytes.length > 0 ? new String(bytes, StandardCharsets.UTF_8) : "<empty>";
                    } catch (IOException e) {
                        body = "<unreadable>";
                    }
                    throw new PythonServiceException(
                            "python service error: status=" + response.getStatusCode() + ", body=" + body,
                            response.getStatusCode().value());
                })
                .build();

        this.maxRetries = maxRetries;
        this.backoffMs = backoffMs;
    }

    public AnalyzeResult analyze(String text, int topK) {
        Map<String, Object> payload = Map.of("text", text, "top_k", topK);

        int attempt = 0;
        while (true) {
            attempt++;
            long start = System.currentTimeMillis();
            try {
                AnalyzeResult result = restClient.post()
                        .uri("/v1/analyze")
                        .contentType(MediaType.APPLICATION_JSON)
                        .body(payload)
                        .retrieve()
                        .body(AnalyzeResult.class);
                log.info("python /v1/analyze ok: cost={}ms, attempt={}",
                        System.currentTimeMillis() - start, attempt);
                return result;
            } catch (PythonServiceException e) {
                // 4xx 是请求本身有问题，重试没意义，直接抛
                if (e.getStatusCode() >= 400 && e.getStatusCode() < 500) {
                    log.warn("python rejected request: {}", e.getMessage());
                    throw e;
                }
                if (attempt > maxRetries) {
                    log.error("python /v1/analyze failed after {} attempts: {}", attempt, e.getMessage());
                    throw e;
                }
                log.warn("python /v1/analyze attempt {}/{} failed, retrying in {}ms: {}",
                        attempt, maxRetries, backoffMs * attempt, e.getMessage());
                sleepQuietly(backoffMs * attempt);
            } catch (Exception e) {
                // 连接超时 / 读超时 / DNS 失败，都属于可重试
                if (attempt > maxRetries) {
                    log.error("python /v1/analyze unreachable after {} attempts", attempt, e);
                    throw new PythonServiceException("python service unreachable: " + e.getMessage(), 503, e);
                }
                log.warn("python /v1/analyze attempt {}/{} error, retrying: {}", attempt, maxRetries, e.toString());
                sleepQuietly(backoffMs * attempt);
            }
        }
    }

    public Map<String, Object> health() {
        return restClient.get()
                .uri("/health")
                .retrieve()
                .body(new org.springframework.core.ParameterizedTypeReference<Map<String, Object>>() {});
    }

    private static void sleepQuietly(long ms) {
        try {
            Thread.sleep(ms);
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
        }
    }

    @JsonIgnoreProperties(ignoreUnknown = true)
    // Python 习惯 snake_case，Java 习惯 camelCase。
    // 不加这个注解，top_words / elapsed_ms 会静默反序列化成 null —— 不报错，只是值没了。
    @JsonNaming(PropertyNamingStrategies.SnakeCaseStrategy.class)
    public record AnalyzeResult(int chars,
                                int words,
                                int sentences,
                                List<List<Object>> topWords,
                                double elapsedMs,
                                String engine) {
    }
}
