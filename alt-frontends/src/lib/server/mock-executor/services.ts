// Canned downstream responses for the `call` states in durable_poc's workflow
// definitions (DWP, HMRC, DVLA, Post Office). Each is shaped to the state's
// `capture` paths and to the happy-path branch of the choice that follows it.
// Anything unmatched falls through to a 503, which the engine routes through
// the call state's `catch` — the same as an unreachable service would.
//
// To exercise an error branch, change a response here (e.g. set the photo
// upload's status to 422 with `code: 'PHOTO_QUALITY'`); Vite reloads it live.

export interface MockHttpResponse {
  status: number;
  body: unknown;
}

interface ServiceStub {
  service: string;
  method: string;
  url: RegExp;
  respond: (body: Record<string, unknown>) => MockHttpResponse;
}

let counter = 0;
const ref = (prefix: string) => `${prefix}-${Date.now().toString(36)}-${++counter}`;

const ADDRESSES = [
  { uprn: '10023456781', single_line: '1 Victoria Street, London, SW1H 0ET', line1: '1 Victoria Street', line2: null, post_town: 'London', postcode: 'SW1H 0ET' },
  { uprn: '10023456782', single_line: '2 Victoria Street, London, SW1H 0ET', line1: '2 Victoria Street', line2: null, post_town: 'London', postcode: 'SW1H 0ET' },
  { uprn: '10023456783', single_line: 'Flat 3, 5 Victoria Street, London, SW1H 0ET', line1: 'Flat 3', line2: '5 Victoria Street', post_town: 'London', postcode: 'SW1H 0ET' }
];

const STUBS: ServiceStub[] = [
  // --- DWP (Maternity Allowance MA1) ---
  {
    service: 'dwp',
    method: 'POST',
    url: /^\/app\/dwp\/v1\/identity-lookup$/,
    respond: () => ({
      status: 200,
      body: {
        title: 'Mrs',
        first_name: 'Jane',
        middle_name: 'Mary',
        surname: 'Smith',
        date_of_birth: '1992-06-15',
        phone: '07700900123',
        address: {
          address_line_1: '42 High Street',
          address_line_2: 'Flat 3B',
          town_or_city: 'Manchester',
          postcode: 'M1 4BT'
        }
      }
    })
  },
  {
    service: 'dwp',
    method: 'POST',
    url: /^\/app\/dwp\/v1\/upload$/,
    respond: (body) => ({
      status: 201,
      body: { upload_ref: ref(String(body.document_type ?? 'DOC')), status: 'received' }
    })
  },
  // --- HMRC ---
  {
    service: 'hmrc',
    method: 'POST',
    url: /^\/app\/hmrc\/v1\/employment-and-earnings$/,
    respond: () => ({
      status: 200,
      body: {
        has_active_employment: true,
        employers: ['Acme Retail Ltd'],
        highest_13_weeks: [520, 520, 515, 530, 520, 520, 525, 520, 520, 510, 520, 520, 520],
        monthly_earnings: [2250, 2250, 2260],
        average_weekly_earnings: 520,
        average_monthly_earnings: 2253
      }
    })
  },
  // --- DVLA ---
  {
    service: 'dvla',
    method: 'GET',
    url: /^\/app\/dvla\/v1\/driver-summary$/,
    respond: () => ({
      status: 200,
      body: {
        driverViewResponse: {
          driver: {
            drivingLicenceNumber: 'SMITH906152JM9AB',
            firstNames: 'Jane Mary',
            lastName: 'Smith',
            dateOfBirth: '1992-06-15',
            email: 'jane.smith@example.com'
          }
        }
      }
    })
  },
  {
    service: 'dvla',
    method: 'GET',
    url: /^\/app\/dvla\/v1\/photo_expiry\/[^/]*$/,
    respond: () => ({ status: 200, body: { expired: false, photo_id: 'PHOTO-EXISTING-001' } })
  },
  {
    service: 'dvla',
    method: 'POST',
    url: /^\/app\/dvla\/v1\/photo_validity$/,
    respond: () => ({ status: 200, body: { photo_id: ref('PHOTO'), photo: { icaoCompliant: true } } })
  },
  {
    service: 'dvla',
    method: 'POST',
    url: /^\/app\/dvla\/v1\/photo$/,
    respond: () => ({ status: 201, body: { photo_id: ref('PHOTO') } })
  },
  {
    service: 'dvla',
    method: 'POST',
    url: /^\/app\/dvla\/v1\/signature$/,
    respond: () => ({ status: 202, body: { signature_id: ref('SIG'), detail: 'Signature accepted' } })
  },
  {
    service: 'dvla',
    method: 'GET',
    url: /^\/app\/dvla\/v1\/organs\/[^/]*$/,
    respond: () => ({
      status: 200,
      body: {
        organDonor: { anyOrgans: false, kidneys: true, liver: true, heart: false, pancreas: false, cornea: true, lungs: false }
      }
    })
  },
  {
    service: 'dvla',
    method: 'POST',
    url: /^\/app\/dvla\/v1\/licence\/address$/,
    respond: () => ({ status: 202, body: { job_id: ref('JOB') } })
  },
  {
    service: 'dvla',
    method: 'GET',
    url: /^\/app\/dvla\/v1\/jobs\/[^/]*$/,
    respond: () => ({ status: 200, body: { state: 'COMPLETED' } })
  },
  // --- Post Office ---
  {
    service: 'postoffice',
    method: 'POST',
    url: /^\/app\/postoffice\/v1\/address_from_postcode$/,
    respond: () => ({ status: 200, body: { addresses: ADDRESSES } })
  }
];

export function callMockService(
  service: string,
  method: string,
  url: string,
  body: Record<string, unknown>
): MockHttpResponse {
  const stub = STUBS.find(
    (s) => s.service === service && s.method === method.toUpperCase() && s.url.test(url)
  );
  if (!stub) {
    return { status: 503, body: { detail: `No mock response for ${method} ${service}:${url}` } };
  }
  return stub.respond(body);
}
