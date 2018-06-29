import time
import subprocess
import sys
from multiprocessing import Pool


def open_server(port):
    if port != '5000':
        time.sleep(3)
    time.sleep(int(port[3]))
    subprocess.call([sys.executable, 'Server.py', port])


if __name__ == '__main__':
    p = Pool(15)
    print(p.map(open_server, ['5000', '5001', '5002', '5003', '5004', '5005', '5006', '5007', '5008', '5009', '5010']))

