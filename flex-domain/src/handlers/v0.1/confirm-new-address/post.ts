import { route } from "@domain";
import { DRIVER } from "@data/store";

export const handler = route(
  "POST /v0.1 confirm-new-address",
  async ({ body, logger }) => {

    logger.info("New address confirmed", { body?.confirmed });

    return { 
      status: 200, 
      data: {
        confirmed: body?.confirmed ?? false,
        addressLine1: body?.addressLine1 ?? DRIVER.address.line1,
        addressLine2: body?.addressLine2 ?? DRIVER.address.line2,
        townOrCity: body?.townOrCity ?? DRIVER.address.town,
        postcode: body?.postcode ?? DRIVER.address.postcode,
      }
    };
  },
)
