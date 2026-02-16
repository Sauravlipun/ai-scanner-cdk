"""
Secure RDS template - Enforces security best practices
Implements the pattern from ZipHQ's production IaC [citation:10]
"""

from aws_cdk import aws_rds as rds, aws_ec2 as ec2
from constructs import Construct

# Allowlist for publicly accessible databases (EXCEPTIONS ONLY!)
ALLOWED_PUBLIC_DBS = ["demo-db", "temp-analytics"]  # Add your exceptions here

class SecureDatabaseInstance(rds.DatabaseInstance):
    """
    Secure-by-default RDS instance with enforced encryption,
    no public access, and mandatory backup configuration.
    
    Developers cannot create publicly accessible databases unless explicitly
    added to ALLOWED_PUBLIC_DBS and approved by security team.
    """
    
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        publicly_accessible: bool = False,
        **kwargs
    ):
        # ENFORCE SECURITY: Block public access by default
        if publicly_accessible and construct_id not in ALLOWED_PUBLIC_DBS:
            raise ValueError(
                f"SECURITY VIOLATION: Database {construct_id} cannot be publicly accessible. "
                "This is a security guardrail. Contact security@ to request an exception."
            )
        
        # ENFORCE ENCRYPTION
        kwargs["storage_encrypted"] = True
        
        # ENFORCE BACKUP RETENTION
        if "backup_retention" not in kwargs or kwargs["backup_retention"].to_days() < 7:
            import aws_cdk as cdk
            kwargs["backup_retention"] = cdk.Duration.days(30)
        
        # ENFORCE DELETION PROTECTION for production
        if kwargs.get("environment", {}).get("ENVIRONMENT") == "prod":
            kwargs["deletion_protection"] = True
        
        super().__init__(scope, construct_id, publicly_accessible=publicly_accessible, **kwargs)
