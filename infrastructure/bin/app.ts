import * as cdk from 'aws-cdk-lib';
import { Tags } from 'aws-cdk-lib';
import { TokenSecretsStack } from '../lib/secrets-stack';
import { SharedVpcStack } from '../lib/shared-vpc-stack';
import { DurablePocStack } from "../lib/durable-poc-stack";

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

new DurablePocStack(
  app,
  "DurablePocStack",
  {
    env,
    vpc: sharedVpc.vpc,
    repoUrl:
      "https://github.com/govuk-once/govuk-agentic-legibility",
  }
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