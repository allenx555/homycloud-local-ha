# 协议依据与验证范围

集成参考宏云智家客户端 com.homycloud.iot 的设备属性与按钮控制流程，并通过网关的本地 DDS 消息定义和真实设备反馈核对。客户端分析依据为应用宝发布的 1.2.16 安装包，没有在开发环境安装或登录该客户端。

发布页面：https://sj.qq.com/appdetail/com.homycloud.iot 。本文不是宏云官方开放 API 文档，也不表示厂家为私有字段提供兼容承诺。

## 来源分工

- DDS/RTPS 通信标准与实现：Eclipse CycloneDDS。
- 宏云消息类型：从网关发现和解析的 LanProto 消息定义，结构保存在 protocol/schemas.json。
- 设备字段与按钮行为：参考原生客户端 ViewModel、仓库封装，并以本地报文与读回状态核对。
- HA 实体、后台通信、状态顺序、反馈与迁移：本项目实现。

客户端的云端 MQTT/HTTP 请求封装未接入本集成，实际路径是 HA → 本地 DDS → 原网关。

## 采用的设备属性

| 类型 | 属性 | 处理 |
| --- | --- | --- |
| 开关 | switch、switch_1 等已声明属性 | 布尔值，不接受用数字或字符串冒充布尔值 |
| 窗帘位置 | percent_control | 数值，按已观察到的末端值做 HA 百分比映射 |
| 窗帘暂停 | control = stop | 使用客户端的原生字段；暂停动作曾在原桥路径中实机验证 |
| 空调 | switch、temp_set、mode、level | 风速 level 与新风风速分开，能力由清单限定 |
| 新风 | switch_air、fan_speed_enum | 独立电源、风速设置 |
| 地暖 | switch_heating、heating_temp_set_c | 独立电源、温度设置 |

字段依据不是逐项执行结果。原生集成对真实网关的验证保持只读；控制路径目前通过模拟 DDS 和实体测试。不同面板未返回的能力不自动补齐，其他固件或型号仍需单独确认。
