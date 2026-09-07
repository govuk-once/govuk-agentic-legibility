//! Mock server for all FLEX API endpoints defined in `live_resources/endpoints/*.md`.
//! Rewrites all URLs: `https://flex.account.gov.uk` -> `http://localhost:<port>`
//!
//! Rust port of the former `mock-server.js`. Route table shape and shared
//! mock data are kept faithful to that original so behaviour is unchanged.

use std::sync::LazyLock;

use regex::{Captures, Regex};
use serde_json::{json, Value};
use tiny_http::{Header, Method, Response, Server};

// ── Shared mock data ────────────────────────────────────────────────────

static USER: LazyLock<Value> = LazyLock::new(|| {
    json!({
        "userId": "usr-7f3a9c1d-2e4b-6a8f",
        "consentStatus": "accepted",
        "pushId": "push-fcm-a1b2c3d4e5f6",
    })
});

static NOTIFICATIONS: LazyLock<Value> = LazyLock::new(|| {
    json!([
        {
            "NotificationID": "notif-001",
            "NotificationTitle": "DVLA Licence Renewal Reminder",
            "NotificationBody": "Your driving licence is due for renewal. Please visit GOV.UK to renew.",
            "MessageTitle": "Licence Renewal",
            "MessageBody": "Renew by 11 March 2025 to avoid a penalty.",
            "DispatchedDateTime": "2026-06-14T09:00:00Z",
            "Status": "RECEIVED",
        },
        {
            "NotificationID": "notif-002",
            "NotificationTitle": "MOT Due",
            "NotificationBody": "Your vehicle AB23CDX MOT is due on 30 June 2025.",
            "MessageTitle": "MOT Reminder",
            "MessageBody": "Book your MOT before 30 June 2025.",
            "DispatchedDateTime": "2026-06-01T08:30:00Z",
            "Status": "READ",
        },
    ])
});

static DRIVER: LazyLock<Value> = LazyLock::new(|| {
    json!({
        "dln": "MORGA753116SM9IJ",
        "firstName": "Sarah",
        "lastName": "Morgan",
        "gender": "F",
        "dateOfBirth": "1975-03-11",
        "address": {
            "numberOrName": "12",
            "street": "Elm Street",
            "line1": "12 Elm Street",
            "line2": "",
            "town": "Bristol",
            "county": "",
            "postcode": "BS1 5AU",
        },
    })
});

static SHARE_CODE: LazyLock<Value> = LazyLock::new(|| {
    json!({
        "shareCodeId": "sc-001-dvla",
        "shareCodeType": "DRIVING_LICENCE",
        "createdAt": "2026-07-01T10:00:00Z",
        "expiresAt": "2026-07-08T10:00:00Z",
        "shareCodeStatus": "ACTIVE",
    })
});

static LOCAL_AUTHORITY: LazyLock<Value> = LazyLock::new(|| {
    json!({
        "id": "E07000189",
        "name": "South Gloucestershire",
        "homepage_url": "https://www.southglos.gov.uk",
        "tier": "unitary",
        "slug": "south-gloucestershire",
        "parent": null,
    })
});

fn now_iso() -> String {
    let secs = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .unwrap_or_default()
        .as_secs();
    // Not a real calendar conversion — good enough for a mock timestamp field.
    format!("1970-01-01T00:00:{:02}Z", secs % 60)
}

fn now_hex() -> String {
    format!(
        "{:x}",
        std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap_or_default()
            .as_millis()
    )
}

fn s(v: &Value, key: &str) -> Option<String> {
    v.get(key).and_then(Value::as_str).map(String::from)
}

fn m(caps: &Captures, i: usize) -> String {
    caps.get(i).map(|m| m.as_str().to_string()).unwrap_or_default()
}

// ── Route table ──────────────────────────────────────────────────────────
// Each entry: { method, path (Regex), status, handler(match, body) -> Option<Value> }
// Routes with more-specific paths must appear before overlapping general ones.

struct Route {
    method: &'static str,
    pattern: Regex,
    status: u16,
    handler: fn(&Captures, Option<&Value>) -> Option<Value>,
}

fn route(method: &'static str, pattern: &str, status: u16, handler: fn(&Captures, Option<&Value>) -> Option<Value>) -> Route {
    Route { method, pattern: Regex::new(pattern).expect("valid route regex"), status, handler }
}

fn routes() -> Vec<Route> {
    vec![
        // ── /udp — One Login User Data Platform ──────────────────────
        route("GET", r"^/udp/v1/users/me$", 200, |_, _| Some(USER.clone())),
        route("GET", r"^/udp/v1/users/push-id$", 200, |_, _| {
            Some(json!({ "userId": USER["userId"], "pushId": USER["pushId"] }))
        }),
        route("PATCH", r"^/udp/v1/users/me/notifications$", 200, |_, body| {
            Some(json!({
                "consentStatus": body.and_then(|b| s(b, "consentStatus")).unwrap_or_else(|| USER["consentStatus"].as_str().unwrap().to_string()),
                "pushId": USER["pushId"],
            }))
        }),
        route("GET", r"^/udp/v1/identity$", 200, |_, _| {
            Some(json!({ "services": ["dvla", "mhclg"] }))
        }),
        route("GET", r"^/udp/v1/identity/([^/]+)$", 200, |caps, _| {
            let service = m(caps, 1);
            Some(json!({
                "service": service,
                "userId": USER["userId"],
                "serviceId": format!("svc-{}-001", service),
                "serviceName": format!("{} Service", service.to_uppercase()),
                "accessToken": "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.mock-access",
                "idToken": "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.mock-id",
                "refreshToken": format!("refresh-mock-{}-001", service),
            }))
        }),
        route("POST", r"^/udp/v1/identity/([^/]+)$", 201, |caps, _| {
            Some(json!({ "service": m(caps, 1), "userId": USER["userId"], "linked": true }))
        }),
        route("DELETE", r"^/udp/v1/identity/([^/]+)$", 204, |_, _| None),

        // ── /dvla — DVLA APIs ─────────────────────────────────────────
        route("GET", r"^/dvla/v1/driver-summary$", 200, |_, _| {
            let mut driver = DRIVER.clone();
            let obj = driver.as_object_mut().unwrap();
            obj.insert("penaltyPoints".into(), json!(3));
            obj.insert("disqualification".into(), json!({ "disqualified": false }));
            obj.insert("eyesight".into(), json!({ "standard": true }));
            obj.insert("hearing".into(), json!({ "standard": true }));
            obj.insert("offences".into(), json!([{ "code": "SP30", "points": 3, "date": "2023-06-15", "expiryDate": "2027-06-15" }]));
            obj.insert("previousDrivingLicence".into(), json!([]));
            obj.insert("licenceType".into(), json!("Full"));
            obj.insert("licenceStatus".into(), json!("Full licence"));
            obj.insert("countryToWhichExchanged".into(), json!(""));
            obj.insert("entitlements".into(), json!([{ "code": "B", "from": "1993-03-12", "to": "2045-03-11", "provisional": false, "restrictionCodes": [] }]));
            obj.insert("testPass".into(), json!([{ "category": "B", "date": "1993-03-11", "certNo": "TC12345678" }]));
            obj.insert("endorsements".into(), json!([{ "code": "SP30", "points": 3, "offenceDate": "2023-06-15", "convictionDate": "2023-09-20" }]));
            Some(json!({ "driverViewResponse": driver }))
        }),
        route("GET", r"^/dvla/v1/customer-summary$", 200, |_, _| {
            Some(json!({
                "customerResponse": {
                    "customerId": "cust-001-dvla",
                    "customerNumber": "CST-998877",
                    "identityId": USER["userId"],
                    "recordStatus": "ACTIVE",
                    "customerType": "DRIVER",
                    "address": DRIVER["address"],
                    "emailAddress": "sarah.morgan@example.gov.uk",
                    "phoneNumber": "+44 7700 900123",
                    "products": ["DRIVING_LICENCE"],
                    "driversEligibilityResponse": {
                        "applications": [{
                            "applicationType": "RENEWAL",
                            "isRequired": true,
                            "ineligibleReason": "",
                            "availableActions": ["APPLY_ONLINE"],
                        }],
                    },
                    "vehicleResponse": [{
                        "registrationNumber": "AB23CDX",
                        "make": "FORD",
                        "model": "FOCUS",
                        "motStatus": "VALID",
                        "fuelType": "PETROL",
                    }],
                    "hasErrors": false,
                },
            }))
        }),
        route("GET", r"^/dvla/v1/driving-licence$", 200, |_, _| {
            Some(json!({
                "driver": {
                    "licenceNumber": DRIVER["dln"],
                    "firstName": DRIVER["firstName"],
                    "lastName": DRIVER["lastName"],
                    "dateOfBirth": DRIVER["dateOfBirth"],
                    "address": DRIVER["address"],
                    "licence": { "licenceType": "Full", "licenceStatus": "Current", "statusQualifier": "" },
                    "licenceType": "Full",
                    "licenceStatus": "Current",
                    "statusQualifier": "",
                    "entitlements": [{ "code": "B", "from": "1993-03-12", "to": "2045-03-11", "provisional": false }],
                    "endorsements": [{ "code": "SP30", "points": 3, "offenceDate": "2023-06-15" }],
                    "testPass": [{ "category": "B", "date": "1993-03-11", "certNo": "TC12345678" }],
                    "token": { "access": "mock-access-token" },
                    "cpc": [],
                    "holder": { "title": "Ms", "sex": "F" },
                },
            }))
        }),
        route("GET", r"^/dvla/v1/vehicle-enquiry/([^/]+)$", 200, |caps, _| {
            Some(json!({
                "registrationNumber": m(caps, 1).to_uppercase(),
                "make": "FORD",
                "model": "FOCUS",
                "colour": "Blue",
                "fuelType": "PETROL",
                "engineCapacity": 1596,
                "co2Emissions": 129,
                "taxStatus": "Taxed",
                "taxDueDate": "2025-01-01",
                "motStatus": "Valid",
                "motExpiryDate": "2025-06-30",
                "yearOfManufacture": 2016,
                "typeApproval": "M1",
                "wheelplan": "2 axle rigid body",
                "monthOfFirstRegistration": "2016-04",
            }))
        }),
        route("GET", r"^/dvla/v1/share-codes$", 200, |_, _| {
            Some(json!({ "shareCodes": [SHARE_CODE.clone()] }))
        }),
        route("POST", r"^/dvla/v1/share-code$", 201, |_, _| {
            Some(json!({
                "shareCodeId": format!("sc-{}", now_hex()),
                "shareCodeType": "DRIVING_LICENCE",
                "createdAt": now_iso(),
                "expiresAt": now_iso(),
                "shareCodeStatus": "ACTIVE",
            }))
        }),
        route("POST", r"^/dvla/v1/share-code/([^/]+)/cancel$", 200, |caps, _| {
            let id = m(caps, 1);
            Some(json!({
                "id": id,
                "shareCodeId": id,
                "shareCodeType": "DRIVING_LICENCE",
                "createdAt": SHARE_CODE["createdAt"],
                "expiresAt": SHARE_CODE["expiresAt"],
                "shareCodeStatus": "CANCELLED",
            }))
        }),
        route("POST", r"^/dvla/v1/unlink/([^/]+)$", 200, |caps, _| {
            Some(json!({ "id": m(caps, 1), "unlinked": true }))
        }),
        route("POST", r"^/dvla/v1/test-notification$", 200, |_, _| {
            Some(json!({ "sent": true, "timestamp": now_iso() }))
        }),

        // ── /uns — Unified Notification Service ──────────────────────
        route("GET", r"^/uns/v1/notifications$", 200, |_, _| Some(NOTIFICATIONS.clone())),
        route("GET", r"^/uns/v1/notifications/([^/]+)$", 200, |caps, _| {
            let mut first = NOTIFICATIONS[0].clone();
            let id = m(caps, 1);
            let obj = first.as_object_mut().unwrap();
            obj.insert("notificationId".into(), json!(id));
            obj.insert("NotificationID".into(), json!(id));
            Some(first)
        }),
        route("DELETE", r"^/uns/v1/notifications/([^/]+)$", 204, |_, _| None),
        route("PATCH", r"^/uns/v1/notifications/([^/]+)/status$", 200, |caps, body| {
            Some(json!({
                "notificationId": m(caps, 1),
                "Status": body.and_then(|b| s(b, "Status")).unwrap_or_else(|| "READ".to_string()),
            }))
        }),

        // ── /example — FLEX example domain ───────────────────────────
        // More-specific paths appear first to avoid partial matches.
        route("GET", r"^/example/v0/resources/runtime$", 200, |_, _| {
            Some(json!({ "environment": "development", "version": "0.1.0-mock", "region": "eu-west-2", "uptime": 3600 }))
        }),
        route("GET", r"^/example/v0/resources$", 200, |_, _| {
            Some(json!({
                "resources": [
                    { "name": "dvla-api", "status": "available", "version": "v1" },
                    { "name": "uns-api", "status": "available", "version": "v1" },
                    { "name": "local-council-api", "status": "available", "version": "v1" },
                ],
            }))
        }),
        route("GET", r"^/example/v0/headers$", 200, |_, _| {
            Some(json!({
                "x-request-id": format!("req-{}", now_hex()),
                "x-correlation-id": format!("corr-{}", now_hex()),
            }))
        }),
        route("GET", r"^/example/v0/identity/([^/]+)$", 200, |caps, _| {
            let service = m(caps, 1);
            Some(json!({
                "service": service,
                "userId": USER["userId"],
                "serviceId": format!("svc-{}-001", service),
                "serviceName": format!("{} Example Service", service.to_uppercase()),
                "accessToken": "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.mock-access",
                "idToken": "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.mock-id",
                "refreshToken": format!("refresh-mock-{}-001", service),
            }))
        }),
        route("POST", r"^/example/v0/todos/([^/]+)/duplicate$", 201, |_, _| {
            Some(json!({
                "id": format!("todo-{}", now_hex()),
                "title": "Duplicated item",
                "completed": false,
                "priority": "medium",
                "createdAt": now_iso(),
            }))
        }),
        route("GET", r"^/example/v0/todos/([^/]+)$", 200, |caps, _| {
            Some(json!({
                "id": m(caps, 1),
                "title": "Book MOT appointment",
                "completed": false,
                "priority": "high",
                "createdAt": "2026-07-01T08:00:00Z",
                "label": "Vehicle",
            }))
        }),
        route("DELETE", r"^/example/v0/todos/([^/]+)$", 204, |_, _| None),
        route("GET", r"^/example/v0/todos$", 200, |_, _| {
            Some(json!([
                { "id": "todo-001", "title": "Book MOT appointment", "completed": false, "priority": "high", "createdAt": "2026-07-01T08:00:00Z" },
                { "id": "todo-002", "title": "Renew driving licence photo", "completed": true, "priority": "medium", "createdAt": "2026-06-20T10:30:00Z" },
            ]))
        }),
        route("POST", r"^/example/v0/todos$", 201, |_, body| {
            Some(json!({
                "id": format!("todo-{}", now_hex()),
                "title": body.and_then(|b| s(b, "title")).unwrap_or_else(|| "New todo".to_string()),
                "completed": body.and_then(|b| b.get("completed").cloned()).unwrap_or(json!(false)),
                "priority": body.and_then(|b| s(b, "priority")).unwrap_or_else(|| "medium".to_string()),
                "createdAt": now_iso(),
            }))
        }),
        route("GET", r"^/example/v0/users/notifications$", 200, |_, _| Some(NOTIFICATIONS.clone())),
        route("PATCH", r"^/example/v0/users/notifications$", 200, |_, body| {
            Some(json!({
                "consentStatus": body.and_then(|b| s(b, "consentStatus")).unwrap_or_else(|| USER["consentStatus"].as_str().unwrap().to_string()),
                "pushId": USER["pushId"],
                "newUserProfileEnabled": true,
            }))
        }),
        route("PATCH", r"^/example/v0/notifications$", 200, |_, body| {
            Some(json!({
                "consentStatus": body.and_then(|b| s(b, "consentStatus")).unwrap_or_else(|| USER["consentStatus"].as_str().unwrap().to_string()),
            }))
        }),

        // ── /local-council — MHCLG Local Council API ─────────────────
        route("GET", r"^/local-council/v1/local-council/([^/]+)$", 200, |caps, _| {
            let mut la = LOCAL_AUTHORITY.clone();
            la.as_object_mut().unwrap().insert("id".into(), json!(m(caps, 1)));
            Some(la)
        }),
        route("POST", r"^/local-council/v1/local-council/([^/]+)$", 200, |caps, body| {
            Some(json!({
                "id": m(caps, 1),
                "name": body.and_then(|b| s(b, "name")).unwrap_or_else(|| LOCAL_AUTHORITY["name"].as_str().unwrap().to_string()),
                "homepage_url": body.and_then(|b| s(b, "homepage_url")).unwrap_or_else(|| LOCAL_AUTHORITY["homepage_url"].as_str().unwrap().to_string()),
                "tier": body.and_then(|b| s(b, "tier")).unwrap_or_else(|| LOCAL_AUTHORITY["tier"].as_str().unwrap().to_string()),
                "slug": body.and_then(|b| s(b, "slug")).unwrap_or_else(|| LOCAL_AUTHORITY["slug"].as_str().unwrap().to_string()),
                "parent": body.and_then(|b| b.get("parent").cloned()).unwrap_or(Value::Null),
            }))
        }),

        // ── DVLA mock update address ───────────────────────────────────
        route("POST", r"^/choose-address-entry-method$", 200, |_, body| {
            Some(json!({
                "usePostcodeLookup": body.and_then(|b| b.get("usePostcodeLookup").cloned()).unwrap_or(Value::Null),
            }))
        }),
        route("POST", r"^/find-address-by-postcode$", 200, |_, body| {
            let line1 = body
                .and_then(|b| s(b, "buildingNumberOrName"))
                .map(|n| format!("{} {}", n, DRIVER["address"]["street"].as_str().unwrap()))
                .unwrap_or_else(|| DRIVER["address"]["line1"].as_str().unwrap().to_string());
            Some(json!({
                "addressLine1": line1,
                "addressLine2": DRIVER["address"]["line2"],
                "townOrCity": DRIVER["address"]["town"],
                "postcode": body.and_then(|b| s(b, "postcode")).unwrap_or_else(|| DRIVER["address"]["postcode"].as_str().unwrap().to_string()),
            }))
        }),
        route("POST", r"^/enter-address-manually$", 200, |_, body| {
            body.cloned()
        }),
        route("POST", r"^/confirm-new-address$", 200, |_, body| {
            Some(json!({
                "confirmed": body.and_then(|b| b.get("confirmed").cloned()).unwrap_or(json!(false)),
                "addressLine1": body.and_then(|b| s(b, "addressLine1")).unwrap_or_else(|| DRIVER["address"]["line1"].as_str().unwrap().to_string()),
                "addressLine2": body.and_then(|b| s(b, "addressLine2")).unwrap_or_else(|| DRIVER["address"]["line2"].as_str().unwrap().to_string()),
                "townOrCity": body.and_then(|b| s(b, "townOrCity")).unwrap_or_else(|| DRIVER["address"]["town"].as_str().unwrap().to_string()),
                "postcode": body.and_then(|b| s(b, "postcode")).unwrap_or_else(|| DRIVER["address"]["postcode"].as_str().unwrap().to_string()),
            }))
        }),
    ]
}

// ── Request handling ────────────────────────────────────────────────────

fn method_str(method: &Method) -> &'static str {
    match method {
        Method::Get => "GET",
        Method::Post => "POST",
        Method::Put => "PUT",
        Method::Delete => "DELETE",
        Method::Patch => "PATCH",
        Method::Head => "HEAD",
        Method::Options => "OPTIONS",
        Method::Connect => "CONNECT",
        Method::Trace => "TRACE",
        Method::NonStandard(_) => "OTHER",
    }
}

/// Binds `127.0.0.1:<port>` and serves the FLEX API mock forever.
pub fn run(port: u16) {
    let server = Server::http(("127.0.0.1", port)).expect("failed to bind mock FLEX server");
    println!("Mock FLEX API -> http://127.0.0.1:{port}");
    let table = routes();

    for mut request in server.incoming_requests() {
        let method = method_str(request.method());
        let path = request.url().split('?').next().unwrap_or("").to_string();

        let mut raw_body = String::new();
        let _ = request.as_reader().read_to_string(&mut raw_body);
        let body: Option<Value> = if raw_body.trim().is_empty() {
            None
        } else {
            serde_json::from_str(&raw_body).ok()
        };

        let matched = table.iter().find(|r| r.method == method && r.pattern.is_match(&path));

        let response = match matched {
            None => {
                let known: Vec<&str> = table.iter().filter(|r| r.pattern.is_match(&path)).map(|r| r.method).collect();
                let status = if known.is_empty() { 404 } else { 405 };
                let error_msg = if status == 405 { "Method not allowed" } else { "Not found" };
                let payload = json!({ "error": error_msg, "path": path, "method": method, "allowed": known });
                json_response(status, &payload)
            }
            Some(route) => {
                let caps = route.pattern.captures(&path).expect("route matched its own pattern");
                let payload = (route.handler)(&caps, body.as_ref());
                if route.status == 204 || payload.is_none() {
                    Response::empty(204).boxed()
                } else {
                    json_response(route.status, &payload.unwrap())
                }
            }
        };

        let _ = request.respond(response);
    }
}

fn json_response(status: u16, payload: &Value) -> tiny_http::ResponseBox {
    let body = serde_json::to_string(payload).unwrap_or_default();
    let content_type = Header::from_bytes(&b"Content-Type"[..], &b"application/json"[..]).unwrap();
    let cors = Header::from_bytes(&b"Access-Control-Allow-Origin"[..], &b"*"[..]).unwrap();
    Response::from_string(body)
        .with_status_code(status)
        .with_header(content_type)
        .with_header(cors)
        .boxed()
}
