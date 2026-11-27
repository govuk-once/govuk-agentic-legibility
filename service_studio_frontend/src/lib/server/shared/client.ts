import { AnthropicBedrock } from '@anthropic-ai/bedrock-sdk';
import { AWS_BEARER_TOKEN_BEDROCK, AWS_REGION } from '$env/static/private';

// Uses the older AnthropicBedrock client (bedrock-runtime) and not AnthropicBedrockMantle (the newer bedrock-mantle
// endpoint), because bedrock-mantle for Claude Sonnet 5 is not offered in eu-west-2. Neither endpoint accepts
// output_config for this model, so the shape of the reply comes from the JSON Schema at the end of the system prompt
// alone, which process-json-schema.ts adds. This client can be replaced once AWS Agent Core is in place, because it
// supports structured outputs.
export const bedrockClient = new AnthropicBedrock({
	apiKey: AWS_BEARER_TOKEN_BEDROCK,
	awsRegion: AWS_REGION
});

// The "eu." geo profile keeps requests within EU
// regions (matching AWS_REGION here), as opposed to "global." which has no data residency guarantee.
export const BEDROCK_MODEL_ID = 'eu.anthropic.claude-sonnet-5';
