# 已知问题与验证边界

## 基础 HA 镜像的 AWS CRT 导入异常

在隔离容器中观察到进程退出码 134。Python 栈位于 awscrt 导入，原生调用栈定位到 _awscrt.abi3.so 的 tree_jitter_get_root_seed 和 tree_jitter_initialize_once；组件版本为 awscrt 0.36.1。

对照：不安装本集成、不安装 DDS、不加载任何自定义原生库、不访问网关，仅在原始 HA 镜像导入 homeassistant.components.http.server，也复现相同退出。此前部分基线尝试成功，因此属于间歇性环境问题，不能简单归因为内存限额或 DDS。

同名 AWS-LC 源码中包含熵采集失败时的 abort 分支，但目前没有取得实际熵采集错误码，不对具体失败原因作进一步结论。参考：https://github.com/aws/aws-lc/blob/main/crypto/fipsmodule/rand/entropy/tree_drbg_jitter_entropy.c 。

本项目没有禁用随机数健康检查、替换 AWS 依赖或调整运行中的 HA 来规避问题。需要在受支持基础环境中继续做稳定性验证。通过的一次测试不能抵消这一已复现现象。

证据：ha-baseline-repeat.json（无 DDS 的对照）、import-order-probe.json（原生栈）、wheel-ha-debug.json（通过的一次独立实体检查）。

为隔离这个问题，配置条目测试夹具在没有配置云服务的临时 HA 中使用 botocore 的可选 CRT 回退（测试进程将 awscrt 标为不可用）。该措施只存在于测试工具，未加入集成或修改现用 HA。`config-entry-real-dds.json` 记录在这个前提下真实 DDS 的加载、状态、重载和卸载结果，不代表基础镜像的原生 SDK 异常已解决。

## DDS 打包基线

完整开发分支的 Python 绑定曾引用稳定 C 库没有导出的 dds_set_trace_sink。已改为配套稳定 11.0.1 源码，仅回移上游 Python 3.14 兼容补丁。当前候选版本为 11.0.1+homycloud.2，旧的 .1 构建不应安装。

新 wheel 已通过独立安装、消息类型构建、本地只读查询和 HA config/deps 加载检查。基础镜像的 AWS CRT 异常单独记录，不能将其误称为本集成已经解决的故障。

## 发布范围

当前 wheel 仅验证 CPython 3.14 / aarch64 / musllinux 1.2。固定输入与构建步骤已提供，尚未进行两次独立构建的字节级摘要比较；不声称已证明字节级可复现。

manifest 的 requirements 仍为空。正式安装源、升级策略、实体迁移、回滚和全部真机控制验证尚未完成，当前不自动替换现用服务。
