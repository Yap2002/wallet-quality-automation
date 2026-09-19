# 电子钱包支付接口自动化与质量保障项目

这是一个支付接口质量工程项目。FastAPI提供可控的最小被测服务，项目主体是Pytest分层自动化框架，并重点验证MySQL并发事务、余额—交易—账务分录一致性、性能基线和持续集成质量门禁。

## 五条核心能力

1. **自动化框架**：Client、Steps、Factory、Database、Assertions、Fixtures和Cases分层，统一认证、幂等键、trace ID、日志、数据清理及Allure证据。
2. **并发事务**：在真实MySQL 8.4上使用InnoDB行锁和确定的双钱包加锁顺序，验证并发提现不超扣、失败请求不落交易、成功交易逐笔借贷平衡。
3. **资金一致性**：每个资金场景同时检查HTTP响应、钱包余额、交易记录和双重记账分录，不能只以接口201作为成功依据。
4. **性能工程**：JMeter验证参数关联、断言和短链路基线；Locust模拟混合负载，并以错误率、P95和吞吐量作为可配置质量阈值。
5. **持续集成**：GitHub Actions和Jenkins将静态检查、接口回归、并发事务门禁、UI Smoke、报告归档分层执行；性能基线采用定时或手动独立流水线。

## 已实现能力

- 用户、CNY钱包、余额查询、充值、提现、转账、部分/全额退款、手续费试算。
- `PENDING → PROCESSING → SUCCEEDED/FAILED → REFUNDED`受限状态机。
- Decimal资金处理，拒绝浮点数、负数、零、超精度和超范围金额。
- 默认转账固定收取2.00元；支持固定、比例、组合、最低、最高、免手续费和优先级规则。
- MySQL事务、行锁、唯一约束、Alembic迁移和双重记账。
- 强制幂等键、同键同参数重放、同键不同参数冲突、失败结果重放。
- 渠道充值、重复/乱序/丢失回调、终态保护和测试环境故障注入。
- Pytest分层接口框架、Requests真实HTTP黑盒测试、HTTPX进程内集成测试、数据库断言、Allure。
- Hypothesis属性测试、pytest-xdist、并发提现一致性测试。
- Postman/Newman、Locust、JMeter、Playwright浏览器测试。
- JSON结构化日志、trace ID、Redis可选状态缓存及断线降级。
- FastAPI标准HTTPBearer安全方案，Swagger可直接使用Bearer API Key调试受保护接口。
- Docker Compose、GitHub Actions、Jenkinsfile、Ruff和mypy。

## 架构

```mermaid
flowchart LR
    T["Pytest / Postman / Playwright / Locust / JMeter"] --> API["FastAPI 钱包服务"]
    UI["Wallet QA Console"] --> API
    API --> S["应用服务：幂等、手续费、退款、渠道回调"]
    S --> PG[("MySQL\n余额、交易、分录、审计")]
    S -. "可选状态缓存" .-> R[("Redis")]
    C["Mock Channel Callback"] --> API
    CI["GitHub Actions / Jenkins"] --> T
```

更详细的分层和资金流见[架构说明](docs/ARCHITECTURE.md)。

## 快速运行

前提：Python 3.12+、Docker Desktop、Node.js。JMeter和Jenkins属于可选工程化工具。

```bash
python3.12 -m venv .venv
.venv/bin/pip install -e '.[test]'
npm ci
docker compose up -d --build
DATABASE_URL='mysql+pymysql://wallet:wallet@localhost:53306/wallet_test?charset=utf8mb4' \
  .venv/bin/alembic upgrade head
```

访问：

- API文档：`http://localhost:8000/docs`
- 钱包测试页面：`http://localhost:8000/wallet`
- 健康检查：`http://localhost:8000/health/live`

## 运行测试

```bash
# 静态质量
.venv/bin/ruff check app tests migrations performance scripts
.venv/bin/ruff format --check app tests migrations performance scripts
.venv/bin/mypy app tests scripts

# API、数据库、属性和并发回归
TEST_DATABASE_URL='mysql+pymysql://wallet:wallet@localhost:53306/wallet_test?charset=utf8mb4' \
  .venv/bin/pytest -n auto --ignore=tests/ui

# Playwright（可复用本机Chrome）
TEST_DATABASE_URL='mysql+pymysql://wallet:wallet@localhost:53306/wallet_test?charset=utf8mb4' \
  .venv/bin/pytest tests/ui --browser-channel chrome

# Postman/Newman
TEST_DATABASE_URL='mysql+pymysql://wallet:wallet@localhost:53306/wallet_test?charset=utf8mb4' \
  npm run newman:wallet

# Allure原始结果
.venv/bin/pytest --alluredir=allure-results
npm run allure:generate

```

性能测试必须记录机器、用户数、持续时间、数据规模和错误率，不能只写一个QPS数字：

```bash
PERF_MAX_FAILURE_RATIO=0.01 PERF_MAX_P95_MS=500 PERF_MIN_RPS=1 \
  .venv/bin/locust -f performance/locustfile.py --headless --users 5 \
  --spawn-rate 5 --run-time 10s --host http://localhost:8000
npm run jmeter:wallet
```

## 测试分层

```text
tests/framework/clients   统一HTTP请求、认证、trace ID、超时和Allure附件
tests/framework/steps     可读业务步骤与有界状态轮询
tests/framework/database  SQL证据、账务查询和精确清理
tests/framework/factories 独立测试数据创建与回收
tests/unit                金额、状态机、手续费、缓存、日志和工程配置
tests/integration         FastAPI + 真实MySQL接口和一致性
tests/regression          真实HTTP业务流程
tests/property            Hypothesis金融不变量
tests/concurrency         多线程资金一致性
tests/ui                  Playwright浏览器链路
```

## 已验证的不变量

- 钱包余额不得为负。
- 同一幂等请求不得重复产生资金影响。
- 退款累计金额不得超过原交易本金。
- 转账和退款的借方总额等于贷方总额。
- 每次余额变化都存在对应账务分录。
- 手续费符合命中规则、上下限和`ROUND_HALF_UP`策略。
- 只有明确的免手续费规则可以收取0元；有效规则缺失时交易失败且不产生资金影响。
- 终态不会因重复或乱序回调返回处理中。
- Redis不可用不会改变MySQL中的资金正确性。

## 持续集成

`.github/workflows/quality.yml`在push和Pull Request时创建干净MySQL环境，依次执行Alembic结构升级、静态检查、接口与资金回归、独立并发事务门禁、Playwright Smoke和Allure结果归档。`Jenkinsfile`提供同等的自建式流水线，数据库URL通过Credentials注入。`.github/workflows/performance.yml`按工作日定时或人工触发Locust基线，根据错误率、P95和RPS决定是否通过。详细说明见[Jenkins指南](docs/JENKINS.md)。

## 真实结果边界

仓库中只记录实际执行结果。2026-09-06，GitHub Actions在MySQL 8.4和Redis 7环境完成云端验收：115条普通回归、1条并发事务测试和3条Playwright UI测试全部通过；10个Newman请求及10个断言通过；Allure、JUnit和Newman证据成功归档。独立Locust工作流使用10个并发用户运行30秒，共完成503个请求、0失败，平均响应时间13ms、P95为32ms、吞吐约17.07 RPS。性能结果仅代表本次GitHub托管Runner小样本，不代表生产容量。本机Jenkins Pipeline也已真实成功并完成报告归档，详细证据见[CI验收记录](docs/CI_ACCEPTANCE.md)。

## 求职材料

- [测试策略](docs/TEST_STRATEGY.md)
- [真实缺陷案例](docs/DEFECT_CASES.md)
- [关键设计取舍](docs/DESIGN_DECISIONS.md)
- [已知限制](docs/KNOWN_LIMITATIONS.md)

## 保密说明

业务名称、接口、数据模型和规则均为原创通用电子钱包示例，不包含或模拟任何前公司内部接口、数据、名称或保密规则。
