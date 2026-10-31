# 按 tag 自动发布

推送版本 tag 会触发 `.github/workflows/release.yml`。工作流先执行源码测试和打包，再创建草稿 Release、上传并校验附件，最后发布。失败时不会把不完整附件作为正式 Release 发布。

## 发布命令

先把改动提交并推送到仓库，再在该提交上打 tag：

```sh
git push origin main
git tag v0.2.2
git push origin v0.2.2
```

tag 必须以 `v` 开头并带完整三段版本号。例如 `v0.2.2` 发布正式版本，`v0.2.3-rc.1`、`v0.2.3-beta.1`、`v0.2.3-dev.1` 发布预发布版本。不要移动已经发布的 tag；修复后使用新版本号。

包内 `manifest.json` 的版本号取自 tag，并规范化为 HA 使用的 Python 版本格式，例如 `v0.2.3-rc.1` 对应 `0.2.3rc1`。工作流不会向源码分支回写版本号。

## Release 附件

- `homycloud_local.zip`：集成目录的内容，包含代码、协议结构、翻译和图标。
- `SHA256SUMS`：ZIP 和发布清单的 SHA256。
- `release-manifest.json`：版本、tag、源码提交、包内文件列表与摘要。

手动安装时，应将 ZIP 内容解压到 HA 配置目录的 `custom_components/homycloud_local/`，不要直接解压到配置根目录。已有私有设备清单不在发布包中。

这个组件 ZIP 不包含 CycloneDDS 原生依赖，也不是包含运行时的一键安装包。新安装仍需准备匹配 HA Python、CPU 和系统的兼容 wheel，参见 [依赖构建说明](../packaging/BUILDING.md) 和 [离线候选包说明](OFFLINE_CANDIDATE.md)。已有兼容运行时可以继续使用，不必为每个集成 tag 重编译 DDS。

## 检查与重跑

普通 `main` 提交、PR 和手动运行也会执行测试和打包，并保留 14 天的 Actions 构建附件，但不会创建 Release。因此可以先确认分支上的打包检查成功，再推送版本 tag。

同一 tag 重跑时，可以补全未发布的草稿。如果已经发布，则只核对附件摘要；摘要不同会失败，不覆盖已发布内容。

Release 发布使用 GitHub 自动提供的 `GITHUB_TOKEN`，只给发布 job `contents: write` 权限，不需要另建个人 Token。仓库需要允许 GitHub Actions 运行；组织策略仍可能限制写权限。

本地复现打包：

```sh
python -m pip install packaging==25.0
python tools/build_release.py --tag v0.2.2 --output local/release-check
```

输出目录必须不存在。这个命令只生成本地文件，不上传、创建 tag 或发布 Release。

参考：[GitHub 工作流触发方式](https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/trigger-a-workflow)。
