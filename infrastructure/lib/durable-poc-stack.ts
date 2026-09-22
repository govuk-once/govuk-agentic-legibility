import {
  Stack,
  StackProps,
  CfnOutput,
} from "aws-cdk-lib";
import { Construct } from "constructs";
import * as ec2 from "aws-cdk-lib/aws-ec2";
import * as iam from "aws-cdk-lib/aws-iam";
import * as ssm from "aws-cdk-lib/aws-ssm";

export interface DurablePocStackProps extends StackProps {
  vpc: ec2.IVpc;
  repoUrl: string;
}

export class DurablePocStack extends Stack {
  constructor(
    scope: Construct,
    id: string,
    props: DurablePocStackProps
  ) {
    super(scope, id, props);

    const securityGroup = new ec2.SecurityGroup(
      this,
      "DurablePocSecurityGroup",
      {
        vpc: props.vpc,
        description:
          "Allow Chat UI and Temporal UI access",
        allowAllOutbound: true,
      }
    );

    securityGroup.addIngressRule(
      ec2.Peer.anyIpv4(),
      ec2.Port.tcp(7860),
      "Chat Application"
    );

    securityGroup.addIngressRule(
      ec2.Peer.anyIpv4(),
      ec2.Port.tcp(8080),
      "Temporal UI"
    );

    const role = new iam.Role(
      this,
      "DurablePocInstanceRole",
      {
        assumedBy: new iam.ServicePrincipal(
          "ec2.amazonaws.com"
        ),
        managedPolicies: [
          iam.ManagedPolicy.fromAwsManagedPolicyName(
            "AmazonSSMManagedInstanceCore"
          ),
        ],
      }
    );

    role.addToPolicy(
      new iam.PolicyStatement({
        actions: [
          "ssm:GetParameter",
          "ssm:GetParameters",
          "ssm:GetParametersByPath",
        ],
        resources: [
          `arn:aws:ssm:${this.region}:${this.account}:parameter/durable_poc/*`,
          `arn:aws:ssm:${this.region}:${this.account}:parameter/workflow-service/*`,
          `arn:aws:ssm:${this.region}:${this.account}:parameter/flex-mock/*`,
        ],
      })
    );

    role.addToPolicy(
      new iam.PolicyStatement({
        actions: [
          "s3:PutObject"
        ],
        resources: [
          "arn:aws:s3:::temp-ailegibility-otel-traces/*"
        ]
      })
    );

    role.addToPolicy(
      new iam.PolicyStatement({
        actions: [
          "bedrock:InvokeModel",
          "bedrock:InvokeModelWithResponseStream"
        ],
        resources: [
          "arn:aws:bedrock:eu-west-2::foundation-model/*"
        ]
      })
    );

    const userData = ec2.UserData.forLinux();

    userData.addCommands(
      "set -euxo pipefail",

      "# Update OS",
      "dnf update -y",

      "# Install prerequisites",
      "dnf install -y git",

      "# Create application directory",
      "mkdir -p /app",
      "chown ec2-user:ec2-user /app",

      "# Install UV as ec2-user",
      "sudo -u ec2-user bash -c 'curl -LsSf https://astral.sh/uv/install.sh | sh'",

      "# Verify uv installation",
      "ls -la /home/ec2-user/.local/bin",

      "# Clone repository",
      `sudo -u ec2-user git clone ${props.repoUrl} /app/durable_poc`,

      "# Install Python 3.14",
      "sudo -u ec2-user /home/ec2-user/.local/bin/uv python install 3.14",

      "# Install project dependencies",
      "cd /app/durable_poc",
      "sudo -u ec2-user /home/ec2-user/.local/bin/uv sync",

      "# Install Temporal CLI",
      "curl -sSf https://temporal.download/cli.sh | sh",

      "# Copy Temporal binary to globally accessible location",
      "cp /root/.temporalio/bin/temporal /usr/local/bin/temporal",
      "chmod 755 /usr/local/bin/temporal",

      "# Verify Temporal installation",
      "/usr/local/bin/temporal version || true",

      "# Create environment file",
      "aws --version",
      "MOCK_SERVER_URL=$(aws ssm get-parameter --region eu-west-2 --name /flex-mock/server-url --query 'Parameter.Value' --output text)",
      "WORKFLOW_SERVER_URL=$(aws ssm get-parameter --region eu-west-2 --name /workflow-service/server-url --query 'Parameter.Value' --output text)",

      "cat <<EOF >/etc/durable-poc.env",
      "DVLA_BASE=${MOCK_SERVER_URL}",
      "POSTOFFICE_BASE=${MOCK_SERVER_URL}",
      "HMRC_BASE=${MOCK_SERVER_URL}",
      "DWP_BASE=${MOCK_SERVER_URL}",
      "WORKFLOW_SERVER_URL=${WORKFLOW_SERVER_URL}",
      "AWS_REGION=eu-west-2",
      "TEMPORAL_ADDRESS=localhost:7233",
      "EOF",

      "# Temporal Service",
      "cat << 'EOF' > /etc/systemd/system/temporal.service",
      "[Unit]",
      "Description=Temporal Dev Server",
      "After=network.target",
      "",
      "[Service]",
      "Type=simple",
      "User=ec2-user",
      "ExecStart=/usr/local/bin/temporal server start-dev --ip 0.0.0.0 --ui-port 8080",
      "Restart=always",
      "",
      "[Install]",
      "WantedBy=multi-user.target",
      "EOF",

      "# Worker Service",
      "cat << 'EOF' > /etc/systemd/system/temporal-worker.service",
      "[Unit]",
      "Description=Durable POC Worker",
      "Requires=temporal.service",
      "After=temporal.service",
      "",
      "[Service]",
      "Type=simple",
      "User=ec2-user",
      "EnvironmentFile=/etc/durable-poc.env",
      "WorkingDirectory=/app/durable_poc/durable_poc",
      "ExecStart=/home/ec2-user/.local/bin/uv run python -m src.worker",
      "Restart=always",
      "",
      "[Install]",
      "WantedBy=multi-user.target",
      "EOF",

      "# Chat Service",
      "cat << 'EOF' > /etc/systemd/system/durable-chat.service",
      "[Unit]",
      "Description=Durable POC Chat Application",
      "Requires=temporal-worker.service",
      "After=temporal-worker.service",
      "",
      "[Service]",
      "Type=simple",
      "User=ec2-user",
      "EnvironmentFile=/etc/durable-poc.env",
      "WorkingDirectory=/app/durable_poc/durable_poc",
      "ExecStart=/home/ec2-user/.local/bin/uv run python -m agent.chat",
      "Restart=always",
      "",
      "[Install]",
      "WantedBy=multi-user.target",
      "EOF",

      "# Enable services",
      "systemctl daemon-reload",
      "systemctl enable temporal",
      "systemctl enable temporal-worker",
      "systemctl enable durable-chat",

      "# Start services",
      "systemctl start temporal",
      "sleep 20",
      "systemctl start temporal-worker",
      "sleep 10",
      "systemctl start durable-chat"
    );

    const instance = new ec2.Instance(
      this,
      "DurablePocInstance",
      {
        vpc: props.vpc,
        vpcSubnets: {
          subnetType: ec2.SubnetType.PUBLIC,
        },
        instanceType: ec2.InstanceType.of(
          ec2.InstanceClass.T3,
          ec2.InstanceSize.MEDIUM
        ),
        machineImage:
          ec2.MachineImage.latestAmazonLinux2023(),
        securityGroup,
        role,
        userData,
        associatePublicIpAddress: true,
      }
    );

    new ssm.StringParameter(this, "DurablePocChatUrl", {
      parameterName: "/durable_poc/chat_url",
      stringValue: `http://${instance.instancePublicDnsName}:7860`,
    });

    new ssm.StringParameter(this, "DurablePocTemporalUrl", {
      parameterName: "/durable_poc/temporal_url",
      stringValue: `http://${instance.instancePublicDnsName}:8080`,
    });

    new CfnOutput(this, "InstancePublicDns", {
      value: instance.instancePublicDnsName,
      description: "EC2 Public DNS",
    });

    new CfnOutput(this, "ChatAppUrl", {
      value: `http://${instance.instancePublicDnsName}:7860`,
      description: "Chat Application URL",
    });

    new CfnOutput(this, "TemporalUiUrl", {
      value: `http://${instance.instancePublicDnsName}:8080`,
      description: "Temporal UI URL",
    });
  }
}