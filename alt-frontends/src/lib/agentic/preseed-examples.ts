import type { AutonomyPolicy } from '$lib/types';

// Canned "pre-seed" fact sheets for the /agentic pages: each gives the
// autonomous answerer enough to walk one of durable_poc's workflow definitions
// (dwp_ma1_schema.json, dvla_coa_schema.json, dvla_coa_adv_schema.json) without
// escalating. Identity details match the mock executor's DWP/DVLA stubs
// (src/lib/server/mock-executor/services.ts), so the "we found these records"
// confirmations line up. Dates are relative to today, because MA1 rejects
// claims made more than 14 weeks before the due week. Address picks ask for the
// option number: interpreter.py only expands a `uprn`-keyed select_one into the
// full address object when given a 1-based index, not the uprn itself.

export interface PreseedExample {
  id: string;
  title: string;
  description: string;
  /** Workflow ids (as listed by GET /workflows) this example is written for. */
  workflows: string[];
  /** Applied alongside the text; an empty notify list lets the run finish unattended. */
  policy: Pick<AutonomyPolicy, 'autonomy_level' | 'notify_categories'>;
  build: (today: Date) => string;
}

const DAY_MS = 24 * 60 * 60 * 1000;

function offset(today: Date, days: number): string {
  const d = new Date(today.getTime() + days * DAY_MS);
  const dd = String(d.getDate()).padStart(2, '0');
  const mm = String(d.getMonth() + 1).padStart(2, '0');
  return `${dd}/${mm}/${d.getFullYear()}`;
}

const MA1_ID = 'dwp.maternity_allowance_ma1_claim';
const COA_ID = 'dvla.change_of_address';
const COA_ADV_ID = 'dvla.change_of_address.v0.1.0';

const MA1_IDENTITY = `About me
- National Insurance number: AB123456C
- Name: Mrs Jane Mary Smith, date of birth 15/06/1992
- Address: Flat 3B, 42 High Street, Manchester, M1 4BT. Phone: 07700900123
- If DWP shows these identity details back to me, they are correct.`;

const MA1_GATES = `Eligibility
- Yes, I want to apply for Maternity Allowance.
- I am not getting Statutory Maternity Pay from any employer.
- I worked for at least 26 of the 66 weeks before my due week. I don't do unpaid work for a partner's business.
- I have my MAT B1 certificate, and an SMP1 form from my employer.
- I understand Maternity Allowance may affect other benefits. I don't claim any, so please continue.`;

const MA1_BANK = `Payment
- Pay me every 4 weeks.
- Account holder: Jane Smith. Bank: Barclays. Sort code: 20-40-60. Account number: 12345678.
- Those payment details are correct, so confirm them when asked.`;

const MA1_EMPLOYED = (today: Date) => `Work
- I am employed (my only type of work) by Acme Retail Ltd, earning about £520 a week. If HMRC shows Acme Retail Ltd and around £520 a week, that is correct.
- I was working for Acme Retail Ltd in the 15th week before my due week. Acme gave me an SMP1 form because I'm not entitled to SMP.
- My SMP1 form is already scanned: when asked to upload it, submit the file reference {"ref": "smp1_acme_retail.pdf", "bytes": 184320}.
- I went on maternity leave on ${offset(today, -7)}.
- I'd like my Maternity Allowance to start on ${offset(today, 7)}.`;

const MA1_UNBORN_BABY = (today: Date) => `My baby
- My baby has not been born yet. The expected date of childbirth on my MAT B1 certificate is ${offset(today, 56)}.
- My MAT B1 certificate is already scanned: when asked to upload it, submit the file reference {"ref": "matb1_certificate.pdf", "bytes": 245760}.`;

export const PRESEED_EXAMPLES: PreseedExample[] = [
  {
    id: 'ma1-employed-unborn',
    title: 'Maternity Allowance: employed, baby due in 8 weeks (whole journey)',
    description: 'Every section of MA1, from eligibility to bank details, with no escalations.',
    workflows: [MA1_ID],
    policy: { autonomy_level: 'assertive', notify_categories: [] },
    build: (today) =>
      [MA1_IDENTITY, MA1_GATES, MA1_UNBORN_BABY(today), MA1_EMPLOYED(today), MA1_BANK].join('\n\n')
  },
  {
    id: 'ma1-self-employed-born',
    title: 'Maternity Allowance: self-employed, baby born 3 weeks ago (whole journey)',
    description: 'Takes the born-baby branch (birth certificate number) and the self-employed branch (UTR).',
    workflows: [MA1_ID],
    policy: { autonomy_level: 'assertive', notify_categories: [] },
    build: (today) =>
      [
        MA1_IDENTITY,
        MA1_GATES.replace('and an SMP1 form from my employer', 'and my birth certificate'),
        `My baby
- My baby has been born. The baby is alive and well and was born in the UK on ${offset(today, -21)}.
- The due date on my MAT B1 certificate was ${offset(today, -14)}.
- My MAT B1 certificate is already scanned: when asked to upload it, submit the file reference {"ref": "matb1_certificate.pdf", "bytes": 245760}.
- For proof of birth, I'll give the birth certificate system number: 123456789.`,
        `Work
- I am self-employed (my only type of work) as a freelance graphic designer. My Unique Taxpayer Reference is 1234567890.
- I stopped working to go on maternity leave on ${offset(today, -28)}.`,
        MA1_BANK
      ].join('\n\n')
  },
  {
    id: 'ma1-stop-at-payment',
    title: 'Maternity Allowance: run to the bank details, then ask me',
    description: 'Same facts as the employed example, but asks a human when it reaches payment.',
    workflows: [MA1_ID],
    policy: { autonomy_level: 'balanced', notify_categories: ['payment'] },
    build: (today) => [MA1_IDENTITY, MA1_GATES, MA1_UNBORN_BABY(today), MA1_EMPLOYED(today)].join('\n\n')
  },
  {
    id: 'coa-postcode',
    title: 'Change of address: postcode search, no new photo (whole journey)',
    description: 'Finds the new address by postcode, keeps the current photo and confirms the licence arrived.',
    workflows: [COA_ID],
    policy: { autonomy_level: 'assertive', notify_categories: [] },
    build: () => `- Yes, I want to change the address on my driving licence.
- Find my new address by postcode search. The postcode is SW1H 0ET.
- My new address is 2 Victoria Street, London, SW1H 0ET, the second search result. Answer that question with the option number 2.
- I don't need to provide a new photo.
- When asked, yes: I have received my new driving licence.`
  },
  {
    id: 'coa-manual',
    title: 'Change of address: typed-in address (whole journey)',
    description: 'Skips the postcode lookup and enters the address by hand.',
    workflows: [COA_ID],
    policy: { autonomy_level: 'assertive', notify_categories: [] },
    build: () => `- Yes, I want to change the address on my driving licence.
- I'd rather type my new address in by hand than search by postcode.
- My new address is: 14 Park Road, Leeds, LS1 5AB.
- I don't need to provide a new photo.
- When asked, yes: I have received my new driving licence.`
  },
  {
    id: 'coa-adv-full',
    title: 'Change of address (advanced): details, signature, address, organ donation',
    description: 'Confirms the DVLA record, signs, searches by postcode and keeps organ donor preferences.',
    workflows: [COA_ADV_ID],
    policy: { autonomy_level: 'assertive', notify_categories: [] },
    build: () => `- Yes, I want to change the address on my driving licence. I don't need to change my name.
- My details: Jane Smith, licence number SMITH906152JM9AB, date of birth 15/06/1992, email jane.smith@example.com. If DVLA shows these, they are correct.
- My photo is fine, so I don't want to upload a new one.
- For my digital signature, use: Jane M Smith
- Search for my new address by postcode (option 1, "Search by Postcode"). The postcode is SW1H 0ET. My address is 2 Victoria Street, London, SW1H 0ET, the second search result. Answer that question with the option number 2.
- I don't want to change my NHS organ donor preferences.
- When asked, yes: I have received my new photocard licence.`
  }
];

export function examplesFor(workflowId: string): PreseedExample[] {
  return PRESEED_EXAMPLES.filter((example) => example.workflows.includes(workflowId));
}
