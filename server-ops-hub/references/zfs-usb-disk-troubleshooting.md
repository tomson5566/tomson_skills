# 排障总结 - ZFS USB磁盘开机不自动导入问题

## 问题现象
- 服务器重启后，`zfs list` 找不到 `storage` 池
- `/root/.openclaw` 挂载点消失，回到根文件系统
- `lsblk` 能看到磁盘分区：
  ```
  sdf         465.8G              
  ├─sdf1     465.8G zfs_member  
  └─sdf9         8M             
  sdg         298.1G             
  ├─sdg1     298.1G zfs_member  
  └─sdg9         8M
  ```

## 排查过程
1. `zpool import` 列出可导入池 → 发现 `storage` 池状态 ONLINE，可以导入
2. 确认池配置：`storage` 是由 sdf(500G) + sdg(320G) 组成的 mirror 镜像，数据完好
3. 导入后挂载点自动就是 `/root/.openclaw`，数据完整恢复

## 根本原因
- 两块磁盘都是 **USB 外接磁盘**
- 系统启动时，USB 磁盘硬件初始化速度比 ZFS 导入服务慢
- ZFS 扫描/导入时磁盘还没准备好，因此找不到磁盘，跳过导入

## 解决方案
给 ZFS 导入服务添加 10 秒启动延迟，等待 USB 磁盘就绪后再执行导入：

### 修改内容：
1. 创建 `/etc/systemd/system/zfs-import-scan.service.d/10-usb-wait.conf`
```ini
[Service]
ExecStartPre=/bin/sleep 10
```

2. 创建 `/etc/systemd/system/zfs-import-cache.service.d/10-usb-wait.conf`
```ini
[Service]
ExecStartPre=/bin/sleep 10
```

3. `systemctl daemon-reload` 重载配置生效

## 验证结果
- 手动导入后 `storage` 池正常挂载到 `/root/.openclaw`
- 数据完整，容量正确：`storage  8.13G   281G  8.13G  /root/.openclaw`
- 下次启动系统会等待 USB 就绪，应该能自动导入

## 经验总结
- USB 外接硬盘做 ZFS 必须考虑启动延迟问题
- ZFS 和普通文件系统不同，必须先 `zpool import` 才能使用
- CentOS/RHEL ZFS 默认用 `zfs-import-cache.service`，两个导入服务都要加延迟才保险
- 排障先 `zpool import`，能看到说明磁盘和数据都好，只是没导入
