# Chapter 26: ElastiCache & Caching Patterns

*AWS Handbook — Pages 126–130 of this PDF edition*
---

## 26.1 Why caching?

Every database query that hits disk (or even memory-optimized databases) adds latency and load. **Caching** stores frequently accessed data in a fast, in-memory layer, reducing database pressure and improving response times from milliseconds to microseconds.

**Amazon ElastiCache** provides fully managed in-memory caching with two engines: **Redis** and **Memcached**.

---

## 26.2 Redis vs Memcached

| Feature | Redis | Memcached |
|---------|-------|-----------|
| **Data structures** | Strings, lists, sets, sorted sets, hashes, streams, bitmaps | Strings only (key-value) |
| **Persistence** | RDB snapshots, AOF | None (pure cache) |
| **Replication** | Primary + up to 5 replicas | None (client-side sharding) |
| **Multi-AZ** | Automatic failover | No |
| **Clustering** | Cluster mode (sharding) | Client-side consistent hashing |
| **Pub/Sub** | Yes | No |
| **Lua scripting** | Yes | No |
| **Backup/restore** | Yes | No |
| **Use case** | Sessions, leaderboards, real-time analytics, queues | Simple object caching |

**Recommendation:** Choose **Redis** unless you need only simple key-value caching with horizontal scaling via client-side sharding.

---

## 26.3 ElastiCache deployment options

| Option | Description |
|--------|-------------|
| **Single node** | Dev/test only; no HA |
| **Multi-AZ with replica** | Primary + replica; automatic failover |
| **Cluster mode disabled** | One shard; up to 5 read replicas |
| **Cluster mode enabled** | Multiple shards; horizontal scaling |
| **Serverless** | Auto-scaling memory; pay per use |

### Node types

| Family | Use case |
|--------|----------|
| **cache.t3/t4g** | Dev/test, burstable |
| **cache.m6g/m7g** | General purpose |
| **cache.r6g/r7g** | Memory-optimized, large datasets |

---

## 26.4 Common caching patterns

### Cache-aside (lazy loading)

Application checks cache first; on miss, reads from database and populates cache:

```
1. App → Cache: GET key
2. Cache miss → App → DB: SELECT
3. App → Cache: SET key (with TTL)
4. App returns data
```

```python
import redis
import json

cache = redis.Redis(host="my-cluster.abc123.cache.amazonaws.com", port=6379)

def get_user(user_id):
    cached = cache.get(f"user:{user_id}")
    if cached:
        return json.loads(cached)

    user = db.query("SELECT * FROM users WHERE id = %s", user_id)
    cache.setex(f"user:{user_id}", 3600, json.dumps(user))  # TTL 1 hour
    return user
```

### Write-through

Application writes to cache and database simultaneously:

```
App → Cache: SET key
App → DB: INSERT/UPDATE
```

Ensures cache is always up to date but adds write latency.

### Write-behind (write-back)

Application writes to cache; cache asynchronously writes to database:

```
App → Cache: SET key
Cache → DB: async write (batched)
```

Highest write performance but risk of data loss if cache fails before DB write.

### Read-through

Cache itself loads data from database on miss (requires cache library support):

```
App → Cache: GET key
Cache miss → Cache → DB: load and return
```

---

## 26.5 Redis data structure use cases

| Structure | Use case | Example |
|-----------|----------|---------|
| **String** | Simple cache, counters | Session token, page view count |
| **Hash** | Object storage | User profile fields |
| **List** | Queues, timelines | Recent activity feed |
| **Set** | Unique items | Online users, tags |
| **Sorted Set** | Leaderboards, rankings | Game scores, trending |
| **Stream** | Event log | Activity stream, messaging |
| **Bitmap** | Feature flags, analytics | Daily active users |
| **HyperLogLog** | Cardinality estimation | Unique visitor count |

### Leaderboard example

```python
# Add score
cache.zadd("leaderboard:2024", {"player-1": 1500, "player-2": 2300})

# Top 10
top_10 = cache.zrevrange("leaderboard:2024", 0, 9, withscores=True)

# Player rank
rank = cache.zrevrank("leaderboard:2024", "player-1")
```

---

## 26.6 Session management

Redis is the standard for distributed session storage:

```python
import uuid

def create_session(user_id):
    session_id = str(uuid.uuid4())
    cache.setex(f"session:{session_id}", 86400, json.dumps({
        "user_id": user_id,
        "created": time.time(),
    }))
    return session_id

def get_session(session_id):
    data = cache.get(f"session:{session_id}")
    return json.loads(data) if data else None
```

Benefits over sticky sessions:
- Any app server can handle any request.
- Sessions survive server restarts.
- Easy session invalidation (delete key).

---

## 26.7 ElastiCache security

| Control | Implementation |
|---------|----------------|
| **Network** | Deploy in private subnets; security groups |
| **Encryption in transit** | TLS (required for compliance) |
| **Encryption at rest** | KMS |
| **AUTH token** | Redis password (required with encryption in transit) |
| **RBAC** | Redis ACLs for fine-grained access (Redis 6+) |

```hcl
resource "aws_elasticache_replication_group" "redis" {
  replication_group_id       = "app-cache"
  description                = "Application Redis cluster"
  node_type                  = "cache.r6g.large"
  num_cache_clusters         = 2
  automatic_failover_enabled = true
  multi_az_enabled           = true

  engine               = "redis"
  engine_version       = "7.0"
  port                 = 6379
  parameter_group_name = "default.redis7"

  subnet_group_name  = aws_elasticache_subnet_group.main.name
  security_group_ids = [aws_security_group.redis.id]

  at_rest_encryption_enabled = true
  transit_encryption_enabled = true
  auth_token                 = var.redis_auth_token

  snapshot_retention_limit = 7
  snapshot_window          = "03:00-05:00"
}
```

---

## 26.8 Monitoring and maintenance

| Metric | Action |
|--------|--------|
| `CPUUtilization` | Scale up node type if > 75% |
| `DatabaseMemoryUsagePercentage` | Scale up or evict; risk of OOM |
| `CacheHitRate` | Low hit rate → review TTLs and key design |
| `Evictions` | Memory pressure; scale up or reduce TTLs |
| `ReplicationLag` | Replica falling behind; check network/load |

### Maintenance windows

ElastiCache applies engine patches during maintenance windows. Enable **auto minor version upgrade** for security patches.

---

## 26.9 Caching anti-patterns

| Anti-pattern | Problem | Solution |
|--------------|---------|----------|
| Cache everything | Memory waste, stale data | Cache only hot data with TTLs |
| No TTL | Stale data forever | Always set expiration |
| Cache stampede | Many requests hit DB on simultaneous expiry | Jittered TTLs, request coalescing |
| Large objects | Memory pressure, slow serialization | Compress or split large values |
| Caching errors | Error responses cached | Don't cache 4xx/5xx responses |
| No cache invalidation strategy | Stale data after updates | Event-driven invalidation via streams/SNS |

---

## 26.10 Chapter summary

- **ElastiCache** provides managed Redis and Memcached for in-memory caching.
- **Redis** supports rich data structures, persistence, replication, and pub/sub.
- **Cache-aside** is the most common pattern; always set **TTLs**.
- Use Redis for sessions, leaderboards, and real-time features.
- Deploy in **private subnets** with encryption in transit and at rest.

---

## 🧪 Lab 26.1 — Redis cache-aside

1. Create an ElastiCache Redis cluster (single node for lab).
2. Write a Python app that implements cache-aside for a DynamoDB table.
3. Measure response time with and without cache.
4. Verify cache hit rate in CloudWatch.

## 🧪 Lab 26.2 — Leaderboard

1. Use Redis sorted sets to build a game leaderboard.
2. Add scores for 20 players.
3. Query top 10 and individual player rank.
4. Implement a "scores in last hour" feature using TTL keys.

---

## Review questions

1. When would you choose Memcached over Redis?
2. How does the cache-aside pattern handle cache misses?
3. What is cache stampede and how do you prevent it?
4. Why is Redis preferred for session management over sticky sessions?
5. What CloudWatch metric indicates your cache is too small?

---

*Next: [Chapter 27 — DMS & DR](./chapter-27-dms-dr.md)*
