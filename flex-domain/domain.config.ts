import { domain } from "@flex/sdk";
import { 
  ChooseAddressMethodSchema,
  AddressSchema,
  ConfirmNewAddressSchema
} from "@schemas/dvla-address";

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
            body: ChooseAddressMethodSchema,\n            response: ChooseAddressMethodSchema
          },
        },
      },
      "/find-address-by-postcode": {
        POST: {
          public: {
            name: "find-address-by-postcode",
            body: AddressSchema,\n            response: AddressSchema
          },
        },
      },
      "/enter-address-manually": {
        POST: {
          public: {
            name: "enter-address-manually",
            body: AddressSchema,\n            response: AddressSchema
          },
        },
      },
      "/confirm-new-address": {
        POST: {
          public: {
            name: "confirm-new-address",
            body: ConfirmNewAddressSchema,\n            response: ConfirmNewAddressSchema
          },
        },
      },
    },
  },
});
