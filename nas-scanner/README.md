# NAS 勒索软件威胁扫描器

面向群晖（Synology）NAS 的勒索软件威胁自检工具。基于 **IOC 特征匹配 + 熵值分析 + 行为异常检测**，
针对 2026 年 10 月起大规模攻击 NAS 的 **C3RB3R / L0CK3D（Cerber 变种）** 做了专项检测，
同时支持群晖 DSM 版本漏洞自检与 NAS 端定时巡检脚本生成。

**扫描全程只读，不会修改任何文件。**

技术栈：[Next.js 16](https://nextjs.org) (App Router) + [shadcn/ui](https://ui.shadcn.com) + Tailwind CSS 4 + TypeScript 5。

---

## 目录

- [快速开始](#快速开始)
- [源码部署（无 Docker）](#源码部署无-docker)
- [扫描能力](#扫描能力)
- [特征库结构](#特征库结构)
- [项目结构](#项目结构)
- [开发规范](#开发规范)
- [常见开发场景](#常见开发场景)

---

## 快速开始

### 开发服务器

```bash
pnpm install
bash scripts/dev.sh
```

启动后打开 [http://localhost:5000](http://localhost:5000)，支持热更新。

### 生产构建与启动

```bash
bash scripts/build.sh     # Next 生产构建 + tsup 打包服务端入口
bash scripts/start.sh     # 前台运行
```

---

## 源码部署（无 Docker）

生产环境采用源码构建 + 后台常驻进程的方式运行。

### 一、首次部署

```bash
cd /home/tangzhiang/workspaces/nas_pro/projects

# 1. 安装依赖（仅允许 pnpm）
pnpm install --prefer-frozen-lockfile

# 2. 构建：Next.js 生产构建 + tsup 打包自定义服务端
bash scripts/build.sh

# 3. 启动（后台常驻，日志写入 logs/app.log）
bash scripts/service.sh start
```

构建产物：

- `.next/` —— Next.js 生产构建产物
- `dist/server.js` —— 由 `src/server.ts` 经 tsup 打包的服务端入口

### 二、服务管理

```bash
bash scripts/service.sh start     # 启动
bash scripts/service.sh stop      # 停止
bash scripts/service.sh restart   # 重启
bash scripts/service.sh status    # 查看状态（PID / 监听地址）
bash scripts/service.sh logs      # 跟踪服务进程日志
bash scripts/service.sh smb-logs  # 查看 SMB 连接诊断日志（排障用）
```

> ⚠️ **已知问题**：`stop` 是按**端口**查找并结束占用进程的，而非按启动时记录的 PID。
> 如果同一台机器上还有其他进程占用 5000 端口，`stop` 会一并结束它们。
> 如需精确停止，请先 `service.sh status` 确认 PID 后手动 `kill`。

### 三、SMB 后端说明

SMB 模式通过调用系统自带的 **`smbclient`（Samba 官方实现）** 完成，
而不是使用 Node 的 `@awo00/smb2` 库。

**原因**：

1. 该库只支持 SMB 2.0.2 / 2.1 方言，无法与要求 SMB3 的群晖协商；
2. 该库生成的 NTLM 消息与 Windows / smbclient 不一致（Workstation 字段填成被连接方地址、
   缺少 `TargetInfo` 与 `ExtendedSessionSecurity` 标志），实测无论怎样调整协商标志，
   都会在 SPNEGO 阶段返回 `NT_STATUS_INVALID_PARAMETER`。

`smbclient` 协商到 SMB3_11，行为与 Windows 一致。

实现见 `src/lib/scanner/smbclient-provider.ts`：

| 接口 | 实现 |
| --- | --- |
| `list()` | `smbclient` 的 `dir` 命令，解析表格输出 |
| `readChunk()` | `smbclient` 的 `get` 命令读取文件头部（熵值分析用） |
| `readTail()` | `get` 后取尾部（部分加密检测用；smbclient 无区间读，故整文件下载） |

**前置条件**：服务器需安装 `smbclient`。

```bash
# RHEL / CentOS / Rocky
sudo dnf install samba-client
# Debian / Ubuntu
sudo apt install smbclient
```

可用环境变量 `SMBCLIENT_BIN` 指定可执行文件路径。

### 四、SMB 连接诊断日志

排查「SMB 连不上」时，**不要只看浏览器页面**，服务端有独立日志：

```bash
bash scripts/service.sh smb-logs        # 看最近 40 条
bash scripts/service.sh smb-logs 100    # 看最近 100 条
bash scripts/service.sh smb-logs -f     # 实时跟踪
```

文件位置：`logs/smb-debug.log`（JSON Lines 格式，超过 5MB 自动归档改名）。

记录的事件：

| event | 含义 |
| --- | --- |
| `scan.request` | 浏览器发来的实际参数（密码已脱敏，只记长度） |
| `smb.connect.start` | 开始连接，含目标信息与后端类型（`smbclient`） |
| `smb.connect.failed` | **认证失败**，含 smbclient 原始错误输出与语义化提示 |
| `smb.connect.ok` | 认证成功 |
| `smb.tree.failed` | **认证通过但共享打不开**（权限或共享名问题） |
| `smb.tree.ok` | 共享打开成功 |
| `scan.done` / `scan.error` | 扫描结果汇总 |

**`smb.connect.failed` 与 `smb.tree.failed` 的区别很关键**：
前者是账号/密码问题，后者是共享名或权限问题 —— 不用再靠猜。

**密码不会出现在日志里**：`sanitizeTarget()` 会把 `password` 替换成 `***`，
只保留 `passwordLength`。

### 五、运行参数

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `PORT` | `5000` | 监听端口，等价于 `DEPLOY_RUN_PORT` |
| `HOSTNAME` | `0.0.0.0` | 监听地址 |
| `COZE_PROJECT_ENV` | `PROD` | `PROD` 走生产模式，非 `PROD` 走 dev 模式 |
| `SMBCLIENT_BIN` | `smbclient` | smbclient 可执行文件路径 |

访问地址：`http://<服务器IP>:5000`。

### 六、部署说明

- 服务以 `setsid` 启动并脱离终端会话，SSH 断开后仍持续运行，父进程为 init（PID 1）。
- 进程未注册开机自启。如需自启，建议写 systemd unit 而非 `rc.local`。
- `Dockerfile` 与 `docker-compose.yml` 保留备用，需先安装 Docker。

---

## 扫描能力

### 一、扫描目标配置

- **SMB 模式**：页面上填写 NAS 的 IP、共享名、用户名与密码，直接连接远端 NAS。
- **本机目录模式**：扫描服务器本地目录（如 `/tmp/mock-nas`，内置演示数据）。
- **NTLM 域**：群晖默认为 `SAMBA`（命令行 `smbclient` 提示符会显示
  `Password for [SAMBA\nas]:`），部分环境为 `WORKGROUP`，留空表示不发送域。

若需要扫描宿主机上已挂载的 NAS 共享目录，参见 `docker-compose.yml` 中的
`volumes` 注释示例（源码部署下直接传入宿主机绝对路径即可）。

### 二、熵值检测原理与判定标准

**熵值怎么算的**：读取文件头部最多 64KB，统计 256 个字节值各自的出现频率，
按 Shannon 公式 `H = -Σ p(i)·log2(p(i))` 计算，单位 bits/byte，范围 0~8。

| 内容类型 | 典型熵值 |
| --- | --- |
| 全零 / 单一内容 | 0.0 |
| 重复英文文本 | ~4.4 |
| 重复中文文本 | ~4.9 |
| 源码 / JSON | 4.8 ~ 6.3 |
| **随机数据（加密后）** | **7.95 ~ 8.0** |

**怎么判定可疑**：熵值 ≥ **7.2** 进入可疑范围，再叠加**文件魔数**判断：

| 情况 | 判定 | 是否报为威胁 |
| --- | --- | --- |
| 熵值 < 7.2 | 正常 | 否 |
| 熵值 ≥ 7.2，且命中已知容器魔数（OLE2/ZIP/PDF/PNG…） | 格式本身如此 | **否**（仅记日志） |
| 熵值 ≥ 7.2，且不命中任何已知魔数 | 疑似被加密 | 是 |

**为什么要看魔数**：`.doc` / `.docx` 这类 Office 文档本质是压缩容器
（老版是 OLE2 复合文档，新版是 ZIP），**内容完全正常时熵值也有 7.8~7.98**，
只看熵值会把它们全部误报。魔数识别还能反过来抓住真威胁：
攻击者把加密后的文件改名成 `.doc`，扩展名白名单挡不住，但文件头没有
OLE2/ZIP 魔数，依然会被判定为疑似加密。

实现见 `src/lib/scanner/entropy.ts`（`judgeEntropy()` / `isBinaryContainer()`）。

**扫描范围限制**：仅对扩展名在 `ENTROPY_CHECK_EXTENSIONS` 里的文本类文件
（`.txt` `.md` `.csv` `.log` `.json` `.xml` `.py` `.js` `.doc` 等）做抽样；
单个文件 ≥ 4KB 且 ≤ 100MB；每次扫描最多抽样 300 个文件。

### 三、C3RB3R / L0CK3D 专项检测

按公开样本分析结论（360 反勒索团队 / Cyclonis / EnigmaSoft）实现了三条专项检测。

**1. 勒索信内容指纹**

`read-me3.txt` 开头第一行即 `C3RB3R INSTRUCTIONS`。文件名可被篡改，
内容指纹才是稳定线索 —— 扫描器会读取 `.txt`/`.html` 文件开头 2KB，
匹配家族标识（`c3rb3r instructions` / `c3rb3r` / `0.085 btc` / `0.17 btc`），
命中即报「勒索信内容」。

**2. 部分加密（只加密头部）—— 最重要的一条**

C3RB3R 对文件**按体积分级**处理：

| 文件大小 | 加密策略 | 整体熵值 | 能否被常规检测发现 |
| --- | --- | --- | --- |
| 小文件 | 整体加密 | 高（7.95+） | ✅ 能 |
| 稍大文件 | **只加密头部** | **不高**（约 6.4） | ❌ **漏检** |
| 最大文件 | 分段加密，每段只动头部 | 中等 | ❌ **漏检** |

只加密头部意味着尾部仍是明文，**整体熵值不足以触发常规阈值**。
扫描器因此对比头部与尾部熵值（各取 8KB，且两者不重叠），
当「头部接近随机数据而尾部仍为明文」时判定为 `部分加密`（severity=critical），
并显示头/尾两个熵值。

仅对 C3RB3R 优先加密列表里的类型（照片、文档、业务数据等扩展名）执行。

**3. 优先加密类型识别**

C3RB3R 优先列表里的扩展名（照片/文档/办公/数据库/源码等）
被改动属于高置信度命中。实现见 `src/lib/scanner/c3rb3r-behavior.ts`。

**4. 系统目录避让说明**

C3RB3R 会主动跳过 `/boot` `/run` `/proc` `/sys` `/dev` `/etc` 等系统目录
（把系统加密到崩溃，勒索者自己也拿不到解密后的系统）。
因此**系统目录未被加密属于预期行为**，不应据此判定安全。

**5. 赎金与流程线索（供人工核对）**

- 初始赎金 **0.085 BTC**，五天内未付翻倍至 **0.17 BTC**
- 暗网站点提供 ≤1MB 的 `.L0CK3D` 文件**免费试解密**
- 比特币交易满 **6 次确认**后自动放行解密器
- 勒索信声称「已下载你大量数据」，威胁在暗网售卖（双重胁迫）

### 四、扫描结果与威胁明细

扫描过程中**一旦发现威胁就会立即显示**，不必等扫描结束：

- **结论横幅**：确认感染 / 存在可疑迹象 / 未发现威胁，附扫描统计与处置摘要
- **威胁明细**：按类型分组（勒索信 / 勒索信内容 / 加密文件 / 高熵文件 / 部分加密 /
  可疑载荷 / 批量修改），每组给出该类威胁的含义说明
- **过滤器**：全部 / 高危 / 可疑快速筛选
- **展开单项**：点击任一威胁项，展开显示**该类威胁的处置建议**（分步骤，可直接照做）
- **中止不丢结果**：手动中止扫描时，已发现的威胁仍会完整列出，并标注「扫描已中止」

实现见 `src/components/scanner/findings-panel.tsx`。

---

## 特征库结构

所有检测特征都是**编译进代码的常量**（无数据库、无外部配置文件），
改完重新构建即可生效。分布在 4 个文件：

| 文件 | 内容 |
| --- | --- |
| `src/lib/scanner/signatures.ts` | **主特征库**：`RANSOMWARE_FAMILIES`（6 个勒索软件家族的名称、加密后缀、勒索信名、内容指纹、严重级别、来源引用）、`KNOWN_HIGH_ENTROPY_EXTENSIONS`（天然高熵格式排除名单）、`ENTROPY_CHECK_EXTENSIONS`（参与熵值检测的类型）、`SUSPICIOUS_PAYLOAD_NAMES`（可疑载荷名）、`matchFilename()`（文件名匹配） |
| `src/lib/scanner/c3rb3r-behavior.ts` | **C3RB3R 专项**：`C3RB3R_PRIORITY_EXTENSIONS`（优先加密扩展名表）、`C3RB3R_EXCLUDED_DIRS`（系统目录避让）、`matchRansomNoteContent()`（勒索信内容指纹） |
| `src/lib/scanner/entropy.ts` | **熵值参数**：`HIGH_ENTROPY_THRESHOLD`(7.2)、`PARTIAL_ENTROPY_DELTA`(1.5)、`ENTROPY_SAMPLE_BYTES`(64KB)、`CONTAINER_MAGIC`（16 种二进制容器魔数）、`judgeEntropy()` / `judgePartialEntropy()` |
| `src/lib/scanner/dsm.ts` | **DSM 修复基线**：`FIXED_VERSIONS`（各版本线修复版本）、`AFFECTED_CVES`、版本比对逻辑 |

**数据流向**：

```
signatures.ts ─┬─→ src/app/page.tsx          （服务端组件直接 import，渲染页面上的「内置威胁特征库」）
                └─→ src/app/api/signatures/route.ts  （对外提供 JSON 接口）
                            │
                            └─→ GET /api/signatures  （families + c3rb3r + entropy 三段数据）
```

页面是**服务端组件直接 import** 特征库并渲染的，不走 API；
`/api/signatures` 是另外对外暴露的 JSON 接口，方便外部系统对接或做特征库版本比对。

**新增一个勒索软件家族**：只需在 `signatures.ts` 的 `RANSOMWARE_FAMILIES`
数组里加一项，`matchFilename()`、页面展示、API 输出会自动生效。

---

## 项目结构

```
src/
├── app/                      # Next.js App Router 目录
│   ├── layout.tsx            # 根布局（metadata 标题/描述）
│   ├── page.tsx              # 首页（含内置威胁特征库展示）
│   ├── globals.css           # 全局样式（shadcn 主题变量）
│   └── api/
│       ├── scan/             # POST SSE 流式扫描（local / smb）
│       ├── dsm-check/        # POST DSM 版本漏洞比对
│       ├── nas-script/       # GET NAS 端巡检脚本
│       └── signatures/       # GET 特征库 JSON
├── components/
│   ├── scanner/              # 业务组件
│   │   ├── scan-panel.tsx     # 扫描主面板（配置 + SSE 进度）
│   │   ├── findings-panel.tsx # 威胁明细与处置建议
│   │   └── dsm-checker.tsx    # DSM 版本自检 + 脚本下载
│   └── ui/                   # shadcn/ui 基础组件（优先使用）
├── lib/
│   ├── scanner/              # 扫描核心
│   │   ├── signatures.ts      #   主特征库
│   │   ├── c3rb3r-behavior.ts #   C3RB3R 专项特征
│   │   ├── entropy.ts         #   熵值计算与判定
│   │   ├── providers.ts       #   文件系统抽象（local）
│   │   ├── smbclient-provider.ts # SMB 后端（smbclient）
│   │   ├── smb-debug-log.ts   #   SMB 诊断日志
│   │   ├── engine.ts          #   扫描引擎（产出 SSE 事件）
│   │   ├── dsm.ts             #   DSM 版本比对
│   │   └── nas-script.ts      #   NAS 巡检脚本生成
│   └── utils.ts              # cn() 等工具函数
├── hooks/                    # 自定义 React Hooks
└── server.ts                 # 自定义服务端入口（tsup 打包为 dist/server.js）

scripts/
├── build.sh                  # 构建脚本
├── dev.sh                    # 开发服务器
├── prepare.sh                # 依赖预处理
├── service.sh                # 生产服务管理（start/stop/restart/status/logs/smb-logs）
└── start.sh                  # 前台启动
```

---

## 开发规范

### 1. 组件开发

**优先使用 shadcn/ui 基础组件**，位于 `src/components/ui/`。开发时应优先复用这些组件。

### 2. 路由开发

```bash
# 创建新路由 /about
mkdir -p src/app/about && touch src/app/about/page.tsx

# 创建动态路由 /posts/[id]
mkdir -p src/app/posts/\[id\] && touch src/app/posts/\[id\]/page.tsx

# 创建 API 路由
mkdir -p src/app/api/xxx && touch src/app/api/xxx/route.ts
```

**API 路由需 `export const runtime = 'nodejs'`**（SMB 扫描需要 Node 运行时）。

### 3. 依赖管理

```bash
pnpm add <package>          # 安装依赖
pnpm add -D <package>       # 添加开发依赖
pnpm remove <package>       # 移除依赖
```

**必须使用 pnpm**，禁止 npm 或 yarn。

### 4. 样式开发

Tailwind CSS v4 + shadcn 主题变量。设计规范见 `DESIGN.md`：

- 基底浅灰白 `#F7F8FA`，卡片纯白 + 1px 浅灰边
- 主色深蓝灰 `#1E3A5F`
- 语义色：安全 `emerald-600` / 可疑 `amber-600` / 威胁 `red-600` / 信息 `sky-600`
- **红色仅用于确认的威胁**，不可滥用
- 等宽字体用于文件路径、日志、版本号、IOC 特征

### 5. TypeScript 规范

- 按 `strict` 心智编写，优先复用当前作用域已声明的变量、函数、类型和导入
- 禁止隐式 `any` 和 `as any`；函数参数、返回值、解构项、事件对象、`catch` 错误
  在使用前应有明确类型或先完成类型收窄
- 清理未使用的变量和导入（`pnpm lint` 会检查）

### 6. Hydration 问题防范

- 严禁在 JSX 渲染逻辑中直接使用 `typeof window`、`Date.now()`、`Math.random()` 等动态数据
- 必须使用 `'use client'` 并配合 `useEffect` + `useState` 确保动态内容仅在客户端挂载后渲染
- 严禁非法 HTML 嵌套（如 `<p>` 嵌套 `<div>`）
- 禁止使用 `<head>` 标签，优先使用 `metadata`

### 7. 校验命令

```bash
pnpm validate    # lint + ts-check + stylelint 并行
# 或分别执行
pnpm ts-check
pnpm lint:build
pnpm lint:style
```

---

## 常见开发场景

### 添加新页面

```bash
mkdir -p src/app/new-page && touch src/app/new-page/page.tsx
```

### 创建业务组件

```bash
mkdir -p src/components/business && touch src/components/business/my-component.tsx
```

### 添加全局状态

在 `src/hooks/` 下创建自定义 Hook，避免在组件间直接传递过多 props。

---

## 技术栈

- **框架**: Next.js 16.1.1 (App Router)
- **React**: 19.2.3
- **UI 组件**: shadcn/ui (基于 Radix UI)
- **样式**: Tailwind CSS v4
- **表单**: React Hook Form 7 + Zod 4
- **图标**: Lucide React
- **图表**: Recharts
- **包管理器**: pnpm 9+（仅允许 pnpm）
- **TypeScript**: 5.9
- **SMB 后端**: 系统 `smbclient`（Samba 官方实现）

> 字体使用系统中文字体栈（PingFang SC / 微软雅黑）与系统等宽字体，未内置 Geist 字体。

---

## 参考文档

- [Next.js 官方文档](https://nextjs.org/docs)
- [shadcn/ui 组件文档](https://ui.shadcn.com)
- [Tailwind CSS 文档](https://tailwindcss.com/docs)
- [React Hook Form](https://react-hookform.com)
- [Samba smbclient 手册](https://www.samba.org/samba/docs/current/man-html/smbclient.1.html)

---

## 重要提示

1. **必须使用 pnpm** 作为包管理器
2. **优先使用 shadcn/ui 组件** 而不是从零开发基础组件
3. **遵循 Next.js App Router 规范**，正确区分服务端/客户端组件
4. **使用 TypeScript** 进行类型安全开发
5. **使用 `@/` 路径别名** 导入模块（已配置）
6. **扫描功能为只读**，不会修改被扫描目标的任何文件
7. **SMB 模式会传输账号密码**，服务应部署在受控网络内，或在前面加反向代理鉴权
