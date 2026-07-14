import * as cdk from 'aws-cdk-lib';
import { TokenSecretsStack } from '../lib/secrets-stack';

const app = new cdk.App();

new TokenSecretsStack(app, 'TokenSecretsStack', {
  env: { 
    account: process.env.CDK_DEFAULT_ACCOUNT, 
    region: process.env.CDK_DEFAULT_REGION || 'eu-west-2' 
  },
});