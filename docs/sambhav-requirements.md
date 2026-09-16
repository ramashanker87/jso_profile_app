# Sambhav feature requirements

Sambhav is integrated into the existing JSO application, reusing its navigation,
login and approval guard, member directory, design system and deployment.

Program title: **Sambhav**. Program slug: `sambhav`.
There are **9 domains**, **exactly 3 ideas per domain**, and **27 idea slots**.

| Code | Exact domain title | Slug | Source page reference |
| --- | --- | --- | --- |
| 01 | FinTech & Financial Inclusion | fintech-financial-inclusion | 6 |
| 02 | AI-Driven Skills Mapping & Entrepreneurship | ai-skills-mapping-entrepreneurship | 7 |
| 03 | Primary, Middle & School Education | primary-middle-school-education | 8 |
| 04 | Higher Education, STEM & Research | higher-education-stem-research | 9 |
| 05 | Content Creation, Media & Public Outreach | content-media-public-outreach | 10 |
| 06 | Community Policy, Governance & Social Research | community-policy-governance-social-research | 11 |
| 07 | Healthcare & Public Health | healthcare-public-health | 12 |
| 08 | Agriculture, Environment & Sustainability | agriculture-environment-sustainability | 13 |
| 09 | Engineering, Industrial & Vocational Skill Development | engineering-industrial-vocational-skills | 14 |

Display domains in this exact order. Source page references are metadata and
must not be appended to visible titles.

## Pages

- `/sambhav`: page title Sambhav, with nine domain cards using existing visual
  components. Each card shows domain number, exact title, optional description,
  status, three idea slots and participating-member count. Domain titles and
  Explore domain controls open the domain details page.
- `/sambhav/domains/{domainSlug}`: exactly three idea sections.
- `/sambhav/domains/{domainSlug}/ideas/{ideaId}`: the selected idea's details.

Each idea section displays idea title, short summary, detailed description,
vision, status, lead member, co-lead member, interested members, vision documents,
project documents and last updated date. Idea IDs are stable domain/slot IDs:
`01-01` through `09-03`. Invalid domains or mismatched idea IDs show a not-found
view linking back to Sambhav.

## Initial content

The supplied specification defines the structure, not populated ideas. Each
domain starts with Idea 1, Idea 2 and Idea 3, all Not started. Empty text fields
show Not provided, roles show Not assigned, document lists show No documents
yet, and the date shows Not yet updated. No content, participants, documents or
update dates are invented.

Participating-member counts deduplicate leads, co-leads and interested members
across the domain's ideas by normalized email. References link to the existing
`/members/{email}` directory. The fixed structure is held in a versioned program definition. Editable content
is saved in the Sambhav metadata table within the existing application and
deployment. There is no separate authentication system or member database.


## Editing and PDF attachments

All approved JSO users can select **Edit domain and ideas** on a domain or idea
page. Domain heading (required, up to 200 characters), description and status, idea titles/summaries/descriptions/visions,
idea statuses and member assignments can be changed. Domain identifiers,
ordering and the three-slot structure remain fixed. Lead, co-lead and interested
members are selected from the existing active member directory. Updates record
the editor's Cognito subject and timestamps. Version checks reject stale saves
so concurrent edits cannot silently replace newer content.

Each idea supports multiple PDF attachments in four categories: vision documents,
project details, member profiles and other documents. Each idea accepts at most
30 PDFs, each no larger than 20 MB. Password-protected or unreadable PDFs are
rejected. PDFs are downloaded through fresh five-minute signed links after
application authorization. File validation does not constitute malware scanning.

Metadata uses a single DynamoDB on-demand table, with encryption and point-in-time
recovery. PDFs reuse the existing encrypted private S3 bucket under `sambhav/`.
Direct uploads use five-minute, size-limited signed POST forms to a staging
prefix. The backend validates the actual PDF bytes, stores a separate final
copy, and records its metadata. Upload policies cannot overwrite published
files. Retrying confirmation does not duplicate a successful attachment.
Unfinished uploads expire after one day; their metadata tickets use DynamoDB TTL.
Text edits retain existing PDF metadata. Attachments can be added and downloaded;
removal/replacement controls are not part of this release.

The architecture uses the existing API Gateway and Lambda functions and does not
require an always-running server. Costs scale with DynamoDB requests and data,
S3 storage/requests and downloads; small metadata volumes incur usage-based
charges rather than a provisioned database capacity charge.
