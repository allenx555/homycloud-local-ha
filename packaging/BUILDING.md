# DDS 原生 wheel 构建

当前构建目标是 CPython 3.14、Linux aarch64、musl 1.2。其他平台需要单独构建和验证，不能通过改文件名或 wheel 标签获得兼容性。

## 构建输入

`inputs.lock.json` 固定基础镜像摘要、上游源码、Alpine 包和 Python 构建工具的版本、来源与 SHA256。Python 输入 wheel 已与 PyPI 官方元数据中的摘要核对；Alpine 包由基础镜像的受信密钥验证签名，不使用 allow-untrusted。

`tools/prepare_build_inputs.py` 下载或读取缓存、核对摘要，并生成离线 Docker 构建上下文。缓存不匹配会报错而不会替换文件；输出目录必须是新目录。APK 和 wheel 打包顺序、权限和时间戳固定。

```text
python tools/prepare_build_inputs.py --cache local/build-cache --output local/build-context
```

已有完整缓存时可以追加 `--offline`。网络需要代理时可显式传入 `--proxy`，不会把代理写进产物。

## 构建

以下命令在支持目标架构的 Docker 环境执行。基础镜像需要预先准备；编译容器运行时完全断网，不挂载 HA 配置或家庭清单。

```sh
mkdir -p local/wheels
docker build --network none --pull=false -t homycloud-dds-builder local/build-context
docker run --rm --network none --cpus 2 --memory 768m \
  --mount type=bind,src="$PWD/local/wheels",dst=/build/wheels \
  homycloud-dds-builder
```

`build-wheel.sh` 从源码编译 libddsc 与 Python 扩展，使用上游 standalone wheel 支持，再通过 auditwheel 打包原生依赖并检查 musllinux 标签。未使用 auditwheel 的 --strip，以避免对修补后 ELF 再次 strip 的已知问题。

构建使用 Release/O2/NDEBUG，关闭高开销的链接时优化（LTO），并固定 SOURCE_DATE_EPOCH。锁定流程不等于已经证明字节级可复现；在完成两次独立构建摘要比较前，不作这一声明。

## 版本与来源

Python 绑定与 C 库均使用 11.0.1 稳定基线。仅回移上游 PR #323、#327 中 cyclonedds/ 目录内的 Python 3.14 注解及继承类型修复，原生扩展源码保持稳定版不变。wheel 采用 PEP 440 本地版本 `11.0.1+homycloud.2`，用于区分本项目兼容构建与上游正式发行包，保留上游元数据和许可文本。

兼容性回移、本地版本号与许可证收录均记录在构建输出 packaging-patches.json 中；不复制旧的原生扩展或旧 libddsc 作为构建产物。

## 产物验证

必须在全新容器中验证，且不挂载旧依赖目录：

1. 从 wheel 安装到独立目录，清空 CYCLONEDDS_HOME、LD_LIBRARY_PATH 和旧的 PYTHONPATH。
2. 确认 ctypes 加载的 libddsc 位于 wheel 安装目录，四种消息类型能够构建。
3. 只读查询测试网关，确认没有创建控制 writer。
4. 再做 HA 实体与后台启动/卸载检查。

通过后才考虑设置正式安装 requirements。当前产物不会自动安装到运行中的 HA；公开发布方式、升级路径与迁移仍需单独完成。构建输出只留在被 Git 忽略目录，不提交二进制。


不直接使用完整开发分支绑定的原因：独立安装检查发现其新日志接口依赖稳定 C 库未导出的符号。当前使用稳定基线加精确上游兼容补丁，避免混用不同原生接口。
