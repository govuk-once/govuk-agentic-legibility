import {
  Stack,
  StackProps,
  CfnOutput,
} from "aws-cdk-lib";
import { Construct } from "constructs";
import * as ec2 from "aws-cdk-lib/aws-ec2";
import * as iam from "aws-cdk-lib/aws-iam";

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

    const vpc = props.vpc;

    const securityGroup = new ec2.SecurityGroup(
      this,
      "DurablePocSecurityGroup",
      {
        vpc,
        description:
          "Allow Chat UI and Temporal UI access",
        allowAllOutbound: true,
      }
    );

    securityGroup.addIngressRule(
      ec2.Peer.anyIpv4(),
      ec2.Port.tcp(7860),
      "FastAPI Chat UI"
    );

    securityGroup.addIngressRule(
      ec2.Peer.anyIpv4(),
      ec2.Port.tcp(8080),
      "Temporal Web UI"
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
        ],
      })
    );

    const userData = ec2.UserData.forLinux();

    userData.addCommands(
      "dnf update -y",
      "dnf install -y git python3.11 python3.11-pip",

      "curl -sSf https://temporal.download/cli.sh | sh",
      "mv /root/.temporalio/bin/temporal /usr/local/bin/",

      "cat << 'EOF' > /etc/systemd/system/temporal.service",
      "[Unit]",
      "Description=Temporal Dev Server",
      "After=network.target",
      "[Service]",
      "Type=simple",
      "ExecStart=/usr/local/bin/temporal server start-dev --ip 0.0.0.0 --ui-port 8080",
      "Restart=always",
      "User=ec2-user",
      "[Install]",
      "WantedBy=multi-user.target",
      "EOF",

      "mkdir -p /app && chown ec2-user:ec2-user /app",
      `sudo -u ec2-user git clone ${props.repoUrl} /app/durable_poc`,
      "sudo -u ec2-user python3.11 -m venv /app/durable_poc/venv",
      "sudo -u ec2-user /app/durable_poc/venv/bin/pip install --upgrade pip",
      "sudo -u ec2-user /app/durable_poc/venv/bin/pip install -r /app/durable_poc/requirements.txt",

      "cat << 'EOF' > /etc/systemd/system/temporal-worker.service",
      "[Unit]",
      "Description=Durable POC Worker",
      "After=temporal.service",
      "[Service]",
      "Type=simple",
      "WorkingDirectory=/app/durable_poc",
      "ExecStart=/app/durable_poc/venv/bin/python -m src.worker",
      "Restart=always",
      "User=ec2-user",
      "[Install]",
      "WantedBy=multi-user.target",
      "EOF",

      "cat << 'EOF' > /etc/systemd/system/durable-chat.service",
      "[Unit]",
      "Description=Durable POC Chat App",
      "After=temporal-worker.service",
      "[Service]",
      "Type=simple",
      "WorkingDirectory=/app/durable_poc",
      "ExecStart=/app/durable_poc/venv/bin/python -m chat",
      "Restart=always",
      "User=ec2-user",
      "[Install]",
      "WantedBy=multi-user.target",
      "EOF",

      "systemctl daemon-reload",
      "systemctl enable temporal",
      "systemctl enable temporal-worker",
      "systemctl enable durable-chat",
      "systemctl start temporal",
      "systemctl start temporal-worker",
      "systemctl start durable-chat"
    );

    const instance = new ec2.Instance(
      this,
      "DurablePocInstance",
      {
        vpc,
        vpcSubnets: {
          subnetType: ec2.SubnetType.PUBLIC,
        },
        instanceType: ec2.InstanceType.of(
          ec2.InstanceClass.T3,
          ec2.InstanceSize.MEDIUM
        ),
        machineImage:
          ec2.MachineImage.latestAmazonLinux2023(),
        role,
        securityGroup,
        userData,
        associatePublicIpAddress: true,
      }
    );

    new CfnOutput(this, "InstancePublicDns", {
      value: instance.instancePublicDnsName,
      description: "EC2 Public DNS",
    });

    new CfnOutput(this, "ChatAppUrl", {
      value: `http://${instance.instancePublicDnsName}:7860`,
      description: "FastAPI Chat Application",
    });

    new CfnOutput(this, "TemporalWebUrl", {
      value: `http://${instance.instancePublicDnsName}:8080`,
      description: "Temporal Web UI",
    });
  }
}