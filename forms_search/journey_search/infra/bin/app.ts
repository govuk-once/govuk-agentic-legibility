import * as cdk from "aws-cdk-lib";
import { Tags } from "aws-cdk-lib";
import { JourneySearchStack } from "../lib/journey-search-stack";

// A separate app from infrastructure/, with the same region default and tags.
const app = new cdk.App();

const env = {
  account: process.env.CDK_DEFAULT_ACCOUNT,
  region: process.env.CDK_DEFAULT_REGION || "eu-west-2",
};

new JourneySearchStack(app, "JourneySearchStack", { env });

Tags.of(app).add("Environment", "development");
Tags.of(app).add("Product", "once-ailegibility");
Tags.of(app).add("ManagedBy", "AWS-CDK");
Tags.of(app).add("Service", "Agentic Legibility");
Tags.of(app).add("Component", "Journey Search");
Tags.of(app).add("Owner", "ai-agentic-legibility@digital.cabinet-office.gov.uk");
Tags.of(app).add("Source", "https://github.com/govuk-once/govuk-agentic-legibility");
