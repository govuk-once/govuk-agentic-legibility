import * as cdk from 'aws-cdk-lib';
import { Construct } from 'constructs';
import * as ec2 from 'aws-cdk-lib/aws-ec2';
import * as ecs from 'aws-cdk-lib/aws-ecs';
import * as ecsPatterns from 'aws-cdk-lib/aws-ecs-patterns';
import * as logs from 'aws-cdk-lib/aws-logs';
import * as rds from 'aws-cdk-lib/aws-rds';
import * as secretsmanager from 'aws-cdk-lib/aws-secretsmanager';

export interface TemporalServerStackProps extends cdk.StackProps {
  vpc: ec2.IVpc;
  database: rds.DatabaseInstance;
  databaseSecret: secretsmanager.ISecret;
}

export class TemporalServerStack extends cdk.Stack {
  public readonly cluster: ecs.Cluster;
  public readonly service: ecs.FargateService;

  constructor(
    scope: Construct,
    id: string,
    props: TemporalServerStackProps,
  ) {
    super(scope, id, props);

    this.cluster = new ecs.Cluster(this, 'TemporalCluster', {
      vpc: props.vpc,
      containerInsights: true,
    });

    const temporalSg = new ec2.SecurityGroup(
      this,
      'TemporalServerSG',
      {
        vpc: props.vpc,
        allowAllOutbound: true,
      },
    );

    const logGroup = new logs.LogGroup(this, 'TemporalLogs', {
      retention: logs.RetentionDays.ONE_MONTH,
    });

    const fargate =
      new ecsPatterns.ApplicationLoadBalancedFargateService(
        this,
        'TemporalService',
        {
          cluster: this.cluster,

          enableExecuteCommand: true,

          cpu: 1024,
          memoryLimitMiB: 2048,

          desiredCount: 1,

          publicLoadBalancer: false,

          securityGroups: [temporalSg],

          taskImageOptions: {
            image: ecs.ContainerImage.fromRegistry(
              'temporalio/auto-setup:1.28'
            ),

            containerPort: 7233,

            environment: {
              DB: 'postgres12',

              DB_PORT: '5432',

              POSTGRES_SEEDS:
                props.database.dbInstanceEndpointAddress,

              POSTGRES_USER: 'temporal',

              POSTGRES_DB: 'temporal',
            },

            secrets: {
              POSTGRES_PWD: ecs.Secret.fromSecretsManager(
                props.databaseSecret,
                'password',
              ),
            },

            logDriver: ecs.LogDrivers.awsLogs({
              streamPrefix: 'temporal',
              logGroup,
            }),
          },
        },
      );

    this.service = fargate.service;

    new cdk.CfnOutput(this, 'TemporalEndpoint', {
      value: fargate.loadBalancer.loadBalancerDnsName,
    });
  }
}
