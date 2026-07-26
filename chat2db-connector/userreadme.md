# Chat2DB Connector 使用说明

一个 Windows 小工具，一键连上公司的 Chat2DB 数据库管理平台。
连上之后浏览器会自动打开 Chat2DB 界面，关掉就断线。

---

## 三步上手

### 第 1 步：生成 SSH 密钥（一次性操作）

按下 `Win` 键，搜 **PowerShell**，打开后**复制粘贴下面这一行**，按回车：

```
ssh-keygen -t ed25519 -f $env:USERPROFILE\.ssh\id_ed25519
```

会问你几个问题，**一路按回车，不要输任何东西**。

看到类似这样的输出就成功了：

```
Your identification has been saved in C:\Users\你的名字\.ssh\id_ed25519
Your public key has been saved in C:\Users\你的名字\.ssh\id_ed25519.pub
```

你会得到两个文件：

| 文件 | 谁拿 | 干啥 |
| --- | --- | --- |
| `id_ed25519` | **你自己留** | 私钥，千万别发给别人 |
| `id_ed25519.pub` | **发给管理员** | 公钥，管理员会装到服务器 |

**用记事本打开 `id_ed25519.pub`，全选复制，发给管理员**。等他回复"好了"再进下一步。

---

### 第 2 步：拿到程序

管理员会把 `Chat2DBConnector.exe` 发给你。把它放到桌面或者任意一个文件夹里，**双击**。

---

### 第 3 步：填配置 + 连接

程序打开后照着填：

| 字段 | 填什么 |
| --- | --- |
| Host | `192.168.0.197` |
| Port | `22` |
| User | `vscode` |
| Private key | 点右边的 **Browse…**，选 `C:\Users\你的用户名\.ssh\id_ed25519` |
| Local port | `10825` |
| Remote host | `127.0.0.1` |
| Remote port | `10825` |
| URL path | 留空（如果浏览器打开后 404 就填 `/chat2db`） |

填完先点 **Save config**（只填一次，下次自动记住），再点 **Connect**。

等几秒，看到日志里出现 `隧道已就绪` 或者浏览器自己弹出来，就成功了 ✅。

**用完点 Disconnect 或者直接关窗口。**

---

## 常见问题

### 🔴 弹窗 "Key file not found"

私钥路径错了。点 **Browse…** 重新选，或者确认第 1 步真的成功了（去 `C:\Users\你的名字\.ssh\` 看下文件在不在）。

### 🔴 日志里 "Auth failed"

私钥和服务器对不上。**联系管理员**，把你的公钥重新发给 TA 装一次。

### 🔴 日志里 "Local port 10825 already in use"

之前开过没关，或者别的程序占着这个端口。

- 先关掉之前那个 Chat2DB Connector 窗口
- 实在不行重启电脑
- 或者在 GUI 里把 **Local port** 改成 `10826`（其他什么都不用改）

### 🔴 浏览器打开了但显示 404 / 空白

Chat2DB 的根路径可能不是 `/`。在 GUI 里找到 **URL path** 那栏，填 `/chat2db`，**Save config** 后再连一次。

### 🟡 杀毒软件报警 / 拦截

正常现象，PyInstaller 打的 exe 经常被误报。

- 右键 exe → 属性 → 勾选"解除锁定" → 确定
- 在杀毒软件里把这个 exe 加白名单

### 🟡 启动很慢（黑屏 5~10 秒）

正常，第一次解压要时间，别关掉，耐心等。

---

## 完全卸载

1. 删除 `Chat2DBConnector.exe`
2. 删除 `C:\Users\你的名字\.chat2db-connector\` 文件夹（你的配置存在这里）
3. 联系管理员从服务器删掉你的公钥（这一条可做可不做，不删别人也用不了你的私钥，只是占个位）

---

## 找谁

- 连不上 / 报错 / 配置问题 → 找 **发给你 exe 的那个同事**
- Chat2DB 本身怎么用 → 问 **Chat2DB 用户群**
- 服务器挂了 / IP 变了 → 找 **运维 / 网管**
