# WeUnix 软件内更新发布说明

这份文档用于发布 WeUnix 桌面版更新。程序内的“检查更新”使用 Tauri 官方 updater：安装包必须经过签名，客户端会校验签名后才允许安装。

发布新版本时，请同步更新 GitHub 与 Gitee 两端 README。README 里的项目定位应保持一致：WeUnix 是面向寝室选择流程的本地桌面控制台，通过本地后端直连关键 API，减少小程序 WebView 页面加载、白屏等待和重复跳转；实测关键流程体感卡顿可降低约 82%，但实际效果受网络、设备和目标服务状态影响。

## 更新源策略

- 主源：GitHub Releases
- 备用源：Gitee 仓库中的 `latest.json`，文件内的下载地址指向 Gitee Releases 资产
- 手动兜底：程序内提供 Releases 页面入口，用户可以手动下载安装包

客户端配置的元数据地址：

```text
https://github.com/linshiqiyyds/Weunix-JLevcDormroom/releases/latest/download/latest.json
https://gitee.com/lin-seventeen/Weunix-JLevcDormroom/raw/main/latest.json
```

如果 GitHub 在国内访问失败，Tauri updater 会继续尝试 Gitee 备用端点。备用端点也不可用时，程序会显示失败原因，并引导用户打开 GitHub Releases 或 Gitee 镜像页面手动下载。

注意：Gitee 当前不等价支持 GitHub 的 `releases/latest/download/latest.json` 固定入口。更稳定的方式是在 Gitee 仓库根目录维护一份 `latest.json`，并让其中的安装包 URL 指向具体 tag 的 Gitee Release 资产。

## 私钥安全

本项目已经把 `.secrets/`、`*.key`、`*.pem` 加入 `.gitignore`。私钥只用于你本机打包签名，绝对不要提交到 GitHub，也不要发给别人。

当前本机私钥位置：

```powershell
E:\Weunix\.secrets\weunix-updater.key
```

如果私钥丢失，旧版本客户端无法信任新签名，软件内更新链路需要重新规划。

## 第一次生成签名钥匙

如果以后换机器或重新初始化，可以执行：

```powershell
cd E:\Weunix\desktop\gui
npx tauri signer generate --ci --write-keys ..\..\.secrets\weunix-updater.key
```

命令会生成：

- `.secrets\weunix-updater.key`：私钥，本地保存
- `.secrets\weunix-updater.key.pub`：公钥，可以写入 `desktop/gui/src-tauri/tauri.conf.json`

更安全的做法是给私钥设置密码，并在发布时配置 `TAURI_SIGNING_PRIVATE_KEY_PASSWORD`。

## 发布新版流程

1. 修改版本号

同时更新：

```text
desktop/gui/package.json
desktop/gui/src-tauri/tauri.conf.json
desktop/gui/src-tauri/Cargo.toml
```

2. 确认后端 exe 已更新到 Tauri resources

```powershell
cd E:\Weunix
py -3 test_all.py
```

3. 设置签名私钥环境变量

```powershell
$env:TAURI_SIGNING_PRIVATE_KEY=(Get-Content -Raw "E:\Weunix\.secrets\weunix-updater.key")
$env:TAURI_SIGNING_PRIVATE_KEY_PASSWORD=""
```

当前 Tauri build 对 updater 产物签名需要读取 `TAURI_SIGNING_PRIVATE_KEY`。只设置 `TAURI_SIGNING_PRIVATE_KEY_PATH` 可能仍然提示找不到私钥。

如果私钥有密码，把空字符串替换为你的密码：

```powershell
$env:TAURI_SIGNING_PRIVATE_KEY_PASSWORD="你的私钥密码"
```

4. 构建桌面安装包和更新产物

```powershell
cd E:\Weunix\desktop\gui
npm run build
npm run tauri:build -- --ci
```

5. 上传 Release 资产

在 GitHub Releases 新建版本，例如 `v0.2.1`，上传 Tauri 生成的安装包、签名文件和 `latest.json`。通常位于：

```text
desktop/gui/src-tauri/target/release/bundle/
```

请确认 Release 里至少包含：

- Windows 安装包，例如 `.msi`
- updater 对应 `.sig` 签名文件
- `latest.json`

本地验证时，Tauri 已生成：

```text
desktop/gui/src-tauri/target/release/bundle/msi/WeUnix_0.2.0_x64_zh-CN.msi
desktop/gui/src-tauri/target/release/bundle/msi/WeUnix_0.2.0_x64_zh-CN.msi.sig
```

如果当前 Tauri CLI 没有自动生成 `latest.json`，需要在 Release 中手动维护同名文件，内容按 Tauri v2 updater JSON 格式填写版本号、发布时间、下载地址和签名。

项目提供了一个辅助脚本，可根据 `.sig` 自动生成 `latest.json`：

```powershell
cd E:\Weunix
.\scripts\make-latest-json.ps1 `
  -Version "0.2.0" `
  -MsiUrl "https://github.com/linshiqiyyds/Weunix-JLevcDormroom/releases/download/v0.2.0/WeUnix_0.2.0_x64_zh-CN.msi" `
  -Notes "WeUnix desktop update."
```

如果当前 Windows 禁止直接运行 `.ps1`，使用下面这种方式临时绕过本次命令的执行策略限制，不会修改系统全局策略：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\make-latest-json.ps1 `
  -Version "0.2.0" `
  -MsiUrl "https://github.com/linshiqiyyds/Weunix-JLevcDormroom/releases/download/v0.2.0/WeUnix_0.2.0_x64_zh-CN.msi" `
  -Notes "WeUnix desktop update."
```

如果要生成 Gitee 镜像版本的 `latest.json`，把 `-MsiUrl` 改成 Gitee Release 里的安装包下载地址。

例如生成根目录的 Gitee 备用元数据：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\make-latest-json.ps1 `
  -Version "0.2.0" `
  -MsiUrl "https://gitee.com/lin-seventeen/Weunix-JLevcDormroom/releases/download/v0.2.0/WeUnix_0.2.0_x64_zh-CN.msi" `
  -OutputPath "latest.json" `
  -Notes "WeUnix desktop update."
```

6. 同步到 Gitee 镜像

把同一批 Release 资产同步到 Gitee 仓库 Release：`https://gitee.com/lin-seventeen/Weunix-JLevcDormroom`。`latest.json` 里的下载地址如果指向 GitHub，国内用户可能仍然下载失败；更稳的方式是让根目录的 `latest.json` 指向 Gitee 具体 tag 下的资产地址，然后提交并推送到 Gitee。

## 发布前检查

```powershell
cd E:\Weunix\desktop\gui
npm run build
cd E:\Weunix\desktop\gui\src-tauri
cargo check
cd E:\Weunix
git status --short
git grep -n -e "PRIVATE KEY" -e "BEGIN" -e "updater-private" -e "weunix-updater.key" -- .
```

最后一条命令不应该在可提交文件中看到私钥内容。如果只在文档里看到本地私钥路径，是正常的。

## 用户侧体验

- 有新版本：设置页会显示新版本号，可以下载并安装
- 已是最新：设置页会显示“已是最新”
- GitHub 不通：程序会继续尝试 Gitee 镜像
- 两个源都失败：显示可读错误，并提供“手动下载”入口
- 安装完成：提示重启 WeUnix 后生效
