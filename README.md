# HomyCloud

<img src="custom_components/homycloud_local/brand/icon.png" alt="HomyCloud" width="96">

**宏云智能 · Home Assistant 本地集成**

通过 DDS 与宏云原网关直接通信，让 Home Assistant 读取、控制设备，无需将宏云设备重新配对，也不通过 MQTT 转发。

> 开发测试版 `0.2.1-dev`。六类实体和控制反馈逻辑已实现，默认只读。正式安装发布、完整迁移及设备逐项实测尚未完成，当前不能视为可直接安装的正式版本。

## 名称

| 用途 | 名称 |
| --- | --- |
| Git 项目目录／仓库 | `homycloud-local-ha` |
| HA 内部标识与集成目录 | `homycloud_local` |
| HA 界面显示名称 | **HomyCloud** |
| 中文说明 | 宏云智能 |

## 工作方式

```text
Home Assistant
  └─ HomyCloud 自定义集成
       └─ CycloneDDS
            └─ 宏云原网关 → 原配设备
```

DDS 初始化、查询、消息读取和原生资源清理在后台线程进行；HA 事件循环接收状态快照。没有控制权限时不创建控制消息发送端。启用控制后，命令有参数校验、反馈匹配和超时处理，不在断线重连后重放旧命令。

## 协议依据

参考宏云智家客户端（`com.homycloud.iot`）中的设备字段和控制流程，并结合网关 DDS 发现、报文及设备反馈核对。本集成实际通过局域网 DDS 通信，不使用宏云云端 API、账号或 Token。

字段与验证范围见 [协议依据](docs/PROTOCOL.md)。官方客户端行为可作为参考，但不等于这些接口是厂家承诺长期兼容的公开 API。

## 设备映射

当前开发依据为 CT-105H/WH-PL 网关及已观察到的协议；不代表所有宏云网关、固件或设备均兼容。

| HA 平台 | 功能 |
| --- | --- |
| Switch | 灯路、空调、新风、地暖电源 |
| Cover | 开、关、暂停、百分比；可在设备清单设置位置反向 |
| Climate | 根据实际能力提供电源、目标温度、模式、风速 |
| Sensor | 温度及原生状态 |
| Number | 带范围和步长校验的数值设置 |
| Select | 枚举设置 |

该表说明已完成代码映射，**不等于每项能力均已实机执行验证**。缺少目标温度、模式或风速反馈的面板不会凭空增加对应能力；原网关返回的窗帘百分比也不等于已做位置校准。

## 已完成的验证

- 在 aarch64/musl、Python 3.14 环境中加载修复后的 DDS，构建网关使用的四种消息类型。
- 新客户端通过真实网关的多设备只读查询验证；不创建控制 writer。
- 独立 HA 环境通过真实网关读取状态，完成配置流程、六类实体注册、重载和卸载；状态类型检查通过，默认只读控制被拒绝，后台错误为零。
- 修复 Number 实体的属性命名冲突，并保证确认后的状态快照先于控制调用返回；用人为延迟快照的模拟测试验证顺序。
- 模拟 DDS 测试空调先开电源再设置模式、风速映射、反馈超时不重试，以及卸载时结束待处理命令。
- 单元测试覆盖状态乱序、窗帘位置正反向、长行程反馈、命令类型、私密字段隔离及迁移计划。

真实网关的验证保持只读。模拟控制通过不等于原生集成已对所有设备完成控制实测。证据见 [docs](docs/)。

## 安装与运行条件

**当前没有正式发布的一键安装包，请勿直接覆盖现用 HA。** 已生成自带 DDS 原生库的开发 wheel，当前验证目标为 CPython 3.14 / aarch64 / musllinux 1.2。其他平台仍需单独构建。

已验证的开发环境：HA 2026.10.4／Python 3.14.9／aarch64／musl。同一局域网中需能与网关交换 DDS 发现与数据报文；跨子网及其他 CPU 平台尚未验证。

DDS 使用配套的 11.0.1 稳定版 C 库和 Python 绑定，仅回移上游 PR #323、#327 的 Python 3.14 运行时兼容修复。固定输入的构建流程见 [DDS 构建说明](packaging/BUILDING.md)；wheel 已通过独立安装和 HA `config/deps` 加载验证，正式安装与版本升级方案仍待完成，二进制不进入本仓库。manifest 的 requirements 暂为空，避免自动安装已知不兼容的正式版本。

隔离测试发现的基础镜像兼容性现象及验证边界见 [已知问题](docs/KNOWN_ISSUES.md)。

已提供 [离线开发候选包说明](docs/OFFLINE_CANDIDATE.md)：包含集成、DDS wheel、离线 pip 和逐文件校验清单，排除家庭私有配置。打包与核对工具不执行安装，也不迁移现有实体。

## 开发者验证流程

1. 在独立环境准备已验证的 DDS 运行依赖，先验证导入与消息类型构建。
2. 将私有设备清单保存在仓库忽略目录或 HA 的私有配置目录；格式参考 [示例](examples/inventory.example.json)。
3. 运行只读查询：

   ```text
   python tools/readonly_probe.py --inventory /private/path/inventory.json --seconds 15
   ```

4. 准备好依赖后才将 `custom_components/homycloud_local` 放入测试 HA；在“设备与服务”添加 **HomyCloud**，指定清单路径，保持“启用设备控制”关闭。
5. 对照旧桥状态和实体引用，再按迁移计划逐项验证。完整迁移前不要删除旧桥或 MQTT 发现记录。

真实清单可从原桥配置提取，导出工具会去掉 MQTT 凭据，并拒绝覆盖已有文件：

```text
python tools/export_inventory.py --bridge-config /private/bridge-config.json --output /private/inventory.json
```

开发版可以在集成选项中显式启用控制。只读模式保留设备实体供观察，但操作服务会报“控制未启用”；不会假装操作成功。

## 配置与隐私

温度传感器默认使用摄氏度（℃），仍可在 HA 的实体设置中按需覆盖。集成图标随 `brand/icon.png` 一起安装，使用 [HA 的本地品牌资源支持](https://contributors.home-assistant.io/core/integrations/brands/)。

- `partition`：家庭私有 DDS 分区。
- `dds_xml`：DDS 网络配置；需对应 HA 实际运行环境，不能盲目沿用仅在旧容器中存在的路径。
- `devices`：设备 ID、名称、已确认能力及查询字段。窗帘可使用 `invert_position: true` 同时反转显示位置和位置命令，暂停命令保持原样。

真实 partition、设备 ID、房间、网络设置及密码不应进入公共仓库。`local/`、`.private/` 已被 Git 忽略。`schemas.json` 仅包含协议消息结构。

## 迁移与回滚

原 MQTT 实体与新集成的平台不同，即使 unique_id 相同也不会自动变成原实体。应先备份设备与实体注册表，保存用户名称、区域、标签、实体 ID，并核对仪表盘、定时自动化和脚本。

只读计划工具不会连接 HA 或修改注册表：

```text
python tools/plan_migration.py --inventory /private/inventory.json --entity-registry /private/core.entity_registry --output /private/migration-plan.json
```

计划标记可匹配项、缺失项和已有原生实体冲突，并保留用户元数据。它目前不执行迁移；设备注册表的合并、引用检查、实际迁移和完整回滚工具仍待实现。

## 测试

无需 HA 的本地测试：

```powershell
python -m unittest discover -s tests -v
python -m compileall -q custom_components tools tests
```

需要 HA 的 worker 测试会在普通 Python 中跳过；在独立 HA Python 环境中运行同一命令即可执行。这些写入测试使用模拟 DDS，不操作实际设备。

## 后续工作

[ROADMAP.md](ROADMAP.md) 记录剩余事项，重点是依赖打包、重连与资源释放测试、迁移回滚，以及分阶段真机验证。当前仍为开发候选版本。
