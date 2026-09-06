pipeline {
    agent any
    options {
        timestamps()
        timeout(time: 30, unit: 'MINUTES')
        disableConcurrentBuilds()
    }
    parameters {
        booleanParam(name: 'RUN_UI', defaultValue: false, description: 'Run Playwright browser smoke tests')
    }
    environment {
        PIP_DISABLE_PIP_VERSION_CHECK = '1'
        APP_ENV = 'test'
        REDIS_URL = 'redis://redis:6379/0'
        TEST_REDIS_URL = 'redis://redis:6379/0'
    }
    stages {
        stage('Prepare workspace') {
            steps {
                sh 'rm -rf allure-results allure-report junit-results newman-results'
                sh 'mkdir -p allure-results junit-results'
            }
        }
        stage('Install') {
            steps {
                sh 'python -m venv .ci-venv'
                sh '.ci-venv/bin/pip install -e ".[test]"'
                retry(3) {
                    sh 'npm ci --prefer-offline --no-audit --no-fund'
                }
            }
        }
        stage('Database migration') {
            steps {
                withCredentials([string(credentialsId: 'wallet-test-database-url', variable: 'DATABASE_URL')]) {
                    sh '.ci-venv/bin/alembic upgrade head'
                }
            }
        }
        stage('Static quality gate') {
            parallel {
                stage('Ruff') {
                    steps {
                        sh '.ci-venv/bin/ruff check app tests migrations performance scripts'
                        sh '.ci-venv/bin/ruff format --check app tests migrations performance scripts'
                    }
                }
                stage('mypy') {
                    steps {
                        sh '.ci-venv/bin/mypy app tests scripts'
                    }
                }
            }
        }
        stage('API and financial regression') {
            steps {
                withCredentials([string(credentialsId: 'wallet-test-database-url', variable: 'TEST_DATABASE_URL')]) {
                    sh '.ci-venv/bin/pytest -n auto --ignore=tests/ui -m "not concurrency" --alluredir=allure-results --junitxml=junit-results/regression.xml'
                }
            }
        }
        stage('Transaction concurrency gate') {
            steps {
                withCredentials([string(credentialsId: 'wallet-test-database-url', variable: 'TEST_DATABASE_URL')]) {
                    sh '.ci-venv/bin/pytest tests/concurrency --alluredir=allure-results --junitxml=junit-results/concurrency.xml'
                }
            }
        }
        stage('Postman and Newman') {
            steps {
                withCredentials([string(credentialsId: 'wallet-test-database-url', variable: 'TEST_DATABASE_URL')]) {
                    sh '.ci-venv/bin/python -m scripts.run_newman'
                }
            }
        }
        stage('UI smoke') {
            when { expression { params.RUN_UI } }
            steps {
                withCredentials([string(credentialsId: 'wallet-test-database-url', variable: 'TEST_DATABASE_URL')]) {
                    sh '.ci-venv/bin/playwright install --with-deps chromium'
                    sh '.ci-venv/bin/pytest tests/ui --browser chromium --alluredir=allure-results --junitxml=junit-results/ui.xml'
                }
            }
        }
    }
    post {
        always {
            sh '''
                if [ -x node_modules/.bin/allure ] && find allure-results -type f -print -quit | grep -q .; then
                    node_modules/.bin/allure generate allure-results --clean -o allure-report
                else
                    echo "No Allure results were produced."
                fi
            '''
            archiveArtifacts artifacts: 'allure-results/**,allure-report/**,junit-results/**,newman-results/**', allowEmptyArchive: true
            junit testResults: 'junit-results/*.xml,newman-results/*.xml', allowEmptyResults: true
            cleanWs(deleteDirs: true, notFailBuild: true)
        }
    }
}
