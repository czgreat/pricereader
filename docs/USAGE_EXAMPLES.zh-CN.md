# 使用和 API 示例

**语言：** [English](USAGE_EXAMPLES.md) | 中文

这些示例使用公开安全的占位数据。复制到自己的环境前，请替换 URL、token、路径和配置，并确认你有权处理对应数据。

## 示例 1：只读仪表盘检查

使用 summary、sources、rules、matches、notifications 等接口验证本地部署。

## 示例 2：手动同步

确认来源规则可公开或仅保存在本地后，手动执行同步/评估。

## curl 示例

```bash
curl http://localhost:8000/healthz
curl http://localhost:8000/api/v1/summary
curl http://localhost:8000/api/v1/sources
curl http://localhost:8000/api/v1/rules
curl -X POST http://localhost:8000/api/v1/sync/run-all
```

接口请求体会随版本变化；以本地 `/docs` 或源码里的模型定义为准。


## 本地验证建议

- 先按 `README.zh-CN.md` 启动项目。
- 先调用健康检查，再执行会写入状态或发通知的操作。
- 使用合成数据或公开演示数据，不要把私人数据写进 issue、截图或提交。
- 如果让 AI assistant 帮忙，把本文件、部署文档和已去敏日志一起提供给它。
