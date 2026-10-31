import os
import django
import time

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'brightloop.settings')
django.setup()

from django.test import Client
from django.contrib.auth import get_user_model
from django.db import connection, reset_queries
from django.conf import settings

User = get_user_model()

def benchmark_pages():
    client = Client()

    # Log in as admin
    admin = User.objects.filter(role=User.ROLE_ADMIN).first()
    if not admin:
        print("Admin user not found!")
        return
    client.force_login(admin)

    pages = [
        ("Finance Dashboard", "/dashboard/"),
        ("Invoice List", "/billing/"),
        ("Subscription List", "/subscriptions/"),
    ]

    print("=" * 70)
    print("PAGE LOAD BENCHMARK (Django Test Client with 5,000 Subscriptions)")
    print("=" * 70)

    # Enable debug query counting for inspection
    settings.DEBUG = True

    results = {}

    for name, url in pages:
        # Warmup request
        reset_queries()
        warmup_resp = client.get(url)
        if warmup_resp.status_code != 200:
            print(f"ERROR: {name} ({url}) returned status {warmup_resp.status_code}")
            continue

        # Timed runs
        times = []
        queries_count = 0
        iterations = 5

        for i in range(iterations):
            reset_queries()
            start = time.perf_counter()
            resp = client.get(url)
            elapsed = time.perf_counter() - start
            times.append(elapsed)
            if i == 0:
                queries_count = len(connection.queries)

        avg_time = sum(times) / len(times)
        min_time = min(times)
        max_time = max(times)
        results[name] = {
            'url': url,
            'avg_ms': avg_time * 1000,
            'min_ms': min_time * 1000,
            'max_ms': max_time * 1000,
            'queries': queries_count,
            'status': resp.status_code,
        }

        print(f"{name:22} | {url:18} | Status: {resp.status_code} | Queries: {queries_count:3d}")
        print(f"  -> Avg: {avg_time*1000:6.2f} ms | Min: {min_time*1000:6.2f} ms | Max: {max_time*1000:6.2f} ms")
        print("-" * 70)

    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    for name, data in results.items():
        pass_fail = "PASS (<1s)" if data['avg_ms'] < 1000 else "FAIL (>1s)"
        print(f"{name:22}: {data['avg_ms']:6.2f} ms (Queries: {data['queries']}) - {pass_fail}")

if __name__ == '__main__':
    benchmark_pages()
