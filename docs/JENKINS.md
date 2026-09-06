# Jenkins 本地流水线说明

Jenkins是可以部署在自己电脑或公司服务器上的持续集成平台。它监听代码变更或人工点击构建，然后按`Jenkinsfile`自动执行迁移、代码检查和测试。它不只是“定时任务”；push、Pull Request、人工触发和定时触发都可以启动流水线。

## 本地启动

```bash
docker compose --profile ci up -d jenkins
```

打开`http://localhost:8080`，创建Pipeline任务并选择仓库中的`Jenkinsfile`。在Credentials中创建Secret text，ID必须为`wallet-test-database-url`，值指向隔离的`wallet_test`数据库。密码不写入Git。

项目提供的Jenkins镜像内置Python 3.12和Node，且不挂载宿主机Docker socket，避免Jenkins获得控制本机全部容器的高权限。流水线将静态检查、接口与金融回归、并发事务门禁和Newman拆成独立阶段；勾选`RUN_UI`才下载浏览器并运行Playwright，避免每次构建浪费时间和空间。Locust性能基线由独立的GitHub Actions定时/手动工作流执行，不与每次提交的快速门禁混跑。

本机已实际验证Jenkins 2.568.1容器启动，`http://localhost:8080/login`返回200；Python 3.12.13、Node 20.20.2、npm 10.8.2以及workflow、Git、Credentials、JUnit、Timestamper和workspace清理插件可用。已创建`wallet-quality-pipeline`任务并配置`wallet-test-database-url`隔离测试库凭据。支付主线116条Pytest与10条Newman断言通过，Allure、JUnit和Newman产物成功归档。数据库凭据由Jenkins Credentials注入，不写入代码仓库。

## 与GitHub Actions的关系

两者都调用项目已有命令，不复制测试逻辑。GitHub Actions是托管式CI，配置简单；Jenkins是自建式CI，可定制性强但需要维护服务器、插件、凭据、备份和升级。
