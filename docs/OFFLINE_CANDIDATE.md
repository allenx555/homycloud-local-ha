# 离线开发候选包

这份包用于独立测试和安装前审阅，不会自动安装、覆盖配置、启用控制或迁移实体。它不是 HACS 正式发行包。原生依赖当前仅验证 CPython 3.14 / Linux aarch64 / musllinux 1.2。

## 内容与完整性

包内含集成代码、协议说明、虚构清单示例、校验工具、兼容 DDS wheel 和离线 pip 启动 wheel。家庭设备清单、partition、网络地址、凭据、抓包及测试日志均不打包。

在仓库根目录生成和核对：

```text
python tools/build_candidate.py --output local/releases/homycloud-0.2.0-dev.zip
python tools/build_candidate.py --verify local/releases/homycloud-0.2.0-dev.zip
```

输出路径必须不存在，避免覆盖已有候选包。文件时间、顺序和文本换行固定；对同一组输入重复打包应得到相同 SHA256。这不代表原生 wheel 已通过两次独立编译的字节级可复现验证。

`bundle-manifest.json` 列出包内各文件的大小和 SHA256，用于检出意外改动。整个 ZIP 的 SHA256 应另行从可信交付记录核对；内部清单本身不提供数字签名或来源认证。

## 独立环境验证

以下步骤仅在与目标架构一致的临时 HA Container 环境中执行，使用空白、可丢弃的配置目录。依赖路径需由实际 Python 版本计算，不能把开发机器上的路径直接复制到 HA。

1. 解压到独立目录，不向现用 HA 解压。
2. 在目标 HA 的 Python 环境运行 `tools/runtime_install_plan.py`，传入 `--wheel`、`--sha256` 和临时 `--ha-config`。它验证 wheel、平台标签，并报告该配置目录下的依赖路径，**不执行安装**。
3. 按报告路径，把 DDS 安装到临时配置的空依赖目录：

   ```sh
   PYTHONPATH=bootstrap/pip-26.2.2-py3-none-any.whl python -m pip install \
     --no-index --no-deps --no-compile --target /temporary/config/deps/lib/python3.14/site-packages \
     wheels/cyclonedds-11.0.1+homycloud.2-cp314-cp314-musllinux_1_2_aarch64.whl
   python tools/verify_ha_deps.py --ha-config /temporary/config
   ```

   上述路径只是示例，应使用第 2 步计算结果。验证应在没有额外 DDS 导入路径和 `CYCLONEDDS_HOME`、`LD_LIBRARY_PATH` 覆盖的新进程中运行。
4. 把 `custom_components/homycloud_local` 放到临时 HA 配置的 `custom_components` 目录，另行准备私有清单。在“设备与服务”添加 HomyCloud，保持控制关闭，检查状态、重载与卸载。

依赖放在配置目录下可避免仅写入容器临时层，但不保证跨 Python 大版本或 CPU/系统架构升级兼容。升级后应重新核对 wheel 标签与依赖路径。

正式迁移仍需备份配置、注册表和引用，制定回滚方案，并分阶段进行设备控制实测。当前候选包没有自动安装器或迁移执行器。
