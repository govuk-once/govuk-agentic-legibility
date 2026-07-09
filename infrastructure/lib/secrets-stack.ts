import * as cdk from 'aws-cdk-lib';
import * as secretsmanager from 'aws-cdk-lib/aws-secretsmanager';
import { Construct } from 'constructs';

export class TokenSecretsStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    // 1. DVLA Linking Token Secret
    const dvlaSecret = new secretsmanager.Secret(this, 'DvlaLinkingTokenSecret', {
      secretName: 'dvla-linking-token',
      description: 'Caches the DVLA linking token',
    });

    // 2. Flex Access Token Secret
    const flexSecret = new secretsmanager.Secret(this, 'FlexAccessTokenSecret', {
      secretName: 'flex-access-token',
      description: 'Caches the Flex JWT access token',
    });
    
    // Output the names to the console after deployment
    new cdk.CfnOutput(this, 'DvlaSecretName', { value: dvlaSecret.secretName });
    new cdk.CfnOutput(this, 'FlexSecretName', { value: flexSecret.secretName });
  }
}