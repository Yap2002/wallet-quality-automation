# 来自真实实现与测试的缺陷案例

## 1. 创建用户后立即创建钱包偶发401

现象：全量测试中，创建用户返回201，紧接着使用新API Key创建钱包偶发401。根因：FastAPI yield数据库依赖的commit可能在响应发送后执行，第二个请求先于commit读取。修复：依赖使用`scope="function"`，保证commit先于201响应，并增加结构回归测试。为什么有价值：涉及HTTP成功语义、事务可见性和竞态，不能靠sleep或重跑掩盖。

## 2. MySQL约束测试捕获了错误的异常类型

现象：首次在真实MySQL 8.4运行负余额和非CNY约束测试时，约束确实生效，但测试只期待`IntegrityError`而失败。根因：MySQL的CHECK约束错误3819经PyMySQL和SQLAlchemy映射为`OperationalError`，二者共同属于更通用的`DBAPIError`。修复：资金规则与数据库约束不变，只把这两条数据库级测试改为捕获`DBAPIError`，并继续断言非法数据无法落库。为什么有价值：说明项目从一开始使用MySQL，也必须在真实MySQL环境验证驱动异常映射、约束和事务语义，不能只根据ORM层的抽象作假设。

## 3. JMeter提取器异常但进程退出码仍可能为0

现象：第一次JMeter运行21个样本全部失败，下游路径仍包含`${user_id}`，但JMeter进程本身可能返回0；第二次24个样本均为502。根因一是一个JSON提取器配置多个变量时匹配序号数量不一致，后处理器抛出异常；根因二是JMX使用字面默认值，没有读取命令行传入的`-Jport`，请求发往错误端口。修复：拆成两个独立提取器，用`${__P(...)}`读取运行属性，并让脚本解析JTL，只要`success=false`就返回失败。最终24个采样0错误。为什么有价值：证明性能工具“运行结束”不等于业务断言通过，CI必须核对参数生效并读取样本结果。

## 4. 非安全浏览器来源缺少crypto.randomUUID

现象：Playwright在容器网络通过HTTP服务名访问钱包页面时，3条UI用例都显示`crypto.randomUUID is not a function`，业务请求没有发出。根因：页面假设所有浏览器来源都提供`crypto.randomUUID()`，但该API通常要求安全上下文，容器内HTTP服务名不属于localhost。修复：封装UUID生成函数，优先使用`randomUUID`，不可用时使用`crypto.getRandomValues`生成RFC 4122 v4格式，并保留极端环境的随机字节降级。修复后原3条UI断言全部通过。为什么有价值：展示浏览器安全上下文、跨环境兼容性和端到端失败定位，且没有通过修改用例绕过问题。

## 5. Redis容器正常但集成测试被跳过

现象：CI等价回归显示112条通过、1条跳过，跳过的是Redis真实读写。根因：应用读取`REDIS_URL`，测试读取`TEST_REDIS_URL`，流水线只配置了前者。修复：CI和Jenkins同时注入两个用途明确的变量，并增加工程化断言。为什么有价值：服务启动成功不代表依赖真的被测试覆盖，CI必须检查skip数量和原因。

## 6. Playwright输出目录清理了JUnit报告

现象：普通回归和并发阶段都显示生成JUnit XML，但UI阶段结束后只剩`ui.xml`。根因：pytest-playwright默认使用`test-results`作为浏览器产物目录，并会在每个Pytest会话启动时清理；JUnit误用了同一目录。修复：JUnit改用独立的`junit-results`，最终三个Pytest阶段和Newman报告同时保留。为什么有价值：测试通过但证据丢失会破坏CI可追溯性。

## 7. Newman子进程没有超时保护

现象：本机Node依赖目录发生小文件I/O延迟时，Newman超过3分钟没有输出，流水线可能无限占用执行器。根因：`subprocess.run`没有timeout。修复：增加默认120秒的`NEWMAN_TIMEOUT_SECONDS`和可配置的`NEWMAN_EXECUTABLE`，超时会让阶段明确失败并执行数据清理。为什么有价值：自动化框架不仅要测业务，也要保证自己的失败行为可控。

以上案例均来自实际命令或测试，不是为了简历虚构。简历保留最有代表性的4个即可，面试追问时再补充CI闭环发现。
