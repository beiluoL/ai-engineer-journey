package com.example.pybridge.client;

/**
 * Python 侧不可用时的统一异常。
 *
 * 为什么要单独定义一个异常类型：
 * Controller 靠它区分「Python 挂了（503）」和「用户参数错了（400）」。
 * 如果把所有失败都包成 RuntimeException，前端永远只能看到 500，
 * 排查时根本分不清是自己的 bug 还是下游 Python 的问题。
 */
public class PythonServiceException extends RuntimeException {

    private final int statusCode;

    public PythonServiceException(String message, int statusCode, Throwable cause) {
        super(message, cause);
        this.statusCode = statusCode;
    }

    public PythonServiceException(String message, int statusCode) {
        this(message, statusCode, null);
    }

    public int getStatusCode() {
        return statusCode;
    }
}
