import * as cdk from 'aws-cdk-lib';
import { Tags } from 'aws-cdk-lib';
import { TokenSecretsStack } from '../lib/secrets-stack';

const app = new cdk.App();

new TokenSecretsStack(app, 'TokenSecretsStack', {
  env: { 
    account: process.env.CDK_DEFAULT_ACCOUNT, 
    region: process.env.CDK_DEFAULT_REGION || 'eu-west-2' 
  },
});

Tags.of(app).add("Environment", "development")
Tags.of(app).add("Product", "once-ailegibility")
Tags.of(app).add("ManagedBy", "AWS-CDK")
Tags.of(app).add("Service", "Agentic Legibility")
Tags.of(app).add("Owner", "ai-agentic-legibility@digital.cabinet-office.gov.uk")
Tags.of(app).add("Source", "https://github.com/govuk-once/govuk-agentic-legibility")