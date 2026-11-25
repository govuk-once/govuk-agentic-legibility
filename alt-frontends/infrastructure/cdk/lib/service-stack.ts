import * as cdk from 'aws-cdk-lib';

import * as ec2 from 'aws-cdk-lib/aws-ec2';
import * as ecs from 'aws-cdk-lib/aws-ecs';
import * as ecsPatterns from 'aws-cdk-lib/aws-ecs-patterns';
import * as ecr from 'aws-cdk-lib/aws-ecr';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as logs from 'aws-cdk-lib/aws-logs';

import { Construct } from 'constructs';

interface ServiceStackProps
  extends cdk.StackProps {
  repositoryName: string;
}

export class AlternativeFrontendsServiceStack
  extends cdk.Stack {

  constructor(
    scope: Construct,
    id: string,
    props: ServiceStackProps,
  ) {
    super(scope, id, props);

    const repository =
      ecr.Repository.fromRepositoryName(
        this,
        'Repository',
        props.repositoryName,
      );

    const vpc =
      ec2.Vpc.fromLookup(
        this,
        'DefaultVpc',
        {
          isDefault: true,
        },
      );

    const cluster =
      new ecs.Cluster(
        this,
        'Cluster',
        {
          clusterName:
            'alternative-frontends',

          vpc,

          containerInsights: true,
        },
      );

    const logGroup =
      new logs.LogGroup(
        this,
        'LogGroup',
        {
          logGroupName:
            '/ecs/alternative-frontends',

          retention:
            logs.RetentionDays.ONE_MONTH,

          removalPolicy:
            cdk.RemovalPolicy.DESTROY,
        },
      );

    const taskRole =
      new iam.Role(
        this,
        'TaskRole',
        {
          assumedBy:
            new iam.ServicePrincipal(
              'ecs-tasks.amazonaws.com',
            ),
        },
      );

    taskRole.addToPolicy(
      new iam.PolicyStatement({
        effect: iam.Effect.ALLOW,

        actions: [
          'polly:SynthesizeSpeech',
          'polly:StartSpeechSynthesisStream',
          'polly:DescribeVoices',
          'transcribe:StartStreamTranscription',
          'bedrock:InvokeModel',
          'bedrock:InvokeModelWithResponseStream'
        ],

        resources: ['*'],
      }),
    );

    const service =
      new ecsPatterns.ApplicationLoadBalancedFargateService(
        this,
        'Service',
        {
          cluster,

          serviceName:
            'alternative-frontends',

          publicLoadBalancer: true,

          desiredCount: 1,

          cpu: 512,

          memoryLimitMiB: 1024,

          taskImageOptions: {
            image:
              ecs.ContainerImage
                .fromEcrRepository(
                  repository,
                  'latest',
                ),

            containerName:
              'alternative-frontends',

            containerPort: 3000,

            taskRole,

            logDriver:
              ecs.LogDrivers.awsLogs({
                streamPrefix:
                  'alternative-frontends',

                logGroup,
              }),
          },
        },
      );

    service.targetGroup.configureHealthCheck({
      path: '/',
      healthyHttpCodes: '200',
      interval:
        cdk.Duration.seconds(30),
    });

    new cdk.CfnOutput(
      this,
      'LoadBalancerUrl',
      {
        value: `http://${service.loadBalancer.loadBalancerDnsName}`,
      },
    );

    new cdk.CfnOutput(
      this,
      'ClusterName',
      {
        value:
          cluster.clusterName,
      },
    );

    new cdk.CfnOutput(
      this,
      'ServiceName',
      {
        value:
          service.service.serviceName,
      },
    );
  }
}
