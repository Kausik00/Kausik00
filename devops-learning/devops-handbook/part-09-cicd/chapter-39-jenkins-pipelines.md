# Chapter 39: Jenkins Pipelines as Code

*DevOps Handbook — Part IX, Pages 771–790*

---

## 39.1 Jenkins in the modern CI/CD landscape

**Jenkins** is the longest-running open-source automation server in DevOps. While cloud-native platforms (GitHub Actions, GitLab CI) dominate greenfield projects, Jenkins remains entrenched in enterprises with thousands of plugins, existing investment, and air-gapped environments.

Modern Jenkins centers on **Pipeline as Code**: pipelines defined in `Jenkinsfile` files stored in Git, versioned alongside application code, and reviewed through pull requests—eliminating click-configured jobs that drift from documentation.

| Strength | Limitation |
|----------|------------|
| 2,000+ plugins | Plugin maintenance burden |
| Self-hosted control | You operate HA, upgrades, security |
| Flexible agents | Complex agent provisioning |
| Declarative & Scripted DSL | Groovy learning curve |

This chapter focuses on **Declarative Pipeline** syntax—the recommended approach for readability and Jenkins validation.

---

## 39.2 Architecture: controller, agents, and plugins

```
┌─────────────────┐     schedules      ┌──────────────────┐
│ Jenkins         │ ─────────────────► │ Agent (executor) │
│ Controller      │                    │ (VM, K8s pod,    │
│ (formerly master)│ ◄── workspace ──── │  Docker, SSH)    │
└─────────────────┘                    └──────────────────┘
        │
        ├── Plugins (Git, Docker, Kubernetes, credentials)
        ├── Job/Pipeline definitions (Jenkinsfile)
        └── Credentials store (encrypted)
```

- **Controller** — Orchestrates builds, serves UI, stores configuration. Never run heavy builds on the controller in production.
- **Agent** — Executes pipeline steps. Labels route jobs (`agent { label 'linux && docker' }`).
- **Plugins** — Extend functionality; pin versions and audit for CVEs.
- **Credentials** — Bound to folders or jobs; referenced by ID in pipelines.

For Kubernetes, the **Kubernetes plugin** creates ephemeral agent pods per build—isolating workloads and scaling horizontally.

---

## 39.3 Declarative Pipeline structure

A minimal `Jenkinsfile` in the repository root:

```groovy
pipeline {
    agent any

    options {
        timestamps()
        timeout(time: 30, unit: 'MINUTES')
        buildDiscarder(logRotator(numToKeepStr: '20'))
    }

    environment {
        APP_NAME = 'order-service'
        REGISTRY = 'registry.example.com'
    }

    stages {
        stage('Checkout') {
            steps {
                checkout scm
            }
        }

        stage('Build') {
            steps {
                sh 'make build'
            }
        }

        stage('Test') {
            steps {
                sh 'make test'
            }
            post {
                always {
                    junit '**/target/surefire-reports/*.xml'
                }
            }
        }

        stage('Docker Build & Push') {
            when {
                branch 'main'
            }
            steps {
                script {
                    docker.withRegistry("https://${REGISTRY}", 'registry-credentials-id') {
                        def image = docker.build("${APP_NAME}:${env.BUILD_NUMBER}")
                        image.push('latest')
                        image.push("${env.GIT_COMMIT.take(7)}")
                    }
                }
            }
        }
    }

    post {
        success {
            slackSend channel: '#ci', message: "Build ${env.BUILD_URL} succeeded"
        }
        failure {
            slackSend channel: '#ci', message: "Build ${env.BUILD_URL} FAILED"
        }
    }
}
```

Declarative blocks:

| Block | Role |
|-------|------|
| `agent` | Where pipeline runs |
| `environment` | Variables and credentials binding |
| `stages` / `stage` | Logical pipeline phases |
| `steps` | Commands and plugin calls |
| `post` | Actions on success/failure/always |
| `when` | Conditional stage execution |
| `options` | Timeouts, concurrency, log retention |

---

## 39.4 Agents and parallelism

Agent directives control execution placement:

```groovy
pipeline {
    agent none

    stages {
        stage('Parallel Tests') {
            parallel {
                stage('Unit') {
                    agent { label 'linux' }
                    steps { sh 'npm run test:unit' }
                }
                stage('Integration') {
                    agent { label 'linux && docker' }
                    steps { sh 'npm run test:integration' }
                }
                stage('Lint') {
                    agent { label 'linux' }
                    steps { sh 'npm run lint' }
                }
            }
        }
    }
}
```

**Docker agent** runs the entire pipeline inside a container:

```groovy
pipeline {
    agent {
        docker {
            image 'node:20-alpine'
            args '-v /var/run/docker.sock:/var/run/docker.sock'
        }
    }
    stages {
        stage('Build') {
            steps { sh 'npm ci && npm run build' }
        }
    }
}
```

**Kubernetes agent** pod template (requires Kubernetes plugin):

```groovy
pipeline {
    agent {
        kubernetes {
            yaml '''
apiVersion: v1
kind: Pod
spec:
  containers:
  - name: maven
    image: maven:3.9-eclipse-temurin-17
    command: ["sleep"]
    args: ["99d"]
    resources:
      limits:
        memory: "1Gi"
        cpu: "1000m"
'''
        }
    }
    stages {
        stage('Maven Build') {
            steps {
                container('maven') {
                    sh 'mvn -B clean verify'
                }
            }
        }
    }
}
```

---

## 39.5 Credentials, parameters, and shared libraries

Never hardcode secrets in Jenkinsfiles. Use the **Credentials Binding** plugin:

```groovy
stage('Deploy') {
    steps {
        withCredentials([
            string(credentialsId: 'deploy-api-token', variable: 'TOKEN'),
            usernamePassword(credentialsId: 'git-deploy', usernameVariable: 'GIT_USER', passwordVariable: 'GIT_PASS')
        ]) {
            sh '''
                curl -H "Authorization: Bearer $TOKEN" \
                     -X POST https://api.example.com/deploy
            '''
        }
    }
}
```

**Parameters** enable manual runs with choices:

```groovy
parameters {
    choice(name: 'ENV', choices: ['staging', 'production'], description: 'Target')
    booleanParam(name: 'RUN_INTEGRATION', defaultValue: true)
}

stage('Deploy') {
    when {
        expression { params.ENV == 'production' }
    }
    steps {
        input message: 'Deploy to production?', ok: 'Deploy'
        sh "./deploy.sh ${params.ENV}"
    }
}
```

**Shared Libraries** centralize Groovy functions across pipelines. Define in **Manage Jenkins → Configure System → Global Pipeline Libraries**, then:

```groovy
@Library('my-devops-lib@v2') _

pipeline {
    agent any
    stages {
        stage('Scan') {
            steps {
                devopsSecurity.scanImage('myapp:latest')
            }
        }
    }
}
```

Libraries live in a Git repo with `vars/` (global steps) and `src/` (classes).

---

## 39.6 Multibranch and organization folders

**Multibranch Pipeline** jobs automatically discover branches and PRs with a `Jenkinsfile`, creating child jobs per branch:

1. Connect GitHub/GitLab/Bitbucket via webhook or polling.
2. Jenkins scans repository for branches containing `Jenkinsfile`.
3. Each branch gets an isolated pipeline history.

**Organization Folder** scans an entire GitHub organization—ideal for microservice estates with one repo per service.

`Jenkinsfile` location can be customized (`Script Path`) for monorepos: `services/payments/Jenkinsfile`.

---

## 39.7 Pipeline durability and best practices

| Practice | Rationale |
|----------|-----------|
| Declarative over Scripted | Easier review, built-in validation |
| Keep controller lightweight | Agents run builds |
| Pin plugin versions | Reproducible builds, fewer surprises |
| Use `options { disableConcurrentBuilds() }` on deploy pipelines | Prevent overlapping deploys |
| Archive artifacts selectively | Disk fills quickly on busy controllers |
| Blue Ocean or Stage View | Visualize parallel stages |
| Backup `$JEN_HOME` | Jobs, credentials, config |
| RBAC via Matrix Authorization | Least privilege for Jenkins UI |

**Scripted Pipeline** (full Groovy) remains for edge cases but should be wrapped in `script { }` blocks inside Declarative when needed.

---

## 39.8 Jenkins vs cloud-native CI (when to stay)

Stay on Jenkins when:

- Regulatory requirements mandate on-premises CI
- Heavy customization via niche plugins is required
- Existing pipeline investment exceeds migration cost

Migrate when:

- Plugin debt and controller HA consume disproportionate ops time
- Teams want CI tightly integrated with Git hosting
- Ephemeral cloud runners reduce agent maintenance

Hybrid patterns exist: Jenkins orchestrates legacy jobs while new services use GitHub Actions, unified by deployment tooling (Argo CD, Spinnaker).

---

## 39.9 Chapter summary

- Jenkins Pipeline as Code (`Jenkinsfile`) brings version control and review to CI/CD definitions.
- Declarative Pipeline provides structured stages, agents, credentials, and post-build actions.
- Agents on VMs, Docker, or Kubernetes execute work; the controller orchestrates only.
- Multibranch pipelines and shared libraries scale Jenkins across many services and teams.

---

## 🧪 Lab 39.1 — Declarative pipeline from scratch

1. Install Jenkins (Docker or local) with Git, Pipeline, Docker Pipeline, and JUnit plugins.
2. Create a Multibranch Pipeline job connected to a sample repo.
3. Add a `Jenkinsfile` with checkout, build, test, and Docker publish stages.
4. Store registry credentials in Jenkins Credentials; reference via `withCredentials`.
5. Add a `when { branch 'main' }` gate on publish; verify feature branches skip deploy.
6. Configure Slack or email notification in `post { failure }`.

---

## 🧪 Lab 39.2 — Kubernetes ephemeral agents

1. Deploy Jenkins with Kubernetes plugin on a test cluster.
2. Define a pod template with `jnlp` and `maven` containers.
3. Run a pipeline that builds a Java app inside the `maven` container.
4. Confirm agent pod is deleted after build completes.

---

## Review questions

1. What problem does Pipeline as Code solve compared to UI-configured jobs?
2. Why should production builds not run on the Jenkins controller?
3. Explain the difference between Declarative and Scripted Pipeline.
4. How do Multibranch Pipelines discover which branches to build?
5. What is a Jenkins Shared Library, and when should you use one?
6. Describe two ways to inject secrets safely into a pipeline step.
7. What are the main operational costs of running Jenkins at enterprise scale?

---

*Continue: Chapter 40 — GitLab CI and Multi-platform Comparison*
