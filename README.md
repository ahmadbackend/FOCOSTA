# Fotocasa Property Pipeline

Collects the Fotocasa (Spain) property catalogue by reconstructing the site's own
search API, then deduplicates, maps and enriches the results into a flat dataset of
private-seller listings and the agencies behind the rest.

The site's frontend is a React app that talks to two JSON gateways. Driving those
directly — rather than parsing rendered HTML — means the extraction survives
frontend changes, returns every field the API exposes rather than only what the page
renders, and costs one request per 30 listings instead of one per listing.

| Endpoint | Role |
|---|---|
| `search.gw.fotocasa.es/v2/suggest` | Location autocomplete — walked to build the region tree |
| `web.gw.fotocasa.es/v1/search/ads` | Paginated ad search, 30 results per page |

## The pipeline

Thirteen stages, each an independent script under `HOMES/`, chained by `main.py`:

```
harvest-locations   suggest API  ->  location tree (depth 3)
filter-locations    drop regions already covered by a parent or a previous run
scrape              paginate every location  ->  raw listing batches
retry               re-request pages that failed
dedupe              collapse duplicate ids across all batches
map-features        raw feature ids  ->  readable field names
filter-private      keep private-seller listings
enrich              normalize features, derive location fields
export              merged JSON + flattened CSV
agencies            unique agency list  ->  phone  ->  email/website
split-regions       one file per province
```

`workflow.txt` has the same chain with the intermediate filenames.

### Design notes

**Resumable by construction.** The scrape stage writes a `_completed.json` marker per
location and a `_location_state.json` checkpoint, so an interrupted run restarts where
it stopped rather than from the beginning. It also stops paginating a location after
`MAX_DUPLICATE_HITS` repeated pages, which is how the API signals it has run out of
distinct results rather than returning an empty page.

**Deduplication is global, not per-file.** Listings appear under several overlapping
regions, so `dedupe` indexes ids across every batch file before writing 5,000-item
output batches.

**Locations are filtered hierarchically.** A region already covered by a larger parent
region is dropped before scraping, which is where most of the redundant requests go.

**Threaded with a shared proxy pool.** One worker per thread, each pulling from a
rotating proxy list, with graceful `SIGINT`/`SIGTERM` handling so a stop still flushes
state.

## Running it

```bash
pip install -r requirements.txt

python main.py list                      # stages, and which outputs already exist
python main.py pipeline                  # the whole chain
python main.py pipeline --dry-run        # print the plan, run nothing
python main.py pipeline --from dedupe    # resume partway
python main.py run scrape --threads 20   # a single stage
```

Every stage is still runnable on its own — `cd HOMES && python multi_thread_corrected.py`
behaves exactly as it always did.

## Configuration

Stages read `FC_*` environment variables and fall back to the default in each script,
so nothing needs configuring to run. Common options are exposed as flags:

| Flag | Sets |
|---|---|
| `--proxy-file` | `FC_PROXY_FILE` — proxy list, `host:port:user:pass` per line |
| `--threads` | `FC_NUM_THREADS` |
| `--sleep` | `FC_SLEEP` — delay between requests |
| `--page-size` | `FC_PAGE_SIZE` |
| `--set NAME=VALUE` | any stage constant, e.g. `--set OUTPUT_ROOT=run2` |

## Data and proxies are not in this repository

`.gitignore` excludes every scrape artifact and the proxy list. The outputs run to
several GB and contain third-party contact details; the proxy file contains
credentials. Point `--proxy-file` at your own list.
