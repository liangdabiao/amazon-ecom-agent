# MCP Setup & Validation Reference

## Goal

确保在正式审计 Amazon ASIN 之前，Claude Code 能稳定调用 `sorftime` 与 `sif-mcp`。

## Required Components

- `claude` CLI 可执行
- `sorftime` MCP：产品详情、评论、竞品关键词/竞品表达
- `sif-mcp`：广告、流量、趋势、经营侧证据

## Minimum Verification Flow

### 1. Check Claude Code itself

```bash
claude --version
claude auth status --text
```

如果 `claude` 不存在：
- 先安装 Claude Code
- 确认 PATH 中能找到 `claude`

如果未登录：
- 先完成 `claude auth login`

### 2. Check MCP visibility

```bash
claude mcp list
```

理想结果：
- 能看到 `sorftime`
- 能看到 `sif-mcp`
- 没有 expired login / unauthorized / connection failed 等错误

## Decision Table

### Both MCPs available
可以执行完整审计。

### Only `sorftime` available
可以执行：
- 页面事实分析
- 评论 / Q&A / 竞品表达分析
- COSMO / Rufus / 改写建议

不要写成定论：
- 广告结构结论
- 流量趋势结论
- CTR / CVR 的经营侧因果判断

### Only `sif-mcp` available
可以提示：
- 经营侧可能有问题
- 但页面与评论证据不足，无法高置信度改写

### Neither MCP available
要求用户补：
- 当前标题
- Bullet
- 描述
- 评论摘要
- 竞品链接或竞品文案

## Troubleshooting Checklist

### `claude mcp list` 看不到 `sorftime`
检查：
- MCP 配置文件是否在 Claude Code 实际读取的位置
- key 是否过期
- URL 是否写错
- MCP 类型是否正确

### `claude mcp list` 看得到 `sif-mcp` 但连不上
检查：
- token 是否过期
- Authorization header 是否正确
- 远端服务是否可访问
- 公司网络 / 代理是否拦截

### MCP 存在但调用异常
处理原则：
- 不隐瞒失败
- 在最终报告里标出 `未获取到`
- 明确哪些判断因缺证据而降级

## Security Notes

- 不要把 key、token、Authorization header 写进报告
- 不要把敏感凭据提交到 GitHub
- 截图与共享文档前先打码
