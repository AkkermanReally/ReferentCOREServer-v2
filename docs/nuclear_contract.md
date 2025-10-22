# RefferentCOREServer v2: The Nuclear Contract

This document specifies the rules and protocols for interacting with RCs v2. It is the single source of truth for component and client developers.

## Protocol: PSP v1.2

All communication with RCs MUST use the Persona Synchronization Protocol (PSP) v1.2, as defined in `rcs/nucleus/protocol.py`.

### The `Envelope`

Every message is an `Envelope` with a specific `type` and `payload`.

## Connecting to RCs

There are two types of actors in the Persona ecosystem: **Components** and **Clients**.

### 1. Components (e.g., `SimpleEchoService`)

- Components are long-running services that provide core functionality.
- **RCs connects to Components.** Components act as WebSocket servers.
- The connection lifecycle is managed entirely by the RCs `HandshakeManager`.
- Upon connection, RCs sends a `handshake` message with an `auth_token` defined in the RCs configuration. The component MUST validate this token.

### 2. Clients (e.g., UI, Admin Scripts)

- Clients are actors that consume the services provided by Components.
- **Clients connect to RCs.** RCs provides a WebSocket server endpoint via its `ClientGateway`.
- Upon connection, a Client **MUST** send a `module_registration` message as its first message.
- The `payload` of this message **MUST** contain an `auth_token`:
  ```json
  {
    "type": "module_registration",
    "return_from": "MyCoolAdminClient",
    "payload": {
      "auth_token": "CLIENT_SECRET_TOKEN_123"
    }
  }
  ```
- If the token is invalid, the connection will be terminated.

## Advanced Feature: Requester-Side Validation

A client or component (the Requester) can ask RCs to manage a distributed transaction and ensure the response is valid before the transaction is considered complete.

To enable this, the Requester sets flags in the `meta` field of its `command` envelope:

```json
{
  "type": "command",
  "return_from": "MyOrchestrator",
  "return_to": "GeminiService",
  "request_id": "req-abc-123",
  "meta": {
    "requires_validation": true,
    "max_retries": 3,
    "validation_timeout_seconds": 45
  },
  "payload": { ... }
}
```

- **`requires_validation`**: (bool, required) Must be `true` to enable the feature.
- **`max_retries`**: (int, optional, default=2) How many times RCs should retry the command if validation fails.
- **`validation_timeout_seconds`**: (int, optional, default=60) How long RCs will wait for a verdict from the Requester before failing the transaction.

After receiving a response, the Requester **MUST** send a verdict back to RCs:

- **On Success**: `{"type": "validation_confirmed", "request_id": "req-abc-123", "payload": {}}`
- **On Failure**: `{"type": "validation_failed", "request_id": "req-abc-123", "payload": {"reason": "Response was empty"}}`
```
