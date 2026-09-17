import * as cdk from 'aws-cdk-lib';
import { Tags } from 'aws-cdk-lib';

import { TokenSecretsStack } from '../lib/secrets-stack';
import { SharedVpcStack } from '../lib/shared-vpc-stack';
import { TemporalDatabaseStack } from '../lib/temporal-database-stack';
import { TemporalServerStack } from '../lib/temporal-server-stack';

const app = new cdk.App();

const env = {
  account: process.env.CDK_DEFAULT_ACCOUNT,
  region: process.env.CDK_DEFAULT_REGION || 'eu-west-2',
};

new TokenSecretsStack(app, 'TokenSecretsStack', {
  env,
});

const sharedVpc = new SharedVpcStack(app, 'SharedVpcStack', {
  env,
});

const database = new TemporalDatabaseStack(
  app,
  'TemporalDatabaseStack',
  {
    env,
    vpc: sharedVpc.vpc,
  },
);

new TemporalServerStack(
  app,
  'TemporalServerStack',
  {
    env,
    vpc: sharedVpc.vpc,
    database: database.database,
    databaseSecret: database.databaseSecret,
  },
);

Tags.of(app).add('Environment', 'development');
Tags.of(app).add('Product', 'once-ailegibility');
Tags.of(app).add('ManagedBy', 'AWS-CDK');
Tags.of(app).add('Service', 'Agentic Legibility');
Tags.of(app).add(
  'Owner',
  'ai-agentic-legibility@digital.cabinet-office.gov.uk',
);
Tags.of(app).add(
  'Source',
  'https://github.com/govuk-once/govuk-agentic-legibility',
);