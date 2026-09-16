# Jobs

The `/jobs` page is available from the main navigation to approved users.

1. Paste an `http://` or `https://` job-opening link.
2. Optionally add a job title or company name, then select **Add job**.
3. Click the title or **View job description** to open the original job website in a new tab.
4. When a vacancy closes, select **Delete closed job**, then **Confirm delete**. Cancel keeps the listing.

All approved users can share links and remove closed listings, consistent with the shared editing model used by Sambhav. Deletion removes the community listing, not the posting on the employer's website. Closing a job is a manual action; external websites may require their own login.

Only the link, title, creation time, and creator's Cognito subject are stored. The source page is not scraped, embedded, or cached. If no title is supplied, the website hostname labels the listing. Re-adding the same normalized URL returns a duplicate error; distinct tracking URLs can still represent the same vacancy.

## API and storage

| Method and path | Behavior |
| --- | --- |
| `GET /job-openings` | List all shared openings, newest first |
| `POST /job-openings` | Create from `{ "url": "https://example.org/jobs/123", "title": "Optional title" }` |
| `DELETE /job-openings/{id}` | Remove the listing; repeat deletion succeeds |

All routes use the existing Cognito authorizer and application-group checks. Links must use HTTP(S), contain no credentials, and be at most 4,000 characters. Titles are limited to 200 characters. External links use `noopener noreferrer`; React renders text without interpreting supplied HTML.

The API stores records in the dedicated `profile-library-prod-job-openings` DynamoDB table. It is distinct from `profile-library-prod-jobs`, which tracks synchronization. The new table uses on-demand billing, encryption, point-in-time recovery, and table deletion protection. IDs are hashes of normalized URLs, and conditional writes prevent concurrent duplicates. Listing scans every DynamoDB page, suitable for a small shared job board.

The browser demo stores jobs in memory until reload. The local Python API stores jobs in memory until restart. Production uses DynamoDB. See the README's full deployment instructions to provision the table, routes, environment setting, and IAM permissions before deploying the frontend.
