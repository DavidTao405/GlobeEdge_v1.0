"""Celery 應用實例。"""

import os

from celery import Celery
from dotenv import load_dotenv

load_dotenv()

REDIS_URL = os.environ.get("WE_REDIS_URL", "redis://localhost:6379/0")

celery_app = Celery(
    "worldedge",
    broker=REDIS_URL,
    backend=REDIS_URL,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Taipei",
    task_soft_time_limit=3600,   # 1 小時軟限制
    task_time_limit=3900,        # 1 小時 5 分硬限制
    worker_prefetch_multiplier=1,  # 一次只拿一個 task（仿真耗時）
)

# 自動發現 tasks
celery_app.autodiscover_tasks(["worldedge.tasks"])
