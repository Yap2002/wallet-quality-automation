# CI质量流水线验收记录

## 2026-09-05本地等价验收

本记录只写实际执行结果，不把“配置文件存在”等同于“远端流水线通过”。

| 验收项 | 实际结果 |
|---|---|
| Docker Compose | MySQL 8.4、Redis 7、FastAPI和Jenkins均成功启动；应用、MySQL、Redis健康 |
| Alembic | 在隔离的`wallet_test`数据库执行`upgrade head`成功 |
| 静态门禁 | Ruff检查、Ruff格式检查通过；mypy strict检查87个源码文件无问题 |
| 普通回归 | 115条支付与框架测试通过，0 failed，0 skipped |
| 并发事务门禁 | 1 passed |
| Playwright UI | 3 passed |
| Postman/Newman | 10 requests、10 assertions、0 failed |
| Allure | 支付主线119个Pytest结果（116条非UI + 3条UI） |
| JUnit | `regression.xml`、`concurrency.xml`、`ui.xml`和Newman XML分别生成 |
| Jenkins运行环境 | 页面HTTP 200；Python 3.12、Node 20和Java 21可用 |
| Jenkins Pipeline | 本机任务`wallet-quality-pipeline`第8次构建SUCCESS，耗时21.603秒 |
| Jenkins测试结果 | 支付主线126项（116条Pytest + 10条Newman断言）全部通过 |
| Jenkins产物归档 | Allure HTML/原始结果、JUnit和Newman XML均可从构建产物下载 |

支付与测试框架共有116条非UI测试，加上3条Playwright UI用例，完整Pytest口径为119条。

## 2026-09-06 GitHub Actions云端验收

私有仓库：`Yap2002/wallet-quality-automation`。远端使用全新的干净提交历史，只包含支付质量工程文件。

| 验收项 | 实际结果 |
|---|---|
| 质量流水线 | Run `34029496130`，SUCCESS，全部18个步骤通过 |
| 运行环境 | GitHub Ubuntu Runner、Python 3.12、MySQL 8.4、Redis 7 |
| 静态门禁 | Ruff通过；89个文件格式检查通过；mypy检查80个源码文件通过 |
| 普通回归 | 115 passed |
| 并发事务门禁 | 1 passed |
| Playwright UI | 3 passed |
| Postman/Newman | 10 requests、10 assertions、0 failed |
| 报告 | Allure HTML生成成功；质量证据Artifact约1.75MB |
| 性能流水线 | Run `34029702689`，SUCCESS，全部12个步骤通过 |
| Locust负载 | 10用户、30秒、503请求、0失败 |
| Locust指标 | 平均13ms、P95 32ms、约17.07 RPS |
| 性能证据 | HTML、CSV与服务日志Artifact约333KB |

质量流水线中的官方GitHub Action已升级到v7，消除了Node.js 20运行时弃用告警。npm安装仍显示Newman 6.2.2上游传递依赖的弃用提示；Newman当前没有更高版本可升级，这些提示不影响测试结果。

## 本次CI闭环发现并修复的问题

1. **Redis测试被静默跳过**：流水线只设置`REDIS_URL`，真实Redis测试读取`TEST_REDIS_URL`。修复为同时设置应用变量和测试变量，并增加配置防回归断言。
2. **JUnit报告被后续Pytest阶段删除**：Playwright插件默认使用`test-results`存放浏览器产物，每次Pytest启动会清理该目录。修复为将JUnit独立放入`junit-results`。
3. **Newman可能无限等待**：运行器没有超时控制。新增`NEWMAN_TIMEOUT_SECONDS`，默认120秒；同时支持`NEWMAN_EXECUTABLE`，便于CI和本机使用不同安装位置。
4. **Allure只归档原始数据**：GitHub Actions和Jenkins现在都会生成Allure HTML，并同时归档Allure、JUnit和Newman证据。
5. **Jenkins插件依赖不完整**：首次真实任务缺少Git和Timestamper插件。修复为在镜像构建时固定安装流水线所需插件。
6. **成功构建没有报告产物**：`post`块重复申请`node`后进入`@2`空工作目录，测试虽通过但找不到报告。修复为直接在当前流水线工作目录生成和归档报告，第8次构建验证通过。

## 范围边界

- 当前没有自动部署阶段，因此严格名称是“CI质量流水线”，不是完整CD。

## 面试表达

> 我分别跑通了本机Jenkins和GitHub Actions质量流水线。GitHub云端环境完成115条普通回归、1条并发事务测试、3条UI测试和10条Newman断言，并归档Allure、JUnit和Newman证据；独立Locust工作流完成503个请求且0失败。性能数据只代表本次受控小样本，项目没有生产自动部署阶段。
