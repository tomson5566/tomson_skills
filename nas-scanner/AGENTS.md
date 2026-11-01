# 项目上下文

### 版本技术栈

- **Framework**: Next.js 16 (App Router)
- **Core**: React 19
- **Language**: TypeScript 5
- **UI 组件**: shadcn/ui (基于 Radix UI)
- **Styling**: Tailwind CSS 4

## 目录结构

```
├── public/                 # 静态资源
├── scripts/                # 构建与启动脚本
│   ├── build.sh            # 构建脚本
│   ├── dev.sh              # 开发环境启动脚本
│   ├── prepare.sh          # 预处理脚本
│   └── start.sh            # 生产环境启动脚本
├── src/
│   ├── app/                # 页面路由与布局
│   ├── components/ui/      # Shadcn UI 组件库
│   ├── hooks/              # 自定义 Hooks
│   ├── lib/                # 工具库
│   │   └── utils.ts        # 通用工具函数 (cn)
│   └── server.ts           # 自定义服务端入口
├── next.config.ts          # Next.js 配置
├── package.json            # 项目依赖管理
└── tsconfig.json           # TypeScript 配置
```

- 项目文件（如 app 目录、pages 目录、components 等）默认初始化到 `src/` 目录下。

## 项目业务说明

本项目是「NAS 勒索软件威胁扫描器」，核心代码位置：

```
src/lib/scanner/
├── signatures.ts    # 勒索软件 IOC 特征库（C3RB3R/L0CK3D、SynoLocker、DeadBolt 等家族）
├── entropy.ts       # Shannon 熵值计算（识别被加密文件）
├── providers.ts     # 文件系统抽象：LocalProvider（本机目录）/ SmbProvider（@awo00/smb2 远程 NAS）
├── engine.ts        # 扫描引擎：异步生成器产出 SSE 事件（progress/finding/log/done/error）
├── dsm.ts           # DSM 版本解析与漏洞比对（Synology-SA-26:13 修复基线）
└── nas-script.ts    # 生成群晖端定时巡检 shell 脚本

src/app/api/
├── scan/route.ts        # POST SSE 流式扫描（body: mode=local|smb + 连接参数）
├── dsm-check/route.ts   # POST DSM 版本漏洞比对（body: { version }）
├── nas-script/route.ts  # GET 下载巡检脚本
└── signatures/route.ts  # GET 威胁特征库

src/components/scanner/
├── scan-panel.tsx       # 主面板：扫描配置 + SSE 进度 + 报告（client component）
└── dsm-checker.tsx      # DSM 版本自检 + 脚本下载（client component）
```

- 新增勒索软件家族特征：只改 `signatures.ts` 的 `RANSOMWARE_FAMILIES`
- 新增 DSM 漏洞修复基线：只改 `dsm.ts` 的 `FIXED_VERSIONS`
- 演示目录：`/tmp/mock-nas`（模拟受感染 NAS，本地模式可直接扫）

## 包管理规范

**仅允许使用 pnpm** 作为包管理器，**严禁使用 npm 或 yarn**。
**常用命令**：
- 安装依赖：`pnpm add <package>`
- 安装开发依赖：`pnpm add -D <package>`
- 安装所有依赖：`pnpm install`
- 移除依赖：`pnpm remove <package>`

## 开发规范

### 编码规范

- 默认按 TypeScript `strict` 心智写代码；优先复用当前作用域已声明的变量、函数、类型和导入，禁止引用未声明标识符或拼错变量名。
- 禁止隐式 `any` 和 `as any`；函数参数、返回值、解构项、事件对象、`catch` 错误在使用前应有明确类型或先完成类型收窄，并清理未使用的变量和导入。

### next.config 配置规范

- 配置的路径不要写死绝对路径，必须使用 path.resolve(__dirname, ...)、import.meta.dirname 或 process.cwd() 动态拼接。

### Hydration 问题防范

1. 严禁在 JSX 渲染逻辑中直接使用 typeof window、Date.now()、Math.random() 等动态数据。**必须使用 'use client' 并配合 useEffect + useState 确保动态内容仅在客户端挂载后渲染**；同时严禁非法 HTML 嵌套（如 <p> 嵌套 <div>）。
2. **禁止使用 head 标签**，优先使用 metadata，详见文档：https://nextjs.org/docs/app/api-reference/functions/generate-metadata
   1. 三方 CSS、字体等资源可在 `globals.css` 中顶部通过 `@import` 引入或使用 next/font
   2. preload, preconnect, dns-prefetch 通过 ReactDOM 的 preload、preconnect、dns-prefetch 方法引入
   3. json-ld 可阅读 https://nextjs.org/docs/app/guides/json-ld

## UI 设计与组件规范 (UI & Styling Standards)

- 模板默认预装核心组件库 `shadcn/ui`，位于`src/components/ui/`目录下
- Next.js 项目**必须默认**采用 shadcn/ui 组件、风格和规范，**除非用户指定用其他的组件和规范。**
