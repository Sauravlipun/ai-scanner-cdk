from aws_cdk import (
    Stack,
    aws_ec2 as ec2,
    Tags,
    CfnOutput
)
from constructs import Construct

class NetworkStack(Stack):
    """
    Network infrastructure: Main VPC, Sandbox VPC, VPC Peering, Security Groups
    Implements complete isolation for sandbox environment [citation:4][citation:8]
    """
    
    def __init__(self, scope: Construct, construct_id: str, 
                 environment: str, project_name: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)
        
        self.environment = environment
        self.project_name = project_name
        
        # ====================================================================
        # MAIN VPC - Application Environment
        # ====================================================================
        self.main_vpc = ec2.Vpc(
            self, "MainVPC",
            ip_addresses=ec2.IpAddresses.cidr("10.0.0.0/16"),
            max_azs=2,
            nat_gateways=2 if environment == "prod" else 1,  # Cost optimization
            subnet_configuration=[
                ec2.SubnetConfiguration(
                    name="Public",
                    subnet_type=ec2.SubnetType.PUBLIC,
                    cidr_mask=24
                ),
                ec2.SubnetConfiguration(
                    name="Private",
                    subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS,
                    cidr_mask=24
                ),
                ec2.SubnetConfiguration(
                    name="Isolated",
                    subnet_type=ec2.SubnetType.PRIVATE_ISOLATED,
                    cidr_mask=24
                )
            ],
            flow_logs={
                "cloudwatch": ec2.FlowLogOptions(
                    destination=ec2.FlowLogDestination.to_cloud_watch_logs()
                )
            }
        )
        
        # ====================================================================
        # SANDBOX VPC - Completely Isolated (no internet)
        # ====================================================================
        self.sandbox_vpc = ec2.Vpc(
            self, "SandboxVPC",
            ip_addresses=ec2.IpAddresses.cidr("10.1.0.0/16"),
            max_azs=2,
            nat_gateways=0,  # NO internet access
            subnet_configuration=[
                ec2.SubnetConfiguration(
                    name="SandboxPrivate",
                    subnet_type=ec2.SubnetType.PRIVATE_ISOLATED,
                    cidr_mask=24
                )
            ]
        )
        
        # ====================================================================
        # VPC PEERING - Orchestrator -> Sandbox communication only
        # ====================================================================
        self.vpc_peering = ec2.CfnVPCPeeringConnection(
            self, "MainToSandboxPeering",
            vpc_id=self.main_vpc.vpc_id,
            peer_vpc_id=self.sandbox_vpc.vpc_id
        )
        
        # Add routes from Main VPC private subnets to Sandbox VPC
        for idx, subnet in enumerate(self.main_vpc.private_subnets):
            ec2.CfnRoute(
                self, f"MainToSandboxRoute{idx}",
                route_table_id=subnet.route_table.route_table_id,
                destination_cidr_block=self.sandbox_vpc.vpc_cidr_block,
                vpc_peering_connection_id=self.vpc_peering.ref
            )
        
        # Add route from Sandbox VPC to Main VPC
        for idx, subnet in enumerate(self.sandbox_vpc.isolated_subnets):
            ec2.CfnRoute(
                self, f"SandboxToMainRoute{idx}",
                route_table_id=subnet.route_table.route_table_id,
                destination_cidr_block=self.main_vpc.vpc_cidr_block,
                vpc_peering_connection_id=self.vpc_peering.ref
            )
        
        # ====================================================================
        # SECURITY GROUPS
        # ====================================================================
        
        # ALB Security Group
        self.alb_sg = ec2.SecurityGroup(
            self, "ALBSG",
            vpc=self.main_vpc,
            description="Security group for Application Load Balancer",
            allow_all_outbound=True
        )
        self.alb_sg.add_ingress_rule(
            peer=ec2.Peer.any_ipv4(),
            connection=ec2.Port.tcp(80),
            description="Allow HTTP from anywhere"
        )
        self.alb_sg.add_ingress_rule(
            peer=ec2.Peer.any_ipv4(),
            connection=ec2.Port.tcp(443),
            description="Allow HTTPS from anywhere"
        )
        
        # ECS Tasks Security Group
        self.ecs_tasks_sg = ec2.SecurityGroup(
            self, "ECSTasksSG",
            vpc=self.main_vpc,
            description="Security group for ECS Fargate tasks",
            allow_all_outbound=True
        )
        self.ecs_tasks_sg.add_ingress_rule(
            peer=self.alb_sg,
            connection=ec2.Port.tcp(8000),
            description="Allow Django traffic from ALB"
        )
        
        # Sandbox Lambda Security Group
        self.sandbox_lambda_sg = ec2.SecurityGroup(
            self, "SandboxLambdaSG",
            vpc=self.sandbox_vpc,
            description="Security group for Sandbox Lambda functions",
            allow_all_outbound=False  # No internet
        )
        self.sandbox_lambda_sg.add_ingress_rule(
            peer=self.ecs_tasks_sg,
            connection=ec2.Port.all_tcp(),
            description="Allow from Orchestrator ECS tasks via VPC peering"
        )
        self.sandbox_lambda_sg.add_egress_rule(
            peer=ec2.Peer.ipv4(self.main_vpc.vpc_cidr_block),
            connection=ec2.Port.all_tcp(),
            description="Allow outbound only to Main VPC"
        )
        
        # ====================================================================
        # OUTPUTS
        # ====================================================================
        CfnOutput(self, "MainVPCId", value=self.main_vpc.vpc_id)
        CfnOutput(self, "SandboxVPCId", value=self.sandbox_vpc.vpc_id)
        CfnOutput(self, "VPCPeeringId", value=self.vpc_peering.ref)
