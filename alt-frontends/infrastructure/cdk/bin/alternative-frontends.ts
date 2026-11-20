#!/usr/bin/env node

import * as cdk from 'aws-cdk-lib';
import * as dotenv from 'dotenv';

import {
  AlternativeFrontendsRepositoryStack,
} from '../lib/repository-stack';

import {
  AlternativeFrontendsServiceStack,
} from '../lib/service-stack';

dotenv.config();

const app = new cdk.App();

const env = {
  account: process.env.CDK_DEFAULT_ACCOUNT,
  region: 'eu-west-2',
};

const repositoryStack =
  new AlternativeFrontendsRepositoryStack(
    app,
    'AlternativeFrontendsRepositoryStack',
    {
      env,
    },
  );

new AlternativeFrontendsServiceStack(
  app,
  'AlternativeFrontendsServiceStack',
  {
    env,
    repositoryName:
      repositoryStack.repository.repositoryName,
  },
);
