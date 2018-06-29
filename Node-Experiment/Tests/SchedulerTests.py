import os, time
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime, timedelta


def tick(scheduler):
    dd = datetime.now() + timedelta(seconds=3)
    scheduler.add_job(tick, 'date', run_date=dd, kwargs={'scheduler': scheduler, 'slot': slot})

    print('! The time is: %s' % datetime.now(), ' slot:', slot)




scheduler = BackgroundScheduler()
slot = 0
dd = datetime.now() + timedelta(seconds=3)
scheduler.add_job(tick, 'date', run_date=dd, kwargs={'scheduler':scheduler,'slot':slot})

scheduler.start()
print('Press Ctrl+{0} to exit'.format('Break' if os.name == 'nt' else 'C'))
print ('cosminas')
try:
    # This is here to simulate application activity (which keeps the main thread alive).
    while True:
        time.sleep(2)
except (KeyboardInterrupt, SystemExit):
    # Not strictly necessary if daemonic mode is enabled but should be done if possible
    scheduler.shutdown()