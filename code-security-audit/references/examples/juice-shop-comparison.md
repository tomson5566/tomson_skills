# Juice Shop 审计对比：白盒 (code-security-audit) vs 黑盒 (Shannon)

> 对比日期: 2026-02-11
> 白盒报告: [juice-shop-audit.md](juice-shop-audit.md) — 本 Skill 产出
> 黑盒报告: [Shannon Report](https://github.com/KeygraphHQ/shannon/blob/main/sample-reports/shannon-report-juice-shop.md) — KeygraphHQ/Shannon 自动化渗透测试工具产出

## 基本信息

| 维度 | 白盒 (code-security-audit) | 黑盒 (Shannon) |
|------|--------------------------|----------------|
| 审计方式 | 源码 Grep + 数据流追踪 + 业务逻辑分析 | 实际发包 + 响应验证 + 动态利用 |
| 漏洞总数 | **42** | **~22**（去重后独立漏洞） |
| 严重等级分布 | 8C / 18H / 12M / 4L | 未统一分级 |
| 报告格式 | 问题代码 + 数据流 + Payload + 修复建议 | curl 命令 + 实际响应 JSON |
| 攻击链 | 6 条 | 无 |
| 覆盖面 | 注入/RCE/XXE/SSRF/JWT/业务逻辑/配置 | 认证/授权/XSS/注入/SSRF |

## 漏洞覆盖矩阵

### 双方都发现（16 个）

| 漏洞类型 | 白盒编号 | Shannon 编号 |
|---------|----------|-------------|
| SQL 注入 — 搜索 UNION | VULN-001 | INJ-VULN-02 |
| SQL 注入 — 登录绕过 | VULN-002 | INJ-VULN-01 / AUTH-VULN-06 |
| XXE 文件读取 | VULN-004 | INJ-VULN-06 |
| SSRF 头像 URL | VULN-005 | SSRF-VULN-01 |
| Mass Assignment 管理员注册 | VULN-008 | AUTHZ-VULN-06 / AUTHZ-VULN-10 |
| NoSQL 操作符注入 | VULN-011 | INJ-VULN-04 |
| MD5 弱哈希 | VULN-017 | AUTH-VULN-07 |
| Basket IDOR | VULN-018 | AUTHZ-VULN-02 |
| Order Checkout IDOR | VULN-019 | AUTHZ-VULN-08 |
| Feedback 伪造 | VULN-021 | AUTHZ-VULN-03 |
| Products 缺少认证 | VULN-022 | AUTHZ-VULN-07 |
| DOM XSS 搜索框 | VULN-023 | XSS-VULN-01 |
| YAML 炸弹 | VULN-027 | INJ-VULN-07 |
| Deluxe 免费升级 | VULN-032 | AUTHZ-VULN-09 |
| 速率限制绕过 / 暴力破解 | VULN-037 | AUTH-VULN-05 |
| User Profile IDOR | VULN-018 范围 | AUTHZ-VULN-01 |

### 白盒独有发现（26 个）

Shannon 的黑盒测试未能发现以下漏洞：

| 编号 | 漏洞 | 为何黑盒难以发现 |
|------|------|----------------|
| VULN-003 | **RCE via eval()** — 用户资料页 | 需要知道 `#{...}` 模板触发 eval 的隐藏路径 |
| VULN-006 | **JWT 私钥硬编码** | 黑盒无法看到源码中的密钥 |
| VULN-007 | **JWT 算法混淆** (none/HS256) | 需要了解 JWT 验证实现细节 |
| VULN-009 | **NoSQL $where 注入** — 评论 | `$where` 拼接需要源码才能定位 |
| VULN-010 | **NoSQL $where 注入** — 订单追踪 | 同上 |
| VULN-012 | **沙箱逃逸** (notevil + vm) | 需要分析 vm 沙箱代码 |
| VULN-013 | **本地文件读取** — dataErasure layout | `res.render()` layout 参数注入 |
| VULN-014 | **Null Byte 文件读取绕过** | `%00` 截断需要了解后端路径处理 |
| VULN-015 | **Zip Slip 任意文件写入** | 需要分析解压逻辑 |
| VULN-016 | **加密密钥目录暴露** | 需要了解静态文件路由配置 |
| VULN-020 | **密码修改跳过当前密码** | 业务逻辑缺陷，需要代码审查 |
| VULN-024 | **存储型 XSS** — Feedback | 需要追踪数据流到管理面板渲染 |
| VULN-025 | **HTTP Header XSS** — True-Client-IP | 需要了解 header 到模板的数据流 |
| VULN-026 | **CORS 完全开放** | 配置审计 |
| VULN-028 | **开放重定向** | `includes()` 绕过需要源码分析 |
| VULN-030 | **优惠券算法可逆** (Z85) | 需要逆向优惠券生成逻辑 |
| VULN-031 | **过期优惠券 `==` 绕过** | 需要分析 JS 类型转换 |
| VULN-033 | **钱包充值无金额校验** | 深层业务逻辑 |
| VULN-034 | **负数订单总价** | 深层业务逻辑 |
| VULN-035 | **CAPTCHA 答案泄露 + 可重放** | 需要分析 CAPTCHA 实现 |
| VULN-036 | **Image CAPTCHA 绕过** | 需要分析验证逻辑 |
| VULN-038 | **前端路由信息泄露** | 需要分析 Angular 路由配置 |
| VULN-039 | **errorhandler 生产环境暴露堆栈** | 配置审计 |
| VULN-040 | **Swagger API 文档暴露** | 配置审计 |
| VULN-041 | **Prometheus Metrics 暴露** | 配置审计 |
| VULN-042 | **helmet.xssFilter() 被注释** | 需要读源码 |

### Shannon 独有发现（6 个）

白盒静态分析未能覆盖以下漏洞：

| Shannon 编号 | 漏洞 | 为何白盒遗漏 |
|-------------|------|-------------|
| XSS-VULN-02 | **JSONP Callback XSS** (`/rest/user/whoami?callback=`) | 未扫描 JSONP 端点模式 |
| AUTH-VULN-01 | **HTTP 明文传输** | 部署层问题，非代码层 |
| AUTH-VULN-02/03 | **缺少 HSTS + Cookie 不安全** | 运行时 HTTP 头检测 |
| AUTH-VULN-08 | **nOAuth 可预测密码** (`btoa(email.reverse())`) | OAuth 回调中的深层业务逻辑 |
| AUTH-VULN-09 | **账户枚举** — 差异响应 | 需要动态对比响应差异 |
| AUTH-VULN-10 | **Token 注销后仍有效** | 需要运行时验证 JWT 生命周期 |
| AUTHZ-VULN-04 | **Memories 匿名访问** | 未扫描缺少认证中间件的端点 |

## 方法论差异分析

### 白盒优势场景

| 场景 | 原因 |
|------|------|
| 隐藏的代码执行路径 (eval/vm) | 黑盒无法猜测触发条件 |
| 硬编码密钥/凭证 | 只有源码可见 |
| 复杂数据流（多跳 Source→Sink） | 需要追踪跨函数/跨文件的数据流 |
| 业务逻辑缺陷（优惠券/钱包/负数） | 需要理解业务规则实现 |
| 配置审计（CORS/Swagger/Metrics） | 需要读取配置文件 |

### 黑盒优势场景

| 场景 | 原因 |
|------|------|
| 运行时行为（Token 失效、暴力破解） | 需要实际发包观察行为 |
| 部署层安全（TLS/HSTS/Cookie 标志） | 代码层面不可见 |
| 响应差异分析（账户枚举） | 需要对比不同输入的响应 |
| 利用可行性验证 | 白盒发现的漏洞不一定可利用 |

### 报告质量对比

| 维度 | 白盒 | 黑盒 |
|------|------|------|
| 定位精度 | ✅ 精确到 文件:行号 | ❌ 仅知道端点 URL |
| 修复建议 | ✅ 提供修复代码 | ❌ 无 |
| 利用证据 | ⚠️ 理论 Payload | ✅ 实际 curl + 响应 |
| 数据流分析 | ✅ Source→Sink 完整路径 | ❌ 无 |
| 攻击链 | ✅ 6 条组合利用链 | ❌ 无 |
| 误报率 | ⚠️ 可能存在（未运行验证） | ✅ 极低（已验证） |

## 结论与改进方向

### 数据总结

- 白盒发现 **42** 个漏洞，黑盒发现 **~22** 个（去重），重叠 **16** 个
- 白盒独有 **26** 个（62%），黑盒独有 **6** 个（14%）
- 白盒覆盖率显著更高，但黑盒的 6 个遗漏项暴露了白盒的盲区

### Skill 改进建议

基于 Shannon 发现的遗漏，以下检查规则应加入 `vulnerability_rules.md`：

1. **JSONP XSS** — 扫描 `callback` 参数 + JSONP 响应模式
2. **nOAuth 可预测密码** — 检查 OAuth 回调中的密码生成逻辑
3. **JWT 无服务端失效** — 检查是否存在 token blacklist/revocation 机制
4. **Memories/资源匿名访问** — 扫描缺少认证中间件的 REST 端点
5. **Cookie 安全标志** — 检查 `express-session` / `cookie-parser` 配置中的 secure/httpOnly/sameSite
