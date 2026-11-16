import type { Actions } from './$types';
import { generateService } from '$lib/server/onboard-service/generate-service';
import { bedrockClient, BEDROCK_MODEL_ID } from '$lib/server/shared/client';
import { draftFromRequest } from '$lib/server/shared/draft-action';

// The client and the model are handed in here, on the server, so the generation itself never imports the token.
export const actions: Actions = {
	default: ({ request }) => draftFromRequest(request, generateService, { client: bedrockClient, modelId: BEDROCK_MODEL_ID })
};
