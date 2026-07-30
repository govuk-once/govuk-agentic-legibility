import { route } from "@domain";
import { DRIVER } from "@data/store";

export const handler = route(
  "POST /v0.1 choose-entry-address-method",
  async ({ body, logger }) => {

    logger.info("Address method entry chosen", { body?.usePostcodeLookup });

    return { 
      status: 200, 
      data: { usePostcodeLookup: body?.usePostcodeLookup }
    };
  },
);
