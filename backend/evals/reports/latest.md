# SupportLens eval report

Run 2026-10-06 00:44 UTC · 35 cases · LLM `fake-extractive-1` · embeddings `local:BAAI/bge-small-en-v1.5` · judge `lexical`

| Metric | Value | What it measures |
| --- | --- | --- |
| Decision accuracy | 80% | Answered when the user's knowledge supports it, refused otherwise |
| Answer rate (answerable) | 82% | Answerable questions that got a cited draft |
| Correct refusal rate (unanswerable) | 75% | Unsupported or out-of-permission questions answered with "insufficient evidence" |
| Unsupported answers | 2 | Drafts produced for questions that should have been refused |
| Retrieval recall@6 | 100% | An expected document was among the retrieved passages |
| Citation precision | 82% | Cited passages that come from an expected document |
| Citation validity | 100% | Model citation markers that pointed at a retrieved passage (before the validator) |
| Faithfulness | 100% | Claims in answers supported by the passages they cite (lexical judge) |
| Key-fact accuracy | 68% | Answers containing the expected fact (e.g. "30 days") |
| Permission violations | 0 | Retrieved passages from collections the asking user can't read (must be 0) |
| Errors | 0 | Provider failures |

Latency: retrieval p50 10 ms / p95 19 ms · generation p50 0 ms / p95 0 ms · model cost $0.0000 (30431 in / 2006 out tokens) · judge cost $0.0000

Evidence gate calibration (best retrieval similarity, min / median / max): answerable 0.66 / 0.76 / 0.84 · unanswerable 0.58 / 0.62 / 0.71 · threshold 0.65

## Cases

| Case | User | Expected | Outcome | Decided by | Cited | Key fact | Faithful |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `returns-window` | alex | answer | ❌ insufficient_evidence | model | — |  |  |
| `refund-timing` | alex | answer | ✅ ready | model | returns-and-refunds.md | yes | 100% |
| `gift-card-refund` | alex | answer | ✅ ready | model | returns-and-refunds.md | yes | 100% |
| `return-shipping-canada` | alex | answer | ✅ ready | model | returns-and-refunds.md | yes | 100% |
| `exchange-color` | alex | answer | ❌ insufficient_evidence | model | — |  |  |
| `opened-earbuds` | alex | answer | ✅ ready | model | bluetooth-troubleshooting.md, returns-and-refunds.md | yes | 100% |
| `express-cost` | alex | answer | ✅ ready | model | shipping-and-delivery.md | yes | 100% |
| `change-address` | alex | answer | ✅ ready | model | accounts-and-privacy.md, shipping-and-delivery.md | yes | 100% |
| `delivered-not-received` | alex | answer | ✅ ready | model | accounts-and-privacy.md, shipping-and-delivery.md | no | 100% |
| `import-duties` | alex | answer | ❌ insufficient_evidence | model | — |  |  |
| `ship-brazil` | alex | answer | ❌ insufficient_evidence | model | — |  |  |
| `warranty-length` | alex | answer | ❌ insufficient_evidence | model | — |  |  |
| `battery-degraded` | alex | answer | ✅ ready | model | battery-and-charging.md, warranty.md | yes | 100% |
| `cracked-housing` | alex | answer | ✅ ready | model | warranty.md | yes | 100% |
| `lost-earbud` | alex | answer | ✅ ready | model | bluetooth-troubleshooting.md, warranty.md | yes | 100% |
| `serial-number` | alex | answer | ✅ ready | model | warranty.md | yes | 100% |
| `reset-link-expired` | alex | answer | ✅ ready | model | accounts-and-privacy.md | no | 100% |
| `delete-account` | alex | answer | ✅ ready | model | accounts-and-privacy.md | no | 100% |
| `pro-price` | alex | answer | ✅ ready | model | battery-and-charging.md, kestrel-cloud-plans.md | no | 100% |
| `annual-refund` | alex | answer | ✅ ready | model | kestrel-cloud-plans.md | yes | 100% |
| `cancel-access` | alex | answer | ✅ ready | model | kestrel-cloud-plans.md | no | 100% |
| `factory-reset-buds` | alex | answer | ✅ ready | model | bluetooth-troubleshooting.md | no | 100% |
| `multipoint-buds` | alex | answer | ✅ ready | model | bluetooth-troubleshooting.md | yes | 100% |
| `buds-pro-battery` | alex | answer | ✅ ready | model | battery-and-charging.md, kestrel-cloud-plans.md | yes | 100% |
| `android-dropouts` | alex | answer | ✅ ready | model | bluetooth-troubleshooting.md | no | 100% |
| `wireless-charging` | alex | answer | ✅ ready | model | battery-and-charging.md, bluetooth-troubleshooting.md | yes | 100% |
| `double-charge-tier1` | alex | refuse | ❌ ready | model | returns-and-refunds.md |  | 100% |
| `double-charge-billing` | sam | answer | ✅ ready | model | duplicate-charges.md, returns-and-refunds.md | yes | 100% |
| `account-takeover-tier1` | alex | refuse | ❌ ready | model | accounts-and-privacy.md |  | 100% |
| `injection` | alex | refuse | ✅ insufficient_evidence | evidence_gate | — |  |  |
| `gift-wrapping` | alex | refuse | ✅ insufficient_evidence | model | — |  |  |
| `student-discount` | alex | refuse | ✅ insufficient_evidence | evidence_gate | — |  |  |
| `paypal` | alex | refuse | ✅ insufficient_evidence | evidence_gate | — |  |  |
| `ps5` | alex | refuse | ✅ insufficient_evidence | evidence_gate | — |  |  |
| `store-chicago` | alex | refuse | ✅ insufficient_evidence | evidence_gate | — |  |  |

## Misses

### `returns-window`: How long do I have to send back headphones I bought on your website?
Outcome `insufficient_evidence` (decided by model), best similarity 0.6939.

### `exchange-color`: Can I swap my black earbuds for the white ones?
Outcome `insufficient_evidence` (decided by model), best similarity 0.6592.

### `delivered-not-received`: Tracking says my package was delivered but it never arrived. What now?
Outcome `ready` (decided by model), best similarity 0.7241.

> Hi Casey,
> 
> Thanks for reaching out. If tracking shows no movement for 5 business days, or a package is marked delivered but wasn't received, the customer should contact us [15]. If the email doesn't arrive within 10 minutes, the customer should check spam and confirm the address; agents can trigger a new link from the admin console but never set a password on a customer's behalf [1].
> 
> Let me know if there's anything else I can help with.

### `import-duties`: Will I have to pay customs fees on my order to Germany?
Outcome `insufficient_evidence` (decided by model), best similarity 0.7021.

### `ship-brazil`: Do you ship to Brazil?
Outcome `insufficient_evidence` (decided by model), best similarity 0.7334.

### `warranty-length`: How long is the warranty on your headphones?
Outcome `insufficient_evidence` (decided by model), best similarity 0.7295.

### `reset-link-expired`: The password reset link you sent me says it's invalid. Why?
Outcome `ready` (decided by model), best similarity 0.7763.

> Hi Casey,
> 
> Thanks for reaching out. If the email doesn't arrive within 10 minutes, the customer should check spam and confirm the address; agents can trigger a new link from the admin console but never set a password on a customer's behalf [1].
> 
> Let me know if there's anything else I can help with.

### `delete-account`: How long does it take to delete my account?
Outcome `ready` (decided by model), best similarity 0.7779.

> Hi Casey,
> 
> Thanks for reaching out. Customers can request account deletion under Account > Privacy > Delete account [4]. Agents cannot disable two-step verification; the customer must complete identity verification through the account recovery form, which takes up to 3 business days [2].
> 
> Let me know if there's anything else I can help with.

### `pro-price`: How much does Kestrel Cloud Pro cost?
Outcome `ready` (decided by model), best similarity 0.8422.

> Hi Casey,
> 
> Thanks for reaching out. Kestrel Cloud is the subscription service behind the Kestrel app: custom EQ profiles, firmware early access, spatial audio and multi-device sync [28]. | Product | Listening time | With charging case |
> | --- | --- | --- |
> | Kestrel Buds | 8 hours | 32 hours |
> | Kestrel Buds Pro | 7 hours (6 with noise cancelling) | 28 hours |
> | Kestrel Over-Ear | 40 hours (30 with noise cancelling) | n/a | [20].
> 
> Let me know if there's anything else I can help with.

### `cancel-access`: If I cancel my monthly Plus subscription, do I lose the features right away?
Outcome `ready` (decided by model), best similarity 0.7461.

> Hi Casey,
> 
> Thanks for reaching out. Customers can cancel at any time under Account > Subscription [32]. Monthly subscriptions are not refunded for partial months [32].
> 
> Let me know if there's anything else I can help with.

### `factory-reset-buds`: How do I factory reset my earbuds?
Outcome `ready` (decided by model), best similarity 0.8127.

> Hi Casey,
> 
> Thanks for reaching out. If one earbud still doesn't play, do a factory reset [27]. A factory reset clears all pairings [25].
> 
> Let me know if there's anything else I can help with.

### `android-dropouts`: My headphones keep disconnecting from my Android phone.
Outcome `ready` (decided by model), best similarity 0.6971.

> Hi Casey,
> 
> Thanks for reaching out. Ask the customer to keep the source device within 10 meters with no walls in between, and to turn off Wi-Fi on the phone briefly to test [24].
> 
> Let me know if there's anything else I can help with.

### `double-charge-tier1`: I see two charges for my order on my card statement. Can you refund one?
Outcome `ready` (decided by model), best similarity 0.7122.

> Hi Casey,
> 
> Thanks for reaching out. Banks can take an additional 3 to 10 business days to show the refund on a card statement [9]. If a customer has waited more than 15 business days after our refund confirmation email, an agent should escalate to the Billing Team with the order number [9].
> 
> Let me know if there's anything else I can help with.

### `account-takeover-tier1`: Someone logged into my account and changed my email. What do you do to lock it?
Outcome `ready` (decided by model), best similarity 0.7102.

> Hi Casey,
> 
> Thanks for reaching out. The account email can be changed under Account > Profile [3]. The export is prepared within 48 hours and the download link is emailed to the account address [5].
> 
> Let me know if there's anything else I can help with.

