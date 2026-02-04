output "url" {
  description = "Point your DNS name (matching the ACM certificate) at this ALB."
  value       = aws_lb.main.dns_name
}

output "ecr_api" {
  value = aws_ecr_repository.api.repository_url
}

output "ecr_web" {
  value = aws_ecr_repository.web.repository_url
}

output "documents_bucket" {
  value = aws_s3_bucket.docs.bucket
}

output "anthropic_secret_arn" {
  description = "Set the API key here before switching llm_provider to anthropic."
  value       = aws_secretsmanager_secret.anthropic.arn
}

output "migrate_command" {
  value = "aws ecs run-task --cluster ${aws_ecs_cluster.main.name} --launch-type FARGATE --task-definition ${aws_ecs_task_definition.migrate.family} --network-configuration 'awsvpcConfiguration={subnets=[${join(",", module.vpc.private_subnets)}],securityGroups=[${aws_security_group.tasks.id}]}'"
}
