"""Read-only authenticated HTTP benchmark of a reviewed cached lesson."""
import argparse
import json
from math import ceil
import os
from pathlib import Path
import time
from urllib.parse import urlsplit
from uuid import UUID

import requests


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-url', required=True)
    parser.add_argument('--generation', type=UUID, required=True)
    parser.add_argument('--samples', type=int, default=20)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    url = urlsplit(args.base_url)
    if url.username or url.password or url.query or url.fragment or not url.hostname or not (url.scheme == 'https' or url.scheme == 'http' and url.hostname in ('localhost','127.0.0.1')):
        parser.error('Use HTTPS, or HTTP localhost, without credentials/query/fragment.')
    token = os.environ.get('PHASE1_BENCHMARK_TOKEN')
    if not token:
        parser.error('Set PHASE1_BENCHMARK_TOKEN in this process; do not pass credentials as command arguments.')
    if not 20 <= args.samples <= 100:
        parser.error('--samples must be 20–100.')
    timings, failures = [], 0
    with requests.Session() as session:
        for _ in range(args.samples):
            started = time.perf_counter()
            try:
                with session.get(args.base_url.rstrip('/') + '/learning/content/' + str(args.generation),
                                 headers={'Authorization': 'Bearer ' + token}, timeout=(5,15), allow_redirects=False) as response:
                    if response.status_code != 200 or response.json().get('verified') is not True:
                        failures += 1
                    else:
                        timings.append(time.perf_counter() - started)
            except (requests.RequestException, ValueError):
                failures += 1
            time.sleep(.1)
    p95 = sorted(timings)[ceil(.95 * len(timings)) - 1] if timings else None
    result = {'samples': args.samples, 'successful': len(timings), 'failed': failures,
              'p95Seconds': round(p95,3) if p95 is not None else None,
              'targetSeconds': 3, 'passed': failures == 0 and p95 is not None and p95 < 3,
              'scope': 'HTTP API response, including authentication and reviewed DB-cache retrieval; not full browser paint time.'}
    output = json.dumps(result, indent=2)
    if args.output:
        args.output.write_text(output, encoding='utf-8')
    print(output)
    raise SystemExit(0 if result['passed'] else 1)


if __name__ == '__main__':
    main()
