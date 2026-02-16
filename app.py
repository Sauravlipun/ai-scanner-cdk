#!/usr/bin/env python3
"""
AI Security Scanner Platform - AWS CDK Application
Implements secure-by-default infrastructure patterns from ZipHQ [citation:10]
"""

import aws_cdk as cdk
from stacks.network_stack import NetworkStack
from stacks.database_stack import DatabaseStack
from stacks.redis_stack import RedisStack
from stacks.ecs_stack import EcsStack
from stacks.lambda_stack import LambdaStack
from stacks.frontend_stack import FrontendStack
from stacks.cicd_stack import CicdStack

app = cdk.App()

# Environment configuration
env = cdk.Environment(
    account=app.node.try_get_context("account") or os.environ.get("CDK_DEFAULT_ACCOUNT"),
    region=app.node.try_get_context("region") or os.environ.get("CDK_DEFAULT_REGION", "us-east-1")
)

# Deployment context (dev/prod)
environment = app.node.try_get_context("environment") or "dev"
project_name = app.node.try_get_context("project_name") or "ai-scanner"

# Tags applied to ALL resources
tags = {
    "Project": project_name,
    "Environment": environment,
    "ManagedBy": "CDK",
    "CostCenter": "Security",
    "terraform-managed": "true"  # Used for SCP enforcement [citation:10]
}

# ============================================================================
# STACK 1: NETWORK - Main VPC + Sandbox VPC + Peering
# ============================================================================
network_stack = NetworkStack(
    app, f"{project_name}-{environment}-network",
    env=env,
    tags=tags,
    environment=environment,
    project_name=project_name
)

# ============================================================================
# STACK 2: DATABASE - RDS PostgreSQL with Secrets Manager
# ============================================================================
db_stack = DatabaseStack(
    app, f"{project_name}-{environment}-database",
    vpc=network_stack.main_vpc,
    ecs_security_group=network_stack.ecs_tasks_sg,
    env=env,
    tags=tags,
    environment=environment,
    project_name=project_name
)
db_stack.add_dependency(network_stack)

# ============================================================================
# STACK 3: REDIS - ElastiCache
# ============================================================================
redis_stack = RedisStack(
    app, f"{project_name}-{environment}-redis",
    vpc=network_stack.main_vpc,
    ecs_security_group=network_stack.ecs_tasks_sg,
    env=env,
    tags=tags,
    environment=environment,
    project_name=project_name
)
redis_stack.add_dependency(network_stack)

# ============================================================================
# STACK 4: ECS - Django Backend + Celery Workers
# ============================================================================
ecs_stack = EcsStack(
    app, f"{project_name}-{environment}-ecs",
    vpc=network_stack.main_vpc,
    ecs_security_group=network_stack.ecs_tasks_sg,
    alb_security_group=network_stack.alb_sg,
    rds_instance=db_stack.rds_instance,
    redis_cluster=redis_stack.redis_cluster,
    rds_secret=db_stack.rds_secret,
    openai_secret=db_stack.openai_secret,  # From DatabaseStack
    env=env,
    tags=tags,
    environment=environment,
    project_name=project_name
)
ecs_stack.add_dependency(db_stack)
ecs_stack.add_dependency(redis_stack)

# ============================================================================
# STACK 5: LAMBDA - AI Script Generator + Sandbox Detonator
# ============================================================================
lambda_stack = LambdaStack(
    app, f"{project_name}-{environment}-lambda",
    main_vpc=network_stack.main_vpc,
    sandbox_vpc=network_stack.sandbox_vpc,
    ecs_security_group=network_stack.ecs_tasks_sg,
    sandbox_lambda_sg=network_stack.sandbox_lambda_sg,
    openai_secret=db_stack.openai_secret,
    env=env,
    tags=tags,
    environment=environment,
    project_name=project_name
)
lambda_stack.add_dependency(db_stack)
lambda_stack.add_dependency(network_stack)

# ============================================================================
# STACK 6: FRONTEND - AWS Amplify (Next.js)
# ============================================================================
frontend_stack = FrontendStack(
    app, f"{project_name}-{environment}-frontend",
    alb_dns=ecs_stack.alb.load_balancer_dns_name,
    env=env,
    tags=tags,
    environment=environment,
    project_name=project_name
)
frontend_stack.add_dependency(ecs_stack)

# ============================================================================
# STACK 7: CI/CD - CodePipeline with tfsec Security Scanning
# ============================================================================
cicd_stack = CicdStack(
    app, f"{project_name}-{environment}-cicd",
    env=env,
    tags=tags,
    environment=environment,
    project_name=project_name
)

# ============================================================================
# SYNTHESIZE
# ============================================================================
app.synth()
