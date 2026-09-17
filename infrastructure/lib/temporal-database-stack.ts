import * as cdk from 'aws-cdk-lib';
import { Construct } from 'constructs';
import * as ec2 from 'aws-cdk-lib/aws-ec2';
import * as rds from 'aws-cdk-lib/aws-rds';
import * as secretsmanager from 'aws-cdk-lib/aws-secretsmanager';

export interface TemporalDatabaseStackProps extends cdk.StackProps {
  vpc: ec2.IVpc;
}

export class TemporalDatabaseStack extends cdk.Stack {
  public readonly database: rds.DatabaseInstance;
  public readonly databaseSecret: secretsmanager.ISecret;

  constructor(
    scope: Construct,
    id: string,
    props: TemporalDatabaseStackProps,
  ) {
    super(scope, id, props);

    const databaseSecurityGroup = new ec2.SecurityGroup(
      this,
      'TemporalDatabaseSecurityGroup',
      {
        vpc: props.vpc,
        description: 'Security group for Temporal PostgreSQL database',
        allowAllOutbound: true,
      },
    );

    databaseSecurityGroup.addIngressRule(
      ec2.Peer.ipv4(props.vpc.vpcCidrBlock),
      ec2.Port.tcp(5432),
      'Allow PostgreSQL access from VPC',
    );

    const credentials = new rds.DatabaseSecret(
      this,
      'TemporalDatabaseCredentials',
      {
        username: 'temporal',
      },
    );

    this.databaseSecret = credentials;

    this.database = new rds.DatabaseInstance(
      this,
      'TemporalPostgres',
      {
        engine: rds.DatabaseInstanceEngine.postgres({
          version: rds.PostgresEngineVersion.VER_16,
        }),

        instanceType: ec2.InstanceType.of(
          ec2.InstanceClass.T4G,
          ec2.InstanceSize.SMALL,
        ),

        credentials: rds.Credentials.fromSecret(credentials),

        databaseName: 'temporal',

        vpc: props.vpc,

        vpcSubnets: {
          subnetType: ec2.SubnetType.PRIVATE_WITH_EGRESS,
        },

        securityGroups: [databaseSecurityGroup],

        allocatedStorage: 20,
        maxAllocatedStorage: 100,

        multiAz: false,

        backupRetention: cdk.Duration.days(7),

        deletionProtection: false,

        removalPolicy: cdk.RemovalPolicy.DESTROY,

        publiclyAccessible: false,

        storageEncrypted: true,

        monitoringInterval: cdk.Duration.seconds(60),
      },
    );

    new cdk.CfnOutput(this, 'TemporalDbEndpoint', {
      value: this.database.dbInstanceEndpointAddress,
    });

    new cdk.CfnOutput(this, 'TemporalDbPort', {
      value: this.database.dbInstanceEndpointPort,
    });

    new cdk.CfnOutput(this, 'TemporalDbSecretArn', {
      value: credentials.secretArn,
    });
  }
}