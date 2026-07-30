import { z } from "zod";


export const chooseAddressMethodSchema = z.object({
  usePostcodeLookup: z.boolean()
});

export const addressSchema = z.object({
  addressLine1: z.string(),
  addressLine2: z.string(),
  townOrCity: z.string(),
  postcode: z.string()
});

export const confirmNewAddressSchema = z.object({
  confirmed: z.boolean(),
  addressLine1: z.string(),
  addressLine2: z.string(),
  townOrCity: z.string(),
  postcode: z.string()
});


  
