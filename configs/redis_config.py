from configs.env_config import REDIS_HOST, REDIS_PORT, REDIS_USERNAME, REDIS_PASSWORD
from redis.asyncio import Redis

redis_client: Redis = Redis(
    host=REDIS_HOST,
    port=REDIS_PORT,
    password=REDIS_PASSWORD,
    decode_responses=True, 
)