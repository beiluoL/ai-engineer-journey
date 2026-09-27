import java.io.BufferedWriter;
import java.io.InputStream;
import java.io.OutputStreamWriter;
import java.nio.charset.StandardCharsets;
import java.nio.file.Path;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.TimeUnit;

/**
 * 方案 B 的最小验证：Java 用 ProcessBuilder 起一个 Python 进程，stdin 传 JSON，stdout 收 JSON。
 *
 * 运行（两个参数：Python 解释器路径、脚本路径）：
 *   java ProcessCallDemo.java \
 *       /path/to/.venv/bin/python \
 *       ../python/text_stats_cli.py
 *
 * 三个必须守住的规矩，不然线上一定出问题：
 *   1. 必须 waitFor(timeout) —— 否则 Python 死循环会把 Java 线程永久挂住；
 *   2. stderr 必须有人读（这里开线程 drain）—— 否则管道缓冲区满，Python 阻塞写 stderr，进程假死；
 *   3. 用完 destroy() / destroyForcibly() —— 超时后不杀进程会留下僵尸，耗尽机器资源。
 */
public class ProcessCallDemo {

    public static void main(String[] args) throws Exception {
        String pythonBin = args.length > 0
                ? args[0]
                : "/Users/beiluo/Documents/alProject/ai-engineer-journey/projects/02-engineering-ai-assistant/.venv/bin/python";
        String script = args.length > 1 ? args[1] : "../python/text_stats_cli.py";

        // 脚本路径一律转成绝对路径：ProcessBuilder 的 directory 会改变相对路径的解析基准，
        // 这是「本地能跑、线上找不到脚本」最常见的原因。
        Path scriptPath = Path.of(script).toAbsolutePath().normalize();

        ProcessBuilder pb = new ProcessBuilder(pythonBin, scriptPath.toString());
        pb.directory(scriptPath.getParent().toFile());
        pb.redirectError(ProcessBuilder.Redirect.PIPE);   // stderr 我们要自己读，不丢弃

        long start = System.currentTimeMillis();
        Process process = pb.start();

        // 1) 异步 drain stderr，防止管道打满导致子进程阻塞
        ExecutorService drain = Executors.newSingleThreadExecutor();
        drain.submit(() -> {
            try (InputStream err = process.getErrorStream()) {
                new String(err.readAllBytes(), StandardCharsets.UTF_8).lines()
                        .forEach(line -> System.out.println("[python:stderr] " + line));
            } catch (Exception ignored) {
                // 进程被杀时流会关闭，静默结束即可
            }
        });

        // 2) 写 stdin（JSON 一行），写完立刻关闭，否则 Python 的 readline() 会一直等
        String payload = "{\"text\":\"Spring Boot calls Python as a subprocess. Python reads stdin and writes stdout.\",\"top_k\":3}";
        try (BufferedWriter writer = new BufferedWriter(
                new OutputStreamWriter(process.getOutputStream(), StandardCharsets.UTF_8))) {
            writer.write(payload);
            writer.newLine();
        }

        // 3) 读 stdout 全部内容
        String stdout;
        try (InputStream in = process.getInputStream()) {
            stdout = new String(in.readAllBytes(), StandardCharsets.UTF_8);
        }

        // 4) 带超时等待，超时就杀
        boolean finished = process.waitFor(20, TimeUnit.SECONDS);
        long cost = System.currentTimeMillis() - start;
        if (!finished) {
            process.destroyForcibly();
            System.out.println("TIMEOUT: python process killed after 20s");
        }
        drain.shutdownNow();

        System.out.println("Exit code  : " + process.exitValue());
        System.out.println("Cost       : " + cost + " ms");
        System.out.println("Stdout     : " + stdout.strip());
    }
}
