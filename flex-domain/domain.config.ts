import { domain } from "@flex/sdk";
import { 
  chooseAddressMethodSchema,
  addressSchema,
  confirmNewAddressSchema
} from "@schemas/dvla-adress";

export const { config, route, routeContext } = domain({
  name: "agentic-legibility",
  common: {
    function: { timeoutSeconds: 30 },
  },
  resources: {
    /* Not yet in use: examples below.
    exampleKey: { type: "kms", path: "/path/to/key" },
    gatewayUrl: { type: "ssm", path: "/path/to/url", scope: "stage" },
    exampleSecret: { type: "secret", path: "/path/to/secret" },
    */
  },
  integrations: {
    /* Not yet in use: examples below.
    udpRead: { type: "gateway", target: "udp", route: "GET /v1/*" },
    udpWrite: { type: "gateway", target: "udp", route: "POST /v1/*" },
    */
  },
  routes: {
    v1: {
      "/choose-address-entry-method": {
        POST: {
          public: {
            name: "choose-address-entry-method",
            response: chooseAddressMethodSchema
          },
        },
      },
      "/find-address-by-postcode": {
        POST: {
          public: {
            name: "find-address-by-postcode",
            response: addressSchema
          },
        },
      },
      "/enter-address-manually": {
        POST: {
          public: {
            name: "enter-address-manually",
            response: adressSchema
          },
        },
      },
      "/confirm-new-address": {
        POST: {
          public: {
            name: "confirm-new-address",
            response: confirmNewAddressSchema
          },
        },
      },
    },
  },
});

// Example: Create alias accessors for reuse throughout your domain
export const getUserContext = routeContext<"GET /v1/user">;
export const createUserContext = routeContext<"POST /v1/user [private]">;
