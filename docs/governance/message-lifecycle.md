# Message Lifecycle

Message lifecycle states:

| State | Meaning |
|---|---|
| `received` | Request reached the API plane. |
| `accepted_for_processing` | The API accepted the message for governed processing. This is not governance approval. |
| `governance_pending` | The processor is evaluating policy, MACI, constitutional, and validation evidence. |
| `governance_approved` | Governance checks approved the message for routing/action. |
| `governance_rejected` | Governance checks rejected the message. |
| `routed` | The message was routed after approval. |
| `execution_pending` | Approved action is waiting for execution. |
| `executed` | Approved action completed. |
| `failed` | Processing failed before a final approved/rejected state. |

Async submit:

```http
POST /api/v1/messages
```

Returns `202` with `status: accepted_for_processing`.

Synchronous submit:

```http
POST /api/v1/messages?mode=validate_and_route
```

Runs the configured processor immediately and returns the immediate governance state.

Status:

```http
GET /api/v1/messages/{message_id}/status
```

Status lookups are tenant-bound. A tenant cannot query another tenant's message status.
