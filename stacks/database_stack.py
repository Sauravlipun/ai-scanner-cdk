from aws_cdk import (
    Stack,
    aws_rds as rds,
    aws_ec2 as ec2,
    aws_secretsmanager as secretsmanager,
    aws_kms as kms,
    Duration,
    CfnOutput
)
from constructs import Construct
from secure_templates.rds import SecureDatabaseInstance

class DatabaseStack(Stack):
    """
    Database infrastructure with AWS Secrets Manager integration
    Uses secure template with enforced encryption and no public access [citation:10]
    """
    
    def __init__(self, scope: Construct, construct_id: str,
                 vpc: ec2.Vpc, ecs_security_group: ec2.SecurityGroup,
                 environment: str, project_name: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)
        
        # ====================================================================
        # KMS Key for RDS Encryption
        # ====================================================================
        self.rds_key = kms.Key(
            self, "RDSEncryptionKey",
            description="KMS key for RDS encryption",
            enable_key_rotation=True,
            alias=f"{project_name}-{environment}-rds-key"
        )
        
        # ====================================================================
        # DB Subnet Group
        # ====================================================================
        db_subnet_group = rds.SubnetGroup(
            self, "DBSubnetGroup",
            description="Subnet group for RDS",
            vpc=vpc,
            vpc_subnets=ec2.SubnetSelection(
                subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS
            )
        )
        
        # ====================================================================
        # RDS Credentials Secret (Auto-generated)
        # ====================================================================
        self.rds_secret = secretsmanager.Secret(
            self, "RDSCredentials",
            secret_name=f"{project_name}-{environment}-rds-credentials",
            generate_secret_string=secretsmanager.SecretStringGenerator(
                secret_string_template='{"username":"postgres"}',
                generate_string_key="password",
                exclude_characters="\"@/\\",
                password_length=24
            )
        )
        
        # ====================================================================
        # OpenAI API Key Secret (Placeholder - must be updated manually)
        # ====================================================================
        self.openai_secret = secretsmanager.Secret(
            self, "OpenAISecret",
            secret_name=f"{project_name}-{environment}-openai-key",
            generate_secret_string=secretsmanager.SecretStringGenerator(
                secret_string_template='{"OPENAI_API_KEY":"REPLACE_WITH_YOUR_KEY"}',
                generate_string_key="placeholder",
                exclude_characters="\"@/\\",
                password_length=32
            )
        )
        
        # ====================================================================
        # SECURE RDS INSTANCE - Using security guardrail template
        # ====================================================================
        self.rds_instance = SecureDatabaseInstance(
            self, "PostgreSQL",
            engine=rds.DatabaseInstanceEngine.postgres(
                version=rds.PostgresEngineVersion.VER_16_1
            ),
            instance_type=ec2.InstanceType.of(
                ec2.InstanceClass.BURSTABLE4_GRAVITON,
                ec2.InstanceSize.MICRO if environment == "dev" else ec2.InstanceSize.LARGE
            ),
            vpc=vpc,
            vpc_subnets=ec2.SubnetSelection(
                subnet_group=db_subnet_group
            ),
            security_groups=[ecs_security_group],
            subnet_group=db_subnet_group,
            credentials=rds.Credentials.from_secret(self.rds_secret),
            database_name="scannerdb",
            allocated_storage=20 if environment == "dev" else 100,
            max_allocated_storage=100 if environment == "dev" else 500,
            storage_type=rds.StorageType.GP3,
            storage_encrypted=True,
            storage_encryption_key=self.rds_key,
            backup_retention=Duration.days(7 if environment == "dev" else 30),
            backup_window="03:00-04:00",
            maintenance_window="sun:04:00-sun:05:00",
            multi_az=False if environment == "dev" else True,
            publicly_accessible=False,  # ENFORCED by secure template
            deletion_protection=True if environment == "prod" else False,
            removal_policy=RemovalPolicy.DESTROY if environment == "dev" else RemovalPolicy.RETAIN,
            environment={"ENVIRONMENT": environment}  # Pass to secure template
        )
        
        # ====================================================================
        # OUTPUTS
        # ====================================================================
        CfnOutput(self, "RDSInstanceEndpoint", value=self.rds_instance.db_instance_endpoint_address)
        CfnOutput(self, "RDSSecretARN", value=self.rds_secret.secret_arn)
        CfnOutput(self, "OpenAISecretARN", value=self.openai_secret.secret_arn)
