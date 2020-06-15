# Custody Trust Framework
This document describes a sample trust framework for guardianship. It is accompanied by [sample schemas](sample-schemas.md)

## Name, version, and Schema
- **Trust Framework Name:**  TR Custody Trust Framework
- **Version:** 1.0
- **Schemas**: SoleCustody, SplitCustody, DividedCustody, JointCustody 

## Scope
This framework is suitable for use by the courts within the boundaries of Turkey.

## Rationales for Guardianship
In this framework, guardianship is based on one or more of the following formally defined rationales:
* `kinship`: 
* `court-order`: 
* `enforced`: 

## Identifying
### Holder
This framework defines the following ways to identify a **Holder (guardian)** in a credential:
* `first-name`: First name should be the name that the guardian acknowledges and answers to
* `last-name`:  Last name may be empty if it is unknown
* `role`: It can be following values: `kinship`, `ad-hoc`, `legal_appointment`.
* `kinship-status`:  If the role is a `kinship`, then this attribute should be filled. Otherwise, it can be left blank. Indicates the degree of kinship. Can be following values: `mother`, `father`, `grandmother`, `grandfather`, `uncle`, `other`.
* `rationalURI`: can be folllowing values as described in [Rationales for Guardianship](#rationales-for-guardianship).

### Proxied
This framework defines the following ways to identify a **dependent** in a credential:
* `first-name`: First name should be the name that the dependent acknowledges and answers to
* `last-name`:  Last name may be empty if it is unknown
* `birth-date`:  Birth date may be approximate
* `photo`: Photo is required and must be a color photo of at least 800x800 pixel resolution.
* `iris`: Not mandatory but strongly recommended.
* `fingerprint`: Not mandatory but strongly recommended.

## Permissions
Defines guardian's permissions. Retrieves data as a string list. This field contains an array of [SGL](https://evernym.github.io/sgl) __rules__.
It can be one of the following items.
- `routine-medical-care`
- `school`
- `necessaries`
- `light-travel`
- `extended-travel`
- `unenroll`
- `contracts`
- `delegate`
- `successor`
- `authorize`

## Constraints
A guardian's ability to control the dependent may be constrained in the following ways:
- `boundaries`: Lorem ipsum dolor sit amet, consectetur adipiscing
- `pointOfOrigin`: Lorem ipsum dolor sit amet, consectetur adipiscing
- `radiusKM`: Lorem ipsum dolor sit amet, consectetur adipiscing
- `jurisdictions`: Lorem ipsum dolor sit amet, consectetur adipiscing
- `trigger`: Lorem ipsum dolor sit amet, consectetur adipiscing
- `circumstances`: Lorem ipsum dolor sit amet, consectetur adipiscing
- `startTime`: Lorem ipsum dolor sit amet, consectetur adipiscing
- `endTime`


## Auditing and Appeal Mechanism
Lorem ipsum dolor sit amet, consectetur adipiscing

## Freshness

## Best Practices
