package com.example.pybridge.web;

import com.example.pybridge.client.PythonServiceException;
import com.example.pybridge.client.TextServiceClient;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.util.Map;

@RestController
public class AnalyzeController {

    private final TextServiceClient pythonClient;

    public AnalyzeController(TextServiceClient pythonClient) {
        this.pythonClient = pythonClient;
    }

    @GetMapping("/api/analyze")
    public Object analyze(@RequestParam(defaultValue = "Spring Boot calls Python, and Python answers with JSON.") String text,
                          @RequestParam(defaultValue = "5") int topK) {
        return pythonClient.analyze(text, topK);
    }

    /**
     * 把 Python 的健康检查透出来。
     * 排障第一步永远是：curl 这个端点看 Java 能不能看到 Python。
     */
    @GetMapping("/api/python-health")
    public Object pythonHealth() {
        try {
            return pythonClient.health();
        } catch (Exception e) {
            return ResponseEntity.status(HttpStatus.SERVICE_UNAVAILABLE)
                    .body(Map.of("status", "down", "reason", e.getMessage()));
        }
    }

    /**
     * 统一异常映射：Python 挂了返回 503，而不是默认 500。
     * 这条决定监控告警能不能正确分类。
     */
    @org.springframework.web.bind.annotation.ExceptionHandler(PythonServiceException.class)
    public ResponseEntity<Map<String, Object>> onPythonError(PythonServiceException e) {
        return ResponseEntity.status(HttpStatus.SERVICE_UNAVAILABLE)
                .body(Map.of("error", "python_unavailable", "detail", e.getMessage()));
    }
}
