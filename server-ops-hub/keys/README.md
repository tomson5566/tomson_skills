# keys/ — SSH 密钥池（多设备免密密钥统一托管）

本目录集中存放所有用于服务器免密登录的 SSH 密钥对，**随 skill 目录一起迁移**：
把整个 `server-ops-hub/` 目录拷到新机器，密钥即随之可用。

多台设备的密钥全部汇聚到本目录统一管理；每个密钥的**来源设备、指纹、备注**
登记在 `index.json`（由管理命令自动维护，勿手改）；服务器侧的多密钥绑定
关系存于 `config/servers.json` 各档案的 `auth.key_names`。

## 权限要求（脚本会自动设置，手工放入时请自查）

- 本目录：`700`
- 私钥文件（如 `default`）：`600`
- 公钥文件（如 `default.pub`）：`644`

## 管理命令

```bash
../scripts/key-manage.sh list                      # 密钥池总览（来源设备/绑定关系）
../scripts/key-manage.sh generate default          # 生成新密钥对
../scripts/key-manage.sh import default ~/.ssh/id_ed25519   # 导入已有私钥
../scripts/key-manage.sh import-all ~/.ssh --device 笔记本  # 批量导入某设备全部私钥
../scripts/key-manage.sh bind <host> --key default          # 绑定密钥到服务器（可绑多个）
../scripts/key-manage.sh deploy <host> --key default        # 部署公钥到服务器
../scripts/key-manage.sh deploy-all <host>                  # 部署密钥池全部公钥到服务器
```

## 安全提示

- 私钥为敏感资产，不要把本目录提交到任何 git 仓库
- 迁移打包件（tar.gz/.skill）内含私钥，传输请加密
