# Momentum HTTP RFC inventory and conformance profile

Status: researched on 2026-10-22 from RFC Editor and IETF Datatracker.
Companion to [the product spec](momentum-consultation-api.md). Application and
container verification is recorded in [the delivery report](momentum-api-delivery.md).
Live transport and IAM verification remain pending; no blanket certification is implied.

## Scope and interpretation

This inventory covers the application contract, its HTTP/TLS dependencies and
the identified future MCP authorization boundary. It is not the recursive list
of every Internet, DNS, TCP, PKI or cryptographic dependency of those protocols.
Adding a capability requires reassessing the applicable RFCs and their updates.

Requirements use the meanings in [RFC 2119](https://www.rfc-editor.org/rfc/rfc2119.html)
and [RFC 8174](https://www.rfc-editor.org/rfc/rfc8174.html). An applicable MUST
cannot be waived; a SHOULD exception needs a recorded reason and consequences.
An optional extension is not required merely because it has an RFC. Project
choices below can be stronger than an RFC and are labelled as such.

There is no single RFC that certifies a REST API. Resource names, `/v1`, business
filters, `page_size` and cursor JSON are this product's conventions. URI ownership
is addressed by [RFC 8820](https://www.rfc-editor.org/rfc/rfc8820.html); guidance
for using HTTP is [RFC 9205](https://www.rfc-editor.org/rfc/rfc9205.html).

## Application baseline

| Reference | Scope and adoption |
| --- | --- |
| [RFC 9110](https://www.rfc-editor.org/rfc/rfc9110.html) | HTTP semantics: methods, status codes, negotiation, authentication challenges, metadata and preconditions. Adopt for every route. |
| [RFC 9111](https://www.rfc-editor.org/rfc/rfc9111.html) | Cache behavior. Project chooses `Cache-Control: no-store`; this is not permission to ignore request preconditions. |
| [RFC 9205](https://www.rfc-editor.org/rfc/rfc9205.html) | BCP 56 for HTTP-based application protocols; preserve HTTP semantics rather than redefining them. |
| [RFC 3986](https://www.rfc-editor.org/rfc/rfc3986.html), [RFC 8820](https://www.rfc-editor.org/rfc/rfc8820.html) | URI syntax, encoding and ownership. RFC 8820 updates 3986 and replaces 7320. |
| [RFC 8259](https://www.rfc-editor.org/rfc/rfc8259.html) | JSON exchanged as UTF-8; finite numbers and valid strings. No NaN/Infinity or duplicate emitted object members. |
| [RFC 9457](https://www.rfc-editor.org/rfc/rfc9457.html) | Adopt Problem Details for application errors, replacing the proposed custom envelope. This format is an explicit project adoption, not a universal HTTP requirement. |
| [RFC 3339](https://www.rfc-editor.org/rfc/rfc3339.html), [RFC 9557](https://www.rfc-editor.org/rfc/rfc9557.html) | Timestamp syntax and its update. Emit UTC timestamps with `Z`, and full dates for analysis dates; do not adopt optional bracketed zone/calendar extensions. |
| [RFC 9562](https://www.rfc-editor.org/rfc/rfc9562.html) | UUID representation, replacing 4122. Preserve stored UUIDs; do not infer time order from UUIDv4. |
| [RFC 6750](https://datatracker.ietf.org/doc/html/rfc6750), [RFC 9700](https://www.rfc-editor.org/rfc/rfc9700.html) | Bearer transport/challenges and updated OAuth security guidance. Local opaque token is not an OAuth authorization server; Cloud Run identity-token verification is a separate managed boundary. |
| [RFC 6648](https://www.rfc-editor.org/rfc/rfc6648.html) | Avoid inventing a new `X-`-prefixed field. This new API chooses `Request-ID`; it is a documented custom field, not an IETF standard. Existing Scanner behavior is unchanged. |

## Transport and identity implementation dependencies

These belong to the HTTP server, TLS libraries, managed ingress and identity
provider. Application tests alone cannot establish their compliance. Record
versions, configuration, provider guarantees and observed live behavior at rollout.
Do not claim support for HTTP/2 or HTTP/3 without negotiation evidence.

| Reference | Owner / condition |
| --- | --- |
| [RFC 9112](https://www.rfc-editor.org/rfc/rfc9112.html), [RFC 9931](https://www.rfc-editor.org/rfc/rfc9931.html) | HTTP/1.1 parsing/framing and the 2026 update for optimistic protocol transitions. Server/ingress; the API offers no Upgrade or CONNECT feature. |
| [RFC 9113](https://www.rfc-editor.org/rfc/rfc9113.html), [RFC 7541](https://www.rfc-editor.org/rfc/rfc7541.html) | HTTP/2 and HPACK, only on a hop where HTTP/2 is enabled. |
| [RFC 9114](https://www.rfc-editor.org/rfc/rfc9114.html), [RFC 9204](https://www.rfc-editor.org/rfc/rfc9204.html) | HTTP/3 and QPACK, only if offered by the ingress. |
| [RFC 9000](https://www.rfc-editor.org/rfc/rfc9000.html), [RFC 9001](https://www.rfc-editor.org/rfc/rfc9001.html), [RFC 9002](https://www.rfc-editor.org/rfc/rfc9002.html) | QUIC transport, TLS integration and loss/congestion behavior, conditional on HTTP/3. Not application implementations. |
| [RFC 9846](https://datatracker.ietf.org/doc/rfc9846/) | Current TLS 1.3 specification, July 2026; replaces RFC 8446. |
| [RFC 9325](https://www.rfc-editor.org/rfc/rfc9325.html), [RFC 9852](https://www.rfc-editor.org/rfc/rfc9852.html), [RFC 10015](https://www.rfc-editor.org/rfc/rfc10015.html), [RFC 8996](https://www.rfc-editor.org/rfc/rfc8996.html) | TLS best practices and updates: new-protocol TLS 1.3 guidance, obsolete TLS 1.2 key exchanges, and prohibition of TLS 1.0/1.1. |
| [RFC 9525](https://www.rfc-editor.org/rfc/rfc9525.html) | TLS service-identity verification; replaces 6125. Clients validate hostname and certificate chain. |
| [RFC 7519](https://www.rfc-editor.org/rfc/rfc7519.html), [RFC 8725](https://www.rfc-editor.org/rfc/rfc8725.html) | JWT semantics/security when an identity boundary accepts JWTs. No decode-only trust; issuer, audience, lifetime and signature are validated by the responsible verifier. |
| [RFC 7515](https://www.rfc-editor.org/rfc/rfc7515.html), [RFC 7517](https://www.rfc-editor.org/rfc/rfc7517.html), [RFC 7518](https://www.rfc-editor.org/rfc/rfc7518.html) | JWS, JWK and algorithms underpinning signed JWTs. Use maintained libraries/provider verification, not custom cryptography. |

Project transport policy: HTTPS on every client-facing authenticated connection,
TLS 1.3 preferred; no TLS 1.0/1.1. Any TLS 1.2 compatibility must satisfy the
updated TLS profile and be recorded. RFC 9852's new-protocol scope must not be
misrepresented as an unconditional ban on TLS 1.2 for every existing HTTPS service.
For development with real credentials use verified local HTTPS. Disposable tokens
over isolated test transports establish only application behavior. Cloud Run's
ingress-to-container hop is a distinct managed trust boundary to document, not an
excuse to expose the container or accept identity headers from arbitrary clients.

## Conditional extensions, not requirements for release one

| Reference | Activation condition |
| --- | --- |
| [RFC 8288](https://www.rfc-editor.org/rfc/rfc8288.html) | If adding HTTP `Link` pagination/discovery links; use registered relation types such as `next`. JSON cursor fields alone do not implement this RFC. |
| [RFC 6585](https://www.rfc-editor.org/rfc/rfc6585.html) | If throttling or ingress limits produce 429/431. A 429 may include `Retry-After`; do not invent a mandatory retry delay. No new rate limiter is implied. |
| [RFC 4648](https://www.rfc-editor.org/rfc/rfc4648.html) | If opaque cursors use base64url; explicitly define padding and reject invalid encodings. Encoding is not signing or authorization. |
| [RFC 7493](https://www.rfc-editor.org/rfc/rfc7493.html) | Optional I-JSON profile. Do not claim numeric interoperability without auditing all financial/statistical fields. |
| [RFC 7239](https://www.rfc-editor.org/rfc/rfc7239.html) | If consuming standardized `Forwarded`. Accept proxy metadata only from trusted ingress; Cloud-specific headers are not automatically this standard. |
| [RFC 6797](https://www.rfc-editor.org/rfc/rfc6797.html) | HSTS if the HTTPS domain policy adopts it; not a substitute for TLS-aware API clients. |
| [RFC 9745](https://www.rfc-editor.org/rfc/rfc9745.html), [RFC 8594](https://www.rfc-editor.org/rfc/rfc8594.html) | Future deprecation and shutdown announcements. RFC 8594 is Informational. Do not announce dates without a real retirement decision. |
| [RFC 9651](https://www.rfc-editor.org/rfc/rfc9651.html) | Structured Fields when an adopted header uses that syntax, e.g. `Deprecation`. Replaces 8941; not a replacement syntax for all existing HTTP headers. |
| [RFC 8615](https://www.rfc-editor.org/rfc/rfc8615.html), [RFC 9727](https://www.rfc-editor.org/rfc/rfc9727.html), [RFC 8631](https://www.rfc-editor.org/rfc/rfc8631.html) | Well-known locations, API catalogue and service-description link relations if discovery is added. RFC 8631 is Informational; `/openapi.json` alone does not implement all three. |
| [RFC 5789](https://www.rfc-editor.org/rfc/rfc5789.html), [RFC 6902](https://www.rfc-editor.org/rfc/rfc6902.html), [RFC 7396](https://datatracker.ietf.org/doc/rfc7396/) | PATCH, JSON Patch, JSON Merge Patch: excluded because the API is read-only. |
| [RFC 6901](https://www.rfc-editor.org/rfc/rfc6901.html) | JSON Pointer if future error details point into a JSON request body; query parameters are not JSON pointers. |

## Future MCP authorization boundary

The [MCP authorization specification consulted](https://modelcontextprotocol.io/specification/2026-07-28/basic/authorization)
uses a selected OAuth feature set. These references inform the future MCP, not
new authorization endpoints in this internal reader. Its external access token
must not be forwarded as the backend's Cloud Run identity token.

| Reference | Future role |
| --- | --- |
| [RFC 6749](https://www.rfc-editor.org/rfc/rfc6749.html), [RFC 9700](https://www.rfc-editor.org/rfc/rfc9700.html), [RFC 6750](https://datatracker.ietf.org/doc/html/rfc6750) | OAuth framework, current security guidance and bearer usage. |
| [RFC 7636](https://www.rfc-editor.org/rfc/rfc7636.html) | PKCE for authorization-code flows. |
| [RFC 8414](https://www.rfc-editor.org/rfc/rfc8414.html), [RFC 9728](https://www.rfc-editor.org/rfc/rfc9728.html) | Authorization-server and protected-resource metadata. |
| [RFC 8707](https://www.rfc-editor.org/rfc/rfc8707.html), [RFC 9207](https://www.rfc-editor.org/rfc/rfc9207.html) | Target-resource binding and authorization-server issuer identification. |
| [RFC 7591](https://www.rfc-editor.org/rfc/rfc7591.html) | Dynamic client registration only if that registration mechanism is selected. |

OAuth 2.1 and client-ID metadata are drafts in the consulted MCP reference, not
published RFCs. OpenID Connect, OpenAPI, JSON Schema and W3C Trace Context have
their own specifications; they must not be advertised as IETF RFCs. The
[RateLimit fields document](https://datatracker.ietf.org/doc/draft-ietf-httpapi-ratelimit-headers/)
is still an Internet-Draft (-11) at this review; do not invent a RateLimit RFC.

## Enforceable application profile

HTTP requirements are grounded in RFC 9110 sections 8–15. `GET` is read-only;
`HEAD` is supported wherever `GET` is supported and has no response content,
including failures. Known disallowed methods return 405 with `Allow`;
unimplemented methods follow 501 semantics. Responses preserve authentication
challenges, negotiation metadata and conditional-request precedence.

Project choices to turn that baseline into a testable contract:

- Each listed resource offers `GET`, `HEAD`, `OPTIONS`. Authenticated OPTIONS
  returns 204 with `Allow: GET, HEAD, OPTIONS`, without content or Content-Length.
  Health retains its liveness exception. This is not a browser CORS policy.
- GET/HEAD take parameters only in the URI; nonempty request bodies are rejected
  with 400. Invalid query/path inputs also use 400. No request media type is
  required for bodyless reads; do not misuse 415 for `Accept` negotiation.
- Success JSON is UTF-8 `application/json`. Honor `Accept` quality values and
  wildcards; unavailable representations give 406. Preserve `Vary: Accept`.
  The supported content coding is identity; respect its exclusion and add other
  codings only with corresponding negotiation tests.
- Error content uses `application/problem+json`; clients should accept both media
  types. When the selected error format is unacceptable, preserve the original
  error status/required headers and omit content. HEAD always omits content.
- Emit a strong ETag for successful GET representations from their exact bytes;
  HEAD uses the same tag. Hashes exclude request-specific headers. Apply
  If-Match before If-None-Match, including wildcard/list and strong/weak rules;
  outcomes include 412 and bodyless 304. Auth/validation/not-found failures win
  over preconditions. Emit no Last-Modified: the store has no authoritative
  last-change time for the assembled representation. Date-based preconditions
  are ignored on that basis. Range is not supported and is ignored.
- Runtime/ingress emits valid Date/framing; do not attach a JSON body to 204/304.
  Omit Content-Length on 304; for HEAD omit it or use the GET representation's
  byte length. Preserve required 304 metadata and `Cache-Control: no-store`.

Bearer profile (RFC 6750 sections 2–3, updated by RFC 9700): credentials travel
only in `Authorization: Bearer ...`, never URLs. Missing/unsupported credentials
give 401 and `WWW-Authenticate: Bearer realm="momentum-api"`, without an OAuth
error or explanatory body. Invalid tokens give 401 with `error="invalid_token"`;
malformed/multiple credential transports give 400 with `error="invalid_request"`.
Insufficient OAuth scope, if scopes are later introduced, gives 403 and the
appropriate Bearer challenge. This release invents no scopes for the local token.
Cloud Run rejections remain provider responses, to test independently.

Problem Details profile (RFC 9457): emit `type`, `title`, `status`, safe `detail`,
and extension `code` for application failures where content is permitted. `status`
matches the HTTP status. Problem types are stable absolute HTTPS URIs owned by
the project, with documentation delivered before release; their exact base belongs
in the reviewed plan. Generic HTTP-only problems may use `about:blank` with the
standard status title. Optional `instance` identifies an occurrence, not a secret
or raw request URL. Clients identify problems by type and tolerate new extensions.

## Verification obligations and remaining evidence

The implementation's HTTP tests must cover methods and bodyless responses,
400/401/403-boundary/404/405/406/412/500/503 behavior, Bearer challenges, token
transport rejection, JSON validity, timestamp/UUID formats, Accept quality zero
and wildcards, content coding, ETag changes, conditional precedence, no-store,
and sanitized Problem Details. Check 304/HEAD headers as well as body absence.

Container tests cover real server framing and header behavior. Live checks cover
TLS/certificate verification, negotiated HTTP version, IAM rejection and permitted
reads. Record upstream/edge error formats separately. Before a conformance claim,
review applicable verified errata, locked server/library versions and any SHOULD
exceptions; reported errata alone are not automatically normative corrections.
This inventory alone is not verification evidence. See the delivery report for
executed application/container checks and remaining live responsibilities.

Superseded baselines: use 9110/9111/9112 rather than the old 7230–7235 HTTP suite;
9113 rather than 7540; 9457 rather than 7807; 8259 rather than 7159; 9562 rather
than 4122; 9846 rather than 8446; 9325 with its updates rather than 7525;
9525 rather than 6125; 9651 rather than 8941. Keep old references only to explain
compatibility or history, not as the current contract.
