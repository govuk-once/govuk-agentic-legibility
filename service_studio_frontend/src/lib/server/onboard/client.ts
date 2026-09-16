import { AnthropicBedrock } from '@anthropic-ai/bedrock-sdk';
import { AWS_BEARER_TOKEN_BEDROCK, AWS_REGION } from '$env/static/private';

// Deliberately the legacy AnthropicBedrock client (InvokeModel on bedrock-runtime), not
// AnthropicBedrockMantle (the newer Messages API endpoint). Only InvokeModel supports output_config.format for
// Anthropic Claude models on Bedrock, the Messages API endpoint rejects it. This is needed for the schema output.
export const bedrockClient = new AnthropicBedrock({
	apiKey: AWS_BEARER_TOKEN_BEDROCK,
	awsRegion: AWS_REGION
});

export const BEDROCK_MODEL_ID = 'anthropic.claude-sonnet-5';
