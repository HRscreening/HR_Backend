# app/workers/connection.py

from arq import create_pool
from arq.connections import RedisSettings
from configs.env_config import REDIS_HOST, REDIS_PORT, REDIS_PASSWORD


redis_settings = RedisSettings(
    host=REDIS_HOST,
    port=REDIS_PORT,
    password=REDIS_PASSWORD,
    database=0,
)

DEFAULT_QUEUE = "default"


async def get_redis_pool():
    return await create_pool(redis_settings)
