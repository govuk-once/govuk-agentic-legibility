import { AnthropicBedrock } from '@anthropic-ai/bedrock-sdk';
import { AWS_BEARER_TOKEN_BEDROCK, AWS_REGION } from '$env/static/private';

// Deliberately the legacy AnthropicBedrock client (bedrock-runtime), not AnthropicBedrockMantle
// (the newer bedrock-mantle endpoint): bedrock-mantle for Claude Sonnet 5 is not offered in
// eu-west-2 at all, only in a handful of other regions. Neither endpoint accepts output_config
// for this model, so the response shape comes from the system prompt alone, not a server side
// constraint, see generate-service.ts.
//update this to not use the legacy AnthropicBedrock client once AWS Agent Core is implemented which can handle structured outputs
export const bedrockClient = new AnthropicBedrock({
	apiKey: AWS_BEARER_TOKEN_BEDROCK,
	awsRegion: AWS_REGION
});

// The "eu." geo profile keeps requests within EU
// regions (matching AWS_REGION here), as opposed to "global." which has no data residency guarantee.
export const BEDROCK_MODEL_ID = 'eu.anthropic.claude-sonnet-5';
