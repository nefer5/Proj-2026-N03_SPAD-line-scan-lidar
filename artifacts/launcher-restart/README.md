# 一键启动器可靠重启验收

2026-10-15。原start-dev.cmd调用run.py --reload --open；run.py发现服务可用便复用，不具备旧启动器/重载器/worker清理。

本次cmd传绝对路径run.py --restart --reload --open。新启动器使用项目路径+进程创建时间+端口所有者+服务祖先链/PID记录确定归属，启动互斥锁串行处理重复点击；无法确认身份的端口/其他项目/共享宿主拒绝停止。默认端口仍唯一维护在run.py，未增加依赖或修改仿真参数。

Uvicorn子进程以暂停状态创建，先加入带KILL_ON_JOB_CLOSE的专属Windows Job Object再执行。其重载器/服务/计算worker自动归入Job，启动器退出即回收服务树；浏览器由Job外的启动器打开。新实例必须返回匹配的随机标识、项目路径和软件版本，才打印Ready并打开浏览器；不是看到旧服务能响应就判断成功。

## 验证

- 27项启动器/页面缓存/共用默认/后台任务定向测试通过。启动器专项12项覆盖旧相对路径实例、孤儿绝对路径启动器、PID复用、原生句柄创建时间核验、其他项目/共享宿主拒绝、当前启动器排除及端口解析。
- 隔离端口实际运行reload服务，并提交任务建立计算worker；随后主动终止旧后端，保留启动器/重载器及可能的worker，再执行--restart。旧4进程均不再存在，新launcher/server PID及instance_id不同，版本匹配，详见isolated-verification.json。
- 隔离端口启动无关HTTP服务，执行--restart返回1，原服务继续存活；测试未杀端口或全机Python。测试结束确认隔离服务/启动器退出。
- 实际8016原旧入口是相对run.py，端口由旧父启动器持有；经新增/api/runtime验证后安全迁移。最终83080启动器、44192服务及新Job就绪，旧实例进程均退出，详见production-verification.json。PID仅为本次运行快照，以当前/api/runtime为准。
- 运行日志及完整测试驱动在本机artifacts/launcher-check（既有忽略目录）；项目进程记录与锁在artifacts/runtime，不提交认证状态或其他浏览器/应用信息。
- Python语法和Git空白检查通过。只做本项目代码/运行服务变更，不属于全局环境配置更新。

使用、失败边界与--stop说明见docs/guides/launcher.md。服务重启保留旧任务/草稿，旧结果不因重启被重算；应重新运行采集验证新的计算逻辑。
