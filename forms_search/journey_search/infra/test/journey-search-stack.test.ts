// Checks the parts of the stack that keep the service secure and working. Run: npm test
import { test } from "node:test";
import * as cdk from "aws-cdk-lib";
import { Match, Template } from "aws-cdk-lib/assertions";
import { JourneySearchStack } from "../lib/journey-search-stack";

const template = Template.fromStack(
  new JourneySearchStack(new cdk.App(), "Test", { env: { account: "123456789012", region: "eu-west-2" } }),
);

test("the catalogue table has an on-demand COSINE vector index", () => {
  template.hasResourceProperties("AWS::DynamoDB::Table", {
    BillingMode: "PAY_PER_REQUEST",
    VectorIndexes: [
      Match.objectLike({
        IndexName: "description-embedding",
        VectorAttribute: { AttributeName: "embedding" },
        Dimensions: 1536,
        DistanceFunction: "COSINE",
        Projection: { ProjectionType: "INCLUDE", NonKeyAttributes: ["title", "description"] },
      }),
    ],
  });
});

test("the MCP runtime only accepts the orchestration client's tokens", () => {
  template.hasResourceProperties("AWS::BedrockAgentCore::Runtime", {
    ProtocolConfiguration: "MCP",
    AuthorizerConfiguration: {
      CustomJWTAuthorizer: {
        DiscoveryUrl: Match.anyValue(),
        AllowedClients: [Match.anyValue()],
        AllowedScopes: ["journey-search/search"],
      },
    },
  });
});

test("callers use OAuth client credentials only", () => {
  template.hasResourceProperties("AWS::Cognito::UserPoolClient", {
    AllowedOAuthFlows: ["client_credentials"],
    GenerateSecret: true,
  });
  template.hasResourceProperties("AWS::Cognito::UserPool", {
    AdminCreateUserConfig: { AllowAdminCreateUserOnly: true },
  });
});

test("the service can only search the vector index, not read or write the table", () => {
  const statements = Object.values(template.findResources("AWS::IAM::Policy")).flatMap(
    (policy: any) => policy.Properties.PolicyDocument.Statement,
  );
  const dynamoActions = statements.flatMap((s: any) => [s.Action].flat()).filter((a: string) => a.startsWith("dynamodb:"));
  if (JSON.stringify(dynamoActions) !== JSON.stringify(["dynamodb:SearchVectors"])) {
    throw new Error(`unexpected DynamoDB permissions: ${dynamoActions}`);
  }
});

test("only AgentCore in this account can assume the execution role", () => {
  template.hasResourceProperties("AWS::IAM::Role", {
    AssumeRolePolicyDocument: {
      Statement: [
        Match.objectLike({
          Principal: { Service: "bedrock-agentcore.amazonaws.com" },
          Condition: { StringEquals: { "aws:SourceAccount": "123456789012" }, ArnLike: Match.anyValue() },
        }),
      ],
    },
  });
});
