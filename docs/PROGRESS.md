# 2026-10-31 阶段记录

本地项目：D:/git/homycloud-local-ha，分支 codex/ha-native-integration。

修复前在 Python 3.14.9 导入 XTypes 时抛出 Member TRY_CONSTRUCT1 is not defined。采用上游 Python 3.14 修复及继承类型修复的固定提交后，四个协议类型均构建成功。

第一轮新客户端实测：15 秒只读查询，27 个配置设备全部回应，101 个属性，未创建控制 writer。HA coordinator 在独立 Core 实例中读取到 27 个设备、27 个在线；卸载后 worker 已停止。证据分别见 read-only-probe.json、coordinator-probe.json、compatibility-probe.json。

现有 Home Assistant、MQTT 和 homycloud-bridge 配置未改，未添加现用 HA 配置条目，未重启这些服务，未发送开关/窗帘/空调控制命令。新增测试文件仅放在独立诊断目录。

尚未完成正式控制平台、实体迁移、可复现二进制打包和长时间稳定性验证；当前成果不能当作已经替换旧桥的正式集成。

最终本地检查：11 项 unittest 全部通过；compileall 通过；项目文件中的已知凭据扫描无命中。仓库已初始化，未 commit 或 push。


## 0.2.0-dev 后续开发

- 显示名改为 HomyCloud，repo homycloud-local-ha、domain homycloud_local 保持不变；README 已重写。
- 六类原生实体代码已实现。独立 HA 实例创建 94 个唯一实体，27 个设备在线；读取状态/能力属性通过，默认只读拒绝控制，停止 worker 成功。见 entities-probe.json。
- 在 HA Python 环境中完成 19 项测试（包括使用模拟 DDS 的控制、反馈超时和卸载测试），未操作真机。见 ha-tests.json。
- 新增 3 项迁移计划测试；真实注册表只读核对 94 项匹配、0 缺失、0 冲突，注册表写入次数 0。私有计划仅放在被 Git 忽略目录，公共证据见 migration-check.json。
- 尚未完成依赖安装包、正式迁移和真机控制验证；现有服务继续运行，未 commit/push。

## 2026-11-01：原生运行时与完整只读流程

- 生成兼容 wheel `11.0.1+homycloud.2`：稳定 C/Python 11.0.1 基线，仅回移上游 Python 3.14 兼容修复；自带 libddsc，并通过独立安装、四种类型构建、真实网关查询和 HA 配置依赖目录加载验证。
- 实际 HA 配置流程与真实只读 DDS 联合验证：94 个实体注册，添加、重复添加拦截、选项表单、重载和卸载均通过；后台错误 0、控制 writer 0、实际控制尝试 0。见 config-entry-real-dds.json。测试夹具使用的可选 AWS CRT 回退及基础镜像已知异常详见 KNOWN_ISSUES.md。
- 修复 Number 状态返回绑定方法引起的递归异常；把反馈确认后的快照发布放在调用完成之前。4 项 HA worker 回归测试通过，含人为延迟快照测试，见 ha-number-regression.json。这不代表已经测量真实设备控制延迟。
- 三轮真实 DDS 启停、查询、退出检查均收到 27/27 设备回应，停止后回到单线程，未见持续递增的退出后 RSS；只是短时验证，不作长期无泄漏保证。见 dds-lifecycle-probe.json。
- 新增离线候选包工具：明确文件范围、排除私有清单、核对运行时摘要，逐文件记录 SHA256，拒绝覆盖已有输出；测试覆盖篡改、意外附加文件、越界路径及固定输入的重复打包。未执行正式安装或迁移。
- 候选包 rc2 包含 36 个文件、3,147,075 字节。4 项打包测试通过；断网临时容器验证离线安装、原生库来源及四种类型构建通过。HA 配置依赖加载测试通过时使用了与前述一致的可选 CRT 测试回退；未隔离 CRT 的尝试再次触发基础 SDK 导入退出，分别见 offline-candidate-probe.json 与 offline-candidate-baseline.json。修复了初包漏收 tools/__init__.py 导致工具包导入冲突的问题，初包保留在忽略的 rejected-candidates 目录。
- HACS 尚不能安装本项目：未发布 GitHub 仓库，原生依赖自动分发和升级方案未完成。离线候选包不代表已取得 HACS 发布支持。
