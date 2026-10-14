# NYC TLC trip record data: source facts

Research for [#36](https://github.com/Paradiddle131/pplk8s/issues/36), part of the map [#35](https://github.com/Paradiddle131/pplk8s/issues/35).
All facts were checked on 2026-10-12 (UTC) unless a line says otherwise.
"Measured" means observed directly with `curl` or `pyarrow` against the live files; "stated" means read from a TLC or NYC page; "unverified" means neither.

## Sources

- TLC trip record page (stated): https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page
- Data dictionaries, all dated March 18, 2025 (stated):
  - https://www.nyc.gov/assets/tlc/downloads/pdf/data_dictionary_trip_records_yellow.pdf
  - https://www.nyc.gov/assets/tlc/downloads/pdf/data_dictionary_trip_records_green.pdf
  - https://www.nyc.gov/assets/tlc/downloads/pdf/data_dictionary_trip_records_hvfhs.pdf
  - https://www.nyc.gov/assets/tlc/downloads/pdf/data_dictionary_trip_records_fhv.pdf
  - https://www.nyc.gov/assets/tlc/downloads/pdf/trip_record_user_guide.pdf (last updated September 23, 2019)
- The files themselves (measured): `https://d37ci6vzurychx.cloudfront.net/trip-data/…`
- NYC Open Data dataset metadata (measured via the Socrata API): https://data.cityofnewyork.us/api/views/rwwi-khbc.json
- NYC.gov terms of use (stated): https://www.nyc.gov/main/terms-of-use

## Hosts and URL pattern

- One host serves every trip file and the zone files: `d37ci6vzurychx.cloudfront.net` (measured; it is the only file host the TLC page links to).
- Trip file pattern: `https://d37ci6vzurychx.cloudfront.net/trip-data/{type}_tripdata_{YYYY}-{MM}.parquet`, with `{type}` one of `yellow`, `green`, `fhv`, `fhvhv` (measured; the TLC page links 599 such URLs).
- Behind the host is Amazon CloudFront in front of S3: responses carry `server: AmazonS3`, `via: … (CloudFront)`, `x-amz-server-side-encryption: AES256` (measured).
- The host resolved to four IPv4 addresses in `18.239.38.0/24` and several `2600:9000:…` IPv6 addresses from an Amsterdam edge (`x-amz-cf-pop: AMS58-P2`) (measured).
  CloudFront edge IPs vary by location and over time, so a cloud egress allowlist must be FQDN-based, not IP-based.
- Allowlist for a pipeline that only downloads data: `d37ci6vzurychx.cloudfront.net:443`.
  Add `www.nyc.gov:443` only if the pipeline also fetches the data dictionaries or scrapes the TLC page; the data path does not need it.
- Published files answer `HTTP/2 200` with `content-length`, `last-modified`, a strong `etag` (S3 MD5, e.g. `"900a77af7fdc23f019e1fe21a9be5e0a"` for green 2026-08), and `accept-ranges: bytes` (measured).
- Range requests work: `curl -r 0-99` on green 2026-08 answered `206` with 100 bytes (measured).
  A download can therefore resume by byte offset, guarded by `If-Range: <etag>` so a republished file restarts from zero.
- The `content-type` is wrong: `application/x-www-form-urlencoded` (measured on green 2026-08); do not branch on it.

## Sizes and row counts, 2024–2026

File sizes are `content-length` from `HEAD`; rows and row groups come from each file's Parquet footer.
The footers were read without downloading whole files: fetch the last 8 bytes, read the footer length, fetch the footer by range, and place it into a sparse file of the right size for `pyarrow.parquet.read_metadata` (measured, scripts in [Method](#method)).

### Size ranges (measured, all 2024-01 to 2026-08 months)

| Type | Size per month | Smallest | Largest |
|---|---|---|---|
| yellow | 49–78 MB | 49,961,641 B (2024-01) | 77,837,865 B (2025-05) |
| green | 0.9–1.5 MB | 920,753 B (2026-02) | 1,453,912 B (2024-05) |
| fhv | 13–27 MB | 13,608,941 B (2024-02) | 26,307,894 B (2025-10) |
| fhvhv | 462–538 MB | 461,632,254 B (2025-02) | 537,576,484 B (2026-05) |

A full month of all four types is about 600 MB; a year is about 7 GB.

### Per month (measured)

Rows with row-group count in parentheses; `403` means not published on 2026-10-12.

| Month | yellow MB | yellow rows (RGs) | green MB | green rows (RGs) | fhv MB | fhv rows (RGs) | fhvhv MB | fhvhv rows (RGs) |
|---|---|---|---|---|---|---|---|---|
| 2024-01 | 50.0 | 2,964,624 (3) | 1.4 | 56,551 (1) | 15.0 | 1,290,116 (2) | 472.8 | 19,663,930 (19) |
| 2024-02 | 50.3 | 3,007,526 (3) | 1.3 | 53,577 (1) | 13.6 | 1,176,093 (2) | 462.5 | 19,359,148 (19) |
| 2024-03 | 60.1 | 3,582,628 (4) | 1.4 | 57,457 (1) | 16.7 | 1,469,352 (2) | 507.9 | 21,280,788 (21) |
| 2024-04 | 59.1 | 3,514,289 (4) | 1.3 | 56,471 (1) | 16.5 | 1,444,626 (2) | 476.1 | 19,733,038 (19) |
| 2024-05 | 62.6 | 3,723,833 (4) | 1.5 | 61,003 (1) | 16.0 | 1,352,502 (2) | 498.6 | 20,704,538 (20) |
| 2024-06 | 59.9 | 3,539,193 (4) | 1.3 | 54,748 (1) | 16.0 | 1,386,539 (2) | 484.4 | 20,123,226 (20) |
| 2024-07 | 52.3 | 3,076,903 (3) | 1.3 | 51,837 (1) | 16.0 | 1,382,739 (2) | 468.4 | 19,182,934 (19) |
| 2024-08 | 51.1 | 2,979,183 (3) | 1.3 | 51,771 (1) | 16.9 | 1,484,471 (2) | 466.0 | 19,128,392 (19) |
| 2024-09 | 61.2 | 3,633,030 (4) | 1.3 | 54,440 (1) | 19.1 | 1,718,375 (2) | 466.5 | 19,209,788 (19) |
| 2024-10 | 64.3 | 3,833,771 (4) | 1.4 | 56,147 (1) | 16.6 | 1,421,231 (2) | 485.1 | 20,028,282 (20) |
| 2024-11 | 60.7 | 3,646,369 (4) | 1.3 | 52,222 (1) | 18.1 | 1,591,082 (2) | 480.2 | 19,987,533 (20) |
| 2024-12 | 61.5 | 3,668,371 (4) | 1.3 | 53,994 (1) | 20.7 | 1,913,200 (2) | 507.5 | 21,068,851 (21) |
| 2025-01 | 59.2 | 3,475,226 (4) | 1.2 | 48,326 (1) | 20.6 | 1,898,108 (2) | 491.1 | 20,405,666 (20) |
| 2025-02 | 60.3 | 3,577,543 (4) | 1.1 | 46,621 (1) | 17.3 | 1,578,722 (2) | 461.6 | 19,339,461 (19) |
| 2025-03 | 70.0 | 4,145,257 (4) | 1.3 | 51,539 (1) | 23.0 | 2,182,992 (3) | 501.8 | 20,536,879 (20) |
| 2025-04 | 67.4 | 3,970,553 (4) | 1.3 | 52,132 (1) | 19.0 | 1,699,478 (2) | 487.2 | 19,753,983 (19) |
| 2025-05 | 77.8 | 4,591,845 (5) | 1.3 | 55,399 (1) | 24.2 | 2,210,721 (3) | 517.4 | 21,091,193 (21) |
| 2025-06 | 73.5 | 4,322,960 (5) | 1.2 | 49,390 (1) | 24.3 | 2,231,731 (3) | 490.8 | 19,868,009 (19) |
| 2025-07 | 66.9 | 3,898,963 (4) | 1.2 | 48,205 (1) | 23.9 | 2,187,536 (3) | 487.2 | 19,653,012 (19) |
| 2025-08 | 62.3 | 3,574,091 (4) | 1.1 | 46,306 (1) | 24.4 | 2,256,854 (3) | 479.6 | 19,271,461 (19) |
| 2025-09 | 72.4 | 4,251,015 (5) | 1.2 | 48,893 (1) | 23.1 | 2,149,292 (3) | 480.9 | 19,434,641 (19) |
| 2025-10 | 75.3 | 4,428,699 (5) | 1.2 | 49,416 (1) | 26.3 | 2,446,615 (3) | 518.5 | 21,308,701 (21) |
| 2025-11 | 71.1 | 4,181,444 (4) | 1.2 | 46,912 (1) | 25.1 | 2,278,604 (3) | 507.5 | 20,818,240 (20) |
| 2025-12 | 73.7 | 4,305,006 (5) | 1.2 | 48,236 (1) | 21.4 | 1,926,891 (2) | 535.8 | 22,108,438 (22) |
| 2026-01 | 64.2 | 3,724,889 (4) | 1.0 | 40,272 (1) | 21.6 | 1,941,722 (2) | 505.9 | 20,940,373 (20) |
| 2026-02 | 58.7 | 3,399,866 (4) | 0.9 | 37,373 (1) | 20.9 | 1,948,529 (2) | 476.8 | 19,875,686 (19) |
| 2026-03 | 67.9 | 3,952,451 (4) | 1.1 | 44,208 (1) | 25.6 | 2,360,690 (3) | 532.6 | 22,058,358 (22) |
| 2026-04 | 64.8 | 3,831,240 (4) | 1.1 | 44,238 (1) | 23.2 | 2,125,630 (3) | 509.9 | 20,995,953 (21) |
| 2026-05 | 69.7 | 4,090,836 (4) | 1.1 | 44,921 (1) | 26.2 | 2,421,419 (3) | 537.6 | 22,125,744 (22) |
| 2026-06 | 65.5 | 3,837,248 (4) | 1.1 | 44,163 (1) | 21.2 | 1,892,696 (2) | 506.8 | 20,775,868 (20) |
| 2026-07 | 61.7 | 3,530,109 (4) | 1.0 | 41,252 (1) | 23.2 | 2,138,604 (3) | 511.2 | 20,921,249 (20) |
| 2026-08 | 59.0 | 3,336,716 (4) | 1.0 | 40,687 (1) | 403 | 403 | 502.4 | 20,493,480 (20) |
| 2026-09 | 403 | 403 | 403 | 403 | 403 | 403 | 403 | 403 |

Byte-exact sizes are the `content-length` of each URL; the table rounds to MB.
Across 2024-01 to 2026-08, FHVHV runs 19.1–22.1 million rows a month in 19–22 row groups, yellow 3.0–4.6 million rows in 3–5 groups, FHV 1.2–2.4 million rows in 2–3 groups, and green 37–61 thousand rows in one group (measured).

## Parquet layout and row groups as a cursor

Measured from footers:

| File | Writer | Codec | Row groups | Rows per group | Largest group, compressed / uncompressed |
|---|---|---|---|---|---|
| yellow 2023-01 | parquet-cpp-arrow 8.0.0 | GZIP | 1 | 3,066,766 | 47.7 MB / 83.2 MB |
| yellow 2024-01 | parquet-cpp-arrow 14.0.2 | ZSTD | 3 | 1,048,576 + tail | 17.6 MB / 28.2 MB |
| yellow 2025-01 | parquet-cpp-arrow 16.1.0 | ZSTD | 4 | 1,048,576 + tail | 17.8 MB / 28.6 MB |
| yellow 2026-08 | parquet-cpp-arrow 21.0.0 | ZSTD | 4 | 1,048,576 + tail | 18.7 MB / 29.2 MB |
| green 2023-01 | parquet-cpp-arrow 8.0.0 | GZIP | 1 | 68,211 | 1.4 MB / 2.1 MB |
| green 2024-01 to 2026-08 | arrow 14 to 21 | ZSTD | 1 | whole file | ≤1.4 MB / ≤1.8 MB |
| fhv 2024-01 | parquet-cpp-arrow 14.0.2 | ZSTD | 2 | 1,048,576 + tail | 11.8 MB / 19.6 MB |
| fhvhv 2023-01 | parquet-cpp-arrow 8.0.0 | GZIP | 1 | 18,479,031 | 473.8 MB / 851.4 MB |
| fhvhv 2024-01 | parquet-cpp-arrow 14.0.2 | ZSTD | 19 | 1,048,576 + tail | 26.4 MB / 36.2 MB |
| fhvhv 2026-08 | parquet-cpp-arrow 21.0.0 | ZSTD | 20 | 1,048,576 + tail | 26.7 MB / 35.8 MB |

What this means for a resumable cursor:

- From 2024 on, every file is written by pyarrow with its default row-group size of 1,048,576 (2^20) rows, so row groups are full 2^20-row blocks plus one shorter tail group.
- A row-group index is a usable cursor for yellow (3–5 groups, ~18 MB each) and FHVHV (19–22 groups, ~26 MB each): each group can be read independently by byte range once the footer is known.
- It is useless for green: every green file is one row group, so the cursor has one position, and at about 1 MB the file never needs one.
- It breaks for 2023 and earlier backfill: those files were written by pyarrow 8.0.0 as a single GZIP row group, so FHVHV 2023-01 is one 474 MB compressed / 851 MB uncompressed group that cannot be split.
- The grouping is a writer default, not a published contract: the writer moved from arrow 8 (2023 files) through 14 and 16 to 21 (2026 files), and files can be republished, so a cursor must be keyed to the file's `etag` and restart if the `etag` changes.
- A byte-range download cursor (offset plus `If-Range: <etag>`) works for every file regardless of row groups, so download resumption and processing resumption are separate concerns.

## Publication

- Stated: "Trip data is published monthly on this website, typically with a two-month delay to allow time for full vendor submissions."
- Stated: "there may be minor changes in the near future to standardize the parquet schema across all years and datasets."
- Measured state on 2026-10-12: yellow, green, and FHVHV are published through 2026-08; FHV only through 2026-07 (FHV lags the others by one month; the TLC page's 2026 August entry lists no FHV file).
- Measured `last-modified` dates show the lag in practice (yellow; green and FHVHV usually share the date, FHV often trails by a month):

| Data month | last-modified | Lag |
|---|---|---|
| 2024-01 | 2024-03-21 | ~2 months |
| 2024-12 | 2025-02-21 | ~2 months |
| 2025-01 and 2025-02 | both 2025-04-23 | 3 and 2 months |
| 2025-04 and 2025-05 | both 2025-06-25 | 2 and 1 months |
| 2025-12, 2026-01, 2026-02 | all 2026-03-25 | 3, 2, 1 months |
| 2026-06 and 2026-07 | both 2026-09-17 | 3 and 2 months |
| 2026-08 | 2026-10-01 | ~1 month |

- Two caveats on those dates:
  - `last-modified` is the latest upload, not the first, so a month that was republished shows its republication date; the data cannot tell a late first publication from a republication.
  - Months often appear in batches (two or three months on one day), and the lag ranges from one to three months, so a trigger must poll rather than assume a fixed day.
- Republication happens: the NYC Open Data copy of 2024 yellow says "The data will only be changed rarely if there are corrections needed" (stated, dataset `rwwi-khbc`), and FHVHV 2025-12 (2026-02-24) and yellow 2025-12 (2026-03-25) differ by a month (measured), which suggests yellow 2025-12 was re-uploaded or delayed (unverified which).
- The `etag` is the change detector: a pipeline that stores the `etag` per loaded month can notice a republication with one `HEAD`.

### How an unpublished month answers

- An unpublished month answers `HTTP/2 403` with `content-type: application/xml`, `server: AmazonS3`, `x-cache: Error from cloudfront`, and the body `<Error><Code>AccessDenied</Code><Message>Access Denied</Message></Error>` (measured on `green_tripdata_2026-09.parquet` and others).
- A file that will never exist answers the same: `purple_tripdata_2024-01.parquet` also gave `403` (measured).
  The bucket denies listing, so S3 returns `403 AccessDenied` instead of `404` for any missing key; "not yet published" and "wrong URL" are indistinguishable.
- No `404` was observed for any URL.

### Rate limiting

- After roughly 500 `HEAD` and ranged `GET` requests from one IP in about four minutes, CloudFront began answering `403` to every URL, including published files (measured, first seen 2026-10-12 21:59:47 UTC).
- That block is distinguishable from an unpublished month: `server: CloudFront` (not `AmazonS3`), `content-type: text/html`, and an HTML body reading "Request blocked. … There might be too much traffic or a configuration error."
- The block lasted about five minutes: polling once a minute, the last blocked answer came at 22:03:54 UTC and the first `200` at 22:04:54 UTC (measured).
- Afterwards about 190 requests paced at roughly one per second (the FHV/FHVHV footer sweep) ran without being blocked (measured).
- Design consequence: classify a `403` by its `server` header and body before treating it as "not yet published", and pace any backfill or probing (no published limit was found; unverified what the threshold is).

## Schema drift, 2023–2026

Measured by comparing footer schemas: every month 2024-01 to 2026-08 for all four types, plus the 2023-01 files as the 2023 baseline; every 2023 yellow and green file was probed on 2026-10-13 (#82).

### 2023 files to 2024 files (all types)

**Only 2023-01 still has the old schema** (probed 2026-10-13, #82): yellow and green 2023-02 to 2023-12 already carry the 2024 types (`VendorID int32`, `passenger_count int64`, `PULocationID int32`), so they were rewritten with the standardised schema; 2023-01 kept `last-modified` 2023-03-20.
The differences below are those of the 2023-01 files.

- 2023 files were written by pyarrow 8.0.0 (format 1.0, GZIP, pandas metadata embedded); 2024 files by pyarrow 14.0.2 (format 2.6, ZSTD, no pandas metadata).
- Yellow, retyped: `VendorID` int64→int32, `passenger_count` double→int64, `RatecodeID` double→int64, `PULocationID` and `DOLocationID` int64→int32, `store_and_fwd_flag` string→large_string.
- Yellow, renamed by case: `airport_fee` (2023) → `Airport_fee` (2024 onward); the data dictionary still spells it `airport_fee`, and FHVHV uses `airport_fee`.
- Green, retyped: `VendorID` int64→int32, `RatecodeID`, `passenger_count`, `payment_type`, `trip_type` double→int64, `PULocationID`/`DOLocationID` int64→int32, `store_and_fwd_flag` string→large_string, and `ehail_fee` null-typed→double.
- FHVHV, retyped: `PULocationID`/`DOLocationID` int64→int32 and all string columns string→large_string.
- The page's warning about standardising the schema "across all years" has reached 2023-02 to 2023-12 but not 2023-01, which still carries `last-modified` 2023-03-20 (measured).

### Added columns

| Column | Types | First month | Source |
|---|---|---|---|
| `cbd_congestion_fee` (double) | yellow, green, fhvhv | 2025-01 | measured; stated on the TLC page ("For 2025 data onwards…") and in the March 18, 2025 dictionaries ("Per-trip charge for MTA's Congestion Relief Zone starting Jan. 5, 2025") |
| `request_source` (large_string) | yellow, green | 2026-06 | measured; not in any data dictionary (dictionaries dated March 18, 2025), meaning unverified |

- `request_source` values in green 2026-08: null 34,377, `A` 5,130, `HV0005` 1,179, `CC` 1 (measured); `HV0005` is an HVFHS licence number, so the column may name the app or channel that requested the trip (unverified).
- FHVHV gained no columns after `cbd_congestion_fee`, and FHV did not change at all, across every month 2024-01 to 2026-08 / 2026-07 (measured, bisected month by month).
- Within 2024-01 to 2026-08 no yellow or green column was removed or retyped (measured).

### Current schemas (measured)

- yellow 2026-08 (21 columns): `VendorID:int32, tpep_pickup_datetime:timestamp[us], tpep_dropoff_datetime:timestamp[us], passenger_count:int64, trip_distance:double, RatecodeID:int64, store_and_fwd_flag:large_string, PULocationID:int32, DOLocationID:int32, payment_type:int64, fare_amount:double, extra:double, mta_tax:double, tip_amount:double, tolls_amount:double, improvement_surcharge:double, total_amount:double, congestion_surcharge:double, Airport_fee:double, cbd_congestion_fee:double, request_source:large_string`
- green 2026-08 (22 columns): `VendorID:int32, lpep_pickup_datetime:timestamp[us], lpep_dropoff_datetime:timestamp[us], store_and_fwd_flag:large_string, RatecodeID:int64, PULocationID:int32, DOLocationID:int32, passenger_count:int64, trip_distance:double, fare_amount:double, extra:double, mta_tax:double, tip_amount:double, tolls_amount:double, ehail_fee:double, improvement_surcharge:double, total_amount:double, payment_type:int64, trip_type:int64, congestion_surcharge:double, cbd_congestion_fee:double, request_source:large_string`
- fhvhv 2026-08 (25 columns): `hvfhs_license_num, dispatching_base_num, originating_base_num:large_string, request_datetime, on_scene_datetime, pickup_datetime, dropoff_datetime:timestamp[us], PULocationID, DOLocationID:int32, trip_miles:double, trip_time:int64, base_passenger_fare, tolls, bcf, sales_tax, congestion_surcharge, airport_fee, tips, driver_pay:double, shared_request_flag, shared_match_flag, access_a_ride_flag, wav_request_flag, wav_match_flag:large_string, cbd_congestion_fee:double`
- fhv 2026-07 (7 columns): `dispatching_base_num:large_string, pickup_datetime:timestamp[us], dropOff_datetime:timestamp[us], PUlocationID:int64, DOlocationID:int64, SR_Flag:int64, Affiliated_base_number:large_string`
  - FHV spells the location columns `PUlocationID`/`DOlocationID` (lower-case `l`) and keeps them int64, unlike the other three types.

### Data quality worth a test

- Green 2026-08 contains pickups outside its month: the minimum `lpep_pickup_datetime` is 2008-12-31 23:06:23 (measured), so a month file is not a clean partition by pickup time.

## Taxi zone lookup

- CSV: https://d37ci6vzurychx.cloudfront.net/misc/taxi_zone_lookup.csv, 12,331 bytes, `last-modified` 2024-02-22 (measured).
  The legacy name `misc/taxi+_zone_lookup.csv` still answers 200 with the same size (measured).
- Shapefile: https://d37ci6vzurychx.cloudfront.net/misc/taxi_zones.zip, 1,022,574 bytes, `last-modified` 2026-02-19 (measured); the TLC page labels this link "Taxi Zone Shapefile (PARQUET)" although the URL is a `.zip` (stated vs measured; contents not inspected).
- Both live on the same host as the trip files, so the allowlist above covers them.

## Licence and terms of use

- The TLC page attaches no licence; it disclaims accuracy: "The trip data was not created by the TLC, and TLC makes no representations as to the accuracy of these data" (stated).
- NYC.gov terms of use claim the site's materials as "the property of the City of New York. All rights are reserved" and say nothing specific about data sets (stated).
- The NYC Open Data copy of the same data (dataset `rwwi-khbc`) has `license: null`, `attribution: "Taxi and Limousine Commission (TLC)"`, and `provenance: official` (measured via the Socrata API).
- NYC's Open Data Law (Administrative Code Title 23, Chapter 5) is linked from the NYC Open Data overview; its text could not be read (codelibrary.amlegal.com answered 403), so the claim that it makes public data sets available without registration or use restrictions is unverified here.
- Reading for a personal, non-commercial learning lab: downloading the public files, keeping them out of git, attributing TLC as the source, and not republishing the data is consistent with everything stated above; no clause found forbids it (an interpretation, not legal advice).

## Method

Run on 2026-10-12 from a WSL2 host in the Netherlands; downloaded files sat in fresh empty directories under `/tmp` and scripts in a separate directory, run with `uvx --from pyarrow python -I`.

- Sizes and status: `curl -sI https://d37ci6vzurychx.cloudfront.net/trip-data/{type}_tripdata_{YYYY}-{MM}.parquet` for every type and month 2024-01 to 2026-12, plus 2023-01.
- Footers without full downloads:

```bash
L=$(curl -sI "$U" | awk 'tolower($1)=="content-length:"{print $2}' | tr -d '\r')
T=$(curl -s -r $((L-8))-$((L-1)) "$U" | od -An -t u4 -N4 | tr -d ' ')   # footer length
truncate -s "$L" "$F"
curl -s -r $((L-8-T))-$((L-1)) "$U" | dd of="$F" bs=1M seek=$((L-8-T)) oflag=seek_bytes conv=notrunc status=none
# then pyarrow.parquet.read_metadata(F) / read_schema(F)
```

- Full downloads, only for green 2024-01 and 2026-08 (about 1 MB each), to read column values.
- No downloaded data was committed.
