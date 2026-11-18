import * as path from "path";
import { CfnOutput, Duration, RemovalPolicy, Stack, StackProps } from "aws-cdk-lib";
import * as bedrockagentcore from "aws-cdk-lib/aws-bedrockagentcore";
import * as cognito from "aws-cdk-lib/aws-cognito";
import * as dynamodb from "aws-cdk-lib/aws-dynamodb";
import * as ecrAssets from "aws-cdk-lib/aws-ecr-assets";
import * as iam from "aws-cdk-lib/aws-iam";
import * as ssm from "aws-cdk-lib/aws-ssm";
import { Construct } from "constructs";

// Must match the service's defaults in src/journey_search/config.py and store.py.
const RUNTIME_NAME = "journey_search";
const VECTOR_INDEX_NAME = "description-embedding";
const VECTOR_ATTRIBUTE = "embedding";
const EMBEDDING_MODEL_ID = "eu.cohere.embed-v4:0";
const EMBEDDING_FOUNDATION_MODEL = "cohere.embed-v4:0";
const EMBEDDING_DIMENSIONS = 1536;
const RESOURCE_SERVER_ID = "journey-search";
const SEARCH_SCOPE = "search";

/**
 * Journey Search as a hosted MCP service.
 *
 * - DynamoDB holds the catalogue, with a COSINE vector index over each journey's embedding.
 * - Amazon Bedrock AgentCore Runtime runs the MCP container behind an HTTPS endpoint.
 * - Callers authenticate with a Cognito OAuth client-credentials token, which AgentCore's JWT
 *   authorizer checks before any request reaches the container. Callers never need AWS credentials.
 */
export class JourneySearchStack extends Stack {
  constructor(scope: Construct, id: string, props?: StackProps) {
    super(scope, id, props);

    // --- Catalogue table with a vector index --------------------------------------------------

    const table = new dynamodb.Table(this, "Catalogue", {
      partitionKey: { name: "workflow_id", type: dynamodb.AttributeType.STRING },
      // Vector indexes require on-demand capacity.
      billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
      pointInTimeRecoverySpecification: { pointInTimeRecoveryEnabled: true },
      // The catalogue can be reloaded, but keep it if the stack is deleted by mistake.
      removalPolicy: RemovalPolicy.RETAIN,
    });
    const cfnTable = table.node.defaultChild as dynamodb.CfnTable;
    cfnTable.vectorIndexes = [
      {
        indexName: VECTOR_INDEX_NAME,
        vectorAttribute: { attributeName: VECTOR_ATTRIBUTE },
        dimensions: EMBEDDING_DIMENSIONS,
        distanceFunction: "COSINE",
        // Only what the tool returns; the embedding itself is never read back.
        projection: { projectionType: "INCLUDE", nonKeyAttributes: ["title", "description"] },
      },
    ];
    const vectorIndexArn = `${table.tableArn}/index/${VECTOR_INDEX_NAME}`;

    // --- Container image (AgentCore Runtime requires ARM64) -----------------------------------

    const image = new ecrAssets.DockerImageAsset(this, "Image", {
      directory: path.join(__dirname, "..", ".."),
      platform: ecrAssets.Platform.LINUX_ARM64,
    });

    // --- Authentication: OAuth client credentials for service-to-service calls ----------------

    const userPool = new cognito.UserPool(this, "Callers", {
      userPoolName: "journey-search-callers",
      // Machine clients only: nobody signs up or signs in as a person.
      selfSignUpEnabled: false,
      removalPolicy: RemovalPolicy.DESTROY,
    });
    const searchScope = new cognito.ResourceServerScope({
      scopeName: SEARCH_SCOPE,
      scopeDescription: "Search service journeys",
    });
    const resourceServer = userPool.addResourceServer("Api", {
      identifier: RESOURCE_SERVER_ID,
      scopes: [searchScope],
    });
    const domain = userPool.addDomain("Domain", {
      cognitoDomain: { domainPrefix: `journey-search-${this.account}` },
    });
    // One client per consuming team, so access can be revoked independently.
    const orchestrationClient = userPool.addClient("OrchestrationTeam", {
      userPoolClientName: "orchestration-team",
      generateSecret: true,
      authFlows: {},
      oAuth: {
        flows: { clientCredentials: true },
        scopes: [cognito.OAuthScope.resourceServer(resourceServer, searchScope)],
      },
      accessTokenValidity: Duration.hours(1),
      enableTokenRevocation: true,
    });

    // --- Execution role: only what the running service needs ----------------------------------

    const role = new iam.Role(this, "RuntimeRole", {
      description: "Journey Search MCP service on AgentCore Runtime",
      assumedBy: new iam.ServicePrincipal("bedrock-agentcore.amazonaws.com", {
        conditions: {
          StringEquals: { "aws:SourceAccount": this.account },
          ArnLike: { "aws:SourceArn": `arn:aws:bedrock-agentcore:${this.region}:${this.account}:*` },
        },
      }),
    });
    image.repository.grantPull(role);
    role.addToPolicy(
      new iam.PolicyStatement({
        sid: "SearchCatalogue",
        actions: ["dynamodb:SearchVectors"],
        resources: [vectorIndexArn],
      }),
    );
    role.addToPolicy(
      new iam.PolicyStatement({
        sid: "EmbedQueries",
        actions: ["bedrock:InvokeModel"],
        resources: [
          `arn:aws:bedrock:${this.region}:${this.account}:inference-profile/${EMBEDDING_MODEL_ID}`,
          // The EU inference profile may route to any EU Region.
          `arn:aws:bedrock:*::foundation-model/${EMBEDDING_FOUNDATION_MODEL}`,
        ],
      }),
    );
    const runtimeLogs = `arn:aws:logs:${this.region}:${this.account}:log-group:/aws/bedrock-agentcore/runtimes/*`;
    role.addToPolicy(
      new iam.PolicyStatement({
        sid: "Logs",
        actions: ["logs:CreateLogGroup", "logs:DescribeLogStreams", "logs:CreateLogStream", "logs:PutLogEvents"],
        resources: [runtimeLogs, `${runtimeLogs}:log-stream:*`],
      }),
    );
    role.addToPolicy(
      new iam.PolicyStatement({
        sid: "DescribeLogGroups",
        actions: ["logs:DescribeLogGroups"],
        resources: [`arn:aws:logs:${this.region}:${this.account}:log-group:*`],
      }),
    );
    role.addToPolicy(
      new iam.PolicyStatement({
        sid: "Tracing",
        actions: ["xray:PutTraceSegments", "xray:PutTelemetryRecords", "xray:GetSamplingRules", "xray:GetSamplingTargets"],
        resources: ["*"],
      }),
    );
    role.addToPolicy(
      new iam.PolicyStatement({
        sid: "Metrics",
        actions: ["cloudwatch:PutMetricData"],
        resources: ["*"],
        conditions: { StringEquals: { "cloudwatch:namespace": "bedrock-agentcore" } },
      }),
    );
    role.addToPolicy(
      new iam.PolicyStatement({
        sid: "WorkloadIdentity",
        actions: ["bedrock-agentcore:GetWorkloadAccessToken", "bedrock-agentcore:GetWorkloadAccessTokenForJWT"],
        resources: [
          `arn:aws:bedrock-agentcore:${this.region}:${this.account}:workload-identity-directory/default`,
          `arn:aws:bedrock-agentcore:${this.region}:${this.account}:workload-identity-directory/default/workload-identity/${RUNTIME_NAME}-*`,
        ],
      }),
    );

    // --- AgentCore Runtime hosting the MCP server ---------------------------------------------

    const runtime = new bedrockagentcore.CfnRuntime(this, "Runtime", {
      agentRuntimeName: RUNTIME_NAME,
      description: "Journey Search: finds GOV.UK service journeys for the orchestrating agent",
      roleArn: role.roleArn,
      agentRuntimeArtifact: { containerConfiguration: { containerUri: image.imageUri } },
      networkConfiguration: { networkMode: "PUBLIC" },
      protocolConfiguration: "MCP",
      authorizerConfiguration: {
        customJwtAuthorizer: {
          discoveryUrl: `https://cognito-idp.${this.region}.amazonaws.com/${userPool.userPoolId}/.well-known/openid-configuration`,
          allowedClients: [orchestrationClient.userPoolClientId],
          allowedScopes: [`${RESOURCE_SERVER_ID}/${SEARCH_SCOPE}`],
        },
      },
      environmentVariables: {
        JOURNEY_SEARCH_TABLE: table.tableName,
        JOURNEY_SEARCH_VECTOR_INDEX: VECTOR_INDEX_NAME,
        JOURNEY_SEARCH_EMBEDDING_MODEL: EMBEDDING_MODEL_ID,
        JOURNEY_SEARCH_EMBEDDING_DIMENSIONS: String(EMBEDDING_DIMENSIONS),
      },
    });
    // The role's policy must exist before AgentCore validates the runtime.
    runtime.node.addDependency(role);

    // --- Outputs -------------------------------------------------------------------------------

    // The MCP URL embeds the runtime ARN, URL-encoded.
    const escapedArn = `arn%3Aaws%3Abedrock-agentcore%3A${this.region}%3A${this.account}%3Aruntime%2F${runtime.attrAgentRuntimeId}`;
    const mcpUrl = `https://bedrock-agentcore.${this.region}.amazonaws.com/runtimes/${escapedArn}/invocations?qualifier=DEFAULT`;
    const tokenUrl = `${domain.baseUrl()}/oauth2/token`;

    const outputs: Record<string, [string, string]> = {
      McpUrl: [mcpUrl, "MCP endpoint for callers"],
      TokenUrl: [tokenUrl, "OAuth token endpoint (client credentials grant)"],
      Scope: [`${RESOURCE_SERVER_ID}/${SEARCH_SCOPE}`, "OAuth scope to request"],
      ClientId: [orchestrationClient.userPoolClientId, "Orchestration team's client ID (secret shared separately)"],
      UserPoolId: [userPool.userPoolId, "Cognito user pool for callers"],
      RuntimeArn: [runtime.attrAgentRuntimeArn, "AgentCore runtime ARN"],
      TableName: [table.tableName, "Catalogue table, for journey-search-load"],
    };
    for (const [name, [value, description]] of Object.entries(outputs)) {
      new CfnOutput(this, name, { value, description });
    }
    for (const [name, value] of [["mcp-url", mcpUrl], ["token-url", tokenUrl], ["table-name", table.tableName]]) {
      new ssm.StringParameter(this, `Param-${name}`, { parameterName: `/journey-search/${name}`, stringValue: value });
    }
  }
}
