import * as cdk from 'aws-cdk-lib';
import * as ecr from 'aws-cdk-lib/aws-ecr';

import { Construct } from 'constructs';

export class AlternativeFrontendsRepositoryStack
  extends cdk.Stack {

  public readonly repository: ecr.Repository;

  constructor(
    scope: Construct,
    id: string,
    props?: cdk.StackProps,
  ) {
    super(scope, id, props);

    this.repository =
      new ecr.Repository(
        this,
        'Repository',
        {
          repositoryName:
            'alternative-frontends',

          imageTagMutability:
            ecr.TagMutability.MUTABLE,

          emptyOnDelete: true,

          removalPolicy:
            cdk.RemovalPolicy.DESTROY,
        },
      );

    this.repository.addLifecycleRule({
      maxImageCount: 10,
    });

    new cdk.CfnOutput(
      this,
      'RepositoryUri',
      {
        value:
          this.repository.repositoryUri,
      },
    );

    new cdk.CfnOutput(
      this,
      'RepositoryName',
      {
        value:
          this.repository.repositoryName,
      },
    );
  }
}
