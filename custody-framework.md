# Custody Trust Framework
This document describes a sample trust framework for guardianship. It is accompanied by [sample schemas](sample-schemas.md)

## Name, Version, and Author
- **Trust Framework Name:**  TR Custody Trust Framework
- **Version:** 1.0
- **Author**:  It is maintained by the Ministry of Justice.

## Scope
This framework is suitable for use by the courts within the boundaries of Turkey.

## Metadata
There must be certain metadata information in the credentials to be given using this framework.
* `case-result`: should be one of the following attributes: `sole-custody`,`split-custody`,`divided-custody` and `joint-custody`
> Additional metadata suggestions are welcome.

## Rationales for Guardianship
In this framework, guardianship is based on one or more of the following formally defined rationales:
* `kinship`: If the person taking custody of the child is a relative, this should be chosen.
* `court-order`: This rationale is required for the legal enforcement of custody use case.
* `enforced`: If the person who takes custody of the child is not a relative, this should be chosen.

## Identifying
### Holder
This framework defines the following ways to identify a **Holder (guardian)** in a credential:
* `first-name`: First name should be the name that the guardian acknowledges and answers to
* `last-name`:  Last name may be empty if it is unknown
* `role`: It can be following values: `kinship`, `ad-hoc`, `legal_appointment`.
* `kinship-status`:  If the role is a `kinship`, then this attribute should be filled. Otherwise, it can be left blank. Indicates the degree of kinship. Can be following values: `mother`, `father`, `grandmother`, `grandfather`, `uncle`, `other`.
* `rationalURI`: can be folllowing values as described in [Rationales for Guardianship](#rationales-for-guardianship).

### Proxied
This framework defines the following ways to identify a **Proxied (dependent)** in a credential:
* `first-name`: First name should be the name that the dependent acknowledges and answers to
* `last-name`:  Last name may be empty if it is unknown
* `birth-date`:  Birth date may be approximate
* `photo`: Photo is required and must be a color photo of at least 800x800 pixel resolution.
* `iris`: Not mandatory but strongly recommended.
* `fingerprint`: Not mandatory but strongly recommended.

## Permissions
Defines guardian's permissions. Retrieves data as a string list. This field contains an array of [SGL](https://evernym.github.io/sgl) __rules__.
It can be one of the following items.
- `routine-medical-care`: Includes all health related use case of dependent
- `school`: It is valid in school-related situations such as enrollment or choosing a course.
- `necessaries`: Basic vital needs
- `light-travel`: For day trips. Boarding stay is not covered.
- `extended-travel`: It covers long-term trips with boarding.
- `contracts`: Permission to issue legal documents on behalf of the Dependent.
- `delegate`: Being able to delegate an authority to another person.
- `successor`: It is the permission to choose a guardian that can replace after her.
- `authorize`: Authority to change permissions.

## Constraints
A guardian's ability to control the dependent may be constrained in the following ways:
- `boundaries`: Can be country, city or region. Boundaries are specified as a comma-separated list of strings. 
- `pointOfOrigin`: Additional way to specify boundaries. It is a string that may use latitude/longitude notation 
- `radiusKM`: Radius is an integer measured in kilometers. Must use with `pointOfOrigin`.
- `jurisdictions`: It indicates in which regions this relationship is valid legally.
- `trigger`: Lorem ipsum dolor sit amet, consectetur adipiscing
- `circumstances`: Lorem ipsum dolor sit amet, consectetur adipiscing
- `startTime`: Indicates on which date this relationship started. It is expressed as ISO8601 timestamps in UTC timezone. 
- `endTime`: Indicates on which date this relationship ended. It is expressed as ISO8601 timestamps in UTC timezone.


## Auditing and Appeal Mechanism
It is strongly recommended that an audit trail be produced any time a guardian performs any action.
### Audit
It should be have following attributes:
- `event_time`
- `event_place`
- `guardian`
- `dependent`
- `event`
- `justifying_permissions`
- `evidence`
### Appeal
It is a linking to an arbitration or adjudication authority for the credential. This mechanism must have contact information such as phone number, web site, or email address, and the contact info must be provided in the guardian credential in the `appeal_uri` field.

## Freshness
> TODO: Could be future work

## Best Practices
