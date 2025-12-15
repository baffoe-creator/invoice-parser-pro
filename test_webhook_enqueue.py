import redis
from rq import Queue

# Connect to Redis
r = redis.Redis.from_url('redis://localhost:6379/0')
q = Queue('webhooks', connection=r)

# Test if we can enqueue a job
from src.webhook import send_webhook

# Enqueue a test job
job = q.enqueue(send_webhook, 'test_invoice_id', 'https://httpbin.org/post')
print(f'✅ Job enqueued! Job ID: {job.id}')
print(f'Queue size: {len(q)}')

# List all jobs in queue
print(f'\nJobs in queue:')
for job in q.jobs:
    print(f'  - {job.func_name} with args: {job.args}')
