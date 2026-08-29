# Schedule import examples

Each CSV contains one illustrative row whose headers match the declared
schedule field IDs and account role IDs. Replace the example account codes with
codes from the target SPRK company. An exact company account ID is also
accepted. Account codes must uniquely identify active posting accounts of the
type allowed by each role.

Dates use `YYYY-MM-DD`; amounts are in the company's base accounting currency;
recognition months are positive whole numbers. Keep account codes formatted as
text when preparing XLSX files. SPRK reads the first worksheet and uses the same
headers for CSV and XLSX.

Import is review-first: preview at most 500 rows, resolve every account and
validation issue, then commit the exact preview. A successful commit creates
all drafts atomically. Reusing the same `importKey` safely returns the original
commit result. Import never posts recognition journals.
