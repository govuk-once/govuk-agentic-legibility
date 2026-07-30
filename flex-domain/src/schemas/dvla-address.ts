import { z } from "zod";


export const ChooseAddressMethodSchema = z.object({
  usePostcodeLookup: z.boolean()
});

export const AddressSchema = z.object({
  addressLine1: z.string(),
  addressLine2: z.string().optional(),
  townOrCity: z.string().optional(),
  postcode: z.string()
});

export const ConfirmNewAddressSchema = z.object({
  confirmed: z.boolean(),
  addressLine1: z.string(),
  addressLine2: z.string().optional(),
  townOrCity: z.string().optional(),
  postcode: z.string()
});


  
