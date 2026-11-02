# HomyCloud

<img src="custom_components/homycloud_local/brand/icon.png" alt="HomyCloud" width="96">

**宏云智能 · Home Assistant 本地集成**

通过局域网 DDS 与宏云原网关直接通信，在 Home Assistant 中读取和控制原配设备。无需重新配对，不依赖 MQTT 或独立桥接容器，也不使用宏云云端 API、账号或 Token。

当前版本 **0.3.0**，为首个公开发布版本。已在实际 HA 环境中部署并完成原 MQTT 接入迁移；支持六类实体。不同网关、固件和设备的兼容性仍需验证，发布版本号不代表所有设备功能均已完成现场测试。

## 功能与兼容范围

当前开发依据为 **CT-105H/WH-PL** 网关及已观察到的设备协议。

| HA 平台 | 功能 |
| --- | --- |
| Switch | 灯路、空调、新风、地暖电源 |
| Cover | 开、关、暂停、百分比；支持在设备清单中反转位置方向 |
| Climate | 按设备实际能力提供电源、目标温度、模式和风速 |
| Sensor | 温度及原生状态；温度默认摄氏度（℃） |
| Number | 带范围与步长校验的数值设置 |
| Select | 枚举设置 |

- 默认**只读**，需要在添加集成或集成选项中开启“启用设备控制”后才能操作。
- 命令具有参数校验、反馈匹配和超时处理；确认后的状态先更新到 HA，再结束等待。断线重连不会重放旧命令。
- 缺少反馈的设备能力不会凭空补全；部分空调模式、风速和设定值仍可能不被设备接受。
- 窗帘百分比依赖网关反馈及设备行程校准，开合方向可通过 `invert_position` 调整。
- 倒计时、每日定时可通过 HA 自动化或辅助元素实现，不属于网关原生定时功能，本集成不会自动创建这些自动化。

## 安装前准备

HACS 负责安装和更新**集成文件**。首次接入还需要以下条件，完成下面四步安装并不等于设备已配置好：

1. **兼容的 CycloneDDS 运行时**：目前已验证 HA 2026.10.4／Python 3.14／aarch64／musl。配套开发 wheel 的构建方法见 [DDS 构建说明](packaging/BUILDING.md)。Release ZIP 不包含 wheel，manifest 的 `requirements` 暂为空，不会自动安装 DDS；其他平台需单独构建和验证。
2. **局域网通信**：HA 应能与网关交换 DDS 发现和数据报文；使用容器时需配置支持这些报文的网络。跨子网通信尚未验证。
3. **私有设备清单**：需要正确的家庭 DDS `partition`、网络配置与设备字段；本版本尚不支持自动发现或从宏云账号自动导入。结构参考 [inventory.example.json](examples/inventory.example.json)，示例中的占位值不能直接使用。

### 通过 HACS 安装（推荐）

1. 打开 HACS → 集成 → 右上角菜单 → 自定义存储库（新版 HACS 可直接从主页面右上角菜单进入）
2. 添加本仓库地址 `https://github.com/allenx555/homycloud-local-ha`，类别选「集成」
3. 搜索「HomyCloud」并下载／安装
4. 重启 Home Assistant

本仓库通过 HACS **自定义存储库**安装，未声称已收录到 HACS 默认商店。HACS 使用 Release 附件 `homycloud_local.zip`，后续可在 HACS 中更新集成文件；已有兼容 DDS 运行时可继续使用。

### 手动安装

1. 从 [Releases](https://github.com/allenx555/homycloud-local-ha/releases) 下载 `homycloud_local.zip`。
2. 将 ZIP 内容解压到 HA 配置目录下的 `custom_components/homycloud_local/`，确保该目录内直接包含 `manifest.json` 和 `__init__.py`。
3. 重启 Home Assistant。

升级前请备份配置；不要把私有设备清单放进 `custom_components/homycloud_local/`，避免更新时被替换。

### 添加集成与启用控制

1. 将私有清单保存为 HA 配置目录下的 `homycloud_local/inventory.json`。这是配置目录中的独立文件夹，与 `custom_components/homycloud_local/` 区分。
2. 打开 **设置 → 设备与服务 → 添加集成 → HomyCloud**。
3. 填写清单路径，默认 `homycloud_local/inventory.json`；先保持控制关闭，核对实体和状态。
4. 确认后进入集成选项，开启“启用设备控制”。若操作报 `HomyCloud is read-only; device control is disabled`，请检查这个选项。
5. 在 HA 的设备和实体设置中调整名称、区域；仪表盘若手动写了卡片标题，需单独修改该标题。

### 将已有定时项归到空调设备

如果已用 YAML 辅助实体和脚本实现本地定时，可在对应设备的私有清单中添加 `schedule_entities`：

```json
"schedule_entities": [
  "input_datetime.example_ac_daily_on",
  "input_boolean.example_ac_daily_on",
  "input_number.example_ac_minutes",
  "timer.example_ac",
  "script.example_ac_start",
  "script.example_ac_cancel"
]
```

填写真实存在的实体 ID 后重新加载集成。这些实体会关联到对应设备并归为“配置”，在设备页集中显示，减少自动概览中的零散辅助项；显式仪表盘卡片仍可正常使用。关联在启动和辅助实体重载后自动核对。

此功能不创建定时任务，不更改实体 ID、名称、时间、启用状态或自动化逻辑，也不会接管已属于其他设备或配置条目的实体。目前支持 YAML 定义的 `input_datetime`、`input_boolean`、`input_number`、`timer` 和 `script`。如曾手动收藏，仍可在概览中取消收藏。

## 工作方式与协议依据

```text
Home Assistant
  └─ HomyCloud 自定义集成
       └─ CycloneDDS
            └─ 宏云原网关 → 原配设备
```

DDS 初始化、查询、读取和资源清理在后台线程进行，HA 事件循环接收状态快照。只读模式不创建控制消息发送端。

本项目参考宏云智家客户端（`com.homycloud.iot`）的设备字段和控制流程，并结合网关报文及设备反馈核对。使用的是局域网协议，不是厂家承诺长期兼容的公开云端 API，也不是官方出品。字段来源与验证边界见 [协议依据](docs/PROTOCOL.md)。

## 当前验证与限制

- 已在实际 HA 环境加载 DDS、注册六类原生实体并读取网关状态，完成原 MQTT 接入迁移；原生运行不再需要旧桥或 MQTT Broker。
- 已验证配置流程、控制选项、重复添加拦截、重载与卸载；控制反馈顺序、空调命令顺序、超时和资源清理有模拟测试覆盖。
- 部分真实控制已取得网关状态反馈，但设备现场动作、所有空调枚举和窗帘行程尚未逐项完成验证。状态反馈不等于现场动作已被观察确认。
- 当前 DDS wheel 仅验证 CPython 3.14／aarch64／musllinux 1.2；尚无自动依赖分发和完整多平台安装方案。
- 历史基础镜像异常与 DDS 构建边界见 [已知问题](docs/KNOWN_ISSUES.md)，后续事项见 [ROADMAP.md](ROADMAP.md)。

## 配置与隐私

私有清单中的主要字段：

| 字段 | 用途 |
| --- | --- |
| `partition` | 家庭私有 DDS 分区 |
| `dds_xml` | 与实际运行环境匹配的 DDS 网络配置 |
| `devices` | 设备 ID、名称、能力及查询字段 |
| `invert_position` | 窗帘实体配置项；同时反转显示位置和位置命令，暂停命令保持原样 |

真实 partition、设备 ID、房间、网络设置、密码和抓包不应提交到公共仓库。`local/`、`.private/` 已被 Git 忽略，发布包也不包含家庭私有清单。协议 `schemas.json` 仅包含消息结构。

## 从旧 MQTT 桥迁移

新集成不会自动接管旧 MQTT 实体的名称、区域和仪表盘引用。迁移前需备份设备／实体注册表，并核对实体 ID、自动化、脚本和仪表盘。完成验证后再删除旧桥、旧 MQTT 发现记录；只有确认其他设备也不使用 MQTT，才能删除 MQTT 集成与 Broker。

仓库提供只读辅助工具，不会自动修改 HA：

```sh
python tools/export_inventory.py --bridge-config /private/bridge-config.json --output /private/inventory.json
python tools/plan_migration.py --inventory /private/inventory.json --entity-registry /private/core.entity_registry --output /private/migration-plan.json
```

实际迁移与完整回滚仍需按各自环境处理，不能把迁移计划视为已执行的迁移。

## 开发与发布

无需 HA 的源码测试：

```sh
python -m pip install packaging==25.0
python -m unittest discover -s tests -v
python -m compileall -q custom_components tools tests
```

依赖 HA 的测试会在普通 Python 环境中跳过，模拟控制测试不会操作实际设备。真实只读查询工具和完整离线候选包说明见 [docs](docs/)。

推送 `v0.3.0` 形式的 tag 后，GitHub Actions 会测试、生成组件 ZIP、SHA256 和版本清单，并自动发布 Release；RC 和开发版标为预发布。普通提交只构建，不发布。操作步骤见 [发布说明](docs/RELEASING.md)。
