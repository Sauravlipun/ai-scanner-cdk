from aws_cdk import (
    Stack,
    aws_lambda as lambda_,
    aws_ec2 as ec2,
    aws_secretsmanager as secretsmanager,
    aws_iam as iam,
    Duration,
    CfnOutput
)
from constructs import Construct
import os

class LambdaStack(Stack):
    """
    Lambda functions for AI Script Generation and Sandbox Detonation
    - AI Script Generator: Calls OpenAI API (no VPC)
    - Script Detonator: Runs in isolated Sandbox VPC with no internet [citation:4][citation:8]
    """
    
    def __init__(self, scope: Construct, construct_id: str,
                 main_vpc: ec2.Vpc, sandbox_vpc: ec2.Vpc,
                 ecs_security_group: ec2.SecurityGroup,
                 sandbox_lambda_sg: ec2.SecurityGroup,
                 openai_secret: secretsmanager.Secret,
                 environment: str, project_name: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)
        
        # ====================================================================
        # AI SCRIPT GENERATOR LAMBDA - OpenAI Integration
        # ====================================================================
        
        # IAM Role for AI Lambda
        ai_role = iam.Role(
            self, "AILambdaRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "service-role/AWSLambdaBasicExecutionRole"
                )
            ]
        )
        
        # Grant access to OpenAI secret
        openai_secret.grant_read(ai_role)
        
        # AI Script Generator Lambda (no VPC - needs internet for OpenAI API)
        self.ai_script_generator = lambda_.Function(
            self, "AIScriptGenerator",
            function_name=f"{project_name}-{environment}-ai-script-generator",
            runtime=lambda_.Runtime.PYTHON_3_11,
            handler="ai_script_generator.lambda_handler",
            code=lambda_.Code.from_asset("lambda/ai_script_generator"),
            role=ai_role,
            timeout=Duration.minutes(5),
            memory_size=1024,
            environment={
                "MODEL": "gpt-4",
                "OPENAI_SECRET_ARN": openai_secret.secret_arn,
                "ENVIRONMENT": environment
            }
        )
        
        # ====================================================================
        # SCRIPT DETONATOR LAMBDA - Isolated Sandbox (NO INTERNET)
        # ====================================================================
        
        # IAM Role for Sandbox Lambda
        sandbox_role = iam.Role(
            self, "SandboxLambdaRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "service-role/AWSLambdaBasicExecutionRole"
                ),
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "service-role/AWSLambdaVPCAccessExecutionRole"
                )
            ]
        )
        
        # Script Detonator Lambda - INSIDE Sandbox VPC, no internet
        self.script_detonator = lambda_.Function(
            self, "ScriptDetonator",
            function_name=f"{project_name}-{environment}-script-detonator",
            runtime=lambda_.Runtime.PYTHON_3_11,
            handler="script_detonator.lambda_handler",
            code=lambda_.Code.from_asset("lambda/script_detonator"),
            role=sandbox_role,
            timeout=Duration.minutes(5),
            memory_size=1024,
            vpc=sandbox_vpc,
            vpc_subnets=ec2.SubnetSelection(
                subnet_type=ec2.SubnetType.PRIVATE_ISOLATED
            ),
            security_groups=[sandbox_lambda_sg],
            allow_public_subnet=False,
            environment={
                "ENVIRONMENT": environment,
                "MAIN_VPC_CIDR": main_vpc.vpc_cidr_block
            }
        )
        
        # ====================================================================
        # OUTPUTS
        # ====================================================================
        CfnOutput(self, "AIScriptGeneratorARN", value=self.ai_script_generator.function_arn)
        CfnOutput(self, "ScriptDetonatorARN", value=self.script_detonator.function_arn)
