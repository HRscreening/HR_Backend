import redis
from configs.env_config import REDIS_HOST, REDIS_PORT, REDIS_USERNAME, REDIS_PASSWORD

redis_conn = redis.Redis(
    host=REDIS_HOST,
    port=REDIS_PORT,
    decode_responses=False,
    username=REDIS_USERNAME,
    password=REDIS_PASSWORD
)

