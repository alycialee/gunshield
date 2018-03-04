import os, sys

ctr = 0

while(True):
    os.system("python runner.py")
    os.system("sshpass -p gpsuserhacktech scp address gpsuser@131.215.159.127:~/gpslogs/log.txt")
    ctr += 1
    print("uploaded ", ctr, " addresses")
