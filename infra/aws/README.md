# Deploying SupportLens to AWS

Terraform in this folder creates the whole stack. It has been validated (`terraform validate`) but
applying it creates billable resources, so nothing here runs automatically.

| Concern | AWS service | Notes |
| --- | --- | --- |
| API + Celery workers + web | **ECS on Fargate** | One image (`backend/Dockerfile.prod`) runs the API, the worker and the migration task; `frontend/Dockerfile` serves the SPA. Deployment circuit breaker with automatic rollback. |
| Routing / TLS | **Application Load Balancer** + ACM | HTTPS only (HTTP redirects). `/api/*` → API service, everything else → web. |
| Database | **RDS for PostgreSQL 17** | pgvector ships with RDS; the first Alembic migration runs `CREATE EXTENSION vector`. Master password managed and rotated by RDS in Secrets Manager; `rds.force_ssl=1`. Multi-AZ in prod. |
| Broker + shared state | **ElastiCache for Redis 7** | Celery broker, circuit-breaker state and worker heartbeat. TLS in transit (`rediss://`). |
| Documents | **S3** | Private bucket (public access blocked, owner-enforced, versioned, SSE). Tasks reach it through their IAM task role; browsers only get 5-minute presigned GET URLs. |
| Secrets | **Secrets Manager** | JWT signing key (generated), Anthropic API key (set by you), DB password (RDS-managed). Injected as ECS secrets, never in task definitions. |
| Images | **ECR** | Immutable tags (git SHA), scan on push. |
| Logs / metrics | **CloudWatch** | JSON log lines per request and per model call (`event=http_request`, `event=llm_call`) → Logs Insights queries for latency, tokens and cost; Container Insights for the services. |
| Network | VPC with public (ALB, NAT) and private (tasks, RDS, Redis) subnets in 2 AZs | Security groups allow only ALB → tasks → RDS/Redis. |

## First deploy

```bash
cd infra/aws
terraform init
terraform apply -var certificate_arn=arn:aws:acm:... -var image_tag=$(git rev-parse --short HEAD) \
  -target=aws_ecr_repository.api -target=aws_ecr_repository.web     # 1. registries first

# 2. build and push both images (or let .github/workflows/deploy.yml do it)
aws ecr get-login-password | docker login --username AWS --password-stdin <account>.dkr.ecr.<region>.amazonaws.com
docker build -f backend/Dockerfile.prod -t <ecr_api>:<sha> backend && docker push <ecr_api>:<sha>
docker build -t <ecr_web>:<sha> frontend && docker push <ecr_web>:<sha>

# 3. everything else, then the API key, then migrations
terraform apply -var certificate_arn=... -var image_tag=<sha>
aws secretsmanager put-secret-value --secret-id $(terraform output -raw anthropic_secret_arn) --secret-string "$ANTHROPIC_API_KEY"
$(terraform output -raw migrate_command)
```

Point a DNS record at `terraform output url`. To load the demo data, run the migrate task with
the command overridden to `python -m app.cli seed`.

## Cost notes

The defaults (2 small API tasks, 1 worker, 2 web tasks, `db.t4g.small` Multi-AZ, `cache.t4g.micro`,
one NAT gateway, an ALB) are sized for a demo. For a quick test, use
`-var environment=staging -var deletion_protection=false` (single-AZ database) and
`terraform destroy` afterwards.
