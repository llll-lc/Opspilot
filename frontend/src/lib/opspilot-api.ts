/**
 * OP-002 工作台壳中唯一对浏览器可见的 API 配置。
 *
 * 这里有意不采用上游 LangGraph passthrough。认证、请求方法和 API Client
 * 分别由其所属任务实现。
 */
export function getOpsPilotApiBaseUrl(): string {
  return (
    process.env.NEXT_PUBLIC_OPSPILOT_API_BASE_URL ?? "http://localhost:8000"
  );
}
