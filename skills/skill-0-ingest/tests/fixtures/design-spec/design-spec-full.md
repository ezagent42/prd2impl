# Rate Limiter Refactor — Design Spec

**Status:** Approved · **Date:** 2026-04-15

## 1. Goal

降低高峰期 API 429 率，从每日 ~3% 降到 <0.3%。

## 2. Current State

当前 limiter 在 `src/middleware/rate_limit.py`，基于 in-memory counter，重启丢状态。

## 3. Design

### 3.1 Redis-backed Counter

新建 `src/middleware/redis_limiter.py`，用 Redis INCR + EXPIRE 做分布式计数。

### 3.2 Sliding Window Algorithm

替换 fixed-window 为 sliding-window log，精度到毫秒。

### 3.3 Fallback Path

Redis 不可用时，回退到 in-memory limiter 并 log warning。

## 4. Behavioral Requirements

- P99 限流判定延迟 < 5ms
- 重启后 60 秒内恢复限流精度
- 向后兼容现有 `@rate_limit` 装饰器签名

## 5. File Changes

### New files
- `src/middleware/redis_limiter.py` — Redis-backed counter
- `src/middleware/sliding_window.py` — algorithm impl

### Modified files
- `src/middleware/rate_limit.py` — delegate to redis_limiter
- `src/config.py` — add REDIS_URL

### Deleted files
- none

## 6. Tests

Fixture suite under `tests/middleware/test_redis_limiter.py` covering redis-up / redis-down / concurrent hits. E2E: run load test at 1000 QPS, observe 429 rate.

## 7. Rollout

1. 实现 redis_limiter + 单测
2. 实现 sliding_window + 单测
3. 改 rate_limit.py delegation + 回归测试
4. 灰度：先 10% 流量，观察 24h
5. 全量切换

## 8. Known Limitations

- Redis 单点若宕机，回退到 in-memory 会丢限流精度（trade-off 选可用性）
- sliding-window 精度依赖 Redis 时钟同步
- 不处理全局限流（只 per-key），per-user 全局限流需另议
