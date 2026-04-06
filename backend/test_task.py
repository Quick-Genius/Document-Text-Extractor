from app.workers.celery_app import celery_app
i = celery_app.control.inspect()
print("Active tasks:", i.active())
print("Reserved tasks:", i.reserved())
print("Scheduled tasks:", i.scheduled())
