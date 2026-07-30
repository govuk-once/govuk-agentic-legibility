import { route } from "@domain";
import { DRIVER } from "@data/store";

export const handler = route(
  "POST /v0.1 find-address-by-postcode",
  async ({ body, logger }) => {

    logger.info("Find address by postcode", {});

    return { 
      status: 200, 
      data: {
        addressLine1: body?.addressLine1 ?? DRIVER.address.line1,
        addressLine2: body?.addressLine2 ?? DRIVER.address.line2,
        townOrCity: body?.townOrCity ?? DRIVER.address.town,
        postcode: body?.postcode ?? DRIVER.address.postcode,
      }
    };
  },
)
