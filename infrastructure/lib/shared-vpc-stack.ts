import * as cdk from 'aws-cdk-lib';
import * as ec2 from 'aws-cdk-lib/aws-ec2';
import * as ssm from 'aws-cdk-lib/aws-ssm';
import { Construct } from 'constructs';

export class SharedVpcStack extends cdk.Stack {
  public readonly vpc: ec2.Vpc;

  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    this.vpc = new ec2.Vpc(this, 'AgenticLegibilitySharedVpc', {
      maxAzs: 2,
      natGateways: 1,
    });

    new ssm.StringParameter(this, 'ALSharedVpcId', {
      parameterName: '/network/al-shared-vpc-id',
      stringValue: this.vpc.vpcId,
      description: 'Shared VPC ID for Agentic Legibility',
    });

    new cdk.CfnOutput(this, 'SharedVpcId', {
      value: this.vpc.vpcId,
      description: 'ID of the shared VPC',
    });
  }
}